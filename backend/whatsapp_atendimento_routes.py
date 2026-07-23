"""Central Multiatendente: fila, assunção (claim), liberação, transferência,
finalização/reabertura, histórico e gestão de atendentes.

Mesmo padrão de segurança de backend/whatsapp_inbox_routes.py: toda rota
exige sessão administrativa real (backend.panel_sessions.exigir_perfis, que
também valida Origin/Referer em métodos mutáveis). A checagem fina de QUAL
perfil pode fazer O QUÊ é sempre revalidada no banco a cada chamada por
backend.atendimento_repository.exigir_atendente -- nunca confia em um botão
oculto no frontend nem só no perfil cacheado na sessão."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel, Field

from backend.atendimento_repository import (
    ErroOperacaoFila,
    atualizar_agente,
    exigir_atendente,
    linha_conversa_fila_publica,
    listar_agentes,
    listar_fila,
    listar_historico_atendimento,
    listar_minhas_conversas,
    liberar_conversa,
    obter_conversa_para_fila,
    reabrir_conversa,
    reivindicar_conversa,
    resolver_conversa,
    transferir_conversa,
)
from backend.database import conectar
from backend.panel_sessions import exigir_perfis
from backend.whatsapp_inbox_repository import obter_conversa
from backend.whatsapp_flags import whatsapp_cloud_inbox_habilitado

router = APIRouter(prefix="/api/admin/whatsapp", tags=["admin-whatsapp-atendimento-multiatendente"])

TAMANHO_PAGINA_PADRAO = 30
TAMANHO_PAGINA_MAXIMO = 100

CODIGO_HTTP_POR_ERRO = {
    "not_found": 404,
    "already_claimed": 409,
    "conversation_resolved": 409,
    "version_conflict": 409,
    "limit_reached": 409,
    "target_limit_reached": 409,
    "invalid_target": 422,
    "invalid_field": 422,
    "invalid_state": 409,
    "forbidden": 403,
}


def _exigir_habilitado() -> None:
    if not whatsapp_cloud_inbox_habilitado():
        raise HTTPException(status_code=503, detail="Central de Atendimento WhatsApp desabilitada ou mal configurada.")


def _sem_cache(response: Response) -> None:
    response.headers["Cache-Control"] = "no-store"


def _erro_http(erro: ErroOperacaoFila) -> HTTPException:
    return HTTPException(status_code=CODIGO_HTTP_POR_ERRO.get(erro.codigo, 400), detail=erro.mensagem)


class TransferirBody(BaseModel):
    target_user_id: int
    reason: str | None = Field(default=None, max_length=300)
    assignment_version: int | None = None


class LiberarBody(BaseModel):
    reason: str | None = Field(default=None, max_length=300)


class ResolverBody(BaseModel):
    assignment_version: int | None = None


class AtualizarAgenteBody(BaseModel):
    perfil: str | None = Field(default=None, max_length=40)
    atendimento_enabled: bool | None = None
    atendimento_max_active_conversations: int | None = Field(default=None, ge=1, le=1000)
    suspender: bool | None = None


@router.get("/queue")
def rota_listar_fila(
    response: Response,
    page: int = Query(default=1, ge=1, le=10_000),
    page_size: int = Query(default=TAMANHO_PAGINA_PADRAO, ge=1, le=TAMANHO_PAGINA_MAXIMO),
    sessao: dict = Depends(exigir_perfis("adm", "supervisor_atendimento", "vendedor")),
):
    _sem_cache(response)
    _exigir_habilitado()
    with conectar() as conn:
        exigir_atendente(conn, sessao)
        linhas, total = listar_fila(conn, pagina=page, tamanho_pagina=page_size)
    return {"ok": True, "total": total, "page": page, "page_size": page_size, "conversations": linhas}


@router.get("/my-conversations")
def rota_minhas_conversas(
    response: Response,
    page: int = Query(default=1, ge=1, le=10_000),
    page_size: int = Query(default=TAMANHO_PAGINA_PADRAO, ge=1, le=TAMANHO_PAGINA_MAXIMO),
    sessao: dict = Depends(exigir_perfis("adm", "supervisor_atendimento", "vendedor")),
):
    _sem_cache(response)
    _exigir_habilitado()
    with conectar() as conn:
        usuario = exigir_atendente(conn, sessao)
        linhas, total = listar_minhas_conversas(conn, usuario_id=usuario["id"], pagina=page, tamanho_pagina=page_size)
    return {"ok": True, "total": total, "page": page, "page_size": page_size, "conversations": linhas}


@router.get("/agents")
def rota_listar_agentes(
    response: Response,
    sessao: dict = Depends(exigir_perfis("adm", "supervisor_atendimento")),
):
    _sem_cache(response)
    with conectar() as conn:
        exigir_atendente(conn, sessao)
        agentes = listar_agentes(conn)
    return {"ok": True, "agents": agentes}


@router.patch("/agents/{user_id}")
def rota_atualizar_agente(
    user_id: int,
    body: AtualizarAgenteBody,
    sessao: dict = Depends(exigir_perfis("adm", "supervisor_atendimento")),
):
    with conectar() as conn:
        ator = exigir_atendente(conn, sessao)
        campos = body.model_dump(exclude_unset=True)
        try:
            atualizado = atualizar_agente(conn, usuario_id=user_id, ator=ator, campos=campos)
        except ErroOperacaoFila as exc:
            raise _erro_http(exc)
        conn.commit()
    return {
        "ok": True,
        "agent": {
            "id": atualizado["id"],
            "nome": atualizado.get("nome"),
            "perfil": atualizado.get("perfil"),
            "atendimento_enabled": bool(atualizado.get("atendimento_enabled")),
            "atendimento_max_active_conversations": atualizado.get("atendimento_max_active_conversations"),
            "atendimento_suspended_at": atualizado.get("atendimento_suspended_at"),
        },
    }


@router.post("/conversations/{conversation_id}/claim")
def rota_claim(
    conversation_id: int,
    sessao: dict = Depends(exigir_perfis("adm", "supervisor_atendimento", "vendedor")),
):
    _exigir_habilitado()
    with conectar() as conn:
        usuario = exigir_atendente(conn, sessao)
        try:
            reivindicar_conversa(conn, conversation_id=conversation_id, usuario=usuario)
        except ErroOperacaoFila as exc:
            conn.commit()
            raise _erro_http(exc)
        conversa = obter_conversa(conn, conversation_id)
        conn.commit()
    return {"ok": True, "conversation": linha_conversa_fila_publica(conversa)}


@router.post("/conversations/{conversation_id}/release")
def rota_release(
    conversation_id: int,
    body: LiberarBody,
    sessao: dict = Depends(exigir_perfis("adm", "supervisor_atendimento", "vendedor")),
):
    _exigir_habilitado()
    with conectar() as conn:
        usuario = exigir_atendente(conn, sessao)
        try:
            liberar_conversa(conn, conversation_id=conversation_id, usuario=usuario, reason=body.reason)
        except ErroOperacaoFila as exc:
            raise _erro_http(exc)
        conversa = obter_conversa(conn, conversation_id)
        conn.commit()
    return {"ok": True, "conversation": linha_conversa_fila_publica(conversa)}


@router.post("/conversations/{conversation_id}/transfer")
def rota_transfer(
    conversation_id: int,
    body: TransferirBody,
    sessao: dict = Depends(exigir_perfis("adm", "supervisor_atendimento", "vendedor")),
):
    _exigir_habilitado()
    with conectar() as conn:
        usuario = exigir_atendente(conn, sessao)
        try:
            transferir_conversa(
                conn,
                conversation_id=conversation_id,
                usuario=usuario,
                target_user_id=body.target_user_id,
                reason=body.reason,
                expected_version=body.assignment_version,
            )
        except ErroOperacaoFila as exc:
            raise _erro_http(exc)
        conversa = obter_conversa(conn, conversation_id)
        conn.commit()
    return {"ok": True, "conversation": linha_conversa_fila_publica(conversa)}


@router.post("/conversations/{conversation_id}/resolve")
def rota_resolve(
    conversation_id: int,
    body: ResolverBody,
    sessao: dict = Depends(exigir_perfis("adm", "supervisor_atendimento", "vendedor")),
):
    _exigir_habilitado()
    with conectar() as conn:
        usuario = exigir_atendente(conn, sessao)
        try:
            resolver_conversa(conn, conversation_id=conversation_id, usuario=usuario, expected_version=body.assignment_version)
        except ErroOperacaoFila as exc:
            raise _erro_http(exc)
        conversa = obter_conversa(conn, conversation_id)
        conn.commit()
    return {"ok": True, "conversation": linha_conversa_fila_publica(conversa)}


@router.post("/conversations/{conversation_id}/reopen")
def rota_reopen(
    conversation_id: int,
    sessao: dict = Depends(exigir_perfis("adm", "supervisor_atendimento")),
):
    _exigir_habilitado()
    with conectar() as conn:
        usuario = exigir_atendente(conn, sessao)
        try:
            reabrir_conversa(conn, conversation_id=conversation_id, usuario=usuario)
        except ErroOperacaoFila as exc:
            raise _erro_http(exc)
        conversa = obter_conversa(conn, conversation_id)
        conn.commit()
    return {"ok": True, "conversation": linha_conversa_fila_publica(conversa)}


@router.get("/conversations/{conversation_id}/assignment-history")
def rota_assignment_history(
    conversation_id: int,
    response: Response,
    page: int = Query(default=1, ge=1, le=10_000),
    page_size: int = Query(default=TAMANHO_PAGINA_PADRAO, ge=1, le=TAMANHO_PAGINA_MAXIMO),
    sessao: dict = Depends(exigir_perfis("adm", "supervisor_atendimento")),
):
    _sem_cache(response)
    with conectar() as conn:
        exigir_atendente(conn, sessao)
        conversa = obter_conversa_para_fila(conn, conversation_id)
        if not conversa:
            raise HTTPException(status_code=404, detail="Conversa não encontrada.")
        linhas, total = listar_historico_atendimento(conn, conversation_id, pagina=page, tamanho_pagina=page_size)
    return {"ok": True, "total": total, "page": page, "page_size": page_size, "history": linhas}
