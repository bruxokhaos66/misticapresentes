"""Testes unitários de services/pagamento_misto_service.py::extrair_pagamentos_mistos
(Fase A — PR #331, revisão do parser de pagamento misto).

Cobrem o formato produzido por services/venda_service.py::resumo_pagamentos_mistos
para cada forma de pagamento suportada (Dinheiro, Pix, Debito, Credito Nx, com e
sem sufixo de taxa), casos com mais de uma parcela em cartão, formatação
numérica brasileira (vírgula decimal, separador de milhar), espaços extras,
formato legado/inválido e as invariantes de segurança do parser: nunca confundir
taxa com valor pago, nunca descartar parcela silenciosamente, nunca aceitar
valor negativo, nunca duplicar formas.
"""

from services.pagamento_misto_service import extrair_pagamentos_mistos, eh_pagamento_misto


def test_forma_unica_dinheiro():
    assert extrair_pagamentos_mistos("Misto: Dinheiro R$ 40,00") == [{"forma": "Dinheiro", "valor": 40.0}]


def test_forma_unica_pix():
    assert extrair_pagamentos_mistos("Misto: Pix R$ 60,00") == [{"forma": "Pix", "valor": 60.0}]


def test_debito_sem_taxa_no_texto():
    assert extrair_pagamentos_mistos("Misto: Debito R$ 61,50") == [{"forma": "Debito", "valor": 61.5}]


def test_credito_a_vista_1x():
    assert extrair_pagamentos_mistos("Misto: Credito 1x R$ 61,50") == [{"forma": "Credito 1x", "valor": 61.5}]


def test_credito_parcelado_varias_parcelas_com_taxa_no_sufixo():
    # resumo_pagamentos_mistos grava "(inclui taxa R$ Y,YY)" -- um SEGUNDO
    # "R$" que é só informativo; o valor pago é o do PRIMEIRO "R$".
    texto = "Misto: Dinheiro R$ 40,00 + Credito 3x R$ 62,50 (inclui taxa R$ 2,50)"
    pagamentos = extrair_pagamentos_mistos(texto)
    assert pagamentos == [
        {"forma": "Dinheiro", "valor": 40.0},
        {"forma": "Credito 3x", "valor": 62.5},
    ]
    # A taxa (2,50) nunca pode ser confundida com o valor pago (62,50).
    valores = [p["valor"] for p in pagamentos]
    assert 2.5 not in valores


def test_debito_e_credito_simultaneos_na_mesma_venda():
    """Mais de uma parcela em cartão na mesma venda: nenhuma pode ser
    descartada silenciosamente (bug original corrigido nesta fase)."""
    texto = "Misto: Debito R$ 30,00 (inclui taxa R$ 1,50) + Credito 3x R$ 62,50 (inclui taxa R$ 2,50)"
    pagamentos = extrair_pagamentos_mistos(texto)
    assert len(pagamentos) == 2
    assert {"forma": "Debito", "valor": 30.0} in pagamentos
    assert {"forma": "Credito 3x", "valor": 62.5} in pagamentos


def test_forma_sem_taxa_e_forma_com_taxa_juntas():
    texto = "Misto: Pix R$ 20,00 + Debito R$ 31,50 (inclui taxa R$ 1,50)"
    pagamentos = extrair_pagamentos_mistos(texto)
    assert pagamentos == [
        {"forma": "Pix", "valor": 20.0},
        {"forma": "Debito", "valor": 31.5},
    ]


def test_valor_com_separador_de_milhar_acima_de_mil():
    texto = "Misto: Dinheiro R$ 1.234,56 + Pix R$ 100,00"
    pagamentos = extrair_pagamentos_mistos(texto)
    assert pagamentos == [
        {"forma": "Dinheiro", "valor": 1234.56},
        {"forma": "Pix", "valor": 100.0},
    ]


def test_espacos_extras_e_formatacao_irregular():
    texto = "misto:   Dinheiro   R$   40,00   +   Pix R$60,00  "
    pagamentos = extrair_pagamentos_mistos(texto)
    assert pagamentos == [
        {"forma": "Dinheiro", "valor": 40.0},
        {"forma": "Pix", "valor": 60.0},
    ]


def test_case_insensitive_no_prefixo_misto():
    assert extrair_pagamentos_mistos("MISTO: Pix R$ 10,00") == [{"forma": "Pix", "valor": 10.0}]


def test_nao_misto_retorna_lista_vazia():
    assert extrair_pagamentos_mistos("Dinheiro") == []
    assert extrair_pagamentos_mistos("Pix") == []
    assert extrair_pagamentos_mistos("Credito 2x") == []


def test_vazio_ou_none_retorna_lista_vazia():
    assert extrair_pagamentos_mistos("") == []
    assert extrair_pagamentos_mistos(None) == []


def test_formato_invalido_sem_valores_utilizaveis_retorna_vazio_mas_e_detectavel():
    """O parser em si retorna [] para texto sem "R$" (comportamento de baixo
    nível) — mas cancelar_venda_service (services/venda_service.py) hoje
    detecta esse caso via eh_pagamento_misto(...) and not pagamentos e levanta
    ValueError em vez de seguir silenciosamente; ver
    tests/test_estorno_caixa_atomico.py::
    test_estorno_de_venda_mista_com_forma_ilegivel_falha_de_forma_observavel."""
    assert extrair_pagamentos_mistos("Misto: texto corrompido sem valores") == []
    assert eh_pagamento_misto("Misto: texto corrompido sem valores") is True


def test_valor_negativo_nunca_e_aceito():
    # "-R$" não é um formato produzido pelo sistema, mas o parser não pode
    # aceitar valor <= 0 mesmo que apareça num registro corrompido.
    pagamentos = extrair_pagamentos_mistos("Misto: Dinheiro R$ -40,00 + Pix R$ 60,00")
    valores = [p["valor"] for p in pagamentos]
    assert all(v > 0 for v in valores)
    # A parcela negativa é descartada (valor <= 0 nunca é incluído) — não
    # silenciosamente convertida em positiva nem duplicada.
    assert pagamentos == [{"forma": "Pix", "valor": 60.0}]


def test_valor_zero_nunca_e_aceito():
    pagamentos = extrair_pagamentos_mistos("Misto: Dinheiro R$ 0,00 + Pix R$ 60,00")
    assert pagamentos == [{"forma": "Pix", "valor": 60.0}]


def test_nao_duplica_formas_quando_string_tem_forma_repetida():
    """O parser não deduplica por design (cada parcela do split é um
    lançamento independente) -- confirma que duas parcelas na MESMA forma são
    mantidas como duas entradas distintas (não coalescidas nem duplicadas
    além do que está no texto)."""
    texto = "Misto: Dinheiro R$ 20,00 + Dinheiro R$ 20,00"
    pagamentos = extrair_pagamentos_mistos(texto)
    assert len(pagamentos) == 2
    assert all(p == {"forma": "Dinheiro", "valor": 20.0} for p in pagamentos)


def test_formato_legado_sem_prefixo_misto_nao_e_tratado_como_misto():
    """Formatos legados encontrados em vendas antigas (ex.: apenas
    "Dinheiro/Pix" texto livre, sem o prefixo "Misto:") não devem ser
    interpretados como pagamento misto -- eh_pagamento_misto e
    extrair_pagamentos_mistos concordam em tratá-los como forma única."""
    assert eh_pagamento_misto("Dinheiro/Pix") is False
    assert extrair_pagamentos_mistos("Dinheiro/Pix") == []
