from __future__ import annotations

import os
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Header, HTTPException, Query
from pydantic import BaseModel, Field

from backend.database import conectar

router = APIRouter(prefix="/api", tags=["pedidos-status"])

STATUS_PEDIDO = {
    "Aguardando pagamento",
    "Pagamento confirmado",
    "Separando pedido",
    "Pronto para retirada",
    "Entregue",
    "Cancelado",
    "Concluído",
}

STATUS_BAIXA_ESTOQUE = {"Pagamento confirmado", "Separando pedido"}


class PedidoStatusIn(BaseModel):
    status: str = Field(min_length=1)
    usuario: str = "Admin"
    observacao: Optional[str] = None


class PedidoObservacaoIn(BaseModel):
    observacao: str = ""
    usuario: str = "Admin"


def validar_site_api_key(chave_recebida: str | None):
    chave = os.environ.get("MISTICA_SITE_API_KEY", "").strip()
    if not chave:
        print("[API] Aviso: MISTICA_SITE_API_KEY não configurada. Status de pedido em modo desenvolvimento.")
        return
    if chave_recebida != chave:
        raise HTTPException(status_code=403, detail="Chave da API do site inválida.")


def garantir_tabela_status(conn):
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS pedido_status_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            venda_id INTEGER NOT NULL,
            status TEXT NOT NULL,
            usuario TEXT DEFAULT 'Admin',
            observacao TEXT DEFAULT '',
            data_hora TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    alteracoes = [
        "ALTER TABLE vendas ADD COLUMN observacao_pedido TEXT",
        "ALTER TABLE vendas ADD COLUMN estoque_baixado INTEGER DEFAULT 0",
        "ALTER TABLE vendas ADD COLUMN estoque_baixado_em TEXT",
    ]
    for sql in alteracoes:
        try:
            conn.execute(sql)
        except Exception:
            pass


def venda_para_pedido(conn, venda):
    itens = conn.execute(
        """
        SELECT id, venda_id, codigo_p, nome_p, quantidade, custo_unitario, valor_unitario, valor_total
        FROM vendas_itens
        WHERE venda_id=?
        ORDER BY id ASC
        """,
        (venda["id"],),
    ).fetchall()
    historico = conn.execute(
        """
        SELECT id, venda_id, status, usuario, observacao, data_hora
        FROM pedido_status_log
        WHERE venda_id=?
        ORDER BY id DESC
        """,
        (venda["id"],),
    ).fetchall()
    data = dict(venda)
    data["itens"] = [dict(row) for row in itens]
    data["historico_status"] = [dict(row) for row in historico]
    return data


def buscar_produto_para_baixa(conn, item):
    codigo = str(item["codigo_p"] or "").strip()
    nome = str(item["nome_p"] or "").strip()

    if codigo:
        produto = conn.execute(
            "SELECT id, codigo_p, nome, quantidade FROM produtos WHERE codigo_p=? AND COALESCE(ativo,1)=1",
            (codigo,),
        ).fetchone()
        if produto:
            return produto

        if codigo.isdigit():
            produto = conn.execute(
                "SELECT id, codigo_p, nome, quantidade FROM produtos WHERE id=? AND COALESCE(ativo,1)=1",
                (int(codigo),),
            ).fetchone()
            if produto:
                return produto

    if nome:
        produto = conn.execute(
            "SELECT id, codigo_p, nome, quantidade FROM produtos WHERE lower(trim(nome))=lower(trim(?)) AND COALESCE(ativo,1)=1",
            (nome,),
        ).fetchone()
        if produto:
            return produto

    return None


def baixar_estoque_do_pedido(conn, venda_id: int, usuario: str, agora: str):
    venda = conn.execute("SELECT id, estoque_baixado FROM vendas WHERE id=?", (venda_id,)).fetchone()
    if not venda:
        raise HTTPException(status_code=404, detail="Pedido não encontrado")
    if int(venda["estoque_baixado"] or 0) == 1:
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
    if not itens:
        return False

    for item in itens:
        quantidade = int(item["quantidade"] or 0)
        if quantidade <= 0:
            continue
        produto = buscar_produto_para_baixa(conn, item)
        if not produto:
            raise HTTPException(status_code=404, detail=f"Produto não encontrado para baixa: {item['nome_p'] or item['codigo_p']}")
        estoque_atual = int(produto["quantidade"] or 0)
        if estoque_atual < quantidade:
            raise HTTPException(status_code=409, detail=f"Estoque insuficiente para {produto['nome']}. Disponível: {estoque_atual}")

    for item in itens:
        quantidade = int(item["quantidade"] or 0)
        if quantidade <= 0:
            continue
        produto = buscar_produto_para_baixa(conn, item)
        conn.execute("UPDATE produtos SET quantidade = quantidade - ? WHERE id=?", (quantidade, produto["id"]))

    conn.execute("UPDATE vendas SET estoque_baixado=1, estoque_baixado_em=? WHERE id=?", (agora, venda_id))
    conn.execute(
        """
        INSERT INTO pedido_status_log (venda_id, status, usuario, observacao, data_hora)
        VALUES (?,?,?,?,?)
        """,
        (venda_id, "Estoque baixado", usuario or "Admin", "Baixa automática ao confirmar/separar pedido", agora),
    )
    return True


@router.get("/pedidos")
def listar_pedidos(status: str = "", limite: int = Query(100, ge=1, le=500)):
    with conectar() as conn:
        garantir_tabela_status(conn)
        if status:
            rows = conn.execute(
                """
                SELECT id, cliente, data_venda, subtotal, desconto, taxa, total_final,
                       forma_pagamento, vendedor, status, data_iso, dia_operacional,
                       origem_sync, local_id, observacao_pedido, estoque_baixado, estoque_baixado_em
                FROM vendas
                WHERE COALESCE(status,'')=?
                ORDER BY id DESC
                LIMIT ?
                """,
                (status, limite),
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT id, cliente, data_venda, subtotal, desconto, taxa, total_final,
                       forma_pagamento, vendedor, status, data_iso, dia_operacional,
                       origem_sync, local_id, observacao_pedido, estoque_baixado, estoque_baixado_em
                FROM vendas
                ORDER BY id DESC
                LIMIT ?
                """,
                (limite,),
            ).fetchall()
        return [venda_para_pedido(conn, row) for row in rows]


@router.get("/pedidos/{venda_id}")
def obter_pedido(venda_id: int):
    with conectar() as conn:
        garantir_tabela_status(conn)
        venda = conn.execute(
            """
            SELECT id, cliente, data_venda, subtotal, desconto, taxa, total_final,
                   forma_pagamento, vendedor, status, data_iso, dia_operacional,
                   origem_sync, local_id, observacao_pedido, estoque_baixado, estoque_baixado_em
            FROM vendas
            WHERE id=?
            """,
            (venda_id,),
        ).fetchone()
        if not venda:
            raise HTTPException(status_code=404, detail="Pedido não encontrado")
        return venda_para_pedido(conn, venda)


@router.get("/pedidos/{venda_id}/status")
def historico_status_pedido(venda_id: int):
    with conectar() as conn:
        garantir_tabela_status(conn)
        venda = conn.execute("SELECT id, status, estoque_baixado, estoque_baixado_em FROM vendas WHERE id=?", (venda_id,)).fetchone()
        if not venda:
            raise HTTPException(status_code=404, detail="Pedido não encontrado")
        historico = conn.execute(
            """
            SELECT id, venda_id, status, usuario, observacao, data_hora
            FROM pedido_status_log
            WHERE venda_id=?
            ORDER BY id DESC
            """,
            (venda_id,),
        ).fetchall()
    return {
        "ok": True,
        "venda_id": venda_id,
        "status_atual": venda["status"],
        "estoque_baixado": bool(venda["estoque_baixado"]),
        "estoque_baixado_em": venda["estoque_baixado_em"],
        "historico": [dict(row) for row in historico],
    }


@router.post("/pedidos/{venda_id}/status")
def atualizar_status_pedido(venda_id: int, payload: PedidoStatusIn, x_mistica_api_key: str | None = Header(default=None)):
    validar_site_api_key(x_mistica_api_key)
    status = payload.status.strip()
    if status not in STATUS_PEDIDO:
        raise HTTPException(status_code=400, detail="Status de pedido inválido")

    agora = datetime.now().isoformat(timespec="seconds")
    estoque_baixado_agora = False
    with conectar() as conn:
        garantir_tabela_status(conn)
        venda = conn.execute("SELECT id FROM vendas WHERE id=?", (venda_id,)).fetchone()
        if not venda:
            raise HTTPException(status_code=404, detail="Pedido não encontrado")

        if status in STATUS_BAIXA_ESTOQUE:
            estoque_baixado_agora = baixar_estoque_do_pedido(conn, venda_id, payload.usuario or "Admin", agora)

        conn.execute("UPDATE vendas SET status=? WHERE id=?", (status, venda_id))
        observacao = payload.observacao or ""
        if estoque_baixado_agora:
            observacao = (observacao + " | " if observacao else "") + "Estoque baixado automaticamente"
        conn.execute(
            """
            INSERT INTO pedido_status_log (venda_id, status, usuario, observacao, data_hora)
            VALUES (?,?,?,?,?)
            """,
            (venda_id, status, payload.usuario or "Admin", observacao, agora),
        )
        conn.commit()

    return {
        "ok": True,
        "venda_id": venda_id,
        "status": status,
        "estoque_baixado_agora": estoque_baixado_agora,
        "data_hora": agora,
    }


@router.post("/pedidos/{venda_id}/observacao")
def atualizar_observacao_pedido(venda_id: int, payload: PedidoObservacaoIn, x_mistica_api_key: str | None = Header(default=None)):
    validar_site_api_key(x_mistica_api_key)
    agora = datetime.now().isoformat(timespec="seconds")
    with conectar() as conn:
        garantir_tabela_status(conn)
        venda = conn.execute("SELECT id, status FROM vendas WHERE id=?", (venda_id,)).fetchone()
        if not venda:
            raise HTTPException(status_code=404, detail="Pedido não encontrado")
        conn.execute("UPDATE vendas SET observacao_pedido=? WHERE id=?", (payload.observacao or "", venda_id))
        conn.execute(
            """
            INSERT INTO pedido_status_log (venda_id, status, usuario, observacao, data_hora)
            VALUES (?,?,?,?,?)
            """,
            (venda_id, venda["status"], payload.usuario or "Admin", "Observação atualizada", agora),
        )
        conn.commit()
    return {"ok": True, "venda_id": venda_id, "observacao": payload.observacao or ""}


@router.delete("/pedidos/{venda_id}")
def cancelar_pedido(venda_id: int, x_mistica_api_key: str | None = Header(default=None)):
    validar_site_api_key(x_mistica_api_key)
    agora = datetime.now().isoformat(timespec="seconds")
    with conectar() as conn:
        garantir_tabela_status(conn)
        venda = conn.execute("SELECT id FROM vendas WHERE id=?", (venda_id,)).fetchone()
        if not venda:
            raise HTTPException(status_code=404, detail="Pedido não encontrado")
        conn.execute("UPDATE vendas SET status='Cancelado' WHERE id=?", (venda_id,))
        conn.execute(
            """
            INSERT INTO pedido_status_log (venda_id, status, usuario, observacao, data_hora)
            VALUES (?,?,?,?,?)
            """,
            (venda_id, "Cancelado", "Admin", "Pedido cancelado pelo painel", agora),
        )
        conn.commit()
    return {"ok": True, "venda_id": venda_id, "status": "Cancelado"}


@router.get("/pedidos/status-log")
def listar_status_pedidos(limite: int = 100):
    limite = max(1, min(limite, 500))
    with conectar() as conn:
        garantir_tabela_status(conn)
        rows = conn.execute(
            """
            SELECT l.id, l.venda_id, v.cliente, v.total_final, l.status, l.usuario, l.observacao, l.data_hora
            FROM pedido_status_log l
            LEFT JOIN vendas v ON v.id = l.venda_id
            ORDER BY l.id DESC
            LIMIT ?
            """,
            (limite,),
        ).fetchall()
    return [dict(row) for row in rows]
