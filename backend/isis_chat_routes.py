"""Camada 9 — endpoints públicos do Chat Inteligente da Isis 2.0 (homologação).

Todas as rotas mutáveis exigem a identidade autorizada de
`backend.isis_chat_auth.identidade_chat_autorizada` (admin OU aluno na
allowlist, com as duas flags de chat ligadas) -- nunca confiam em flag
lida só no navegador. `GET /config` e `GET /status` são as únicas exceções
"públicas de leitura", e mesmo assim devolvem sempre um estado seguro
(nunca vazam se uma conta específica está ou não autorizada).
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from backend.database import conectar
from backend.isis_chat_auth import IdentidadeChat, identidade_chat_autorizada, identidade_chat_opcional, validar_origem_csrf
from backend.isis_chat_flags import chat_habilitado, chat_homolog_habilitado, resumo_flags, tamanho_maximo_mensagem
from backend.isis_chat_service import processar_mensagem
from backend.isis_chat_session import (
    LimiteMensagensExcedido,
    LimiteSessaoPorHoraExcedido,
    SessaoChatInvalida,
    criar_sessao,
    encerrar_sessao,
    garantir_tabelas_isis_chat,
    obter_sessao,
    tocar_sessao,
)
from backend.logging_config import get_logger
from backend.rate_limit import limitar_requisicoes

logger = get_logger(__name__)
router = APIRouter(prefix="/api/isis2/chat", tags=["isis2-chat"])

limitar_criacao_sessao = limitar_requisicoes("isis_chat_sessoes", limite=10, janela_segundos=60)
limitar_mensagens = limitar_requisicoes("isis_chat_mensagens", limite=30, janela_segundos=60)
limitar_config = limitar_requisicoes("isis_chat_config", limite=30, janela_segundos=60)

_MENSAGEM_TAMANHO_MAXIMO_ABSOLUTO = 4000  # teto de defesa em profundidade; o limite real vem da flag


class MensagemIn(BaseModel):
    texto: str = Field(min_length=1, max_length=_MENSAGEM_TAMANHO_MAXIMO_ABSOLUTO)


def _base_url(request: Request) -> str:
    from backend.api_security import ORIGENS_PERMITIDAS

    origem = request.headers.get("origin") or ""
    if origem in ORIGENS_PERMITIDAS:
        return origem
    return ORIGENS_PERMITIDAS[0] if ORIGENS_PERMITIDAS else ""


@router.get("/config", dependencies=[Depends(limitar_config)])
def obter_config_publica(identidade: IdentidadeChat | None = Depends(identidade_chat_opcional)):
    """Estado seguro para o widget decidir se deve montar. Nunca expõe
    detalhe de autorização de outra conta nem variável de ambiente bruta."""
    if not chat_habilitado():
        return {"enabled": False, "homolog": False, "authorized": False}
    return {
        "enabled": True,
        "homolog": chat_homolog_habilitado(),
        "authorized": identidade is not None,
    }


@router.get("/status")
def status_chat():
    """Estado agregado (sem dado de sessão/usuário) para diagnóstico
    público de disponibilidade -- nenhum campo administrativo."""
    flags = resumo_flags()
    return {
        "enabled": flags["chat_enabled"],
        "homolog_enabled": flags["chat_homolog_enabled"],
        "ai_enabled": flags["chat_ai_enabled"],
        "product_recommendations_enabled": flags["chat_product_recommendations_enabled"],
        "deterministic_mode": not flags["chat_ai_enabled"],
    }


@router.post("/sessoes", dependencies=[Depends(limitar_criacao_sessao)])
def criar_sessao_chat(request: Request, identidade: IdentidadeChat = Depends(identidade_chat_autorizada)):
    validar_origem_csrf(request)
    try:
        with conectar() as conn:
            garantir_tabelas_isis_chat(conn)
            sessao = criar_sessao(conn, user_type=identidade.tipo, user_ref=identidade.referencia)
    except LimiteSessaoPorHoraExcedido:
        raise HTTPException(status_code=429, detail="Limite de novas sessões por hora atingido. Tente novamente mais tarde.")
    logger.info(
        "isis chat: sessão iniciada",
        extra={"evento": "isis_chat_sessao_iniciada", "session_id": sessao.session_id[:8], "user_type": identidade.tipo},
    )
    return {
        "session_id": sessao.session_id,
        "message": "Olá! Sou a Isis. Posso ajudar você a encontrar produtos, kits e cursos da Mística.",
        "remaining_messages": _limite_atual(),
        "privacy_notice": "A Isis usa as informações desta conversa apenas para ajudar na recomendação de produtos e melhorar o atendimento.",
        "homolog_badge": "Isis em homologação",
    }


def _limite_atual() -> int:
    from backend.isis_chat_flags import max_mensagens_por_sessao

    return max_mensagens_por_sessao()


@router.get("/sessoes/{session_id}")
def obter_sessao_chat(session_id: str, identidade: IdentidadeChat = Depends(identidade_chat_autorizada)):
    try:
        with conectar() as conn:
            garantir_tabelas_isis_chat(conn)
            sessao = obter_sessao(conn, session_id, user_ref=identidade.referencia)
    except SessaoChatInvalida as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {
        "session_id": sessao.session_id,
        "intent_atual": sessao.intent_atual,
        "contador_mensagens": sessao.contador_mensagens,
        "remaining_messages": max(0, _limite_atual() - sessao.contador_mensagens),
        "resumo": sessao.resumo,
    }


@router.post("/sessoes/{session_id}/mensagens", dependencies=[Depends(limitar_mensagens)])
def enviar_mensagem(
    session_id: str,
    payload: MensagemIn,
    request: Request,
    identidade: IdentidadeChat = Depends(identidade_chat_autorizada),
):
    validar_origem_csrf(request)
    texto = payload.texto[: tamanho_maximo_mensagem()]
    try:
        with conectar() as conn:
            garantir_tabelas_isis_chat(conn)
            sessao = obter_sessao(conn, session_id, user_ref=identidade.referencia)
            tocar_sessao(conn, session_id)
            try:
                resposta = processar_mensagem(conn, sessao, texto, base_url=_base_url(request))
            except LimiteMensagensExcedido:
                raise HTTPException(
                    status_code=429,
                    detail="Você atingiu o limite de mensagens desta sessão. Encerre e abra uma nova conversa.",
                )
    except SessaoChatInvalida as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except HTTPException:
        raise
    except Exception:
        logger.exception("isis chat: falha ao processar mensagem", extra={"evento": "isis_chat_erro_processamento"})
        return {
            "message": "Não consegui processar sua mensagem agora. Tente novamente em instantes.",
            "intent": "erro",
            "recommendations": [],
            "complementary_items": [],
            "suggested_kit": None,
            "remaining_messages": max(0, _limite_atual() - 1),
        }
    return resposta


@router.delete("/sessoes/{session_id}")
def encerrar_sessao_chat(session_id: str, request: Request, identidade: IdentidadeChat = Depends(identidade_chat_autorizada)):
    validar_origem_csrf(request)
    with conectar() as conn:
        garantir_tabelas_isis_chat(conn)
        encerrada = encerrar_sessao(conn, session_id, user_ref=identidade.referencia)
    if not encerrada:
        raise HTTPException(status_code=404, detail="Sessão não encontrada.")
    return {"ok": True}
