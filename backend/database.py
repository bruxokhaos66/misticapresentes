import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterable

from config import DB_PATH
from database.migrations import init_db


@contextmanager
def conectar():
    # Resolve o caminho uma única vez e passa explicitamente para `init_db`
    # (em vez de deixá-lo ler o global `database.connection.DB_PATH`
    # ambiente): isso garante que a migração rode contra o MESMO arquivo
    # que a conexão abaixo vai abrir, mesmo que outro código concorrente no
    # processo (ex.: um teste monkeypatchando `database.connection.DB_PATH`
    # para seu próprio arquivo temporário) tenha alterado aquele global no
    # meio do caminho -- causa raiz do SIGBUS visto no CI do commit 46e020a,
    # onde a tarefa de fundo `_expirar_pedidos_periodicamente` (viva numa
    # thread de um `TestClient` nunca fechado em outro módulo de teste) lia
    # esse global exatamente enquanto um teste de persistência o apontava
    # para um arquivo que estava sendo removido/recriado.
    db_path = os.fspath(DB_PATH)
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    init_db(db_path)
    conn = sqlite3.connect(db_path, timeout=15)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA synchronous = NORMAL")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def listar(sql: str, params: Iterable[Any] = ()) -> list[dict[str, Any]]:
    with conectar() as conn:
        rows = conn.execute(sql, tuple(params)).fetchall()
        return [dict(row) for row in rows]


def obter(sql: str, params: Iterable[Any] = ()) -> dict[str, Any] | None:
    with conectar() as conn:
        row = conn.execute(sql, tuple(params)).fetchone()
        return dict(row) if row else None


def executar(sql: str, params: Iterable[Any] = ()) -> int:
    with conectar() as conn:
        cur = conn.execute(sql, tuple(params))
        return int(cur.lastrowid or 0)
