"""Testes do módulo de vendas/caixa (services/venda_service.py e
services/caixa_service.py).

Cobre a lógica de cálculo de totais, pagamentos mistos e fechamento de caixa
hoje (em float), servindo de rede de segurança para a futura migração dessas
contas para Decimal (ver services/venda_service.py e caixa_service.py).
"""
import pytest

import database.connection as db_conn
import config
from services import venda_service
from services.venda_service import (
    calcular_total_venda,
    calcular_total_venda_misto,
    dinheiro_para_float,
    normalizar_forma_pagamento,
    normalizar_pagamentos_mistos,
    total_taxas_pagamentos_mistos,
    validar_pagamentos_mistos_fechados,
)
from services.caixa_service import normalizar_forma_caixa


# ---------------------------------------------------------------------------
# dinheiro_para_float: parsing de valores monetários digitados
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "bruto,esperado",
    [
        ("R$ 1.234,56", 1234.56),
        ("1234,56", 1234.56),
        ("1234.56", 1234.56),
        ("1.234", 1234.0),
        ("10", 10.0),
        ("-10,50", -10.5),
        ("", 0.0),
        (None, 0.0),
        (10, 10.0),
        (10.5, 10.5),
    ],
)
def test_dinheiro_para_float_formatos(bruto, esperado):
    assert dinheiro_para_float(bruto) == pytest.approx(esperado)


def test_dinheiro_para_float_entrada_invalida_nao_estoura():
    # entrada não numérica cai no fallback de dígitos; não deve lançar exceção
    assert dinheiro_para_float("abc") == 0.0


# ---------------------------------------------------------------------------
# normalizar_forma_pagamento / normalizar_forma_caixa: aliases
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "bruto,esperado",
    [
        ("dinheiro", "Dinheiro"),
        ("PIX", "Pix"),
        ("debito", "Debito"),
        ("Débito", "Debito"),
        ("credito 1x", "Credito 1x"),
        ("Crédito 2X", "Credito 2x"),
        ("crédito 3x", "Credito 3x"),
    ],
)
def test_normalizar_forma_pagamento(bruto, esperado):
    assert normalizar_forma_pagamento(bruto) == esperado
    assert normalizar_forma_caixa(bruto) == esperado


# ---------------------------------------------------------------------------
# calcular_total_venda: subtotal, desconto e taxa de cartão
# ---------------------------------------------------------------------------

def test_calcular_total_venda_dinheiro_sem_taxa():
    carrinho = [{"t": 50.0}, {"t": 30.0}]
    calculo = calcular_total_venda(carrinho, 0, "Dinheiro")
    assert calculo["s"] == pytest.approx(80.0)
    assert calculo["d"] == pytest.approx(0.0)
    assert calculo["tx"] == pytest.approx(0.0)
    assert calculo["tot"] == pytest.approx(80.0)


def test_calcular_total_venda_credito_3x_soma_taxa_fixa():
    carrinho = [{"t": 100.0}]
    calculo = calcular_total_venda(carrinho, 0, "Credito 3x")
    assert calculo["tx"] == pytest.approx(2.50)
    assert calculo["tot"] == pytest.approx(102.50)


def test_calcular_total_venda_desconto_percentual_aplica_sobre_subtotal():
    carrinho = [{"t": 200.0}]
    calculo = calcular_total_venda(carrinho, 10, "Dinheiro")
    assert calculo["s"] == pytest.approx(200.0)
    assert calculo["d"] == pytest.approx(20.0)
    assert calculo["tot"] == pytest.approx(180.0)


def test_calcular_total_venda_desconto_e_limitado_a_12_por_cento():
    carrinho = [{"t": 100.0}]
    calculo = calcular_total_venda(carrinho, 50, "Dinheiro")
    assert calculo["d"] == pytest.approx(12.0)
    assert calculo["tot"] == pytest.approx(88.0)


def test_calcular_total_venda_desconto_negativo_vira_zero():
    carrinho = [{"t": 100.0}]
    calculo = calcular_total_venda(carrinho, -5, "Dinheiro")
    assert calculo["d"] == pytest.approx(0.0)
    assert calculo["tot"] == pytest.approx(100.0)


def test_calcular_total_venda_soma_muitos_itens_pequenos_sem_desviar():
    """Regressão para o erro clássico de float: somar 0.10 trinta vezes deve
    fechar em 3.00 e não em algo como 2.9999999999999996."""
    carrinho = [{"t": 0.10} for _ in range(30)]
    calculo = calcular_total_venda(carrinho, 0, "Dinheiro")
    assert calculo["s"] == pytest.approx(3.0, abs=1e-9)


# ---------------------------------------------------------------------------
# Pagamentos mistos
# ---------------------------------------------------------------------------

def test_normalizar_pagamentos_mistos_ignora_valores_nao_positivos():
    pagamentos = [{"forma": "Dinheiro", "valor": 10}, {"forma": "Pix", "valor": 0}, {"forma": "Pix", "valor": -5}]
    normalizados = normalizar_pagamentos_mistos(pagamentos)
    assert normalizados == [{"forma": "Dinheiro", "valor": 10.0}]


def test_total_taxas_pagamentos_mistos_soma_taxas_por_forma():
    pagamentos = [{"forma": "Dinheiro", "valor": 50}, {"forma": "Credito 2x", "valor": 50}]
    assert total_taxas_pagamentos_mistos(pagamentos) == pytest.approx(2.0)


def test_validar_pagamentos_mistos_fechados_aceita_total_exato():
    calculo = {"s": 100.0, "d": 0.0}
    pagamentos = [{"forma": "Dinheiro", "valor": 60}, {"forma": "Pix", "valor": 40}]
    resultado = validar_pagamentos_mistos_fechados(calculo, pagamentos)
    assert {p["forma"] for p in resultado} == {"Dinheiro", "Pix"}


def test_validar_pagamentos_mistos_fechados_rejeita_valor_faltando():
    calculo = {"s": 100.0, "d": 0.0}
    pagamentos = [{"forma": "Dinheiro", "valor": 60}, {"forma": "Pix", "valor": 30}]
    with pytest.raises(ValueError, match="Falta receber"):
        validar_pagamentos_mistos_fechados(calculo, pagamentos)


def test_validar_pagamentos_mistos_fechados_rejeita_valor_excedente():
    calculo = {"s": 100.0, "d": 0.0}
    pagamentos = [{"forma": "Dinheiro", "valor": 60}, {"forma": "Pix", "valor": 50}]
    with pytest.raises(ValueError, match="excedente"):
        validar_pagamentos_mistos_fechados(calculo, pagamentos)


def test_validar_pagamentos_mistos_fechados_rejeita_lista_vazia():
    calculo = {"s": 100.0, "d": 0.0}
    with pytest.raises(ValueError, match="incompleto"):
        validar_pagamentos_mistos_fechados(calculo, [])


def test_validar_pagamentos_mistos_fechados_inclui_taxa_de_cartao_no_fechamento():
    # base 100, pago metade dinheiro + metade credito 1x (taxa fixa 1.50)
    calculo = {"s": 100.0, "d": 0.0}
    pagamentos = [{"forma": "Dinheiro", "valor": 50}, {"forma": "Credito 1x", "valor": 51.50}]
    resultado = validar_pagamentos_mistos_fechados(calculo, pagamentos)
    assert len(resultado) == 2


def test_calcular_total_venda_misto_relata_total_pago_e_taxa():
    carrinho = [{"t": 100.0}]
    pagamentos = [{"forma": "Dinheiro", "valor": 50}, {"forma": "Pix", "valor": 50}]
    calculo = calcular_total_venda_misto(carrinho, 0, pagamentos)
    assert calculo["base"] == pytest.approx(100.0)
    assert calculo["total_pago"] == pytest.approx(100.0)
    assert calculo["tx"] == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# Integração: venda real + caixa (usa banco temporário, como em smoke_test.py)
# ---------------------------------------------------------------------------

@pytest.fixture()
def banco_temporario(tmp_path, monkeypatch):
    db_path = str(tmp_path / "venda_caixa.db")
    monkeypatch.setattr(config, "DB_PATH", db_path)
    monkeypatch.setattr(db_conn, "DB_PATH", db_path)
    monkeypatch.setattr(venda_service, "_confirmar_venda_no_banco_central", lambda venda_id: (True, None))

    from database import init_db

    init_db()
    return db_path


def test_venda_mista_soma_corretamente_no_fechamento_de_caixa(banco_temporario):
    from database import query_db
    from services.caixa_service import abrir_caixa, resumo_fechamento_caixa, fechar_caixa_conferido
    from services.produto_service import cadastrar_produto_service
    from services.venda_service import registrar_venda_service

    query_db("INSERT INTO categorias (nome) VALUES (?)", ("Teste",), commit=True)
    codigo = cadastrar_produto_service(
        nome="Produto Misto",
        custo=5.0,
        lucro=100.0,
        preco=100.0,
        quantidade=10,
        estoque_minimo=2,
        categoria="Teste",
        usuario="Teste",
    )

    caixa_id = abrir_caixa(0.0, "Teste")

    carrinho = [{"id": codigo, "n": "Produto Misto", "q": 1, "p": 100.0, "t": 100.0}]
    calculo = calcular_total_venda(carrinho, 0, "Misto")
    pagamentos = [{"forma": "Dinheiro", "valor": 40}, {"forma": "Pix", "valor": 60}]
    registrar_venda_service(
        carrinho,
        "Consumidor Final",
        "01/01/2026 10:00",
        "2026-01-01 10:00:00",
        calculo,
        "Misto",
        "Teste",
        caixa_id,
        pagamentos_mistos=pagamentos,
    )

    resumo = resumo_fechamento_caixa()
    assert resumo["saldo"] == pytest.approx(100.0)
    assert resumo["formas"]["Dinheiro"] == pytest.approx(40.0)
    assert resumo["formas"]["Pix"] == pytest.approx(60.0)

    diferenca = fechar_caixa_conferido(
        caixa_id,
        resumo["saldo"],
        resumo["formas"],
        {"Dinheiro": 40.0, "Pix": 60.0, "Debito": 0.0, "Credito": 0.0},
    )
    assert diferenca == pytest.approx(0.0)


def test_fechar_caixa_conferido_detecta_diferenca_por_forma(banco_temporario):
    from services.caixa_service import abrir_caixa, lancar_fluxo, resumo_fechamento_caixa, fechar_caixa_conferido

    caixa_id = abrir_caixa(0.0, "Teste")
    lancar_fluxo("Entrada", "Venda avulsa", 100.0, caixa_id, forma_pagamento="Dinheiro")

    resumo = resumo_fechamento_caixa()
    # operador conta 5 reais a menos na gaveta do que o sistema espera
    diferenca = fechar_caixa_conferido(
        caixa_id,
        resumo["saldo"],
        resumo["formas"],
        {"Dinheiro": 95.0, "Pix": 0.0, "Debito": 0.0, "Credito": 0.0},
    )
    assert diferenca == pytest.approx(-5.0)


def test_resumo_fechamento_caixa_agrega_parcelas_de_credito(banco_temporario):
    from services.caixa_service import abrir_caixa, lancar_fluxo, resumo_fechamento_caixa

    caixa_id = abrir_caixa(0.0, "Teste")
    lancar_fluxo("Entrada", "Venda cartao", 30.0, caixa_id, forma_pagamento="Credito 1x")
    lancar_fluxo("Entrada", "Venda cartao", 20.0, caixa_id, forma_pagamento="Credito 2x")
    lancar_fluxo("Entrada", "Venda cartao", 10.0, caixa_id, forma_pagamento="Credito 3x")

    resumo = resumo_fechamento_caixa()
    assert resumo["formas"]["Credito"] == pytest.approx(60.0)
    assert resumo["formas_detalhadas"]["Credito 1x"] == pytest.approx(30.0)
    assert resumo["formas_detalhadas"]["Credito 2x"] == pytest.approx(20.0)
    assert resumo["formas_detalhadas"]["Credito 3x"] == pytest.approx(10.0)


def test_resumo_fechamento_caixa_muitos_lancamentos_pequenos_fecha_exato(banco_temporario):
    """Regressão específica para a migração a Decimal: 41 lançamentos de
    R$ 0,10 em dinheiro precisam fechar em exatamente R$ 4,10, sem sobra de
    ponto flutuante tipo 4.099999999999999."""
    from services.caixa_service import abrir_caixa, lancar_fluxo, resumo_fechamento_caixa

    caixa_id = abrir_caixa(0.0, "Teste")
    for _ in range(41):
        lancar_fluxo("Entrada", "Venda avulsa", 0.10, caixa_id, forma_pagamento="Dinheiro")

    resumo = resumo_fechamento_caixa()
    assert resumo["saldo"] == 4.10
    assert resumo["formas"]["Dinheiro"] == 4.10
