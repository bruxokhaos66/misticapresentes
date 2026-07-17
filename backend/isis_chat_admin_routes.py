"""Camada 10 — painel administrativo do Chat Inteligente da Isis 2.0.

Todas as rotas exigem sessão de administrador (`exigir_perfil("adm")`).
Nenhuma rota aqui permite inserir chave de API, ativar publicação
automática, alterar checkout, executar consulta arbitrária ao banco ou
visualizar dado sensível completo -- só métricas agregadas, estado de
flags (somente leitura -- flags reais vêm do ambiente, nunca editadas
pelo painel/.env em runtime) e ações seguras (limpar sessões expiradas).
"""
from __future__ import annotations

from fastapi import APIRouter, Depends

from backend.audit import registrar_auditoria
from backend.database import conectar
from backend.isis_chat_flags import resumo_flags, resumo_flags_estudio_permanece_desativado
from backend.isis_chat_session import garantir_tabelas_isis_chat, limpar_sessoes_expiradas
from backend.logging_config import get_logger
from backend.panel_sessions import exigir_perfil

logger = get_logger(__name__)
router = APIRouter(prefix="/api/admin/isis2/chat", tags=["isis2-chat-admin"])
exigir_admin = exigir_perfil("adm")


def _usuario(sessao: dict) -> str:
    return str(sessao.get("login") or sessao.get("nome") or "adm")


@router.get("/config")
def obter_config_admin(sessao: dict = Depends(exigir_admin)):
    """Somente leitura: as flags reais só podem ser alteradas via variável
    de ambiente do servidor (nunca por este endpoint, nunca editando o
    `.env` a partir do painel)."""
    return {
        "chat": resumo_flags(),
        "content_studio_fase3": resumo_flags_estudio_permanece_desativado(),
    }


@router.get("/metricas")
def obter_metricas(sessao: dict = Depends(exigir_admin)):
    with conectar() as conn:
        garantir_tabelas_isis_chat(conn)
        linhas = conn.execute(
            """
            SELECT evento, COUNT(*) AS total
            FROM isis_chat_metrics
            WHERE date(criado_em) = date('now', 'localtime')
            GROUP BY evento
            """
        ).fetchall()
        contadores_hoje = {linha["evento"]: int(linha["total"]) for linha in linhas}

        sessoes_hoje = conn.execute(
            "SELECT COUNT(*) AS total FROM isis_chat_sessions WHERE date(criado_em) = date('now', 'localtime')"
        ).fetchone()
        sessoes_ativas = conn.execute(
            "SELECT COUNT(*) AS total FROM isis_chat_sessions WHERE status='ativa'"
        ).fetchone()
        sessoes_bloqueadas = conn.execute(
            "SELECT COUNT(*) AS total FROM isis_chat_sessions WHERE status='expirada'"
        ).fetchone()

    return {
        "sessoes_iniciadas_hoje": int(sessoes_hoje["total"] or 0),
        "sessoes_ativas_agora": int(sessoes_ativas["total"] or 0),
        "sessoes_expiradas_total": int(sessoes_bloqueadas["total"] or 0),
        "mensagens_recebidas_hoje": contadores_hoje.get("mensagem_recebida", 0),
        "recomendacoes_exibidas_hoje": contadores_hoje.get("recomendacoes_exibidas", 0),
        "kits_sugeridos_hoje": contadores_hoje.get("kit_sugerido", 0),
        "fallback_sem_resultado_hoje": contadores_hoje.get("fallback_sem_resultado", 0),
        "prompt_injection_bloqueado_hoje": contadores_hoje.get("prompt_injection_bloqueado", 0),
        "chamadas_ia_hoje": 0,
        "custo_estimado_centavos_hoje": 0,
    }


@router.get("/sessoes")
def listar_sessoes_admin(sessao: dict = Depends(exigir_admin)):
    """Só metadados agregados -- nunca o texto integral da conversa (não
    existe coluna de texto completo na tabela)."""
    with conectar() as conn:
        garantir_tabelas_isis_chat(conn)
        linhas = conn.execute(
            """
            SELECT session_id, user_type, status, intent_atual, contador_mensagens, criado_em, ultimo_acesso
            FROM isis_chat_sessions
            ORDER BY criado_em DESC
            LIMIT 200
            """
        ).fetchall()
    return {"sessoes": [dict(linha) for linha in linhas]}


@router.get("/erros")
def listar_erros(sessao: dict = Depends(exigir_admin)):
    with conectar() as conn:
        garantir_tabelas_isis_chat(conn)
        linhas = conn.execute(
            "SELECT evento, COUNT(*) AS total FROM isis_chat_metrics WHERE evento LIKE '%erro%' OR evento LIKE '%bloqueado%' GROUP BY evento"
        ).fetchall()
    return {"erros": [dict(linha) for linha in linhas]}


@router.post("/sessoes/limpar-expiradas")
def limpar_sessoes(sessao: dict = Depends(exigir_admin)):
    with conectar() as conn:
        garantir_tabelas_isis_chat(conn)
        total_removido = limpar_sessoes_expiradas(conn)
        registrar_auditoria(conn, "isis_chat_sessions", None, "limpar_expiradas", _usuario(sessao), depois={"removidas": total_removido})
    logger.info(
        "isis chat: limpeza de sessões expiradas executada por admin",
        extra={"evento": "isis_chat_limpeza_admin", "removidas": total_removido},
    )
    return {"ok": True, "removidas": total_removido}
