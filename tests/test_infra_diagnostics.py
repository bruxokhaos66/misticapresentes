"""Testes do módulo backend/infra_diagnostics.py (Fase 1 - PR 4).

Cobre os cenários de diagnóstico seguro de banco/disco usados por
/api/health (checagem leve, sem escrita) e /api/diagnostico/sistema
(checagem completa, com teste real de escrita), incluindo disco
indisponível, filesystem somente leitura e espaço insuficiente simulados.
Nunca toca no disco real além de arquivos temporários criados pelo próprio
teste (tmp_path).
"""

import os
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


# --- disco_diretorio_disponivel (checagem leve do /api/health) ---


def test_disco_diretorio_disponivel_true_em_pasta_gravavel(monkeypatch, tmp_path):
    pasta = tmp_path / "sub"
    pasta.mkdir()
    monkeypatch.setattr(infra_diagnostics, "DB_PATH", str(pasta / "diag.db"))
    assert infra_diagnostics.disco_diretorio_disponivel() is True


def test_disco_diretorio_disponivel_false_quando_pasta_nao_existe(monkeypatch, tmp_path):
    # A checagem leve nunca cria a pasta (isso ficaria a cargo do teste de
    # escrita completo, só usado no diagnóstico autenticado).
    monkeypatch.setattr(infra_diagnostics, "DB_PATH", str(tmp_path / "nao-existe" / "diag.db"))
    assert infra_diagnostics.disco_diretorio_disponivel() is False


def test_disco_diretorio_disponivel_nao_escreve_nada(monkeypatch, tmp_path):
    pasta = tmp_path / "sub"
    pasta.mkdir()
    monkeypatch.setattr(infra_diagnostics, "DB_PATH", str(pasta / "diag.db"))
    for _ in range(5):
        infra_diagnostics.disco_diretorio_disponivel()
    assert list(pasta.iterdir()) == []


def test_disco_diretorio_disponivel_false_sem_permissao_de_escrita(monkeypatch, tmp_path):
    pasta = tmp_path / "sub"
    pasta.mkdir()
    monkeypatch.setattr(infra_diagnostics, "DB_PATH", str(pasta / "diag.db"))
    monkeypatch.setattr(os, "access", lambda *a, **k: False)
    assert infra_diagnostics.disco_diretorio_disponivel() is False


# --- escrita_disco_segura (teste real, só usado no diagnóstico autenticado) ---


def test_escrita_disco_segura_ok_e_remove_o_arquivo(monkeypatch, tmp_path):
    pasta = tmp_path / "sub"
    monkeypatch.setattr(infra_diagnostics, "DB_PATH", str(pasta / "diag.db"))
    sucesso, motivo = infra_diagnostics.escrita_disco_segura()
    assert sucesso is True
    assert motivo == "ok"
    assert list(pasta.iterdir()) == []


def test_escrita_disco_segura_diretorio_inexistente_quando_mkdir_falha(monkeypatch, tmp_path):
    monkeypatch.setattr(infra_diagnostics, "DB_PATH", str(tmp_path / "sub" / "diag.db"))

    def _falha_mkdir(*args, **kwargs):
        raise OSError("disco indisponivel (simulado)")

    monkeypatch.setattr("pathlib.Path.mkdir", _falha_mkdir)
    sucesso, motivo = infra_diagnostics.escrita_disco_segura()
    assert sucesso is False
    assert motivo == "diretorio_inexistente"


def test_escrita_disco_segura_permissao_negada_quando_mkdir_nega(monkeypatch, tmp_path):
    monkeypatch.setattr(infra_diagnostics, "DB_PATH", str(tmp_path / "sub" / "diag.db"))

    def _permissao_negada(*args, **kwargs):
        raise PermissionError("permissao negada (simulado)")

    monkeypatch.setattr("pathlib.Path.mkdir", _permissao_negada)
    sucesso, motivo = infra_diagnostics.escrita_disco_segura()
    assert sucesso is False
    assert motivo == "permissao_negada"


def test_escrita_disco_segura_sem_espaco(monkeypatch, tmp_path):
    pasta = tmp_path / "sub"
    pasta.mkdir()
    monkeypatch.setattr(infra_diagnostics, "DB_PATH", str(pasta / "diag.db"))

    def _sem_espaco(*args, **kwargs):
        raise OSError(28, "No space left on device (simulado)")

    monkeypatch.setattr("tempfile.mkstemp", _sem_espaco)
    sucesso, motivo = infra_diagnostics.escrita_disco_segura()
    assert sucesso is False
    assert motivo == "sem_espaco"


def test_escrita_disco_segura_somente_leitura(monkeypatch, tmp_path):
    pasta = tmp_path / "sub"
    pasta.mkdir()
    monkeypatch.setattr(infra_diagnostics, "DB_PATH", str(pasta / "diag.db"))

    def _somente_leitura(*args, **kwargs):
        raise OSError(30, "Read-only file system (simulado)")

    monkeypatch.setattr("tempfile.mkstemp", _somente_leitura)
    sucesso, motivo = infra_diagnostics.escrita_disco_segura()
    assert sucesso is False
    assert motivo == "somente_leitura"


def test_escrita_disco_segura_falha_criacao_generica(monkeypatch, tmp_path):
    pasta = tmp_path / "sub"
    pasta.mkdir()
    monkeypatch.setattr(infra_diagnostics, "DB_PATH", str(pasta / "diag.db"))

    def _falha_generica(*args, **kwargs):
        raise OSError(5, "erro generico (simulado)")

    monkeypatch.setattr("tempfile.mkstemp", _falha_generica)
    sucesso, motivo = infra_diagnostics.escrita_disco_segura()
    assert sucesso is False
    assert motivo == "falha_criacao"


def test_escrita_disco_segura_falha_remocao_nao_deixa_arquivo_ilegivel(monkeypatch, tmp_path):
    pasta = tmp_path / "sub"
    monkeypatch.setattr(infra_diagnostics, "DB_PATH", str(pasta / "diag.db"))

    from pathlib import Path

    original_unlink = Path.unlink

    def _falha_unlink(self, *args, **kwargs):
        if self.name.startswith(".mistica_health_"):
            raise OSError("falha ao remover (simulado)")
        return original_unlink(self, *args, **kwargs)

    monkeypatch.setattr(Path, "unlink", _falha_unlink)
    sucesso, motivo = infra_diagnostics.escrita_disco_segura()
    assert sucesso is False
    assert motivo == "falha_remocao"


def test_escrita_disco_segura_nao_segue_symlink_para_fora(monkeypatch, tmp_path):
    dentro = tmp_path / "dentro"
    fora = tmp_path / "fora"
    dentro.mkdir()
    fora.mkdir()
    monkeypatch.setattr(infra_diagnostics, "DB_PATH", str(dentro / "diag.db"))

    # Mesmo se algo tentasse redirecionar a criação para fora da pasta
    # esperada, a checagem de `parents` detecta e recusa o resultado.
    import tempfile as tempfile_module

    real_mkstemp = tempfile_module.mkstemp

    def _mkstemp_fora(*args, **kwargs):
        return real_mkstemp(dir=str(fora), prefix=kwargs.get("prefix", ""))

    monkeypatch.setattr(tempfile_module, "mkstemp", _mkstemp_fora)
    sucesso, motivo = infra_diagnostics.escrita_disco_segura()
    assert sucesso is False
    assert motivo == "caminho_inesperado"
    # O arquivo criado fora não fica esquecido.
    assert list(fora.iterdir()) == []


# --- espaco_disco_bytes / classificação ---


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


def test_classificar_espaco_livre_usa_limiares_configuraveis(monkeypatch):
    monkeypatch.setattr(infra_diagnostics, "LIMIAR_CRITICO_PERCENT", 10.0)
    monkeypatch.setattr(infra_diagnostics, "LIMIAR_ATENCAO_PERCENT", 20.0)
    assert infra_diagnostics.classificar_espaco_livre(5.0) == "critico"
    assert infra_diagnostics.classificar_espaco_livre(15.0) == "atencao"
    assert infra_diagnostics.classificar_espaco_livre(50.0) == "saudavel"


def test_diagnostico_disco_completo_estrutura_e_classificacao(monkeypatch, tmp_path):
    pasta = tmp_path / "sub"
    monkeypatch.setattr(infra_diagnostics, "DB_PATH", str(pasta / "diag.db"))
    resultado = infra_diagnostics.diagnostico_disco_completo()
    assert resultado["acessivel"] is True
    assert resultado["escrita_ok"] is True
    assert resultado["escrita_motivo"] == "ok"
    assert resultado["classificacao"] in ("saudavel", "atencao", "critico")
    assert resultado["espaco_livre_percentual"] is not None
    assert resultado["espaco_total_bytes"] > 0


def test_diagnostico_disco_completo_pouco_espaco_simulado(monkeypatch, tmp_path):
    pasta = tmp_path / "sub"
    monkeypatch.setattr(infra_diagnostics, "DB_PATH", str(pasta / "diag.db"))
    monkeypatch.setattr(
        infra_diagnostics,
        "espaco_disco_bytes",
        lambda: {"livre_bytes": 1_000, "total_bytes": 100_000, "usado_bytes": 99_000},
    )
    resultado = infra_diagnostics.diagnostico_disco_completo()
    assert resultado["espaco_livre_percentual"] == 1.0
    assert resultado["classificacao"] == "critico"
