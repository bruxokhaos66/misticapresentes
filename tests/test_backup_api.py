import hashlib
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


def test_backup_status_exige_chave_valida():
    response = client.get("/api/backup/status")
    assert response.status_code in (401, 403)


def test_backup_status_administrativo_exige_autenticacao():
    response = client.get("/api/admin/backup/status")
    assert response.status_code in (401, 403)


def test_backup_status_administrativo_usa_auth_existente_e_nao_expoe_caminhos(monkeypatch):
    monkeypatch.setattr(
        backup_routes,
        "obter_status_backup",
        lambda: {
            "ultimo_backup": "backup_2026-07-14_03-00-00.db",
            "tamanho_bytes": 4096,
            "data": "2026-07-14T03:00:00-03:00",
            "quantidade_backups": 1,
            "espaco_livre_bytes": 500_000_000,
            "proximo_backup": "2026-07-15T03:00:00-03:00",
            "status": "ok",
            "ultimo_erro": None,
            "integridade": "ok",
        },
    )
    response = client.get("/api/admin/backup/status", headers=HEADERS)

    assert response.status_code == 200
    assert set(response.json()) == {
        "ultimo_backup",
        "tamanho_bytes",
        "data",
        "quantidade_backups",
        "espaco_livre_bytes",
        "proximo_backup",
        "status",
        "ultimo_erro",
        "integridade",
    }
    assert "/data" not in response.text
    assert str(config.DB_PATH) not in response.text


def test_backup_download_exige_chave_valida():
    response = client.get("/api/backup/download")
    assert response.status_code in (401, 403)


def test_sem_autenticacao_nao_revela_se_backup_ou_banco_existem():
    """A validação da chave acontece antes de qualquer checagem de arquivo,
    então uma requisição não autenticada não pode distinguir "banco existe"
    de "banco não existe" nem ver qualquer caminho."""
    response_manual = client.post("/api/backup/manual")
    response_download = client.get("/api/backup/download")
    response_status = client.get("/api/backup/status")

    for response in (response_manual, response_download, response_status):
        corpo = response.text.lower()
        assert "banco de dados" not in corpo
        assert "arquivo" not in corpo
        assert str(config.DB_PATH).lower() not in corpo
        assert str(config.BACKUP_DIR).lower() not in corpo


def test_content_disposition_usa_nome_sanitizado():
    response = client.get("/api/backup/download", headers=HEADERS)
    assert response.status_code == 200
    disposicao = response.headers["content-disposition"]
    assert str(config.BACKUP_DIR) not in disposicao
    assert ".." not in disposicao
    assert "/" not in disposicao and "\\" not in disposicao


def test_erro_ao_criar_backup_nao_revela_db_path(monkeypatch):
    def _falhar(*args, **kwargs):
        raise RuntimeError(f"falha simulada acessando {config.DB_PATH}")

    monkeypatch.setattr(backup_routes, "criar_backup_seguro", _falhar)

    response = client.post("/api/backup/manual", headers=HEADERS)
    assert response.status_code == 500
    assert str(config.DB_PATH) not in response.text


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


# --- Ciclo de vida completo do arquivo temporário de download -------------
#
# GET /api/backup/download cria uma cópia efêmera do banco e a remove via
# BackgroundTask assim que a resposta termina de ser enviada. Os testes
# abaixo comprovam, de ponta a ponta, que essa remoção nunca acontece antes
# do cliente ter recebido o arquivo completo, e que ela nunca alcança outros
# backups.


def test_download_devolve_arquivo_completo_com_checksum_correspondente():
    """1) o corpo da resposta é o arquivo inteiro; 2) o checksum bate."""
    response = client.get("/api/backup/download", headers=HEADERS)
    assert response.status_code == 200

    checksum_anunciado = response.headers["x-backup-checksum-sha256"]
    checksum_recebido = hashlib.sha256(response.content).hexdigest()
    assert checksum_recebido == checksum_anunciado
    assert len(response.content) > 0
    assert int(response.headers["content-length"]) == len(response.content)


def test_arquivo_temporario_existe_durante_o_envio_e_e_removido_apos(monkeypatch):
    """3) o arquivo existe enquanto a resposta precisa dele; 4) some depois."""
    estado_durante_limpeza = {}
    original = backup_routes._remover_arquivo_temporario

    def _remover_espiao(caminho):
        # Neste ponto o BackgroundTask está rodando, o que só acontece depois
        # que o Starlette já enviou o corpo inteiro da resposta (ver
        # comentário em backend/backup_routes.py). O arquivo ainda deve
        # existir aqui — é exatamente o que a chamada real precisa encontrar
        # para conseguir apagá-lo.
        estado_durante_limpeza["existia_no_momento_da_limpeza"] = os.path.exists(caminho)
        estado_durante_limpeza["tamanho_no_momento_da_limpeza"] = (
            os.path.getsize(caminho) if os.path.exists(caminho) else 0
        )
        estado_durante_limpeza["caminho"] = caminho
        original(caminho)

    monkeypatch.setattr(backup_routes, "_remover_arquivo_temporario", _remover_espiao)

    response = client.get("/api/backup/download", headers=HEADERS)
    assert response.status_code == 200

    assert estado_durante_limpeza["existia_no_momento_da_limpeza"] is True
    assert estado_durante_limpeza["tamanho_no_momento_da_limpeza"] == len(response.content)

    caminho = estado_durante_limpeza["caminho"]
    assert not os.path.exists(caminho)
    assert not os.path.exists(f"{caminho}.sha256")


def test_limpeza_do_download_nunca_remove_outros_backups(tmp_path):
    """5) a limpeza (mesmo em caso de falha) não pode remover backups permanentes."""
    permanente = tmp_path / "mistica_backup_20200101_000000.db"
    permanente.write_bytes(b"backup permanente, nao deve ser tocado")
    outro_download = tmp_path / "mistica_backup_download_20200101_000000.db"
    outro_download.write_bytes(b"outro download efemero, tambem nao deve ser tocado")

    alvo = tmp_path / "mistica_backup_download_20260101_000000.db"
    alvo.write_bytes(b"conteudo do arquivo que sera limpo")
    (alvo.with_suffix(alvo.suffix + ".sha256")).write_text("hash  nome\n")

    # A função de limpeza recebe exatamente um caminho e só mexe nele (e no
    # seu sidecar .sha256) — nunca faz varredura do diretório. Isso garante
    # que, independentemente de quando/como ela é chamada (sucesso, erro,
    # ou uma falha de envio no meio do caminho), backups permanentes e
    # cópias de download de outras requisições nunca são afetados.
    backup_routes._remover_arquivo_temporario(str(alvo))

    assert not alvo.exists()
    assert permanente.exists() and permanente.read_bytes() == b"backup permanente, nao deve ser tocado"
    assert outro_download.exists()


def test_backup_download_nao_deixa_arquivos_orfaos_no_diretorio():
    antes = set(os.listdir(config.BACKUP_DIR)) if os.path.isdir(config.BACKUP_DIR) else set()

    response = client.get("/api/backup/download", headers=HEADERS)
    assert response.status_code == 200

    depois = set(os.listdir(config.BACKUP_DIR)) if os.path.isdir(config.BACKUP_DIR) else set()
    novos = depois - antes
    assert novos == set()
