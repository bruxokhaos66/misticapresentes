import sqlite3

import services.backup_service as backup_service


def _criar_banco_simples(caminho):
    conn = sqlite3.connect(str(caminho))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("CREATE TABLE clientes (id INTEGER PRIMARY KEY, nome TEXT)")
    conn.execute("INSERT INTO clientes (nome) VALUES ('Cliente Teste')")
    conn.commit()
    conn.close()


def test_criar_backup_local_usa_backup_seguro_e_produz_arquivo_valido(tmp_path, monkeypatch):
    banco = tmp_path / "mistica_presentes.db"
    _criar_banco_simples(banco)

    destino_dir = tmp_path / "backups"
    status_path = tmp_path / "ultimo_backup.json"

    monkeypatch.setattr(backup_service, "BACKUP_DIR", destino_dir)
    monkeypatch.setattr(backup_service, "STATUS_PATH", status_path)
    monkeypatch.setattr(backup_service, "encontrar_bancos", lambda: [banco])

    dados = backup_service.criar_backup_local("teste_desktop")

    assert dados["ok"] is True
    assert len(dados["arquivos"]) == 1
    caminho_backup = dados["arquivos"][0]

    conn = sqlite3.connect(caminho_backup)
    try:
        resultado = conn.execute("PRAGMA integrity_check").fetchone()[0]
        total = conn.execute("SELECT COUNT(*) FROM clientes").fetchone()[0]
    finally:
        conn.close()
    assert str(resultado).strip().lower() == "ok"
    assert total == 1


def test_criar_backup_local_sem_banco_encontrado_nao_falha(tmp_path, monkeypatch):
    destino_dir = tmp_path / "backups"
    status_path = tmp_path / "ultimo_backup.json"

    monkeypatch.setattr(backup_service, "BACKUP_DIR", destino_dir)
    monkeypatch.setattr(backup_service, "STATUS_PATH", status_path)
    monkeypatch.setattr(backup_service, "encontrar_bancos", lambda: [])

    dados = backup_service.criar_backup_local("teste_desktop")

    assert dados["ok"] is False
    assert "erro" in dados
