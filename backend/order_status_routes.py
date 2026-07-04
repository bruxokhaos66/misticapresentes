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
    try:
        conn.execute("ALTER TABLE vendas ADD COLUMN observacao_pedido TEXT")
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


@router.get("/pedidos")
def listar_pedidos(status: str = "", limite: int = Query(100, ge=1, le=500)):
    with conectar() as conn:
        garantir_tabela_status(conn)
        if status:
            rows = conn.execute(
                """
                SELECT id, cliente, data_venda, subtotal, desconto, taxa, total_final,
                       forma_pagamento, vendedor, status, data_iso, dia_operacional,
                       origem_sync, local_id, observacao_pedido
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
                       origem_sync, local_id, observacao_pedido
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
                   origem_sync, local_id, observacao_pedido
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
        venda = conn.execute("SELECT id, status FROM vendas WHERE id=?", (venda_id,)).fetchone()
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
        "historico": [dict(row) for row in historico],
    }


@router.post("/pedidos/{venda_id}/status")
def atualizar_status_pedido(venda_id: int, payload: PedidoStatusIn, x_mistica_api_key: str | None = Header(default=None)):
    validar_site_api_key(x_mistica_api_key)
    status = payload.status.strip()
    if status not in STATUS_PEDIDO:
        raise HTTPException(status_code=400, detail="Status de pedido inválido")

    agora = datetime.now().isoformat(timespec="seconds")
    with conectar() as conn:
        garantir_tabela_status(conn)
        venda = conn.execute("SELECT id FROM vendas WHERE id=?", (venda_id,)).fetchone()
        if not venda:
            raise HTTPException(status_code=404, detail="Pedido não encontrado")

        conn.execute("UPDATE vendas SET status=? WHERE id=?", (status, venda_id))
        conn.execute(
            """
            INSERT INTO pedido_status_log (venda_id, status, usuario, observacao, data_hora)
            VALUES (?,?,?,?,?)
            """,
            (venda_id, status, payload.usuario or "Admin", payload.observacao or "", agora),
        )
        conn.commit()

    return {
        "ok": True,
        "venda_id": venda_id,
        "status": status,
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
