"""Camada 2 — sessão de conversa do Chat Inteligente da Isis 2.0.

Sessão própria do chat (não confundir com a sessão de autenticação de
admin/aluno usada só para autorização -- `backend.isis_chat_auth`):
identificador opaco gerado no servidor, sem nenhum dado sensível, com TTL,
limite de mensagens e limpeza de sessões expiradas.

Nunca guarda: senha, documento, cartão, dado de pagamento ou o texto
integral da conversa. Só o necessário para continuar o atendimento:
intenção atual, preferências relevantes, faixa de preço, IDs dos produtos
já sugeridos, um resumo curto e contadores/timestamps.
"""
from __future__ import annotations

import json
import secrets
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from backend.isis_chat_flags import max_mensagens_por_sessao, max_sessoes_por_hora, sessao_ttl_minutos

_FORMATO_DATA = "%Y-%m-%d %H:%M:%S"


def _agora() -> datetime:
    return datetime.now()


def _txt(momento: datetime) -> str:
    return momento.strftime(_FORMATO_DATA)


def _parse(valor: str | None) -> datetime | None:
    if not valor:
        return None
    try:
        return datetime.strptime(valor, _FORMATO_DATA)
    except ValueError:
        return None


def garantir_tabelas_isis_chat(conn) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS isis_chat_sessions (
            session_id TEXT PRIMARY KEY,
            user_type TEXT NOT NULL,
            user_ref TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'ativa',
            intent_atual TEXT,
            preferencias_json TEXT,
            preco_min REAL,
            preco_max REAL,
            produtos_sugeridos_json TEXT,
            resumo TEXT,
            contador_mensagens INTEGER NOT NULL DEFAULT 0,
            criado_em TEXT NOT NULL,
            expira_em TEXT NOT NULL,
            ultimo_acesso TEXT NOT NULL,
            encerrada_em TEXT
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_isis_chat_sessions_status ON isis_chat_sessions(status)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_isis_chat_sessions_criado ON isis_chat_sessions(criado_em)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_isis_chat_sessions_user_ref ON isis_chat_sessions(user_ref)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_isis_chat_sessions_intent ON isis_chat_sessions(intent_atual)")

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS isis_chat_messages_summary (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            papel TEXT NOT NULL,
            intent TEXT,
            resumo TEXT,
            criado_em TEXT NOT NULL
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_isis_chat_msg_session ON isis_chat_messages_summary(session_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_isis_chat_msg_criado ON isis_chat_messages_summary(criado_em)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_isis_chat_msg_intent ON isis_chat_messages_summary(intent)")

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS isis_chat_recommendations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            produto_id INTEGER,
            nome TEXT,
            preco REAL,
            score REAL,
            motivo TEXT,
            criado_em TEXT NOT NULL
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_isis_chat_reco_session ON isis_chat_recommendations(session_id)")

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS isis_chat_metrics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            evento TEXT NOT NULL,
            intent TEXT,
            valor INTEGER NOT NULL DEFAULT 1,
            criado_em TEXT NOT NULL
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_isis_chat_metrics_evento ON isis_chat_metrics(evento)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_isis_chat_metrics_criado ON isis_chat_metrics(criado_em)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_isis_chat_metrics_intent ON isis_chat_metrics(intent)")

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS isis_chat_audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario TEXT,
            acao TEXT NOT NULL,
            detalhe_json TEXT,
            criado_em TEXT NOT NULL
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_isis_chat_audit_criado ON isis_chat_audit_log(criado_em)")


class LimiteSessaoPorHoraExcedido(Exception):
    pass


class SessaoChatInvalida(Exception):
    pass


class LimiteMensagensExcedido(Exception):
    pass


@dataclass
class SessaoChat:
    session_id: str
    user_type: str
    user_ref: str
    status: str
    intent_atual: str | None
    preferencias: dict = field(default_factory=dict)
    preco_min: float | None = None
    preco_max: float | None = None
    produtos_sugeridos: list = field(default_factory=list)
    resumo: str = ""
    contador_mensagens: int = 0
    criado_em: str = ""
    expira_em: str = ""
    ultimo_acesso: str = ""

    @classmethod
    def de_linha(cls, linha: dict) -> "SessaoChat":
        return cls(
            session_id=linha["session_id"],
            user_type=linha["user_type"],
            user_ref=linha["user_ref"],
            status=linha["status"],
            intent_atual=linha.get("intent_atual"),
            preferencias=json.loads(linha.get("preferencias_json") or "{}"),
            preco_min=linha.get("preco_min"),
            preco_max=linha.get("preco_max"),
            produtos_sugeridos=json.loads(linha.get("produtos_sugeridos_json") or "[]"),
            resumo=linha.get("resumo") or "",
            contador_mensagens=int(linha.get("contador_mensagens") or 0),
            criado_em=linha.get("criado_em") or "",
            expira_em=linha.get("expira_em") or "",
            ultimo_acesso=linha.get("ultimo_acesso") or "",
        )


def criar_sessao(conn, *, user_type: str, user_ref: str) -> SessaoChat:
    """Cria a sessão só se a conta ainda não atingiu o limite por hora.

    A checagem antiga (SELECT COUNT(*) seguido de um INSERT separado)
    tinha a mesma janela de corrida do limite de mensagens: duas
    requisições concorrentes de criação de sessão para a mesma conta
    podiam ler a mesma contagem e ambas passar. Aqui o `INSERT ... SELECT
    ... WHERE` faz SQLite avaliar a contagem e inserir a linha numa única
    instrução atômica -- a segunda requisição concorrente, executada
    depois da primeira já ter commitado sua própria sessão, enxerga a
    contagem já atualizada e falha com `rowcount == 0`."""
    agora = _agora()
    limite_inferior = agora - timedelta(hours=1)
    session_id = secrets.token_urlsafe(24)
    expira_em = agora + timedelta(minutes=sessao_ttl_minutos())

    cur = conn.execute(
        """
        INSERT INTO isis_chat_sessions
            (session_id, user_type, user_ref, status, contador_mensagens, criado_em, expira_em, ultimo_acesso)
        SELECT ?, ?, ?, 'ativa', 0, ?, ?, ?
        WHERE (
            SELECT COUNT(*) FROM isis_chat_sessions WHERE user_ref=? AND criado_em>=?
        ) < ?
        """,
        (
            session_id, user_type, user_ref, _txt(agora), _txt(expira_em), _txt(agora),
            user_ref, _txt(limite_inferior), max_sessoes_por_hora(),
        ),
    )
    if cur.rowcount == 0:
        raise LimiteSessaoPorHoraExcedido()

    conn.execute(
        "INSERT INTO isis_chat_metrics (evento, valor, criado_em) VALUES ('sessao_iniciada', 1, ?)",
        (_txt(agora),),
    )
    return SessaoChat(
        session_id=session_id,
        user_type=user_type,
        user_ref=user_ref,
        status="ativa",
        intent_atual=None,
        criado_em=_txt(agora),
        expira_em=_txt(expira_em),
        ultimo_acesso=_txt(agora),
    )


def obter_sessao(conn, session_id: str, *, user_ref: str) -> SessaoChat:
    """Isolamento de sessão: só devolve a sessão se pertencer ao mesmo
    `user_ref` que a criou -- nunca permite um usuário ler/escrever a
    sessão de outro, mesmo conhecendo o identificador opaco."""
    linha = conn.execute(
        "SELECT * FROM isis_chat_sessions WHERE session_id=? AND user_ref=?", (session_id, user_ref)
    ).fetchone()
    if not linha:
        raise SessaoChatInvalida("Sessão não encontrada.")
    dados = dict(linha)
    agora = _agora()
    if dados["status"] != "ativa":
        raise SessaoChatInvalida("Sessão encerrada.")
    expira = _parse(dados["expira_em"])
    if not expira or expira < agora:
        conn.execute(
            "UPDATE isis_chat_sessions SET status='expirada', encerrada_em=? WHERE session_id=?",
            (_txt(agora), session_id),
        )
        raise SessaoChatInvalida("Sessão expirada.")
    return SessaoChat.de_linha(dados)


def tocar_sessao(conn, session_id: str) -> None:
    agora = _agora()
    nova_expiracao = agora + timedelta(minutes=sessao_ttl_minutos())
    conn.execute(
        "UPDATE isis_chat_sessions SET ultimo_acesso=?, expira_em=? WHERE session_id=?",
        (_txt(agora), _txt(nova_expiracao), session_id),
    )


def registrar_mensagem(conn, sessao: SessaoChat, *, papel: str, intent: str | None, resumo_curto: str) -> int:
    """Incrementa o contador atomicamente (UPDATE...WHERE contador <
    limite, numa única instrução) e grava só um resumo curto (nunca o
    texto integral do usuário) -- devolve o novo total de mensagens da
    sessão.

    A checagem "sessao.contador_mensagens >= limite" feita só em memória
    (valor lido no início da requisição) seria uma janela clássica de
    TOCTOU: duas requisições concorrentes para a mesma sessão poderiam
    ler o mesmo valor, passar na checagem e ultrapassar o limite. O
    `WHERE contador_mensagens < ?` faz SQLite avaliar a condição e
    escrever atomicamente na mesma instrução -- a segunda requisição
    concorrente, ao tentar depois da primeira já ter incrementado, não
    encontra mais nenhuma linha que satisfaça o `WHERE` e falha com
    `rowcount == 0`."""
    limite = max_mensagens_por_sessao()
    agora = _agora()
    cur = conn.execute(
        "UPDATE isis_chat_sessions SET contador_mensagens = contador_mensagens + 1 "
        "WHERE session_id=? AND contador_mensagens < ?",
        (sessao.session_id, limite),
    )
    if cur.rowcount == 0:
        raise LimiteMensagensExcedido()

    linha = conn.execute(
        "SELECT contador_mensagens FROM isis_chat_sessions WHERE session_id=?", (sessao.session_id,)
    ).fetchone()
    novo_total = int(linha["contador_mensagens"]) if linha else sessao.contador_mensagens + 1

    conn.execute(
        "INSERT INTO isis_chat_messages_summary (session_id, papel, intent, resumo, criado_em) VALUES (?,?,?,?,?)",
        (sessao.session_id, papel, intent, (resumo_curto or "")[:80], _txt(agora)),
    )
    return novo_total


def atualizar_estado_sessao(
    conn,
    session_id: str,
    *,
    intent_atual: str | None = None,
    preferencias: dict | None = None,
    preco_min: float | None = None,
    preco_max: float | None = None,
    produtos_sugeridos: list | None = None,
    resumo: str | None = None,
) -> None:
    campos, valores = [], []
    if intent_atual is not None:
        campos.append("intent_atual=?")
        valores.append(intent_atual)
    if preferencias is not None:
        campos.append("preferencias_json=?")
        valores.append(json.dumps(preferencias, ensure_ascii=False))
    if preco_min is not None:
        campos.append("preco_min=?")
        valores.append(preco_min)
    if preco_max is not None:
        campos.append("preco_max=?")
        valores.append(preco_max)
    if produtos_sugeridos is not None:
        campos.append("produtos_sugeridos_json=?")
        valores.append(json.dumps(produtos_sugeridos[:20], ensure_ascii=False))
    if resumo is not None:
        campos.append("resumo=?")
        valores.append(resumo[:280])
    if not campos:
        return
    valores.append(session_id)
    conn.execute(f"UPDATE isis_chat_sessions SET {', '.join(campos)} WHERE session_id=?", tuple(valores))


def encerrar_sessao(conn, session_id: str, *, user_ref: str) -> bool:
    agora = _agora()
    cur = conn.execute(
        "UPDATE isis_chat_sessions SET status='encerrada', encerrada_em=? WHERE session_id=? AND user_ref=? AND status='ativa'",
        (_txt(agora), session_id, user_ref),
    )
    return cur.rowcount > 0


def limpar_sessoes_expiradas(conn, *, retencao_dias: int = 30) -> int:
    """Limpeza de sessões expiradas/encerradas: marca como expiradas as
    sessões ativas cujo TTL já passou e apaga definitivamente sessões e
    resumos de mensagens mais antigos que a retenção configurada (não
    guarda histórico completo indefinidamente)."""
    agora = _agora()
    conn.execute(
        "UPDATE isis_chat_sessions SET status='expirada', encerrada_em=? WHERE status='ativa' AND expira_em<?",
        (_txt(agora), _txt(agora)),
    )
    limite_retencao = _txt(agora - timedelta(days=retencao_dias))
    ids_antigos = [
        row["session_id"]
        for row in conn.execute(
            "SELECT session_id FROM isis_chat_sessions WHERE status!='ativa' AND criado_em<?",
            (limite_retencao,),
        ).fetchall()
    ]
    if ids_antigos:
        marcadores = ",".join("?" * len(ids_antigos))
        conn.execute(f"DELETE FROM isis_chat_messages_summary WHERE session_id IN ({marcadores})", ids_antigos)
        conn.execute(f"DELETE FROM isis_chat_recommendations WHERE session_id IN ({marcadores})", ids_antigos)
        conn.execute(f"DELETE FROM isis_chat_sessions WHERE session_id IN ({marcadores})", ids_antigos)
    return len(ids_antigos)
