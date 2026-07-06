from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Query

from backend.database import conectar

router = APIRouter(prefix="/api", tags=["auditoria-login"])


def garantir_tabela_login_auditoria(conn):
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS login_auditoria (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            login TEXT,
            sucesso INTEGER DEFAULT 0,
            motivo TEXT,
            ip TEXT,
            user_agent TEXT,
            data_hora TEXT
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_login_auditoria_data ON login_auditoria(data_hora)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_login_auditoria_login ON login_auditoria(login)")


@router.get("/auth/auditoria")
def listar_auditoria_login(limite: int = Query(50, ge=1, le=200)):
    with conectar() as conn:
        garantir_tabela_login_auditoria(conn)
        rows = conn.execute(
            """
            SELECT id, login, sucesso, motivo, ip, user_agent, data_hora
            FROM login_auditoria
            ORDER BY id DESC
            LIMIT ?
            """,
            (limite,),
        ).fetchall()

    return {
        "status": "ok",
        "auditoria": [dict(row) for row in rows],
        "total_exibido": len(rows),
        "data_hora": datetime.now().isoformat(timespec="seconds"),
    }


@router.get("/auth/auditoria/resumo")
def resumo_auditoria_login():
    with conectar() as conn:
        garantir_tabela_login_auditoria(conn)
        total = conn.execute("SELECT COUNT(*) AS total FROM login_auditoria").fetchone()["total"] or 0
        sucesso = conn.execute("SELECT COUNT(*) AS total FROM login_auditoria WHERE sucesso=1").fetchone()["total"] or 0
        falha = conn.execute("SELECT COUNT(*) AS total FROM login_auditoria WHERE sucesso=0").fetchone()["total"] or 0
        ultimo = conn.execute(
            """
            SELECT login, sucesso, motivo, data_hora
            FROM login_auditoria
            ORDER BY id DESC
            LIMIT 1
            """
        ).fetchone()

    return {
        "status": "ok",
        "total": int(total),
        "sucessos": int(sucesso),
        "falhas": int(falha),
        "ultimo_evento": dict(ultimo) if ultimo else None,
        "data_hora": datetime.now().isoformat(timespec="seconds"),
    }
