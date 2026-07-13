import hashlib
import os
import sqlite3
import time

import pytest

import database.backup as backup_mod
from database.backup import BackupInvalidoError, criar_backup_seguro


def _criar_banco_simples(caminho, wal=False):
    conn = sqlite3.connect(str(caminho))
    if wal:
        conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("CREATE TABLE pedidos (id INTEGER PRIMARY KEY, valor REAL)")
    conn.execute("INSERT INTO pedidos (valor) VALUES (10.5)")
    conn.commit()
    return conn


def test_backup_de_banco_simples(tmp_path):
    origem = tmp_path / "origem.db"
    _criar_banco_simples(origem).close()

    info = criar_backup_seguro(str(origem), str(tmp_path / "backups"), "teste")

    assert os.path.exists(info["caminho"])
    assert info["tamanho_bytes"] > 0
    assert info["nome"] == os.path.basename(info["caminho"])


def test_backup_consistente_com_banco_em_wal_e_conexao_aberta(tmp_path):
    origem = tmp_path / "origem_wal.db"
    conn = _criar_banco_simples(origem, wal=True)
    try:
        # A conexão de origem permanece aberta durante o backup, simulando
        # escrita concorrente ativa em modo WAL (o cenário que quebrava
        # shutil.copy2).
        info = criar_backup_seguro(str(origem), str(tmp_path / "backups"), "wal")
    finally:
        conn.close()

    dst = sqlite3.connect(info["caminho"])
    try:
        linhas = dst.execute("SELECT valor FROM pedidos").fetchall()
    finally:
        dst.close()
    assert linhas == [(10.5,)]


def test_escrita_recente_presente_no_snapshot(tmp_path):
    origem = tmp_path / "origem.db"
    conn = _criar_banco_simples(origem, wal=True)
    conn.execute("INSERT INTO pedidos (valor) VALUES (99.9)")
    conn.commit()
    try:
        info = criar_backup_seguro(str(origem), str(tmp_path / "backups"), "recente")
    finally:
        conn.close()

    dst = sqlite3.connect(info["caminho"])
    try:
        total = dst.execute("SELECT COUNT(*) FROM pedidos WHERE valor = 99.9").fetchone()[0]
    finally:
        dst.close()
    assert total == 1


def test_backup_abre_normalmente_e_integrity_check_ok(tmp_path):
    origem = tmp_path / "origem.db"
    _criar_banco_simples(origem).close()

    info = criar_backup_seguro(str(origem), str(tmp_path / "backups"), "teste")

    dst = sqlite3.connect(info["caminho"])
    try:
        resultado = dst.execute("PRAGMA integrity_check").fetchone()[0]
    finally:
        dst.close()
    assert str(resultado).strip().lower() == "ok"


def test_checksum_sha256_e_gerado_e_confere_com_o_arquivo(tmp_path):
    origem = tmp_path / "origem.db"
    _criar_banco_simples(origem).close()

    info = criar_backup_seguro(str(origem), str(tmp_path / "backups"), "teste")

    assert len(info["checksum_sha256"]) == 64
    digest = hashlib.sha256()
    with open(info["caminho"], "rb") as f:
        digest.update(f.read())
    assert digest.hexdigest() == info["checksum_sha256"]

    sidecar = f"{info['caminho']}.sha256"
    assert os.path.exists(sidecar)
    with open(sidecar, encoding="utf-8") as f:
        conteudo = f.read()
    assert info["checksum_sha256"] in conteudo
    # O sidecar não deve conter caminho absoluto, apenas o nome do arquivo.
    assert str(tmp_path) not in conteudo


def test_origem_e_destino_nao_podem_ser_o_mesmo_arquivo(tmp_path, monkeypatch):
    origem = tmp_path / "mesmo.db"
    _criar_banco_simples(origem).close()

    def _forcar_mesmo_caminho(destino_dir, prefixo, tag_extra, extensao):
        return origem.name, str(origem)

    monkeypatch.setattr(backup_mod, "_gerar_caminho_backup", _forcar_mesmo_caminho)

    with pytest.raises(ValueError):
        criar_backup_seguro(str(origem), str(tmp_path), "mesmo")

    # O arquivo de origem não pode ter sido apagado pela tentativa.
    assert origem.exists()


def test_falha_de_backup_nao_apaga_backups_antigos(tmp_path):
    destino_dir = tmp_path / "backups"
    destino_dir.mkdir()
    antigo = destino_dir / "teste_20200101_000000.db"
    antigo.write_bytes(b"conteudo antigo valido")

    origem_invalida = tmp_path / "nao_e_sqlite.db"
    origem_invalida.write_text("isto nao e um banco sqlite valido")

    with pytest.raises(Exception):
        criar_backup_seguro(str(origem_invalida), str(destino_dir), "teste")

    assert antigo.exists()
    assert antigo.read_bytes() == b"conteudo antigo valido"
    # Nenhum arquivo extra (o backup inválido recém-criado) deve ter sobrado.
    assert list(destino_dir.iterdir()) == [antigo]


def test_retencao_remove_somente_backups_reconhecidos(tmp_path, monkeypatch):
    monkeypatch.setattr(backup_mod, "BACKUP_DIR", str(tmp_path))

    reconhecido = tmp_path / "mistica_auto_20200101_000000.db"
    reconhecido.write_bytes(b"x")
    estranho = tmp_path / "arquivo_qualquer_do_usuario.db"
    estranho.write_bytes(b"x")

    tempo_antigo = time.time() - 40 * 24 * 3600
    os.utime(reconhecido, (tempo_antigo, tempo_antigo))
    os.utime(estranho, (tempo_antigo, tempo_antigo))

    backup_mod.limpar_backups_antigos()

    assert not reconhecido.exists()
    assert estranho.exists()


def test_backup_recem_criado_nao_e_removido_pela_retencao(tmp_path, monkeypatch):
    monkeypatch.setattr(backup_mod, "BACKUP_DIR", str(tmp_path))
    monkeypatch.setattr(backup_mod, "DB_PATH", str(tmp_path / "origem.db"))
    _criar_banco_simples(tmp_path / "origem.db").close()

    caminho = backup_mod.realizar_backup()

    assert caminho is not None
    assert os.path.exists(caminho)


def test_nomes_maliciosos_ou_traversal_sao_rejeitados(tmp_path):
    origem = tmp_path / "origem.db"
    _criar_banco_simples(origem).close()
    destino_dir = tmp_path / "backups"

    info = criar_backup_seguro(
        str(origem),
        str(destino_dir),
        prefixo="../../etc/passwd",
        tag_extra="../../../malicioso",
    )

    caminho_gerado = os.path.abspath(info["caminho"])
    destino_resolvido = os.path.abspath(str(destino_dir))
    assert caminho_gerado.startswith(destino_resolvido + os.sep)
    assert ".." not in info["nome"]
    assert "/" not in info["nome"] and "\\" not in info["nome"]


def test_restauracao_em_arquivo_separado_permite_consultar_dados(tmp_path):
    """A restauração é validada em arquivo separado, sem tocar no banco ativo."""
    origem_ativa = tmp_path / "banco_ativo.db"
    conn = _criar_banco_simples(origem_ativa, wal=True)
    conn.execute("INSERT INTO pedidos (valor) VALUES (42.0)")
    conn.commit()
    conn.close()

    info = criar_backup_seguro(str(origem_ativa), str(tmp_path / "backups"), "restauracao")

    # "Restaura" abrindo o backup em um caminho totalmente separado do banco
    # ativo — o arquivo ativo nunca é sobrescrito neste fluxo automatizado.
    destino_restauracao = tmp_path / "restaurado.db"
    restaurado_conn = sqlite3.connect(str(destino_restauracao))
    origem_backup_conn = sqlite3.connect(info["caminho"])
    try:
        origem_backup_conn.backup(restaurado_conn)
    finally:
        origem_backup_conn.close()
        restaurado_conn.close()

    verificacao = sqlite3.connect(str(destino_restauracao))
    try:
        valores = {row[0] for row in verificacao.execute("SELECT valor FROM pedidos")}
    finally:
        verificacao.close()
    assert valores == {10.5, 42.0}

    # O banco ativo original permanece intocado.
    ativa_conn = sqlite3.connect(str(origem_ativa))
    try:
        valores_ativa = {row[0] for row in ativa_conn.execute("SELECT valor FROM pedidos")}
    finally:
        ativa_conn.close()
    assert valores_ativa == {10.5, 42.0}
