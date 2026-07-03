import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterable

from config import DB_PATH
from database.migrations import init_db


@contextmanager
def conectar():
    Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    init_db()
    conn = sqlite3.connect(DB_PATH, timeout=15)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA synchronous = NORMAL")
    conn.execute("PRAGMA journal_mode = WAL")
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
