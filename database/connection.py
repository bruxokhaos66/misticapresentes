import sqlite3

from config import DB_PATH


def get_connection():
    """Abre uma conexao SQLite padronizada para transacoes."""
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.execute("PRAGMA synchronous = NORMAL")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def query_db(sql, params=(), commit=False):
    """Executa comandos SQL com fechamento seguro da conexão."""
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.execute("PRAGMA synchronous = NORMAL")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA foreign_keys = ON")
    cur = conn.cursor()
    try:
        cur.execute(sql, params)
        res = cur.fetchall()
        if commit:
            conn.commit()
        return res
    except Exception:
        if commit:
            conn.rollback()
        raise
    finally:
        conn.close()
