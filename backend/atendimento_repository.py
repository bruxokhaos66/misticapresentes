"""Central Multiatendente: perfis, fila, assunção (claim), liberação,
transferência, finalização/reabertura e histórico imutável de conversas do
WhatsApp (backend/whatsapp_atendimento_routes.py).

Reaproveita `usuarios` (perfis adm/supervisor_atendimento/vendedor,
ver backend/user_sync_routes.py::_normalizar_perfil) e
`whatsapp_conversations` (colunas `assigned_user_id`/`queue_status`/
`assignment_version` -- ver database/migrations.py::
_criar_estrutura_atendimento_multiatendente). Nenhuma função aqui abre sua
própria conexão: todo caller controla a transação, para que
claim/release/transfer sejam operações atômicas de ponta a ponta (uma única
transação SQLite -- ver backend/database.py::conectar, que já roda em modo
WAL com um único escritor por vez).

O histórico (atendimento_assignment_history) nunca grava conteúdo de
mensagem, telefone completo, token ou payload bruto da Meta -- só ids,
motivo (texto curto sanitizado) e versões."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import HTTPException

from backend.atendimento_flags import (
    atendimento_max_conversas_padrao,
    atendimento_permite_transferencia_por_vendedor,
    atendimento_sellers_habilitado,
)

PERFIS_ATENDIMENTO = {"adm", "supervisor_atendimento", "vendedor"}
PERFIS_GESTAO = {"adm", "supervisor_atendimento"}
STATUS_PRESENCA_VALIDOS = {"online", "ausente", "ocupado", "offline"}
ACOES_HISTORICO_VALIDAS = {
    "claim", "release", "transfer", "resolve", "reopen", "auto_reopen", "send_denied", "admin_override",
}
QUEUE_STATUS_VALIDOS = {"waiting", "assigned", "resolved"}


def _agora() -> str:
    return datetime.now().isoformat(timespec="seconds")


def sanitizar_motivo(valor: str | None, *, limite: int = 300) -> str | None:
    """Nunca persiste HTML/script -- o motivo é sempre exibido via
    textContent no frontend, mas aqui já removemos bytes de controle e
    truncamos defensivamente, igual a whatsapp_inbox_repository.sanitizar_texto."""
    if valor is None:
        return None
    texto = "".join(ch for ch in str(valor) if ch == "\n" or ch == "\t" or ord(ch) >= 32)
    texto = texto.strip()
    return texto[:limite] if texto else None


# ---------------------------------------------------------------------------
# Usuários / atendentes
# ---------------------------------------------------------------------------

def obter_usuario_por_id(conn, usuario_id: int | None) -> dict | None:
    if not usuario_id:
        return None
    linha = conn.execute("SELECT * FROM usuarios WHERE id=?", (usuario_id,)).fetchone()
    return dict(linha) if linha else None


def exigir_atendente(conn, sessao: dict) -> dict:
    """Valida no BANCO (nunca só na sessão cacheada) se este usuário pode
    operar a Central agora. ADM sempre pode (compatibilidade com o fluxo
    legado, mesmo com ATENDIMENTO_SELLERS_ENABLED desligada).
    supervisor_atendimento/vendedor exigem a flag ligada, usuário ativo, não
    suspenso do atendimento e atendimento_enabled=1."""
    perfil = sessao.get("perfil")
    if perfil not in PERFIS_ATENDIMENTO:
        raise HTTPException(status_code=403, detail="Perfil sem acesso à Central de Atendimento.")

    usuario = obter_usuario_por_id(conn, sessao.get("usuario_id"))
    if not usuario:
        raise HTTPException(status_code=403, detail="Sessão sem usuário associado.")

    if perfil == "adm":
        return usuario

    if not atendimento_sellers_habilitado():
        raise HTTPException(status_code=403, detail="Central multiatendente desabilitada para este perfil.")
    if not int(usuario.get("ativo") or 0):
        raise HTTPException(status_code=403, detail="Usuário inativo.")
    if usuario.get("atendimento_suspended_at"):
        raise HTTPException(status_code=403, detail="Acesso ao atendimento suspenso.")
    if not int(usuario.get("atendimento_enabled") or 0):
        raise HTTPException(status_code=403, detail="Atendimento não habilitado para este usuário.")
    return usuario


def registrar_atividade_atendente(conn, usuario_id: int | None) -> None:
    if not usuario_id:
        return
    conn.execute(
        "UPDATE usuarios SET atendimento_last_activity_at=? WHERE id=?",
        (_agora(), usuario_id),
    )


def limite_maximo_conversas(usuario: dict) -> int:
    valor = usuario.get("atendimento_max_active_conversations")
    if valor is None:
        return atendimento_max_conversas_padrao()
    try:
        valor_int = int(valor)
    except (TypeError, ValueError):
        return atendimento_max_conversas_padrao()
    return valor_int if valor_int > 0 else atendimento_max_conversas_padrao()


def contar_conversas_ativas(conn, usuario_id: int) -> int:
    linha = conn.execute(
        "SELECT COUNT(*) AS n FROM whatsapp_conversations WHERE assigned_user_id=? AND queue_status='assigned'",
        (usuario_id,),
    ).fetchone()
    return int(linha["n"] if linha else 0)


def autorizado_para_conversa(usuario: dict, conversa: dict) -> bool:
    """Autorização horizontal: adm/supervisor sempre podem ver/agir; vendedor
    só na conversa atribuída a ele. Nunca decidido pelo frontend."""
    if usuario.get("perfil") in PERFIS_GESTAO:
        return True
    return conversa.get("assigned_user_id") is not None and conversa.get("assigned_user_id") == usuario.get("id")


# ---------------------------------------------------------------------------
# Histórico imutável
# ---------------------------------------------------------------------------

def registrar_historico_atendimento(
    conn,
    *,
    conversation_id: int,
    action: str,
    from_user_id: int | None = None,
    to_user_id: int | None = None,
    performed_by_user_id: int | None = None,
    reason: str | None = None,
    previous_version: int | None = None,
    new_version: int | None = None,
) -> None:
    if action not in ACOES_HISTORICO_VALIDAS:
        raise ValueError(f"Ação de histórico inválida: {action!r}")
    conn.execute(
        """
        INSERT INTO atendimento_assignment_history
            (conversation_id, action, from_user_id, to_user_id, performed_by_user_id, reason, previous_version, new_version, created_at)
        VALUES (?,?,?,?,?,?,?,?,?)
        """,
        (
            conversation_id, action, from_user_id, to_user_id, performed_by_user_id,
            sanitizar_motivo(reason), previous_version, new_version, _agora(),
        ),
    )


def listar_historico_atendimento(conn, conversation_id: int, *, pagina: int = 1, tamanho_pagina: int = 50) -> tuple[list[dict], int]:
    total_row = conn.execute(
        "SELECT COUNT(*) AS n FROM atendimento_assignment_history WHERE conversation_id=?", (conversation_id,)
    ).fetchone()
    total = int(total_row["n"] if total_row else 0)
    offset = max(0, (pagina - 1) * tamanho_pagina)
    linhas = conn.execute(
        """
        SELECT * FROM atendimento_assignment_history
         WHERE conversation_id=?
         ORDER BY id DESC
         LIMIT ? OFFSET ?
        """,
        (conversation_id, tamanho_pagina, offset),
    ).fetchall()
    return [dict(row) for row in linhas], total


# ---------------------------------------------------------------------------
# Claim / release / transfer / resolve / reopen -- todas atômicas via UPDATE
# condicional (WHERE inclui o estado esperado) + checagem de rowcount.
# ---------------------------------------------------------------------------

class ErroOperacaoFila(Exception):
    def __init__(self, codigo: str, mensagem: str):
        self.codigo = codigo
        self.mensagem = mensagem
        super().__init__(mensagem)


def obter_conversa_para_fila(conn, conversation_id: int) -> dict | None:
    linha = conn.execute("SELECT * FROM whatsapp_conversations WHERE id=?", (conversation_id,)).fetchone()
    return dict(linha) if linha else None


def reivindicar_conversa(conn, *, conversation_id: int, usuario: dict) -> dict:
    """POST .../claim -- atômico: dois atendentes clicando ao mesmo tempo
    nunca assumem a mesma conversa (UPDATE condicional na mesma transação; o
    modo WAL do SQLite serializa escritores, então não há corrida real entre
    duas chamadas concorrentes desta função)."""
    agora = _agora()
    cur = conn.execute(
        """
        UPDATE whatsapp_conversations
           SET assigned_user_id=?, assigned_at=?, assignment_version=assignment_version+1,
               queue_status='assigned', updated_at=?
         WHERE id=? AND assigned_user_id IS NULL AND queue_status='waiting' AND resolved_at IS NULL
        """,
        (usuario["id"], agora, agora, conversation_id),
    )
    if cur.rowcount == 0:
        conversa = obter_conversa_para_fila(conn, conversation_id)
        if not conversa:
            raise ErroOperacaoFila("not_found", "Conversa não encontrada.")
        if conversa.get("queue_status") == "resolved" or conversa.get("resolved_at"):
            raise ErroOperacaoFila("conversation_resolved", "Esta conversa já está encerrada.")
        if conversa.get("assigned_user_id") is not None:
            raise ErroOperacaoFila("already_claimed", "Esta conversa já foi assumida por outro atendente.")
        raise ErroOperacaoFila("invalid_state", "Não foi possível assumir esta conversa no estado atual.")

    conversa = obter_conversa_para_fila(conn, conversation_id)
    limite = limite_maximo_conversas(usuario)
    ativos = contar_conversas_ativas(conn, usuario["id"])
    if ativos > limite:
        # Reverte a reivindicação dentro da MESMA transação -- o limite é
        # respeitado mesmo sob corrida (duas claims quase simultâneas do
        # mesmo vendedor em duas abas, por exemplo).
        conn.execute(
            """
            UPDATE whatsapp_conversations
               SET assigned_user_id=NULL, assigned_at=NULL, assignment_version=assignment_version+1,
                   queue_status='waiting', updated_at=?
             WHERE id=?
            """,
            (_agora(), conversation_id),
        )
        raise ErroOperacaoFila("limit_reached", f"Limite de {limite} conversas ativas atingido.")

    registrar_historico_atendimento(
        conn, conversation_id=conversation_id, action="claim",
        from_user_id=None, to_user_id=usuario["id"], performed_by_user_id=usuario["id"],
        previous_version=conversa["assignment_version"] - 1, new_version=conversa["assignment_version"],
    )
    registrar_atividade_atendente(conn, usuario["id"])
    return conversa


def liberar_conversa(conn, *, conversation_id: int, usuario: dict, reason: str | None) -> dict:
    conversa = obter_conversa_para_fila(conn, conversation_id)
    if not conversa:
        raise ErroOperacaoFila("not_found", "Conversa não encontrada.")
    if conversa.get("queue_status") == "resolved":
        raise ErroOperacaoFila("conversation_resolved", "Esta conversa já está encerrada.")
    if usuario.get("perfil") not in PERFIS_GESTAO and conversa.get("assigned_user_id") != usuario.get("id"):
        raise ErroOperacaoFila("forbidden", "Você só pode liberar conversas atribuídas a você.")

    agora = _agora()
    cur = conn.execute(
        """
        UPDATE whatsapp_conversations
           SET assigned_user_id=NULL, assigned_at=NULL, assignment_version=assignment_version+1,
               queue_status='waiting', updated_at=?
         WHERE id=? AND assignment_version=? AND queue_status='assigned'
        """,
        (agora, conversation_id, conversa["assignment_version"]),
    )
    if cur.rowcount == 0:
        raise ErroOperacaoFila("version_conflict", "Esta conversa foi alterada por outra ação; recarregue e tente novamente.")

    nova = obter_conversa_para_fila(conn, conversation_id)
    registrar_historico_atendimento(
        conn, conversation_id=conversation_id, action="release",
        from_user_id=conversa.get("assigned_user_id"), to_user_id=None, performed_by_user_id=usuario["id"],
        reason=reason, previous_version=conversa["assignment_version"], new_version=nova["assignment_version"],
    )
    registrar_atividade_atendente(conn, usuario["id"])
    return nova


def transferir_conversa(
    conn, *, conversation_id: int, usuario: dict, target_user_id: int, reason: str | None, expected_version: int | None,
) -> dict:
    conversa = obter_conversa_para_fila(conn, conversation_id)
    if not conversa:
        raise ErroOperacaoFila("not_found", "Conversa não encontrada.")
    if conversa.get("queue_status") == "resolved":
        raise ErroOperacaoFila("conversation_resolved", "Não é possível transferir uma conversa encerrada.")
    if expected_version is not None and int(expected_version) != int(conversa["assignment_version"]):
        raise ErroOperacaoFila("version_conflict", "Esta conversa foi alterada por outra ação; recarregue e tente novamente.")
    if target_user_id == usuario.get("id"):
        raise ErroOperacaoFila("invalid_target", "Selecione um atendente diferente de você mesmo.")

    perfil = usuario.get("perfil")
    if perfil not in PERFIS_GESTAO:
        if conversa.get("assigned_user_id") != usuario.get("id"):
            raise ErroOperacaoFila("forbidden", "Você só pode transferir conversas atribuídas a você.")
        if not atendimento_permite_transferencia_por_vendedor():
            raise ErroOperacaoFila("forbidden", "Transferência por vendedor está desabilitada.")

    destino = obter_usuario_por_id(conn, target_user_id)
    if not destino:
        raise ErroOperacaoFila("invalid_target", "Atendente de destino não encontrado.")
    if not int(destino.get("ativo") or 0):
        raise ErroOperacaoFila("invalid_target", "Atendente de destino está inativo.")
    if destino.get("atendimento_suspended_at"):
        raise ErroOperacaoFila("invalid_target", "Atendente de destino está suspenso do atendimento.")
    if not int(destino.get("atendimento_enabled") or 0):
        raise ErroOperacaoFila("invalid_target", "Atendente de destino não tem atendimento habilitado.")
    if destino.get("perfil") not in PERFIS_ATENDIMENTO:
        raise ErroOperacaoFila("invalid_target", "Atendente de destino não tem perfil permitido.")
    if perfil not in PERFIS_GESTAO and destino.get("perfil") != "vendedor":
        raise ErroOperacaoFila("invalid_target", "Vendedor só pode transferir para outro vendedor.")

    limite_destino = limite_maximo_conversas(destino)
    ativos_destino = contar_conversas_ativas(conn, target_user_id)
    if ativos_destino >= limite_destino:
        raise ErroOperacaoFila("target_limit_reached", "Atendente de destino já atingiu o limite de conversas ativas.")

    agora = _agora()
    cur = conn.execute(
        """
        UPDATE whatsapp_conversations
           SET assigned_user_id=?, assigned_at=?, assignment_version=assignment_version+1,
               queue_status='assigned', updated_at=?
         WHERE id=? AND assignment_version=? AND queue_status!='resolved'
        """,
        (target_user_id, agora, agora, conversation_id, conversa["assignment_version"]),
    )
    if cur.rowcount == 0:
        raise ErroOperacaoFila("version_conflict", "Esta conversa foi alterada por outra ação; recarregue e tente novamente.")

    nova = obter_conversa_para_fila(conn, conversation_id)
    registrar_historico_atendimento(
        conn, conversation_id=conversation_id, action="transfer",
        from_user_id=conversa.get("assigned_user_id"), to_user_id=target_user_id, performed_by_user_id=usuario["id"],
        reason=reason, previous_version=conversa["assignment_version"], new_version=nova["assignment_version"],
    )
    registrar_atividade_atendente(conn, usuario["id"])
    return nova


def resolver_conversa(conn, *, conversation_id: int, usuario: dict, expected_version: int | None = None) -> dict:
    conversa = obter_conversa_para_fila(conn, conversation_id)
    if not conversa:
        raise ErroOperacaoFila("not_found", "Conversa não encontrada.")
    if conversa.get("queue_status") == "resolved":
        raise ErroOperacaoFila("conversation_resolved", "Esta conversa já está encerrada.")
    if expected_version is not None and int(expected_version) != int(conversa["assignment_version"]):
        raise ErroOperacaoFila("version_conflict", "Esta conversa foi alterada por outra ação; recarregue e tente novamente.")
    if usuario.get("perfil") not in PERFIS_GESTAO and conversa.get("assigned_user_id") != usuario.get("id"):
        raise ErroOperacaoFila("forbidden", "Você só pode finalizar conversas atribuídas a você.")

    agora = _agora()
    nome_usuario = usuario.get("nome") or usuario.get("login") or "Atendente"
    cur = conn.execute(
        """
        UPDATE whatsapp_conversations
           SET queue_status='resolved', status='resolved', resolved_at=?, resolved_by=?,
               assignment_version=assignment_version+1, updated_at=?
         WHERE id=? AND assignment_version=? AND queue_status!='resolved'
        """,
        (agora, nome_usuario, agora, conversation_id, conversa["assignment_version"]),
    )
    if cur.rowcount == 0:
        raise ErroOperacaoFila("version_conflict", "Esta conversa foi alterada por outra ação; recarregue e tente novamente.")

    nova = obter_conversa_para_fila(conn, conversation_id)
    registrar_historico_atendimento(
        conn, conversation_id=conversation_id, action="resolve",
        from_user_id=conversa.get("assigned_user_id"), to_user_id=conversa.get("assigned_user_id"), performed_by_user_id=usuario["id"],
        previous_version=conversa["assignment_version"], new_version=nova["assignment_version"],
    )
    registrar_atividade_atendente(conn, usuario["id"])
    return nova


def reabrir_conversa(conn, *, conversation_id: int, usuario: dict) -> dict:
    """Só adm/supervisor_atendimento -- ver documentação da rota. Reabre sem
    atendente (waiting), nunca reatribuindo automaticamente."""
    if usuario.get("perfil") not in PERFIS_GESTAO:
        raise ErroOperacaoFila("forbidden", "Somente administradores ou supervisores podem reabrir conversas.")
    conversa = obter_conversa_para_fila(conn, conversation_id)
    if not conversa:
        raise ErroOperacaoFila("not_found", "Conversa não encontrada.")
    if conversa.get("queue_status") != "resolved":
        raise ErroOperacaoFila("invalid_state", "Esta conversa não está encerrada.")

    agora = _agora()
    cur = conn.execute(
        """
        UPDATE whatsapp_conversations
           SET queue_status='waiting', status='open', resolved_at=NULL, resolved_by=NULL,
               assigned_user_id=NULL, assigned_at=NULL, assignment_version=assignment_version+1, updated_at=?
         WHERE id=? AND queue_status='resolved'
        """,
        (agora, conversation_id),
    )
    if cur.rowcount == 0:
        raise ErroOperacaoFila("version_conflict", "Esta conversa foi alterada por outra ação; recarregue e tente novamente.")

    nova = obter_conversa_para_fila(conn, conversation_id)
    registrar_historico_atendimento(
        conn, conversation_id=conversation_id, action="reopen",
        from_user_id=conversa.get("assigned_user_id"), to_user_id=None, performed_by_user_id=usuario["id"],
        previous_version=conversa["assignment_version"], new_version=nova["assignment_version"],
    )
    return nova


def reabrir_automaticamente_se_resolvida(conn, conversation_id: int) -> bool:
    """Chamada pelo processamento do webhook (backend/whatsapp_inbox_service.py)
    quando chega uma nova mensagem de cliente numa conversa já encerrada.
    Nunca atribui automaticamente a nenhum atendente -- só volta para
    'waiting' e registra o evento no histórico (performed_by_user_id=None:
    ação do sistema, não de uma pessoa)."""
    conversa = obter_conversa_para_fila(conn, conversation_id)
    if not conversa or conversa.get("queue_status") != "resolved":
        return False
    agora = _agora()
    cur = conn.execute(
        """
        UPDATE whatsapp_conversations
           SET queue_status='waiting', resolved_at=NULL, resolved_by=NULL,
               assigned_user_id=NULL, assigned_at=NULL, assignment_version=assignment_version+1, updated_at=?
         WHERE id=? AND queue_status='resolved'
        """,
        (agora, conversation_id),
    )
    if cur.rowcount == 0:
        return False
    nova = obter_conversa_para_fila(conn, conversation_id)
    registrar_historico_atendimento(
        conn, conversation_id=conversation_id, action="auto_reopen",
        from_user_id=conversa.get("assigned_user_id"), to_user_id=None, performed_by_user_id=None,
        previous_version=conversa["assignment_version"], new_version=nova["assignment_version"],
    )
    return True


# ---------------------------------------------------------------------------
# Listagens (fila / minhas conversas / agentes)
# ---------------------------------------------------------------------------

def linha_conversa_fila_publica(row: dict) -> dict:
    return {
        "id": row.get("id"),
        "status": row.get("status"),
        "queue_status": row.get("queue_status"),
        "assigned_user_id": row.get("assigned_user_id"),
        "assigned_at": row.get("assigned_at"),
        "assignment_version": row.get("assignment_version"),
        "unread_count": row.get("unread_count"),
        "last_message_at": row.get("last_message_at"),
        "last_inbound_at": row.get("last_inbound_at"),
        "created_at": row.get("created_at"),
        "resolved_at": row.get("resolved_at"),
        "customer_id": row.get("customer_id") or row.get("contato_customer_id"),
        "order_id": row.get("order_id"),
        "contact": {
            "profile_name": row.get("profile_name"),
            "phone_last4": row.get("phone_last4"),
        },
    }


def listar_fila(conn, *, pagina: int, tamanho_pagina: int) -> tuple[list[dict], int]:
    total_row = conn.execute(
        "SELECT COUNT(*) AS n FROM whatsapp_conversations WHERE queue_status='waiting'"
    ).fetchone()
    total = int(total_row["n"] if total_row else 0)
    offset = max(0, (pagina - 1) * tamanho_pagina)
    linhas = conn.execute(
        """
        SELECT c.*, ct.profile_name, ct.phone_last4, ct.customer_id AS contato_customer_id
          FROM whatsapp_conversations c
          JOIN whatsapp_contacts ct ON ct.id = c.contact_id
         WHERE c.queue_status='waiting'
         ORDER BY (c.unread_count > 0) DESC, c.created_at ASC
         LIMIT ? OFFSET ?
        """,
        (tamanho_pagina, offset),
    ).fetchall()
    return [linha_conversa_fila_publica(dict(row)) for row in linhas], total


def listar_minhas_conversas(conn, *, usuario_id: int, pagina: int, tamanho_pagina: int) -> tuple[list[dict], int]:
    total_row = conn.execute(
        "SELECT COUNT(*) AS n FROM whatsapp_conversations WHERE assigned_user_id=? AND queue_status='assigned'",
        (usuario_id,),
    ).fetchone()
    total = int(total_row["n"] if total_row else 0)
    offset = max(0, (pagina - 1) * tamanho_pagina)
    linhas = conn.execute(
        """
        SELECT c.*, ct.profile_name, ct.phone_last4, ct.customer_id AS contato_customer_id
          FROM whatsapp_conversations c
          JOIN whatsapp_contacts ct ON ct.id = c.contact_id
         WHERE c.assigned_user_id=? AND c.queue_status='assigned'
         ORDER BY (c.unread_count > 0) DESC, COALESCE(c.last_message_at, c.created_at) DESC
         LIMIT ? OFFSET ?
        """,
        (usuario_id, tamanho_pagina, offset),
    ).fetchall()
    return [linha_conversa_fila_publica(dict(row)) for row in linhas], total


def _linha_agente_publica(row: dict) -> dict:
    return {
        "id": row.get("id"),
        "nome": row.get("nome"),
        "login": row.get("login"),
        "perfil": row.get("perfil"),
        "ativo": bool(row.get("ativo")),
        "atendimento_enabled": bool(row.get("atendimento_enabled")),
        "atendimento_status": row.get("atendimento_status") or "offline",
        "atendimento_max_active_conversations": row.get("atendimento_max_active_conversations"),
        "atendimento_suspended_at": row.get("atendimento_suspended_at"),
        "atendimento_last_activity_at": row.get("atendimento_last_activity_at"),
    }


def listar_agentes(conn) -> list[dict]:
    """Só perfis de atendimento (adm/supervisor_atendimento/vendedor) -- nunca
    devolve senha/hash/salt."""
    linhas = conn.execute(
        """
        SELECT id, nome, login, perfil, ativo, atendimento_enabled, atendimento_status,
               atendimento_max_active_conversations, atendimento_suspended_at, atendimento_last_activity_at
          FROM usuarios
         WHERE perfil IN ('adm','supervisor_atendimento','vendedor') AND COALESCE(ativo,1)=1
         ORDER BY nome COLLATE NOCASE
        """
    ).fetchall()
    agentes = [_linha_agente_publica(dict(row)) for row in linhas]
    for agente in agentes:
        with_id = agente["id"]
        agente["active_conversations"] = contar_conversas_ativas(conn, with_id)
    return agentes


# ---------------------------------------------------------------------------
# Gestão de vendedores (painel administrativo -- só adm/supervisor)
# ---------------------------------------------------------------------------

CAMPOS_GESTAO_PERMITIDOS = {
    "atendimento_enabled", "perfil", "atendimento_max_active_conversations",
    "atendimento_suspended_at", "atendimento_status",
}


def atualizar_agente(conn, *, usuario_id: int, ator: dict, campos: dict) -> dict:
    """Aplica alterações administrativas num atendente. `ator` é quem está
    fazendo a alteração (já validado como adm/supervisor pela rota)."""
    alvo = obter_usuario_por_id(conn, usuario_id)
    if not alvo:
        raise ErroOperacaoFila("not_found", "Atendente não encontrado.")
    if alvo.get("perfil") == "adm" and ator.get("perfil") != "adm":
        raise ErroOperacaoFila("forbidden", "Somente administradores podem alterar outro administrador.")
    if usuario_id == ator.get("id") and "perfil" in campos and campos["perfil"] != alvo.get("perfil"):
        raise ErroOperacaoFila("forbidden", "Você não pode alterar o próprio perfil.")

    sets: list[str] = []
    valores: list[Any] = []
    antes: dict = {}
    depois: dict = {}

    if "perfil" in campos:
        novo_perfil = str(campos["perfil"] or "").strip()
        if novo_perfil not in ("vendedor", "supervisor_atendimento"):
            raise ErroOperacaoFila("invalid_field", "Perfil deve ser 'vendedor' ou 'supervisor_atendimento'.")
        if ator.get("perfil") == "supervisor_atendimento" and novo_perfil == "supervisor_atendimento" and alvo.get("perfil") == "vendedor":
            # supervisor pode promover vendedor a supervisor, mas nunca a adm
            # (já bloqueado acima -- 'adm' nem é aceito em novo_perfil).
            pass
        antes["perfil"] = alvo.get("perfil")
        depois["perfil"] = novo_perfil
        sets.append("perfil=?")
        valores.append(novo_perfil)

    if "atendimento_enabled" in campos:
        valor = 1 if campos["atendimento_enabled"] else 0
        antes["atendimento_enabled"] = alvo.get("atendimento_enabled")
        depois["atendimento_enabled"] = valor
        sets.append("atendimento_enabled=?")
        valores.append(valor)

    if "atendimento_max_active_conversations" in campos:
        bruto = campos["atendimento_max_active_conversations"]
        valor_max = None if bruto in (None, "") else int(bruto)
        if valor_max is not None and valor_max <= 0:
            raise ErroOperacaoFila("invalid_field", "Limite de conversas deve ser maior que zero.")
        antes["atendimento_max_active_conversations"] = alvo.get("atendimento_max_active_conversations")
        depois["atendimento_max_active_conversations"] = valor_max
        sets.append("atendimento_max_active_conversations=?")
        valores.append(valor_max)

    if "suspender" in campos:
        suspender = bool(campos["suspender"])
        novo_valor = _agora() if suspender else None
        antes["atendimento_suspended_at"] = alvo.get("atendimento_suspended_at")
        depois["atendimento_suspended_at"] = novo_valor
        sets.append("atendimento_suspended_at=?")
        valores.append(novo_valor)

    if not sets:
        return alvo

    sets.append("updated_at=?")
    valores.append(_agora())
    valores.append(usuario_id)
    conn.execute(f"UPDATE usuarios SET {', '.join(sets)} WHERE id=?", valores)

    from backend.audit import registrar_auditoria
    registrar_auditoria(
        conn, "atendimento_agente", usuario_id, "atualizar_agente",
        ator.get("nome") or ator.get("login") or "Sistema", antes=antes, depois=depois,
    )
    return obter_usuario_por_id(conn, usuario_id)
