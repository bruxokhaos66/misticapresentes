from __future__ import annotations

import sqlite3


LIMITE_ENCOMENDA_PADRAO = 10
LIMITE_ENCOMENDA_MAXIMO = 100


def garantir_colunas_comerciais(conn: sqlite3.Connection) -> None:
    """Garante as colunas comerciais sem depender da ordem das migrações antigas.

    A função é idempotente e pode ser chamada antes de consultas, cadastro ou
    checkout. O backend passa a distinguir explicitamente produto de estoque
    normal de produto sob encomenda, sem inferir apenas por categoria ou selo.
    """
    colunas = {row[1] for row in conn.execute("PRAGMA table_info(produtos)").fetchall()}
    if "sob_encomenda" not in colunas:
        conn.execute("ALTER TABLE produtos ADD COLUMN sob_encomenda INTEGER NOT NULL DEFAULT 0")
    if "limite_encomenda" not in colunas:
        conn.execute(
            f"ALTER TABLE produtos ADD COLUMN limite_encomenda INTEGER NOT NULL DEFAULT {LIMITE_ENCOMENDA_PADRAO}"
        )


def normalizar_regra_encomenda(*, sob_encomenda: bool, limite_encomenda: int) -> tuple[int, int]:
    sob = 1 if sob_encomenda else 0
    limite = int(limite_encomenda or LIMITE_ENCOMENDA_PADRAO)
    if limite < 1 or limite > LIMITE_ENCOMENDA_MAXIMO:
        raise ValueError(
            f"Limite de encomenda deve estar entre 1 e {LIMITE_ENCOMENDA_MAXIMO}."
        )
    return sob, limite
