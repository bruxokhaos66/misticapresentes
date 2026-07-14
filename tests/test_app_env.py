"""Testes de normalização/validação de APP_ENV (homologação operacional).

Confirma que o ambiente reportado no log de startup reflete de fato a
variável APP_ENV configurada no Render (produção), com normalização segura
de espaços/caixa, fallback local para 'development' e nenhum vazamento do
valor bruto de uma variável não reconhecida no log.
"""

import importlib
import logging

import pytest

import backend.api_security as api_security
import backend.main as main


@pytest.mark.parametrize(
    "valor_bruto",
    ["production", "Production", "PRODUCTION", " production", "production ", "  PrOdUcTiOn  ", "\tproduction\n"],
)
def test_app_env_variantes_de_producao_normalizam_para_production(valor_bruto):
    assert api_security._normalizar_ambiente(valor_bruto) == "production"


@pytest.mark.parametrize(
    "valor_bruto",
    ["development", "Development", "DEVELOPMENT", " development ", "\tDEVELOPMENT\n"],
)
def test_app_env_variantes_de_desenvolvimento_normalizam_para_development(valor_bruto):
    assert api_security._normalizar_ambiente(valor_bruto) == "development"


@pytest.mark.parametrize("valor_bruto", ["prod", "prd", "teste", "abc", ""])
def test_app_env_valores_invalidos_caem_no_fallback_seguro(valor_bruto, caplog):
    with caplog.at_level(logging.WARNING, logger="backend.api_security"):
        resultado = api_security._normalizar_ambiente(valor_bruto)

    assert resultado == "development"

    registros = [r for r in caplog.records if r.name == "backend.api_security"]
    assert registros, f"esperava WARNING para APP_ENV invalido: {valor_bruto!r}"
    for record in registros:
        assert record.levelname == "WARNING"
        texto = record.getMessage().lower()
        if valor_bruto:
            assert valor_bruto.lower() not in texto
        for chave, valor in record.__dict__.items():
            if chave in logging.LogRecord("", 0, "", 0, "", (), None).__dict__:
                continue
            if chave == "message":
                continue
            # Só o tamanho do valor bruto pode ser exposto -- nunca o
            # conteúdo, em nenhum campo estruturado extra do log.
            assert chave in {"evento", "tamanho_valor_bruto"}
            if valor_bruto:
                assert str(valor).lower() != valor_bruto.lower()


def test_app_env_invalido_loga_warning_sem_expor_valor_bruto(caplog):
    valor_sensivel = "valor-secreto-invalido-xyz"
    with caplog.at_level(logging.WARNING, logger="backend.api_security"):
        resultado = api_security._normalizar_ambiente(valor_sensivel)

    assert resultado == "development"
    registros = [r for r in caplog.records if r.name == "backend.api_security"]
    assert registros, "esperava um warning para APP_ENV invalido"
    for record in registros:
        assert record.levelname == "WARNING"
        texto = record.getMessage().lower()
        assert valor_sensivel not in texto
        for chave, valor in record.__dict__.items():
            if chave in logging.LogRecord("", 0, "", 0, "", (), None).__dict__:
                continue
            assert valor_sensivel not in str(valor).lower()


def test_app_env_genuinamente_ausente_nao_gera_warning(monkeypatch, caplog):
    # Variável nunca definida (caso local comum) é diferente de definida e
    # vazia: aqui não há nada para diagnosticar, então não deve haver warning.
    monkeypatch.delenv("APP_ENV", raising=False)
    with caplog.at_level(logging.WARNING, logger="backend.api_security"):
        try:
            modulo = importlib.reload(api_security)
            registros = [r for r in caplog.records if r.name == "backend.api_security"]
            assert modulo.APP_ENV == "development"
            assert not registros
        finally:
            importlib.reload(api_security)


def test_backend_main_usa_a_mesma_fonte_normalizada_do_app_env():
    # main.py não deve mais ler os.environ("APP_ENV") por conta própria: usa
    # a mesma constante normalizada/validada de backend.api_security.
    assert main.APP_ENV == api_security.APP_ENV
    assert main.APP_ENV in {"production", "development"}


def test_backend_main_nao_le_app_env_diretamente_do_os_environ():
    # Fonte única: nenhuma leitura paralela de os.environ para APP_ENV fora
    # de backend/api_security.py (backend web só -- api/main.py é a API
    # local/desktop, fora do escopo desta checagem).
    with open(main.__file__, encoding="utf-8") as arquivo:
        codigo = arquivo.read()
    assert 'os.environ.get("APP_ENV"' not in codigo
    assert "os.environ.get('APP_ENV'" not in codigo
    assert 'os.getenv("APP_ENV"' not in codigo


def test_app_env_producao_via_variavel_de_ambiente_real(monkeypatch):
    monkeypatch.setenv("APP_ENV", " Production ")
    try:
        modulo = importlib.reload(api_security)
        assert modulo.APP_ENV == "production"
        assert modulo.IS_PRODUCTION is True
    finally:
        monkeypatch.delenv("APP_ENV", raising=False)
        importlib.reload(api_security)


def test_app_env_ausente_via_variavel_de_ambiente_real(monkeypatch):
    monkeypatch.delenv("APP_ENV", raising=False)
    try:
        modulo = importlib.reload(api_security)
        assert modulo.APP_ENV == "development"
        assert modulo.IS_PRODUCTION is False
    finally:
        importlib.reload(api_security)
