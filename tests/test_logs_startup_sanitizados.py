"""Confirma que os logs de inicialização (Fase 1 - PR 4) nunca vazam
caminhos absolutos, variáveis de ambiente, segredos ou stack trace -- só
status booleano, versão, ambiente e duração, nos níveis INFO/WARNING/ERROR
apropriados.
"""

import logging

import backend.main as main

PROIBIDOS = (
    "/data",
    "/var/data",
    "/mnt",
    "/home",
    "/opt/render",
    "documents",
    "mistica_gestao_v20.db",
    "traceback",
    "secret",
    "senha",
    "password",
    "token",
)


def _texto_completo_do_record(record: logging.LogRecord) -> str:
    partes = [record.getMessage()]
    for chave, valor in record.__dict__.items():
        if chave in logging.LogRecord("", 0, "", 0, "", (), None).__dict__:
            continue
        partes.append(f"{chave}={valor}")
    return " ".join(partes).lower()


def test_verificar_persistencia_banco_nao_loga_caminho(caplog):
    with caplog.at_level(logging.INFO, logger="backend.main"):
        main._verificar_persistencia_banco()

    registros = [r for r in caplog.records if r.name == "backend.main"]
    assert registros, "esperava pelo menos um log de startup_persistencia"
    for record in registros:
        assert not hasattr(record, "db_dir")
        assert not hasattr(record, "db_path")
        texto = _texto_completo_do_record(record)
        for proibido in PROIBIDOS:
            assert proibido not in texto, f"log vazou '{proibido}': {texto}"
        assert record.levelname in ("INFO", "WARNING", "ERROR")


def test_verificar_persistencia_banco_usa_warning_quando_efemero(monkeypatch, caplog):
    monkeypatch.delenv("MISTICA_DB_PATH", raising=False)
    monkeypatch.delenv("DATABASE_PATH", raising=False)
    with caplog.at_level(logging.INFO, logger="backend.main"):
        main._verificar_persistencia_banco()

    registros = [r for r in caplog.records if r.name == "backend.main"]
    assert any(r.levelname == "WARNING" and getattr(r, "persistente", None) is False for r in registros)


def test_log_startup_concluido_nao_vaza_dados_internos(monkeypatch, tmp_path, caplog):
    import database.connection as connection

    caminho = str(tmp_path / "startup.db")
    monkeypatch.setattr(connection, "DB_PATH", caminho)
    monkeypatch.setattr("backend.database.DB_PATH", caminho)
    monkeypatch.setattr("backend.infra_diagnostics.DB_PATH", caminho)

    with caplog.at_level(logging.INFO, logger="backend.main"):
        import asyncio

        async def _rodar():
            async with main.lifespan(main.app):
                pass

        asyncio.run(_rodar())

    registros = [r for r in caplog.records if r.name == "backend.main" and getattr(r, "evento", None) == "startup_concluido"]
    assert registros
    record = registros[0]
    assert record.levelname == "INFO"
    assert isinstance(record.duracao_ms, (int, float))
    assert record.duracao_ms >= 0
    assert isinstance(record.banco_ok, bool)
    assert isinstance(record.disco_ok, bool)
    texto = _texto_completo_do_record(record)
    for proibido in PROIBIDOS:
        assert proibido not in texto, f"log vazou '{proibido}': {texto}"
