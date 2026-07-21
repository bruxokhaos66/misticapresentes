"""Painel administrativo: histórico e status operacional das notificações
por WhatsApp (backend/whatsapp_outbox.py / backend/whatsapp_worker.py).

Nunca expõe token, app secret, verify token, payload bruto do provedor ou
número de telefone completo -- só o que é necessário para o administrador
acompanhar a fila (evento, status, tentativas, erro sanitizado) e agir
(reprocessar/cancelar), sempre autenticado e auditado.
"""
from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query

from backend.audit import registrar_auditoria
from backend.database import conectar
from backend.panel_sessions import exigir_sessao_ou_chave_api
from backend.rate_limit import limitar_requisicoes
from backend.whatsapp_flags import diagnostico_configuracao_whatsapp

router = APIRouter(prefix="/api/admin/whatsapp-notificacoes", tags=["admin-whatsapp-notificacoes"])

limitar_reprocessar = limitar_requisicoes("whatsapp_reprocessar", limite=30, janela_segundos=60)

_CAMPOS_PUBLICOS = (
    "id", "event_type", "order_id", "channel", "provider", "template_name",
    "status", "attempts", "created_at", "updated_at", "sent_at", "delivered_at",
    "read_at", "failed_at", "next_attempt_at", "last_error_code", "last_error_summary",
)

_STATUS_REPROCESSAVEIS = {"permanently_failed"}
_STATUS_CANCELAVEIS = {"pending", "retry"}


def _linha_publica(row: dict) -> dict:
    publica = {campo: row.get(campo) for campo in _CAMPOS_PUBLICOS}
    # Nunca expõe recipient_reference (hash interno) nem payload_json bruto
    # (pode conter o valor do pedido, mas não é PII -- ainda assim mantido
    # fora da listagem padrão por minimalismo; disponível via payload_json
    # só quando necessário, nunca em texto de erro do provedor).
    publica["destinatario"] = "admin (mascarado)" if row.get("recipient_reference") else None
    return publica


@router.get("/status")
def status_configuracao_whatsapp(sessao: dict = Depends(exigir_sessao_ou_chave_api(perfil_minimo="adm"))):
    """Estado operacional não sensível para o painel: habilitado/desabilitado,
    provider, validade da configuração, contagem de destinatários e da fila."""
    diagnostico = diagnostico_configuracao_whatsapp()
    with conectar() as conn:
        contagens = {
            row["status"]: row["total"]
            for row in conn.execute("SELECT status, COUNT(*) AS total FROM notification_outbox GROUP BY status").fetchall()
        }
        mais_antiga_pendente = conn.execute(
            "SELECT MIN(created_at) AS criado_em FROM notification_outbox WHERE status IN ('pending','retry')"
        ).fetchone()
    if not diagnostico["effective_enabled"]:
        diagnostico["mensagem"] = "Notificações por WhatsApp não configuradas."
    return {
        "ok": True,
        **diagnostico,
        "queue_counts": contagens,
        "oldest_pending_created_at": mais_antiga_pendente["criado_em"] if mais_antiga_pendente else None,
    }


@router.get("")
def listar_notificacoes(
    order_id: int | None = Query(default=None),
    status: str | None = Query(default=None),
    limite: int = Query(50, ge=1, le=200),
    sessao: dict = Depends(exigir_sessao_ou_chave_api(perfil_minimo="adm")),
):
    condicoes = []
    parametros: list = []
    if order_id is not None:
        condicoes.append("order_id=?")
        parametros.append(order_id)
    if status:
        condicoes.append("status=?")
        parametros.append(status)
    where = f"WHERE {' AND '.join(condicoes)}" if condicoes else ""
    with conectar() as conn:
        rows = conn.execute(
            f"SELECT * FROM notification_outbox {where} ORDER BY id DESC LIMIT ?",
            (*parametros, limite),
        ).fetchall()
    return {"ok": True, "total": len(rows), "notificacoes": [_linha_publica(dict(row)) for row in rows]}


@router.post("/{notificacao_id}/reprocessar", dependencies=[Depends(limitar_reprocessar)])
def reprocessar_notificacao(notificacao_id: int, sessao: dict = Depends(exigir_sessao_ou_chave_api(perfil_minimo="adm"))):
    """Reagenda uma notificação permanentemente falha para uma nova
    tentativa imediata -- nunca cria uma linha nova (evitaria duplicidade),
    apenas reabre a mesma linha já existente. Só permitido para
    'permanently_failed' -- reprocessar uma linha já enviada/entregue nunca
    é aceito aqui (evitaria reenviar a mesma mensagem)."""
    usuario = str(sessao.get("nome") or sessao.get("login") or "Admin")
    agora = datetime.now().isoformat(timespec="seconds")
    with conectar() as conn:
        linha = conn.execute("SELECT id, status, event_type, order_id FROM notification_outbox WHERE id=?", (notificacao_id,)).fetchone()
        if not linha:
            raise HTTPException(status_code=404, detail="Notificação não encontrada.")
        if str(linha["status"]) not in _STATUS_REPROCESSAVEIS:
            raise HTTPException(status_code=409, detail=f"Notificação em '{linha['status']}' não pode ser reprocessada.")
        conn.execute(
            "UPDATE notification_outbox SET status='retry', next_attempt_at=?, attempts=0, last_error_code=NULL, last_error_summary=NULL, updated_at=? WHERE id=? AND status='permanently_failed'",
            (agora, agora, notificacao_id),
        )
        registrar_auditoria(
            conn, "notification_outbox", notificacao_id, "reprocessar_manual", usuario,
            depois={"event_type": linha["event_type"], "order_id": linha["order_id"]},
        )
        conn.commit()
    return {"ok": True, "id": notificacao_id, "status": "retry"}


@router.post("/{notificacao_id}/cancelar")
def cancelar_notificacao(notificacao_id: int, sessao: dict = Depends(exigir_sessao_ou_chave_api(perfil_minimo="adm"))):
    """Cancela uma notificação ainda pendente/em retry -- nunca uma já
    enviada (a mensagem, se enviada, não pode ser "desenviada")."""
    usuario = str(sessao.get("nome") or sessao.get("login") or "Admin")
    agora = datetime.now().isoformat(timespec="seconds")
    with conectar() as conn:
        linha = conn.execute("SELECT id, status FROM notification_outbox WHERE id=?", (notificacao_id,)).fetchone()
        if not linha:
            raise HTTPException(status_code=404, detail="Notificação não encontrada.")
        if str(linha["status"]) not in _STATUS_CANCELAVEIS:
            raise HTTPException(status_code=409, detail=f"Notificação em '{linha['status']}' não pode ser cancelada.")
        conn.execute(
            "UPDATE notification_outbox SET status='cancelled', updated_at=? WHERE id=? AND status IN ('pending','retry')",
            (agora, notificacao_id),
        )
        registrar_auditoria(conn, "notification_outbox", notificacao_id, "cancelar_manual", usuario)
        conn.commit()
    return {"ok": True, "id": notificacao_id, "status": "cancelled"}
