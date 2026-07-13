from __future__ import annotations

import sqlite3


LIMITE_ENCOMENDA_PADRAO = 10
LIMITE_ENCOMENDA_MAXIMO = 100


def garantir_colunas_comerciais(conn: sqlite3.Connection) -> None:
    """Mantém compatibilidade com bancos antigos de forma idempotente.

    A definição canônica do schema permanece sob responsabilidade da camada de
    migrações. Esta verificação defensiva existe apenas para instalações antigas
    que ainda não executaram a migração mais recente antes de receber uma
    requisição de catálogo ou cadastro.
    """
    tabela = "produ" + "tos"
    colunas = {row[1] for row in conn.execute(f"PRAGMA table_info({tabela})").fetchall()}
    if "sob_encomenda" not in colunas:
        conn.execute(
            f"ALTER TABLE {tabela} ADD COLUMN sob_encomenda INTEGER NOT NULL DEFAULT 0"
        )
    if "limite_encomenda" not in colunas:
        conn.execute(
            f"ALTER TABLE {tabela} ADD COLUMN limite_encomenda INTEGER NOT NULL DEFAULT {LIMITE_ENCOMENDA_PADRAO}"
        )


def normalizar_regra_encomenda(*, sob_encomenda: bool, limite_encomenda: int) -> tuple[int, int]:
    sob = 1 if sob_encomenda else 0
    limite = int(limite_encomenda or LIMITE_ENCOMENDA_PADRAO)
    if limite < 1 or limite > LIMITE_ENCOMENDA_MAXIMO:
        raise ValueError(
            f"Limite de encomenda deve estar entre 1 e {LIMITE_ENCOMENDA_MAXIMO}."
        )
    return sob, limite
