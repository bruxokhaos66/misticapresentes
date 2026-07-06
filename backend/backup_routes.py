from __future__ import annotations

import shutil
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query

from backend.database import conectar
from config import BACKUP_DIR, DB_PATH

router = APIRouter(prefix="/api", tags=["backup"])


@router.post("/backup/manual")
def criar_backup_manual():
    origem = Path(DB_PATH)
    destino_dir = Path(BACKUP_DIR)

    if not origem.exists():
        raise HTTPException(status_code=404, detail="Arquivo do banco de dados não encontrado")

    try:
        destino_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        destino = destino_dir / f"mistica_backup_{timestamp}.db"
        shutil.copy2(origem, destino)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Falha ao criar backup: {exc}") from exc

    return {
        "status": "ok",
        "mensagem": "Backup manual criado com sucesso.",
        "arquivo": str(destino),
        "tamanho_bytes": destino.stat().st_size,
        "data_hora": datetime.now().isoformat(timespec="seconds"),
    }


@router.get("/backup/status")
def status_backup_manual():
    origem = Path(DB_PATH)
    destino_dir = Path(BACKUP_DIR)
    backups = []

    if destino_dir.exists():
        arquivos = sorted(destino_dir.glob("mistica_backup_*.db"), key=lambda item: item.stat().st_mtime, reverse=True)
        for arquivo in arquivos[:10]:
            backups.append(
                {
                    "arquivo": str(arquivo),
                    "nome": arquivo.name,
                    "tamanho_bytes": arquivo.stat().st_size,
                    "modificado_em": datetime.fromtimestamp(arquivo.stat().st_mtime).isoformat(timespec="seconds"),
                }
            )

    return {
        "status": "ok",
        "banco_existe": origem.exists(),
        "backup_dir": str(destino_dir),
        "backup_dir_existe": destino_dir.exists(),
        "ultimos_backups": backups,
        "data_hora": datetime.now().isoformat(timespec="seconds"),
    }


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
