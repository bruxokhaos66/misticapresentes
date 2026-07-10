from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field

from backend.database import conectar, executar
from backend.order_status_routes import (
    validar_site_api_key,
    baixar_estoque_do_pedido,
    buscar_produto_para_baixa,
    cancelar_com_reposicao,
)

router = APIRouter(tags=["pedidos-api-seguro"])

STATUS_ALIASES = {"Pago": "Pagamento confirmado", "Em separação": "Separando pedido"}
STATUS_PERMITIDOS = {"Aguardando pagamento", "Pagamento confirmado", "Separando pedido", "Pronto para retirada", "Entregue", "Cancelado", "Concluído"}
STATUS_BAIXA_ESTOQUE = {"Pagamento confirmado", "Separando pedido"}


class StatusPayload(BaseModel):
    status: str = Field(min_length=1)
    usuario: str = "Site/API"
    observacao: Optional[str] = None


class CancelamentoPayload(BaseModel):
    usuario: str = "Site/API"
    observacao: Optional[str] = None


class ClientePayload(BaseModel):
    nome: str = Field(min_length=1)
    telefone: Optional[str] = None
    cpf: Optional[str] = None
    endereco: Optional[str] = None
    nascimento: Optional[str] = None


def normalizar_status(status: str) -> str:
    status = str(status or "").strip()
    status = STATUS_ALIASES.get(status, status)
    if status not in STATUS_PERMITIDOS:
        raise HTTPException(status_code=400, detail="Status de pedido inválido.")
    return status


def alterar_status(venda_id: int, payload: StatusPayload, chave: str | None):
    validar_site_api_key(chave)
    status = normalizar_status(payload.status)
    agora = datetime.now().isoformat(timespec="seconds")
    with conectar() as conn:
        venda = conn.execute("SELECT id FROM pedidos WHERE id=?", (venda_id,)).fetchone()
        if not venda:
            raise HTTPException(status_code=404, detail="Pedido não encontrado.")
        if status == "Cancelado":
            retorno = cancelar_com_reposicao(conn, venda_id, payload.usuario, payload.observacao, agora)
            conn.commit()
            return {**retorno, "data_hora": agora}
        baixou = False
        if status in STATUS_BAIXA_ESTOQUE:
            baixou = baixar_estoque_do_pedido(conn, venda_id, payload.usuario or "Site/API", agora)
        conn.execute("UPDATE pedidos SET status=? WHERE id=?", (status, venda_id))
        obs = payload.observacao or ""
        if baixou:
            obs = (obs + " | " if obs else "") + "Estoque baixado automaticamente"
        conn.execute(
            "INSERT INTO pedido_status_log (venda_id, status, usuario, observacao, data_hora) VALUES (?,?,?,?,?)",
            (venda_id, status, payload.usuario or "Site/API", obs, agora),
        )
        conn.commit()
    return {"ok": True, "venda_id": venda_id, "status": status, "estoque_baixado_agora": baixou, "data_hora": agora}


def cancelar(venda_id: int, payload: CancelamentoPayload | None, chave: str | None):
    validar_site_api_key(chave)
    payload = payload or CancelamentoPayload()
    agora = datetime.now().isoformat(timespec="seconds")
    with conectar() as conn:
        retorno = cancelar_com_reposicao(conn, venda_id, payload.usuario, payload.observacao, agora)
        conn.commit()
    return {**retorno, "data_hora": agora}


@router.post("/clientes")
def criar_cliente_seguro(cliente: ClientePayload, x_mistica_api_key: str | None = Header(default=None)):
    validar_site_api_key(x_mistica_api_key)
    novo_id = executar(
        """
        INSERT INTO clientes (nome, telefone, cpf, endereco, nascimento, ativo)
        VALUES (?,?,?,?,?,1)
        """,
        (cliente.nome, cliente.telefone, cliente.cpf, cliente.endereco, cliente.nascimento),
    )
    return {"id": novo_id, "status": "criado"}


@router.post("/vendas/{venda_id}/status")
def status_venda(venda_id: int, payload: StatusPayload, x_mistica_api_key: str | None = Header(default=None)):
    return alterar_status(venda_id, payload, x_mistica_api_key)


@router.post("/vendas/{venda_id}/cancelar")
def cancelar_venda(venda_id: int, payload: CancelamentoPayload | None = None, x_mistica_api_key: str | None = Header(default=None)):
    return cancelar(venda_id, payload, x_mistica_api_key)


@router.post("/pedidos/{venda_id}/cancelar")
def cancelar_pedido(venda_id: int, payload: CancelamentoPayload | None = None, x_mistica_api_key: str | None = Header(default=None)):
    return cancelar(venda_id, payload, x_mistica_api_key)
