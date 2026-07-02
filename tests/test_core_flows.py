import sqlite3
from datetime import datetime

import pytest

import database
from database import query_db
from services.caixa_service import abrir_caixa, marcar_conta_paga, salvar_conta
from services.produto_service import cadastrar_produto_service
from services.venda_service import calcular_total_venda, cancelar_venda_service, registrar_venda_service


@pytest.fixture()
def banco_limpo(tmp_path, monkeypatch):
    db_path = tmp_path / "mistica_teste.db"
    backup_dir = tmp_path / "backups"
    monkeypatch.setattr(database, "DB_PATH", str(db_path))
    monkeypatch.setattr(database, "BACKUP_DIR", str(backup_dir))
    database.init_db()
    return db_path


def test_init_db_cria_tabelas_obrigatorias(banco_limpo):
    conn = sqlite3.connect(banco_limpo)
    try:
        tabelas = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
    finally:
        conn.close()

    obrigatorias = {
        "usuarios",
        "login_tentativas",
        "logs",
        "categorias",
        "produtos",
        "clientes",
        "fornecedores",
        "vendas",
        "vendas_itens",
        "movimentacao_estoque",
        "inventario_estoque",
        "caixa_diario",
        "fluxo_caixa",
        "contas_a_pagar",
        "historico_precos",
        "isis_logs",
    }
    assert obrigatorias.issubset(tabelas)


def test_venda_baixa_estoque_e_cancelamento_devolve_estoque(banco_limpo):
    codigo = cadastrar_produto_service(
        nome="Incenso Teste",
        custo=2.0,
        lucro=100.0,
        preco=4.0,
        quantidade=10,
        estoque_minimo=2,
        categoria="Incensos",
        usuario="Teste",
    )
    caixa_id = abrir_caixa(100.0, "Teste")
    carrinho = [{"id": codigo, "n": "Incenso Teste", "q": 3, "p": 4.0, "t": 12.0}]
    calculo = calcular_total_venda(carrinho, 0, "Dinheiro")
    venda_id = registrar_venda_service(
        carrinho,
        "Consumidor Final",
        datetime.now().strftime("%d/%m/%Y %H:%M"),
        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        calculo,
        "Dinheiro",
        "Teste",
        caixa_id,
    )

    estoque_pos_venda = query_db("SELECT quantidade FROM produtos WHERE codigo_p=?", (codigo,))[0][0]
    assert estoque_pos_venda == 7

    cancelar_venda_service(venda_id, "Teste", caixa_id)
    estoque_pos_cancelamento = query_db("SELECT quantidade FROM produtos WHERE codigo_p=?", (codigo,))[0][0]
    status = query_db("SELECT status FROM vendas WHERE id=?", (venda_id,))[0][0]
    assert estoque_pos_cancelamento == 10
    assert status == "Cancelado"


def test_pagamento_de_conta_lanca_saida_no_fluxo(banco_limpo):
    caixa_id = abrir_caixa(200.0, "Teste")
    salvar_conta("Compra teste", 50.0, "10/07/2026", "Compras")
    conta_id = query_db("SELECT id FROM contas_a_pagar WHERE descricao=?", ("Compra teste",))[0][0]

    marcar_conta_paga(conta_id, caixa_id)

    status = query_db("SELECT status FROM contas_a_pagar WHERE id=?", (conta_id,))[0][0]
    fluxo = query_db("SELECT tipo, valor FROM fluxo_caixa WHERE caixa_id=? AND descricao LIKE ?", (caixa_id, "%Compra teste%"))
    assert status == "Pago"
    assert fluxo == [("Saida", 50.0)]


def test_debito_usa_taxa_percentual_de_1_5_porcento():
    carrinho = [{"t": 100.0}]
    calculo = calcular_total_venda(carrinho, 0, "Debito")
    assert calculo["tx"] == pytest.approx(1.5)
    assert calculo["tot"] == pytest.approx(101.5)
