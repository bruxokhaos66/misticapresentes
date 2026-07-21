"""Testes unitários da função de domínio centralizada de frete
(backend/frete.py) — Fase 3."""

from backend.frete import calcular_frete, normalizar_texto, normalizar_uf


def test_retirada_e_sempre_zero():
    assert calcular_frete("retirada", "Qualquer Cidade", "PR") == 0.0
    assert calcular_frete("retirada", None, None) == 0.0


def test_entrega_pinhalzinho_sc_e_zero():
    assert calcular_frete("entrega", "Pinhalzinho", "SC") == 0.0


def test_entrega_outra_cidade_sc_e_30():
    assert calcular_frete("entrega", "Chapecó", "SC") == 30.0


def test_entrega_fora_de_sc_e_50():
    assert calcular_frete("entrega", "Curitiba", "PR") == 50.0
    assert calcular_frete("entrega", "Pinhalzinho", "PR") == 50.0


def test_frete_gratis_zera_qualquer_entrega():
    assert calcular_frete("entrega", "Curitiba", "PR", frete_gratis=True) == 0.0
    assert calcular_frete("entrega", "Chapecó", "SC", frete_gratis=True) == 0.0


def test_normalizacao_ignora_acento_caixa_e_espacos():
    variações = ["Pinhalzinho", "pinhalzinho", " PINHALZINHO ", "Pínhálzinho", "PinhalZinho  "]
    for cidade in variações:
        assert calcular_frete("entrega", cidade, "sc") == 0.0, cidade
        assert calcular_frete("entrega", cidade, " Sc ") == 0.0, cidade


def test_forma_recebimento_desconhecida_nao_e_tratada_como_entrega():
    assert calcular_frete(None, "Curitiba", "PR") == 0.0
    assert calcular_frete("qualquer-coisa", "Curitiba", "PR") == 0.0


def test_normalizar_texto_e_normalizar_uf():
    assert normalizar_texto("  São   Paulo ") == "sao paulo"
    assert normalizar_uf(" sc ") == "SC"
