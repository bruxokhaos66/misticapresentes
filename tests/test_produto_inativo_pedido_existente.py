from __future__ import annotations

import importlib
import sqlite3


# Importar a aplicação executa o bootstrap normal e instala a busca usada pelos
# pedidos já persistidos, exatamente como acontece em produção.
importlib.import_module("backend.main")

from backend import order_status_routes  # noqa: E402
from backend.order_product_lookup import buscar_produto_persistido_para_estoque  # noqa: E402


def criar_banco():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute(
        """
        CREATE TABLE produtos (
            id INTEGER PRIMARY KEY,
            codigo_p TEXT,
            nome TEXT NOT NULL,
            quantidade INTEGER NOT NULL,
            ativo INTEGER NOT NULL DEFAULT 1
        )
        """
    )
    conn.execute(
        "INSERT INTO produtos (id, codigo_p, nome, quantidade, ativo) VALUES (1, 'PROD-1', 'Produto inativado', 7, 0)"
    )
    return conn


def test_bootstrap_instala_busca_exclusiva_para_pedido_persistido():
    assert order_status_routes.buscar_produto_para_baixa is buscar_produto_persistido_para_estoque


def test_produto_inativo_e_localizado_por_codigo_para_baixa_ou_reposicao():
    conn = criar_banco()
    try:
        produto = order_status_routes.buscar_produto_para_baixa(
            conn,
            {"codigo_p": "PROD-1", "nome_p": "Produto inativado"},
        )
        assert produto is not None
        assert produto["id"] == 1
        assert produto["quantidade"] == 7
        assert produto["ativo"] if "ativo" in produto.keys() else True
    finally:
        conn.close()


def test_produto_inativo_e_localizado_por_id_legado():
    conn = criar_banco()
    try:
        produto = order_status_routes.buscar_produto_para_baixa(
            conn,
            {"codigo_p": "1", "nome_p": ""},
        )
        assert produto is not None
        assert produto["codigo_p"] == "PROD-1"
    finally:
        conn.close()


def test_produto_inativo_e_localizado_por_nome_apenas_como_fallback_legado():
    conn = criar_banco()
    try:
        produto = order_status_routes.buscar_produto_para_baixa(
            conn,
            {"codigo_p": "", "nome_p": " produto INATIVADO "},
        )
        assert produto is not None
        assert produto["id"] == 1
    finally:
        conn.close()


def test_produto_inexistente_continua_nao_sendo_inventado():
    conn = criar_banco()
    try:
        produto = order_status_routes.buscar_produto_para_baixa(
            conn,
            {"codigo_p": "NAO-EXISTE", "nome_p": "Produto inexistente"},
        )
        assert produto is None
    finally:
        conn.close()
