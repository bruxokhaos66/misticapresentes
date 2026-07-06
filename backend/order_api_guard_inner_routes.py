from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field

from backend.database import conectar, executar
from backend.order_status_routes import garantir_tabela_status, validar_site_api_key, baixar_estoque_do_pedido, buscar_produto_para_baixa

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


class ProdutoPayload(BaseModel):
    codigo_p: Optional[str] = None
    nome: str = Field(min_length=1)
    preco: float = 0.0
    quantidade: int = 0
    categoria: Optional[str] = None
    custo: float = 0.0
    lucro: float = 0.0
    estoque_minimo: int = 0


class ClientePayload(BaseModel):
    nome: str = Field(min_length=1)
    telefone: Optional[str] = None
    cpf: Optional[str] = None
    endereco: Optional[str] = None
    nascimento: Optional[str] = None


class VendaItemPayload(BaseModel):
    produto_id: Optional[int] = None
    codigo_p: Optional[str] = None
    nome_p: Optional[str] = None
    quantidade: int = 0
    custo_unitario: float = 0.0
    valor_unitario: float = 0.0
    valor_total: float = 0.0


class VendaPayload(BaseModel):
    origem: Optional[str] = "api"
    local_id: Optional[int] = None
    cliente: Optional[str] = "Cliente não informado"
    subtotal: float = 0.0
    desconto: float = 0.0
    taxa: float = 0.0
    total_final: float = 0.0
    forma_pagamento: Optional[str] = None
    vendedor: Optional[str] = None
    status: Optional[str] = "Concluído"
    data_venda: Optional[str] = None
    data_iso: Optional[str] = None
    dia_operacional: Optional[str] = None
    baixa_estoque: bool = False
    itens: list[VendaItemPayload] = Field(default_factory=list)


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


def buscar_produto_venda(conn, item):
    if item.produto_id:
        produto = conn.execute(
            "SELECT id, codigo_p, nome, quantidade FROM produtos WHERE id=? AND COALESCE(ativo,1)=1",
            (item.produto_id,),
        ).fetchone()
        if produto:
            return produto
    if item.codigo_p:
        produto = conn.execute(
            "SELECT id, codigo_p, nome, quantidade FROM produtos WHERE codigo_p=? AND COALESCE(ativo,1)=1",
            (item.codigo_p,),
        ).fetchone()
        if produto:
            return produto
    return None


def baixar_estoque_venda_site(conn, itens: list[VendaItemPayload]):
    for item in itens:
        produto = buscar_produto_venda(conn, item)
        if not produto:
            raise HTTPException(status_code=404, detail=f"Produto não encontrado: {item.codigo_p or item.nome_p}")
        quantidade = int(item.quantidade or 0)
        if int(produto["quantidade"] or 0) < quantidade:
            raise HTTPException(status_code=409, detail=f"Estoque insuficiente para {produto['nome']}. Disponível: {produto['quantidade']}")
    for item in itens:
        produto = buscar_produto_venda(conn, item)
        conn.execute("UPDATE produtos SET quantidade = quantidade - ? WHERE id=?", (int(item.quantidade or 0), produto["id"]))


def salvar_venda_site(venda: VendaPayload):
    agora = datetime.now()
    data_venda = venda.data_venda or agora.strftime("%d/%m/%Y %H:%M:%S")
    data_iso = venda.data_iso or agora.isoformat(timespec="seconds")
    dia_operacional = venda.dia_operacional or agora.strftime("%d/%m/%Y")
    with conectar() as conn:
        for sql in [
            "ALTER TABLE vendas ADD COLUMN origem_sync TEXT",
            "ALTER TABLE vendas ADD COLUMN local_id INTEGER",
            "CREATE INDEX IF NOT EXISTS idx_vendas_local_id ON vendas(local_id)",
        ]:
            try:
                conn.execute(sql)
            except Exception:
                pass
        if venda.baixa_estoque:
            baixar_estoque_venda_site(conn, venda.itens)
        cur = conn.execute(
            """
            INSERT INTO vendas (
                cliente, data_venda, subtotal, desconto, taxa, total_final,
                forma_pagamento, vendedor, status, data_iso, dia_operacional,
                origem_sync, local_id
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                venda.cliente,
                data_venda,
                venda.subtotal,
                venda.desconto,
                venda.taxa,
                venda.total_final,
                venda.forma_pagamento,
                venda.vendedor,
                venda.status or "Concluído",
                data_iso,
                dia_operacional,
                "api",
                venda.local_id,
            ),
        )
        venda_id = int(cur.lastrowid)
        for item in venda.itens:
            conn.execute(
                """
                INSERT INTO vendas_itens
                (venda_id, codigo_p, nome_p, quantidade, custo_unitario, valor_unitario, valor_total)
                VALUES (?,?,?,?,?,?,?)
                """,
                (
                    venda_id,
                    item.codigo_p,
                    item.nome_p,
                    int(item.quantidade or 0),
                    item.custo_unitario,
                    item.valor_unitario,
                    item.valor_total,
                ),
            )
    return {"id": venda_id, "local_id": venda.local_id, "status": "criado", "estoque_baixado": venda.baixa_estoque}


def repor_estoque_cancelamento(conn, venda_id: int, usuario: str, agora: str):
    venda = conn.execute("SELECT id, estoque_baixado, estoque_reposto_cancelamento FROM vendas WHERE id=?", (venda_id,)).fetchone()
    if not venda:
        raise HTTPException(status_code=404, detail="Pedido não encontrado.")
    if int(venda["estoque_baixado"] or 0) != 1:
        return False
    if int(venda["estoque_reposto_cancelamento"] or 0) == 1:
        return False

    itens = conn.execute("SELECT id, codigo_p, nome_p, quantidade FROM vendas_itens WHERE venda_id=? ORDER BY id ASC", (venda_id,)).fetchall()
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

    conn.execute("UPDATE vendas SET estoque_reposto_cancelamento=1, estoque_reposto_em=? WHERE id=?", (agora, venda_id))
    conn.execute(
        "INSERT INTO pedido_status_log (venda_id, status, usuario, observacao, data_hora) VALUES (?,?,?,?,?)",
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
        "INSERT INTO pedido_status_log (venda_id, status, usuario, observacao, data_hora) VALUES (?,?,?,?,?)",
        (venda_id, "Cancelado", usuario or "Site/API", observacao or ("Cancelado pela API segura" if not ja_cancelado else "Já estava cancelado; estoque não reposto novamente"), agora),
    )
    return {"ok": True, "venda_id": venda_id, "status": "Cancelado", "estoque_reposto_agora": estoque_reposto, "ja_cancelado": ja_cancelado}


def alterar_status(venda_id: int, payload: StatusPayload, chave: str | None):
    validar_site_api_key(chave)
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


@router.post("/produtos")
def criar_produto_seguro(produto: ProdutoPayload, x_mistica_api_key: str | None = Header(default=None)):
    validar_site_api_key(x_mistica_api_key)
    novo_id = executar(
        """
        INSERT INTO produtos (codigo_p, nome, preco, quantidade, categoria, custo, lucro, estoque_minimo, ativo)
        VALUES (?,?,?,?,?,?,?,?,1)
        """,
        (produto.codigo_p, produto.nome, produto.preco, produto.quantidade, produto.categoria, produto.custo, produto.lucro, produto.estoque_minimo),
    )
    return {"id": novo_id, "status": "criado"}


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


@router.post("/vendas")
def criar_venda_segura(venda: VendaPayload, x_mistica_api_key: str | None = Header(default=None)):
    validar_site_api_key(x_mistica_api_key)
    return salvar_venda_site(venda)


@router.post("/vendas/{venda_id}/status")
def status_venda(venda_id: int, payload: StatusPayload, x_mistica_api_key: str | None = Header(default=None)):
    return alterar_status(venda_id, payload, x_mistica_api_key)


@router.post("/vendas/{venda_id}/cancelar")
def cancelar_venda(venda_id: int, payload: CancelamentoPayload | None = None, x_mistica_api_key: str | None = Header(default=None)):
    return cancelar(venda_id, payload, x_mistica_api_key)


@router.post("/pedidos/{venda_id}/cancelar")
def cancelar_pedido(venda_id: int, payload: CancelamentoPayload | None = None, x_mistica_api_key: str | None = Header(default=None)):
    return cancelar(venda_id, payload, x_mistica_api_key)
