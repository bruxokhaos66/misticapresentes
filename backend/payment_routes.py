from __future__ import annotations

import os
import secrets
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Header, HTTPException, Query
from pydantic import BaseModel, Field

from backend.database import conectar
from backend.order_status_routes import baixar_estoque_do_pedido, garantir_tabela_status

router = APIRouter(prefix="/api", tags=["pagamentos"])

STATUS_PAGAMENTO = {"Aguardando", "Confirmado", "Recusado", "Cancelado", "Estornado"}


class PagamentoIn(BaseModel):
    venda_id: int = Field(gt=0)
    forma: str = "Pix"
    valor: float = Field(ge=0)
    status: str = "Confirmado"
    comprovante: Optional[str] = None
    observacao: Optional[str] = None
    usuario: str = "Admin"


class PagamentoStatusIn(BaseModel):
    status: str = Field(min_length=1)
    observacao: Optional[str] = None
    usuario: str = "Admin"


def validar_site_api_key(chave_recebida: str | None):
    chave = os.environ.get("MISTICA_SITE_API_KEY", "").strip() or os.environ.get("MISTICA_SYNC_KEY", "").strip()
    if not chave:
        raise HTTPException(status_code=503, detail="Configure MISTICA_SITE_API_KEY ou MISTICA_SYNC_KEY para permitir escrita pela API.")
    if not chave_recebida or not secrets.compare_digest(str(chave_recebida), chave):
        raise HTTPException(status_code=403, detail="Chave da API inválida.")


def garantir_tabela_pagamentos(conn):
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS pagamentos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            venda_id INTEGER NOT NULL,
            forma TEXT DEFAULT 'Pix',
            valor REAL DEFAULT 0,
            status TEXT DEFAULT 'Aguardando',
            comprovante TEXT DEFAULT '',
            observacao TEXT DEFAULT '',
            usuario TEXT DEFAULT 'Admin',
            data_hora TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """
    )


def registrar_log_status(conn, venda_id: int, status: str, usuario: str, observacao: str):
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
    conn.execute(
        """
        INSERT INTO pedido_status_log (venda_id, status, usuario, observacao, data_hora)
        VALUES (?,?,?,?,?)
        """,
        (venda_id, status, usuario or "Admin", observacao or "", datetime.now().isoformat(timespec="seconds")),
    )


@router.post("/pagamentos")
def registrar_pagamento(payload: PagamentoIn, x_mistica_api_key: str | None = Header(default=None)):
    validar_site_api_key(x_mistica_api_key)
    status = payload.status.strip()
    if status not in STATUS_PAGAMENTO:
        raise HTTPException(status_code=400, detail="Status de pagamento inválido")

    agora = datetime.now().isoformat(timespec="seconds")
    with conectar() as conn:
        garantir_tabela_pagamentos(conn)
        venda = conn.execute("SELECT id, total_final FROM vendas WHERE id=?", (payload.venda_id,)).fetchone()
        if not venda:
            raise HTTPException(status_code=404, detail="Pedido não encontrado")
        cur = conn.execute(
            """
            INSERT INTO pagamentos (venda_id, forma, valor, status, comprovante, observacao, usuario, data_hora)
            VALUES (?,?,?,?,?,?,?,?)
            """,
            (
                payload.venda_id,
                payload.forma or "Pix",
                payload.valor,
                status,
                payload.comprovante or "",
                payload.observacao or "",
                payload.usuario or "Admin",
                agora,
            ),
        )
        pagamento_id = int(cur.lastrowid)
        if status == "Confirmado":
            garantir_tabela_status(conn)
            baixar_estoque_do_pedido(conn, payload.venda_id, payload.usuario or "Admin", agora, "Baixa automática ao confirmar pagamento")
            conn.execute("UPDATE vendas SET status='Pagamento confirmado' WHERE id=?", (payload.venda_id,))
            registrar_log_status(conn, payload.venda_id, "Pagamento confirmado", payload.usuario, "Pagamento confirmado manualmente")
        conn.commit()

    return {"ok": True, "id": pagamento_id, "venda_id": payload.venda_id, "status": status, "data_hora": agora}


@router.get("/pagamentos")
def listar_pagamentos(venda_id: Optional[int] = None, limite: int = Query(100, ge=1, le=500)):
    with conectar() as conn:
        garantir_tabela_pagamentos(conn)
        if venda_id:
            rows = conn.execute(
                """
                SELECT p.*, v.cliente, v.total_final
                FROM pagamentos p
                LEFT JOIN vendas v ON v.id = p.venda_id
                WHERE p.venda_id=?
                ORDER BY p.id DESC
                LIMIT ?
                """,
                (venda_id, limite),
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT p.*, v.cliente, v.total_final
                FROM pagamentos p
                LEFT JOIN vendas v ON v.id = p.venda_id
                ORDER BY p.id DESC
                LIMIT ?
                """,
                (limite,),
            ).fetchall()
    return [dict(row) for row in rows]


@router.put("/pagamentos/{pagamento_id}/status")
def atualizar_status_pagamento(pagamento_id: int, payload: PagamentoStatusIn, x_mistica_api_key: str | None = Header(default=None)):
    validar_site_api_key(x_mistica_api_key)
    status = payload.status.strip()
    if status not in STATUS_PAGAMENTO:
        raise HTTPException(status_code=400, detail="Status de pagamento inválido")

    with conectar() as conn:
        garantir_tabela_pagamentos(conn)
        pagamento = conn.execute("SELECT id, venda_id FROM pagamentos WHERE id=?", (pagamento_id,)).fetchone()
        if not pagamento:
            raise HTTPException(status_code=404, detail="Pagamento não encontrado")
        conn.execute(
            "UPDATE pagamentos SET status=?, observacao=? WHERE id=?",
            (status, payload.observacao or "", pagamento_id),
        )
        if status == "Confirmado":
            garantir_tabela_status(conn)
            agora = datetime.now().isoformat(timespec="seconds")
            baixar_estoque_do_pedido(conn, pagamento["venda_id"], payload.usuario or "Admin", agora, "Baixa automática ao confirmar pagamento")
            conn.execute("UPDATE vendas SET status='Pagamento confirmado' WHERE id=?", (pagamento["venda_id"],))
            registrar_log_status(conn, pagamento["venda_id"], "Pagamento confirmado", payload.usuario, payload.observacao or "Pagamento confirmado")
        conn.commit()
    return {"ok": True, "id": pagamento_id, "status": status}
