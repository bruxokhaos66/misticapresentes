"""Armazenamento simples do servidor dedicado.

A primeira versão usa SQLite persistente no servidor/cloud. Em produção maior,
pode ser trocado por PostgreSQL mantendo o mesmo contrato de API.
"""
from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = Path(os.getenv("MISTICA_CLOUD_DB", BASE_DIR / "mistica_cloud.db"))


def agora_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def conn():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(str(DB_PATH))
    c.row_factory = sqlite3.Row
    return c


def init_cloud_db():
    with conn() as c:
        c.execute(
            """
            CREATE TABLE IF NOT EXISTS lojas (
                id TEXT PRIMARY KEY,
                nome TEXT NOT NULL,
                token_hash TEXT NOT NULL,
                criado_em TEXT NOT NULL,
                atualizado_em TEXT NOT NULL
            )
            """
        )
        c.execute(
            """
            CREATE TABLE IF NOT EXISTS snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                loja_id TEXT NOT NULL,
                payload TEXT NOT NULL,
                recebido_em TEXT NOT NULL,
                origem TEXT,
                FOREIGN KEY(loja_id) REFERENCES lojas(id)
            )
            """
        )
        c.execute("CREATE INDEX IF NOT EXISTS idx_snapshots_loja_id ON snapshots(loja_id, id DESC)")
        c.commit()


def upsert_loja(loja_id: str, nome: str, token_hash: str):
    now = agora_iso()
    with conn() as c:
        c.execute(
            """
            INSERT INTO lojas (id, nome, token_hash, criado_em, atualizado_em)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                nome=excluded.nome,
                token_hash=excluded.token_hash,
                atualizado_em=excluded.atualizado_em
            """,
            (loja_id, nome, token_hash, now, now),
        )
        c.commit()


def get_loja(loja_id: str) -> dict[str, Any] | None:
    with conn() as c:
        row = c.execute("SELECT * FROM lojas WHERE id=?", (loja_id,)).fetchone()
        return dict(row) if row else None


def salvar_snapshot(loja_id: str, payload: dict[str, Any], origem: str = "sincronizador-local"):
    now = agora_iso()
    with conn() as c:
        c.execute(
            "INSERT INTO snapshots (loja_id, payload, recebido_em, origem) VALUES (?, ?, ?, ?)",
            (loja_id, json.dumps(payload, ensure_ascii=False), now, origem),
        )
        c.execute("UPDATE lojas SET atualizado_em=? WHERE id=?", (now, loja_id))
        c.commit()


def ultimo_snapshot(loja_id: str) -> dict[str, Any] | None:
    with conn() as c:
        row = c.execute(
            "SELECT payload, recebido_em, origem FROM snapshots WHERE loja_id=? ORDER BY id DESC LIMIT 1",
            (loja_id,),
        ).fetchone()
        if not row:
            return None
        payload = json.loads(row["payload"])
        payload["cloud_recebido_em"] = row["recebido_em"]
        payload["cloud_origem"] = row["origem"]
        return payload


def historico_snapshots(loja_id: str, limite: int = 20) -> list[dict[str, Any]]:
    limite = max(1, min(int(limite or 20), 100))
    with conn() as c:
        rows = c.execute(
            "SELECT payload, recebido_em, origem FROM snapshots WHERE loja_id=? ORDER BY id DESC LIMIT ?",
            (loja_id, limite),
        ).fetchall()
    saida = []
    for row in rows:
        payload = json.loads(row["payload"])
        saida.append({"recebido_em": row["recebido_em"], "origem": row["origem"], "dashboard": payload})
    return saida
