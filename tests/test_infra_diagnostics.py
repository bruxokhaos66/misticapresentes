"""Testes do módulo backend/infra_diagnostics.py (Fase 1 - PR 4).

Cobre os cenários de diagnóstico seguro de banco/disco usados por
/api/health, /api/version e /api/diagnostico/sistema, incluindo disco
indisponível e espaço insuficiente simulados (sem tocar em disco real além
de arquivos temporários criados pelo próprio teste).
"""

import shutil

import backend.database as backend_database
import backend.infra_diagnostics as infra_diagnostics
import database.connection as connection


def test_banco_acessivel_true_com_banco_valido(monkeypatch, tmp_path):
    caminho = str(tmp_path / "diag.db")
    monkeypatch.setattr(connection, "DB_PATH", caminho)
    monkeypatch.setattr(backend_database, "DB_PATH", caminho)
    monkeypatch.setattr(infra_diagnostics, "DB_PATH", caminho)
    assert infra_diagnostics.banco_acessivel() is True


def test_banco_acessivel_false_com_caminho_invalido(monkeypatch):
    # Pasta que não pode existir: caminho aponta para dentro de um arquivo comum.
    monkeypatch.setattr(backend_database, "DB_PATH", "/dev/null/impossivel/banco.db")
    assert infra_diagnostics.banco_acessivel() is False


def test_disco_acessivel_true_em_pasta_gravavel(monkeypatch, tmp_path):
    monkeypatch.setattr(infra_diagnostics, "DB_PATH", str(tmp_path / "sub" / "diag.db"))
    assert infra_diagnostics.disco_acessivel() is True
    # A verificação não deixa arquivo temporário para trás.
    assert list((tmp_path / "sub").iterdir()) == []


def test_disco_acessivel_false_quando_disco_indisponivel(monkeypatch, tmp_path):
    monkeypatch.setattr(infra_diagnostics, "DB_PATH", str(tmp_path / "sub" / "diag.db"))

    def _falha_mkdir(*args, **kwargs):
        raise OSError("disco indisponivel (simulado)")

    monkeypatch.setattr("pathlib.Path.mkdir", _falha_mkdir)
    assert infra_diagnostics.disco_acessivel() is False


def test_disco_acessivel_false_quando_escrita_falha_espaco_insuficiente(monkeypatch, tmp_path):
    pasta = tmp_path / "sub"
    pasta.mkdir()
    monkeypatch.setattr(infra_diagnostics, "DB_PATH", str(pasta / "diag.db"))

    def _sem_espaco(*args, **kwargs):
        raise OSError("No space left on device (simulado)")

    monkeypatch.setattr("tempfile.NamedTemporaryFile", _sem_espaco)
    assert infra_diagnostics.disco_acessivel() is False


def test_espaco_disco_bytes_retorna_numeros_validos(monkeypatch, tmp_path):
    monkeypatch.setattr(infra_diagnostics, "DB_PATH", str(tmp_path / "diag.db"))
    resultado = infra_diagnostics.espaco_disco_bytes()
    assert resultado is not None
    assert resultado["total_bytes"] > 0
    assert resultado["livre_bytes"] >= 0
    assert resultado["usado_bytes"] >= 0


def test_espaco_disco_bytes_retorna_none_em_falha(monkeypatch, tmp_path):
    monkeypatch.setattr(infra_diagnostics, "DB_PATH", str(tmp_path / "diag.db"))

    def _falha_disk_usage(*args, **kwargs):
        raise OSError("falha simulada")

    monkeypatch.setattr(shutil, "disk_usage", _falha_disk_usage)
    assert infra_diagnostics.espaco_disco_bytes() is None
