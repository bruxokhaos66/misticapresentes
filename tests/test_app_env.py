"""Testes de normalização/validação de APP_ENV (homologação operacional).

Confirma que o ambiente reportado no log de startup reflete de fato a
variável APP_ENV configurada no Render (produção), com normalização segura
de espaços/caixa, fallback local para 'development' e nenhum vazamento do
valor bruto de uma variável não reconhecida no log.
"""

import importlib
import logging

import backend.api_security as api_security
import backend.main as main


def test_app_env_producao_e_reconhecido():
    assert api_security._normalizar_ambiente("production") == "production"


def test_app_env_ausente_usa_fallback_development():
    assert api_security._normalizar_ambiente("development") == "development"


def test_app_env_normaliza_espacos_e_caixa():
    assert api_security._normalizar_ambiente("  Production  ") == "production"
    assert api_security._normalizar_ambiente("DEVELOPMENT") == "development"
    assert api_security._normalizar_ambiente("\tPRODUCTION\n") == "production"


def test_app_env_valor_invalido_usa_fallback_seguro():
    assert api_security._normalizar_ambiente("staging") == "development"
    assert api_security._normalizar_ambiente("prod") == "development"
    assert api_security._normalizar_ambiente("qualquer-coisa") == "development"


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


def test_app_env_vazio_nao_gera_warning(caplog):
    with caplog.at_level(logging.WARNING, logger="backend.api_security"):
        resultado = api_security._normalizar_ambiente("")
    assert resultado == "development"
    registros = [r for r in caplog.records if r.name == "backend.api_security"]
    assert not registros


def test_backend_main_usa_a_mesma_fonte_normalizada_do_app_env():
    # main.py não deve mais ler os.environ("APP_ENV") por conta própria: usa
    # a mesma constante normalizada/validada de backend.api_security.
    assert main.APP_ENV is api_security.APP_ENV
    assert main.APP_ENV in {"production", "development"}


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
