from __future__ import annotations

import importlib
import sqlite3
from datetime import datetime


# Importar a aplicação executa o bootstrap normal e instala a busca usada pelos
# pedidos já persistidos, exatamente como acontece em produção.
importlib.import_module("backend.main")

from backend import order_status_routes  # noqa: E402
from backend.order_product_lookup import buscar_produto_persistido_para_estoque  # noqa: E402


def criar_banco():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE produtos (
            id INTEGER PRIMARY KEY,
            codigo_p TEXT,
            nome TEXT NOT NULL,
            quantidade INTEGER NOT NULL,
            ativo INTEGER NOT NULL DEFAULT 1
        );
        CREATE TABLE pedidos (
            id INTEGER PRIMARY KEY,
            estoque_baixado INTEGER NOT NULL DEFAULT 0,
            estoque_baixado_em TEXT,
            estoque_reposto_cancelamento INTEGER NOT NULL DEFAULT 0,
            estoque_reposto_em TEXT
        );
        CREATE TABLE pedidos_itens (
            id INTEGER PRIMARY KEY,
            pedido_id INTEGER NOT NULL,
            codigo_p TEXT,
            nome_p TEXT,
            quantidade INTEGER NOT NULL,
            tipo_item TEXT NOT NULL
        );
        CREATE TABLE pedido_status_log (
            id INTEGER PRIMARY KEY,
            venda_id INTEGER NOT NULL,
            status TEXT,
            usuario TEXT,
            observacao TEXT,
            data_hora TEXT
        );
        INSERT INTO produtos (id, codigo_p, nome, quantidade, ativo)
        VALUES (1, 'PROD-1', 'Produto inativado', 7, 0);
        INSERT INTO pedidos (id, estoque_baixado, estoque_reposto_cancelamento)
        VALUES (10, 0, 0);
        INSERT INTO pedidos_itens (id, pedido_id, codigo_p, nome_p, quantidade, tipo_item)
        VALUES (100, 10, 'PROD-1', 'Produto inativado', 2, 'fisico');
        """
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


def test_produto_inativado_apos_criacao_do_pedido_ainda_tem_baixa_real(monkeypatch):
    conn = criar_banco()
    monkeypatch.setattr(order_status_routes, "registrar_auditoria", lambda *args, **kwargs: None)
    agora = datetime.now().isoformat(timespec="seconds")
    try:
        baixou = order_status_routes.baixar_estoque_do_pedido(conn, 10, "Teste", agora)
        conn.commit()

        produto = conn.execute("SELECT quantidade, ativo FROM produtos WHERE id=1").fetchone()
        pedido = conn.execute("SELECT estoque_baixado FROM pedidos WHERE id=10").fetchone()
        assert baixou is True
        assert produto["ativo"] == 0
        assert produto["quantidade"] == 5
        assert pedido["estoque_baixado"] == 1
    finally:
        conn.close()


def test_produto_inativado_apos_baixa_ainda_tem_reposicao_real(monkeypatch):
    conn = criar_banco()
    monkeypatch.setattr(order_status_routes, "registrar_auditoria", lambda *args, **kwargs: None)
    agora = datetime.now().isoformat(timespec="seconds")
    try:
        assert order_status_routes.baixar_estoque_do_pedido(conn, 10, "Teste", agora) is True
        assert order_status_routes.repor_estoque_cancelamento(conn, 10, "Teste", agora) is True
        conn.commit()

        produto = conn.execute("SELECT quantidade, ativo FROM produtos WHERE id=1").fetchone()
        pedido = conn.execute(
            "SELECT estoque_baixado, estoque_reposto_cancelamento FROM pedidos WHERE id=10"
        ).fetchone()
        assert produto["ativo"] == 0
        assert produto["quantidade"] == 7
        assert pedido["estoque_baixado"] == 1
        assert pedido["estoque_reposto_cancelamento"] == 1
        assert order_status_routes.repor_estoque_cancelamento(conn, 10, "Teste", agora) is False
        assert conn.execute("SELECT quantidade FROM produtos WHERE id=1").fetchone()["quantidade"] == 7
    finally:
        conn.close()
