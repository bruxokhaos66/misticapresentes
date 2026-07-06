from __future__ import annotations

import os
import secrets
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field

from backend.database import conectar
from backend.order_status_routes import garantir_tabela_status, baixar_estoque_do_pedido, buscar_produto_para_baixa

router = APIRouter(prefix="/api", tags=["pedidos-api-seguro"])

STATUS_ALIASES = {
    "Pago": "Pagamento confirmado",
    "Em separação": "Separando pedido",
}
STATUS_PERMITIDOS = {
    "Aguardando pagamento",
    "Pagamento confirmado",
    "Separando pedido",
    "Pronto para retirada",
    "Entregue",
    "Cancelado",
    "Concluído",
}
STATUS_BAIXA_ESTOQUE = {"Pagamento confirmado", "Separando pedido"}


class StatusPayload(BaseModel):
    status: str = Field(min_length=1)
    usuario: str = "Site/API"
    observacao: Optional[str] = None


class CancelamentoPayload(BaseModel):
    usuario: str = "Site/API"
    observacao: Optional[str] = None


def exigir_chave_site(chave_recebida: str | None):
    chave = os.environ.get("MISTICA_SITE_API_KEY", "").strip() or os.environ.get("MISTICA_SYNC_KEY", "").strip()
    if not chave:
        raise HTTPException(status_code=503, detail="Configure MISTICA_SITE_API_KEY ou MISTICA_SYNC_KEY para liberar escrita pública.")
    if not chave_recebida or not secrets.compare_digest(str(chave_recebida), chave):
        raise HTTPException(status_code=403, detail="Chave da API inválida.")


def normalizar_status(status: str) -> str:
    status = str(status or "").strip()
    status = STATUS_ALIASES.get(status, status)
    if status not in STATUS_PERMITIDOS:
        raise HTTPException(status_code=400, detail="Status de pedido inválido.")
    return status


def garantir_colunas_cancelamento(conn):
    garantir_tabela_status(conn)
    for sql in [
        "ALTER TABLE vendas ADD COLUMN estoque_reposto_cancelamento INTEGER DEFAULT 0",
        "ALTER TABLE vendas ADD COLUMN estoque_reposto_em TEXT",
    ]:
        try:
            conn.execute(sql)
        except Exception:
            pass


def repor_estoque_cancelamento(conn, venda_id: int, usuario: str, agora: str):
    venda = conn.execute(
        "SELECT id, estoque_baixado, estoque_reposto_cancelamento FROM vendas WHERE id=?",
        (venda_id,),
    ).fetchone()
    if not venda:
        raise HTTPException(status_code=404, detail="Pedido não encontrado.")
    if int(venda["estoque_baixado"] or 0) != 1:
        return False
    if int(venda["estoque_reposto_cancelamento"] or 0) == 1:
        return False

    itens = conn.execute(
        """
        SELECT id, codigo_p, nome_p, quantidade
        FROM vendas_itens
        WHERE venda_id=?
        ORDER BY id ASC
        """,
        (venda_id,),
    ).fetchall()
    total = 0
    for item in itens:
        quantidade = int(item["quantidade"] or 0)
        if quantidade <= 0:
            continue
        produto = buscar_produto_para_baixa(conn, item)
        if not produto:
            raise HTTPException(status_code=404, detail=f"Produto não encontrado para reposição: {item['nome_p'] or item['codigo_p']}")
        conn.execute("UPDATE produtos SET quantidade = quantidade + ? WHERE id=?", (quantidade, produto["id"]))
        total += quantidade

    conn.execute(
        "UPDATE vendas SET estoque_reposto_cancelamento=1, estoque_reposto_em=? WHERE id=?",
        (agora, venda_id),
    )
    conn.execute(
        """
        INSERT INTO pedido_status_log (venda_id, status, usuario, observacao, data_hora)
        VALUES (?,?,?,?,?)
        """,
        (venda_id, "Estoque reposto", usuario or "Site/API", f"Reposição automática: {total} item(ns)", agora),
    )
    return total > 0


def cancelar_com_reposicao(conn, venda_id: int, usuario: str, observacao: str | None, agora: str):
    garantir_colunas_cancelamento(conn)
    venda = conn.execute("SELECT id, status FROM vendas WHERE id=?", (venda_id,)).fetchone()
    if not venda:
        raise HTTPException(status_code=404, detail="Pedido não encontrado.")
    ja_cancelado = str(venda["status"] or "").lower().startswith("cancel")
    estoque_reposto = False if ja_cancelado else repor_estoque_cancelamento(conn, venda_id, usuario, agora)
    conn.execute("UPDATE vendas SET status='Cancelado' WHERE id=?", (venda_id,))
    conn.execute(
        """
        INSERT INTO pedido_status_log (venda_id, status, usuario, observacao, data_hora)
        VALUES (?,?,?,?,?)
        """,
        (
            venda_id,
            "Cancelado",
            usuario or "Site/API",
            observacao or ("Cancelado pela API segura" if not ja_cancelado else "Já estava cancelado; estoque não reposto novamente"),
            agora,
        ),
    )
    return {"ok": True, "venda_id": venda_id, "status": "Cancelado", "estoque_reposto_agora": estoque_reposto, "ja_cancelado": ja_cancelado}


def alterar_status(venda_id: int, payload: StatusPayload, chave: str | None):
    exigir_chave_site(chave)
    status = normalizar_status(payload.status)
    agora = datetime.now().isoformat(timespec="seconds")
    with conectar() as conn:
        garantir_colunas_cancelamento(conn)
        venda = conn.execute("SELECT id FROM vendas WHERE id=?", (venda_id,)).fetchone()
        if not venda:
            raise HTTPException(status_code=404, detail="Pedido não encontrado.")
        if status == "Cancelado":
            retorno = cancelar_com_reposicao(conn, venda_id, payload.usuario, payload.observacao, agora)
            conn.commit()
            return {**retorno, "data_hora": agora}
        baixou = False
        if status in STATUS_BAIXA_ESTOQUE:
            baixou = baixar_estoque_do_pedido(conn, venda_id, payload.usuario or "Site/API", agora)
        conn.execute("UPDATE vendas SET status=? WHERE id=?", (status, venda_id))
        obs = payload.observacao or ""
        if baixou:
            obs = (obs + " | " if obs else "") + "Estoque baixado automaticamente"
        conn.execute(
            """
            INSERT INTO pedido_status_log (venda_id, status, usuario, observacao, data_hora)
            VALUES (?,?,?,?,?)
            """,
            (venda_id, status, payload.usuario or "Site/API", obs, agora),
        )
        conn.commit()
    return {"ok": True, "venda_id": venda_id, "status": status, "estoque_baixado_agora": baixou, "data_hora": agora}


def cancelar(venda_id: int, payload: CancelamentoPayload | None, chave: str | None):
    exigir_chave_site(chave)
    payload = payload or CancelamentoPayload()
    agora = datetime.now().isoformat(timespec="seconds")
    with conectar() as conn:
        retorno = cancelar_com_reposicao(conn, venda_id, payload.usuario, payload.observacao, agora)
        conn.commit()
    return {**retorno, "data_hora": agora}


@router.post("/vendas/{venda_id}/status")
def status_venda(venda_id: int, payload: StatusPayload, x_mistica_api_key: str | None = Header(default=None)):
    return alterar_status(venda_id, payload, x_mistica_api_key)


@router.post("/pedidos/{venda_id}/status-seguro")
def status_pedido_seguro(venda_id: int, payload: StatusPayload, x_mistica_api_key: str | None = Header(default=None)):
    return alterar_status(venda_id, payload, x_mistica_api_key)


@router.post("/vendas/{venda_id}/cancelar")
def cancelar_venda(venda_id: int, payload: CancelamentoPayload | None = None, x_mistica_api_key: str | None = Header(default=None)):
    return cancelar(venda_id, payload, x_mistica_api_key)


@router.post("/pedidos/{venda_id}/cancelar")
def cancelar_pedido(venda_id: int, payload: CancelamentoPayload | None = None, x_mistica_api_key: str | None = Header(default=None)):
    return cancelar(venda_id, payload, x_mistica_api_key)
