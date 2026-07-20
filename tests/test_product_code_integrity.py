from __future__ import annotations

import importlib
import sqlite3

from fastapi import HTTPException


importlib.import_module("backend.main")

from backend import product_routes  # noqa: E402
from backend.product_code_integrity import (  # noqa: E402
    MENSAGEM_CODIGO_DUPLICADO,
    buscar_codigo_duplicado_incluindo_inativos,
    converter_erro_integridade_produto,
)


def criar_banco():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute(
        """
        CREATE TABLE produtos (
            id INTEGER PRIMARY KEY,
            codigo_p TEXT,
            nome TEXT NOT NULL,
            ativo INTEGER NOT NULL DEFAULT 1
        )
        """
    )
    conn.execute("CREATE UNIQUE INDEX idx_produtos_codigo_unico ON produtos(codigo_p)")
    conn.execute("INSERT INTO produtos (id, codigo_p, nome, ativo) VALUES (1, 'COD-1', 'Produto antigo', 0)")
    return conn


def test_bootstrap_instala_busca_que_inclui_produtos_inativos():
    assert product_routes._codigo_duplicado is buscar_codigo_duplicado_incluindo_inativos


def test_codigo_de_produto_inativo_continua_reservado():
    conn = criar_banco()
    try:
        encontrado = product_routes._codigo_duplicado(conn, " cod-1 ")
        assert encontrado is not None
        assert encontrado["id"] == 1
        assert encontrado["ativo"] == 0
    finally:
        conn.close()


def test_edicao_do_proprio_produto_pode_manter_o_codigo():
    conn = criar_banco()
    try:
        assert product_routes._codigo_duplicado(conn, "COD-1", excluir_id=1) is None
    finally:
        conn.close()


def test_integrity_error_de_codigo_vira_conflito_amigavel():
    erro = sqlite3.IntegrityError("UNIQUE constraint failed: produtos.codigo_p")
    traduzido = converter_erro_integridade_produto(erro)
    assert isinstance(traduzido, HTTPException)
    assert traduzido.status_code == 409
    assert traduzido.detail == MENSAGEM_CODIGO_DUPLICADO


def test_integrity_error_sem_relacao_com_codigo_nao_e_ocultado():
    erro = sqlite3.IntegrityError("FOREIGN KEY constraint failed")
    assert converter_erro_integridade_produto(erro) is None


def test_endpoints_de_criacao_e_edicao_recebem_protecao_de_corrida():
    endpoints = {
        rota.endpoint.__name__: rota.endpoint
        for rota in product_routes.router.routes
        if getattr(rota, "endpoint", None)
    }
    assert getattr(endpoints["criar_produto_completo"], "__mistica_codigo_integridade__", False)
    assert getattr(endpoints["atualizar_produto_completo"], "__mistica_codigo_integridade__", False)
