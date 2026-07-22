import sqlite3
import threading
from contextlib import contextmanager

from config import DB_PATH

# Override thread-local do caminho do banco, usado só por
# `database.migrations.init_db(db_path=...)` (ver `usar_db_path` abaixo).
# É thread-local -- não um `DB_PATH` global reatribuído -- para que a
# migração feita por uma thread (ex.: a tarefa periódica de expiração de
# pedidos, chamada por `backend.database.conectar()`) nunca seja visível
# para `query_db`/`get_connection` chamados por QUALQUER outra thread
# (ex.: uma requisição HTTP concorrente, ou um teste que monkeypatcha
# `DB_PATH` só para a duração da própria função). Ver
# tests/test_persistencia_banco.py para o cenário de corrida que isso evita.
_thread_local = threading.local()


def _resolver_db_path() -> str:
    return getattr(_thread_local, "caminho", None) or DB_PATH


@contextmanager
def usar_db_path(caminho: str):
    """Faz `get_connection`/`query_db` usarem `caminho` em vez de `DB_PATH`,
    só para a duração do bloco e só na thread que o chamou -- nunca afeta o
    que outras threads veem (nem o próprio `DB_PATH` de módulo, que continua
    monkeypatchável por testes exatamente como antes)."""
    anterior = getattr(_thread_local, "caminho", None)
    _thread_local.caminho = caminho
    try:
        yield
    finally:
        if anterior is None:
            del _thread_local.caminho
        else:
            _thread_local.caminho = anterior


def get_connection():
    """Abre uma conexao SQLite padronizada para transacoes."""
    conn = sqlite3.connect(_resolver_db_path(), timeout=10)
    conn.execute("PRAGMA synchronous = NORMAL")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def query_db(sql, params=(), commit=False):
    """Executa comandos SQL com fechamento seguro da conexão."""
    conn = sqlite3.connect(_resolver_db_path(), timeout=10)
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
