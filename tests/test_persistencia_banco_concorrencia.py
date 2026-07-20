"""Regressão de concorrência para o piso de estoque no SQLite.

O teste usa banco temporário, barreira de largada e dez conexões reais disputando
as últimas cinco unidades. A garantia esperada é que apenas cinco UPDATEs
consigam reivindicar uma unidade e que o saldo final nunca fique negativo.
"""

from __future__ import annotations

import sqlite3
import threading

import database.connection as connection
import database.migrations as migrations
from database.migrations import init_db


def test_decremento_concorrente_respeita_piso_zero(monkeypatch, tmp_path):
    caminho = str(tmp_path / "teste_piso_estoque.db")
    monkeypatch.setattr(connection, "DB_PATH", caminho)
    monkeypatch.setattr(migrations, "DOCS_PATH", str(tmp_path))
    init_db()

    connection.query_db(
        "INSERT INTO produtos (codigo_p, nome, preco, quantidade) VALUES (?,?,?,?)",
        ("COD-PISO", "Produto Últimas Unidades", 5.0, 5),
        commit=True,
    )

    total_threads = 10
    barreira = threading.Barrier(total_threads)
    resultados: list[int] = []
    erros: list[Exception] = []
    lock = threading.Lock()

    def disputar_unidade() -> None:
        conn = None
        try:
            conn = sqlite3.connect(caminho, timeout=15, isolation_level=None)
            conn.execute("PRAGMA journal_mode = WAL")
            barreira.wait(timeout=10)
            conn.execute("BEGIN IMMEDIATE")
            cur = conn.execute(
                """
                UPDATE produtos
                   SET quantidade = quantidade - 1
                 WHERE codigo_p = ?
                   AND COALESCE(quantidade, 0) > 0
                """,
                ("COD-PISO",),
            )
            conn.commit()
            with lock:
                resultados.append(cur.rowcount)
        except Exception as exc:  # pragma: no cover - preserva detalhe da falha
            if conn is not None:
                conn.rollback()
            with lock:
                erros.append(exc)
        finally:
            if conn is not None:
                conn.close()

    threads = [threading.Thread(target=disputar_unidade) for _ in range(total_threads)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=20)

    assert all(not thread.is_alive() for thread in threads), "Uma thread ficou bloqueada na disputa de estoque."
    assert not erros
    assert len(resultados) == total_threads
    assert sum(resultados) == 5
    assert resultados.count(1) == 5
    assert resultados.count(0) == 5

    saldo = connection.query_db(
        "SELECT quantidade FROM produtos WHERE codigo_p=?",
        ("COD-PISO",),
    )[0][0]
    assert saldo == 0
    assert saldo >= 0
