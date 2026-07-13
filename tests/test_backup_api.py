import importlib
import os
import sqlite3

os.environ.setdefault("MISTICA_SITE_API_KEY", "test-api-key")
os.environ.setdefault("MISTICA_SYNC_KEY", "test-api-key")

from fastapi.testclient import TestClient  # noqa: E402

import backend.backup_routes as backup_routes  # noqa: E402
import config  # noqa: E402

main = importlib.import_module("backend.main")
client = TestClient(main.app)
client.__enter__()
HEADERS = {"X-Mistica-Api-Key": "test-api-key"}


def test_backup_manual_exige_chave_valida():
    response = client.post("/api/backup/manual")
    assert response.status_code in (401, 403)


def test_backup_download_exige_chave_valida():
    response = client.get("/api/backup/download")
    assert response.status_code in (401, 403)


def test_backup_status_nao_revela_caminho_absoluto():
    response = client.get("/api/backup/status", headers=HEADERS)
    assert response.status_code == 200
    corpo = response.text
    # O diretório de backups configurado (absoluto, específico do host) não
    # pode aparecer na resposta pública — só o nome relativo da pasta.
    assert str(config.BACKUP_DIR) not in corpo
    assert str(config.DB_PATH) not in corpo
    assert os.path.expanduser("~") not in corpo


def test_backup_manual_resposta_nao_revela_caminho_absoluto_e_traz_checksum():
    response = client.post("/api/backup/manual", headers=HEADERS)
    assert response.status_code == 200
    data = response.json()
    assert str(config.BACKUP_DIR) not in response.text
    assert "arquivo" in data
    # O nome do arquivo não deve conter separador de diretório.
    assert "/" not in data["arquivo"] and "\\" not in data["arquivo"]
    assert len(data["checksum_sha256"]) == 64


def test_backup_download_remove_arquivo_temporario_apos_resposta():
    antes = set(os.listdir(config.BACKUP_DIR)) if os.path.isdir(config.BACKUP_DIR) else set()

    response = client.get("/api/backup/download", headers=HEADERS)
    assert response.status_code == 200
    assert len(response.content) > 0

    depois = set(os.listdir(config.BACKUP_DIR)) if os.path.isdir(config.BACKUP_DIR) else set()
    novos = depois - antes
    # A cópia de download é efêmera: nenhum arquivo novo do tipo "download"
    # deve permanecer no diretório de backups após a resposta ser enviada.
    restantes_de_download = [n for n in novos if "download" in n]
    assert restantes_de_download == []


def test_backup_baixado_abre_e_passa_no_integrity_check(tmp_path):
    response = client.get("/api/backup/download", headers=HEADERS)
    assert response.status_code == 200

    caminho_local = tmp_path / "baixado.db"
    caminho_local.write_bytes(response.content)

    conn = sqlite3.connect(str(caminho_local))
    try:
        resultado = conn.execute("PRAGMA integrity_check").fetchone()[0]
    finally:
        conn.close()
    assert str(resultado).strip().lower() == "ok"
