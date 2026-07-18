from __future__ import annotations

import os
import secrets
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field

from backend.audit import registrar_auditoria
from backend.database import conectar
from backend.order_status_routes import (
    STATUS_PEDIDO_COMPROVANTE_ENVIADO,
    STATUS_PEDIDO_PAGAMENTO_EM_ANALISE,
    cancelar_pedido as cancelar_pedido_api_key,
    expirar_pedidos_pendentes,
    venda_para_pedido,
)
from backend.panel_sessions import exigir_sessao_ou_chave_api
from backend.payment_routes import PagamentoIn, registrar_pagamento as registrar_pagamento_api_key
from backend.rate_limit import _client_ip, limitar_requisicoes

router = APIRouter(prefix="/api", tags=["pedidos-notificacao"])

limitar_comprovante_cliente = limitar_requisicoes("comprovante_cliente", limite=20, janela_segundos=60)

# Status em que o pedido ainda depende de conferência humana (nunca inclui
# "Pagamento confirmado"/"Aguardando encomenda": esses só são produzidos por
# POST /api/pagamentos, ver backend/payment_routes.py).
STATUS_PIX_PENDENTES = {
    "Aguardando pagamento",
    "Pagamento divergente",
    STATUS_PEDIDO_COMPROVANTE_ENVIADO,
    STATUS_PEDIDO_PAGAMENTO_EM_ANALISE,
}

# Transições aceitas pelas ações do cliente/admin deste arquivo. Cada chave é
# o status de origem; o valor é o status de destino. Qualquer outra
# combinação é rejeitada com 409 — nunca aplicamos a transição "mais próxima"
# nem pulamos estados.
TRANSICAO_CLIENTE_ENVIOU_COMPROVANTE = {
    "Aguardando pagamento": STATUS_PEDIDO_COMPROVANTE_ENVIADO,
    "Pagamento divergente": STATUS_PEDIDO_COMPROVANTE_ENVIADO,
}
TRANSICAO_ADMIN_MARCAR_RECEBIDO = {
    STATUS_PEDIDO_COMPROVANTE_ENVIADO: STATUS_PEDIDO_PAGAMENTO_EM_ANALISE,
}
TRANSICAO_ADMIN_REJEITAR = {
    STATUS_PEDIDO_COMPROVANTE_ENVIADO: "Aguardando pagamento",
    STATUS_PEDIDO_PAGAMENTO_EM_ANALISE: "Aguardando pagamento",
}


def _sanitizar_texto(valor: Optional[str], limite: int = 280) -> str:
    texto = str(valor or "").strip()
    texto = "".join(ch for ch in texto if ch == " " or (ord(ch) >= 32 and ch != "\x7f"))
    return texto[:limite]


def _chave_api_servidor() -> str:
    """A chave MISTICA_SITE_API_KEY/MISTICA_SYNC_KEY nunca é digitada nem
    guardada no navegador (ver backend/panel_sessions.py). As duas rotas
    abaixo (confirmar pagamento e cancelar pelo painel) existem para que uma
    sessão de administrador autenticada por cookie consiga acionar as MESMAS
    rotas já existentes e testadas (registrar_pagamento/cancelar_pedido, com
    toda a conciliação de valor e reposição de estoque que elas já fazem),
    sem que o navegador precise conhecer a chave: o servidor a lê do próprio
    ambiente e a repassa internamente."""
    chave = os.environ.get("MISTICA_SITE_API_KEY", "").strip() or os.environ.get("MISTICA_SYNC_KEY", "").strip()
    if not chave:
        raise HTTPException(status_code=503, detail="Configure MISTICA_SITE_API_KEY ou MISTICA_SYNC_KEY no servidor.")
    return chave


@router.get("/pedidos/pix/pendentes")
def listar_pedidos_pix_pendentes(limite: int = Query(100, ge=1, le=500), sessao: dict = Depends(exigir_sessao_ou_chave_api())):
    """Pedidos Pix aguardando confirmação (painel administrativo). Nunca
    inclui pedidos já pagos, cancelados ou concluídos."""
    with conectar() as conn:
        expirar_pedidos_pendentes(conn)
        placeholders = ",".join("?" for _ in STATUS_PIX_PENDENTES)
        rows = conn.execute(
            f"""
            SELECT id, cliente, telefone, data_venda, total_final, forma_pagamento, status,
                   data_iso, expira_em, pix_txid, visualizado_admin_em, visualizado_admin_por,
                   comprovante_enviado_em
            FROM pedidos
            WHERE COALESCE(status,'') IN ({placeholders})
            ORDER BY id DESC
            LIMIT ?
            """,
            (*STATUS_PIX_PENDENTES, limite),
        ).fetchall()
        pedidos = [venda_para_pedido(conn, row) for row in rows]
    total_nao_visualizados = sum(1 for pedido in pedidos if not pedido.get("visualizado_admin_em"))
    return {
        "ok": True,
        "total": len(pedidos),
        "total_nao_visualizados": total_nao_visualizados,
        "pedidos": pedidos,
    }


@router.post("/pedidos/{venda_id}/visualizar")
def marcar_pedido_visualizado(venda_id: int, sessao: dict = Depends(exigir_sessao_ou_chave_api())):
    """Marca que um administrador já viu este pedido no painel. Não altera o
    status financeiro do pedido — é só um sinal de UI/auditoria, idempotente:
    a primeira chamada grava quem e quando; chamadas seguintes não sobrescrevem."""
    agora = datetime.now().isoformat(timespec="seconds")
    usuario = str(sessao.get("nome") or sessao.get("login") or "Admin")
    with conectar() as conn:
        venda = conn.execute("SELECT id, visualizado_admin_em FROM pedidos WHERE id=?", (venda_id,)).fetchone()
        if not venda:
            raise HTTPException(status_code=404, detail="Pedido não encontrado")
        ja_visualizado = bool(venda["visualizado_admin_em"])
        if not ja_visualizado:
            conn.execute(
                "UPDATE pedidos SET visualizado_admin_em=?, visualizado_admin_por=? WHERE id=? AND visualizado_admin_em IS NULL",
                (agora, usuario, venda_id),
            )
            registrar_auditoria(conn, "pedido", venda_id, "visualizado_admin", usuario, depois={"visualizado_em": agora})
            conn.commit()
    return {"ok": True, "venda_id": venda_id, "ja_visualizado": ja_visualizado}


class ComprovanteClienteIn(BaseModel):
    txid: str | None = None


@router.post("/pedidos/{venda_id}/comprovante", dependencies=[Depends(limitar_comprovante_cliente)])
def cliente_iniciou_envio_comprovante(venda_id: int, request: Request, payload: ComprovanteClienteIn = Body(default=ComprovanteClienteIn())):
    """Registra que o cliente clicou em "Já paguei — enviar comprovante pelo
    WhatsApp" para ESTE pedido. O site nunca consegue confirmar que o cliente
    de fato anexou o comprovante na conversa do WhatsApp — isso só é validado
    depois, manualmente, pelo administrador (ver
    marcar_comprovante_recebido/POST /api/pagamentos). Esta ação nunca marca
    o pedido como pago.

    Autenticação: o pix_txid do próprio pedido funciona como identificador
    público limitado (mesmo padrão já usado por GET /api/pedidos/{id}/status
    e /recibo) — sem ele, o id sozinho não dá acesso a pedidos alheios. A
    resposta de acesso negado é sempre a mesma, com pedido existente ou não,
    para não servir de oráculo de enumeração.

    Auditoria: IP e User-Agent do clique ficam registrados em audit_log
    (nunca em pedido_status_log, que é exibido ao operador no painel) só
    para investigar disputas/fraude — não afetam a confirmação financeira,
    que continua exclusivamente manual via POST /api/pagamentos."""
    ip_cliente = _client_ip(request)
    user_agent_cliente = str(request.headers.get("user-agent", ""))[:255]
    with conectar() as conn:
        expirar_pedidos_pendentes(conn)
        venda = conn.execute("SELECT id, status, pix_txid, comprovante_enviado_em FROM pedidos WHERE id=?", (venda_id,)).fetchone()
        if not venda or not venda["pix_txid"] or not payload.txid or not secrets.compare_digest(str(payload.txid), str(venda["pix_txid"])):
            raise HTTPException(status_code=403, detail="Acesso negado. Informe o código do pedido (txid) para registrar o comprovante.")

        status_atual = str(venda["status"] or "")
        agora = datetime.now().isoformat(timespec="seconds")

        # Idempotente: se o pedido já está em "Comprovante enviado" (ou
        # adiante), um novo clique/retry não repete a transição nem duplica
        # o carimbo de data/hora original.
        if status_atual not in TRANSICAO_CLIENTE_ENVIOU_COMPROVANTE:
            return {
                "ok": True,
                "venda_id": venda_id,
                "status": status_atual,
                "ja_registrado": True,
                "comprovante_enviado_em": venda["comprovante_enviado_em"],
            }

        status_novo = TRANSICAO_CLIENTE_ENVIOU_COMPROVANTE[status_atual]
        claim = conn.execute(
            "UPDATE pedidos SET status=?, comprovante_enviado_em=COALESCE(comprovante_enviado_em, ?) WHERE id=? AND status=?",
            (status_novo, agora, venda_id, status_atual),
        )
        if claim.rowcount == 0:
            # Corrida concorrente já mudou o status: não reabrimos nem
            # sobrescrevemos, apenas devolvemos o estado atual.
            atual = conn.execute("SELECT status, comprovante_enviado_em FROM pedidos WHERE id=?", (venda_id,)).fetchone()
            return {
                "ok": True,
                "venda_id": venda_id,
                "status": str(atual["status"] or ""),
                "ja_registrado": True,
                "comprovante_enviado_em": atual["comprovante_enviado_em"],
            }

        conn.execute(
            "INSERT INTO pedido_status_log (venda_id, status, usuario, observacao, data_hora) VALUES (?,?,?,?,?)",
            (venda_id, status_novo, "Cliente", "Cliente indicou ter pago e iniciou envio do comprovante pelo WhatsApp.", agora),
        )
        registrar_auditoria(
            conn, "pedido", venda_id, "cliente_iniciou_envio_comprovante", "Cliente",
            antes={"status": status_atual},
            depois={"status": status_novo, "ip": ip_cliente, "user_agent": user_agent_cliente},
        )
        conn.commit()
    return {
        "ok": True,
        "venda_id": venda_id,
        "status": status_novo,
        "ja_registrado": False,
        "comprovante_enviado_em": agora,
    }


class AcaoComprovanteAdminIn(BaseModel):
    observacao: Optional[str] = None


@router.post("/pedidos/{venda_id}/comprovante/recebido")
def marcar_comprovante_recebido(venda_id: int, payload: AcaoComprovanteAdminIn = Body(default=AcaoComprovanteAdminIn()), sessao: dict = Depends(exigir_sessao_ou_chave_api())):
    """Ação administrativa: marca que o comprovante foi recebido/visto na
    conversa do WhatsApp e move o pedido para conferência ("Pagamento em
    análise"). Continua não confirmando pagamento — isso só acontece via
    POST /api/pagamentos, depois de o administrador conferir o valor
    creditado no aplicativo bancário."""
    usuario = str(sessao.get("nome") or sessao.get("login") or "Admin")
    agora = datetime.now().isoformat(timespec="seconds")
    with conectar() as conn:
        venda = conn.execute("SELECT id, status FROM pedidos WHERE id=?", (venda_id,)).fetchone()
        if not venda:
            raise HTTPException(status_code=404, detail="Pedido não encontrado")
        status_atual = str(venda["status"] or "")
        if status_atual == STATUS_PEDIDO_PAGAMENTO_EM_ANALISE:
            return {"ok": True, "venda_id": venda_id, "status": status_atual, "ja_registrado": True}
        if status_atual not in TRANSICAO_ADMIN_MARCAR_RECEBIDO:
            raise HTTPException(status_code=409, detail=f"Pedido em '{status_atual}' não pode ser marcado como comprovante recebido.")
        status_novo = TRANSICAO_ADMIN_MARCAR_RECEBIDO[status_atual]
        claim = conn.execute("UPDATE pedidos SET status=? WHERE id=? AND status=?", (status_novo, venda_id, status_atual))
        if claim.rowcount == 0:
            raise HTTPException(status_code=409, detail="O status do pedido mudou nesse meio-tempo. Atualize a página e tente novamente.")
        observacao = _sanitizar_texto(payload.observacao) or "Comprovante recebido, aguardando conferência do valor no aplicativo bancário."
        conn.execute(
            "INSERT INTO pedido_status_log (venda_id, status, usuario, observacao, data_hora) VALUES (?,?,?,?,?)",
            (venda_id, status_novo, usuario, observacao, agora),
        )
        registrar_auditoria(
            conn, "pedido", venda_id, "comprovante_marcado_recebido", usuario,
            antes={"status": status_atual}, depois={"status": status_novo},
        )
        conn.commit()
    return {"ok": True, "venda_id": venda_id, "status": status_novo, "ja_registrado": False}


@router.post("/pedidos/{venda_id}/comprovante/rejeitar")
def rejeitar_comprovante(venda_id: int, payload: AcaoComprovanteAdminIn = Body(default=AcaoComprovanteAdminIn()), sessao: dict = Depends(exigir_sessao_ou_chave_api())):
    """Ação administrativa: rejeita o comprovante enviado (ilegível, valor
    incompatível, suspeita de fraude etc.) e devolve o pedido para
    "Aguardando pagamento", para que o cliente tente de novo. Nunca cancela
    o pedido — cancelamento é uma ação separada (DELETE /api/pedidos/{id})."""
    usuario = str(sessao.get("nome") or sessao.get("login") or "Admin")
    agora = datetime.now().isoformat(timespec="seconds")
    with conectar() as conn:
        venda = conn.execute("SELECT id, status FROM pedidos WHERE id=?", (venda_id,)).fetchone()
        if not venda:
            raise HTTPException(status_code=404, detail="Pedido não encontrado")
        status_atual = str(venda["status"] or "")
        if status_atual not in TRANSICAO_ADMIN_REJEITAR:
            raise HTTPException(status_code=409, detail=f"Pedido em '{status_atual}' não tem comprovante pendente para rejeitar.")
        status_novo = TRANSICAO_ADMIN_REJEITAR[status_atual]
        claim = conn.execute("UPDATE pedidos SET status=?, comprovante_enviado_em=NULL WHERE id=? AND status=?", (status_novo, venda_id, status_atual))
        if claim.rowcount == 0:
            raise HTTPException(status_code=409, detail="O status do pedido mudou nesse meio-tempo. Atualize a página e tente novamente.")
        observacao = _sanitizar_texto(payload.observacao) or "Comprovante rejeitado pelo administrador."
        conn.execute(
            "INSERT INTO pedido_status_log (venda_id, status, usuario, observacao, data_hora) VALUES (?,?,?,?,?)",
            (venda_id, status_novo, usuario, observacao, agora),
        )
        registrar_auditoria(
            conn, "pedido", venda_id, "comprovante_rejeitado", usuario,
            antes={"status": status_atual}, depois={"status": status_novo, "motivo": observacao},
        )
        conn.commit()
    return {"ok": True, "venda_id": venda_id, "status": status_novo}


class ConfirmarPagamentoPainelIn(BaseModel):
    valor: float = Field(ge=0)


@router.post("/pedidos/{venda_id}/confirmar-pagamento-painel")
def confirmar_pagamento_painel(venda_id: int, payload: ConfirmarPagamentoPainelIn, sessao: dict = Depends(exigir_sessao_ou_chave_api(perfil_minimo="adm"))):
    """Confirma o pagamento a partir do painel administrativo (sessão de
    cookie), pedindo ao administrador antes o valor exatamente como
    conferido no aplicativo bancário (a interface exige a confirmação
    "Confirme no aplicativo bancário que o valor foi creditado. Um
    comprovante isolado pode ser falso." antes de chamar esta rota).

    Reaproveita, sem duplicar, a mesma rota/lógica de conciliação já
    existente e testada (POST /api/pagamentos — valor recebido comparado ao
    total autoritativo do pedido antes de confirmar e baixar estoque)."""
    usuario = str(sessao.get("nome") or sessao.get("login") or "Admin")
    resposta = registrar_pagamento_api_key(
        payload=PagamentoIn(venda_id=venda_id, forma="Pix", valor=payload.valor, status="Confirmado", usuario=usuario),
        x_mistica_api_key=_chave_api_servidor(),
        idempotency_key=None,
    )
    return resposta


@router.post("/pedidos/{venda_id}/cancelar-painel")
def cancelar_pedido_painel(venda_id: int, sessao: dict = Depends(exigir_sessao_ou_chave_api(perfil_minimo="adm"))):
    """Cancela o pedido a partir do painel administrativo (sessão de
    cookie), reaproveitando a mesma rota/lógica já existente
    (DELETE /api/pedidos/{id} — reposição de estoque e histórico já
    tratados ali, sem duplicação)."""
    return cancelar_pedido_api_key(venda_id, x_mistica_api_key=_chave_api_servidor())
