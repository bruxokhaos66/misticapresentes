"""Auditoria de integridade referencial do banco SQLite.

Execute na raiz do projeto:
    python scripts/auditoria_integridade_referencial.py

Ativa `PRAGMA foreign_keys = ON` e executa `PRAGMA foreign_key_check` sobre
o banco configurado (`config.DB_PATH`), reportando registros orfaos ligados
as chaves estrangeiras hoje declaradas no schema (cursos/LMS e loja da nuvem).

Este script é somente leitura: nunca apaga, corrige ou altera dados. Serve
apenas para gerar o diagnóstico que uma futura migração de constraints deve
usar como base antes de reforçar o schema das tabelas de pedidos.
"""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from config import DB_PATH  # noqa: E402


def auditar(db_path: str | Path = DB_PATH) -> list[dict]:
    """Retorna a lista de violações encontradas por PRAGMA foreign_key_check.

    Cada item tem: tabela, rowid, tabela_referenciada, indice_da_fk.
    Lista vazia significa que não há violações.
    """
    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute("PRAGMA foreign_keys = ON")
        cur = conn.execute("PRAGMA foreign_key_check")
        colunas = [c[0] for c in cur.description]
        return [dict(zip(colunas, linha)) for linha in cur.fetchall()]
    finally:
        conn.close()


def main() -> int:
    if not Path(DB_PATH).exists():
        print(f"Banco nao encontrado em: {DB_PATH}")
        return 1

    violacoes = auditar(DB_PATH)
    if not violacoes:
        print("PRAGMA foreign_key_check: nenhuma violacao encontrada.")
        return 0

    print(f"PRAGMA foreign_key_check: {len(violacoes)} violacao(oes) encontrada(s):")
    for v in violacoes:
        print(f"  - tabela={v.get('table')} rowid={v.get('rowid')} referencia={v.get('parent')}")
    print("\nNenhum dado foi alterado. Revise os registros acima antes de qualquer migracao de schema.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
