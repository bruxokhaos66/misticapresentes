import importlib
import os

from fastapi.testclient import TestClient


TEST_API_KEY = "test-api-key"
os.environ.setdefault("MISTICA_SITE_API_KEY", TEST_API_KEY)
os.environ.setdefault("MISTICA_SYNC_KEY", TEST_API_KEY)

main = importlib.import_module("backend.main")
client = TestClient(main.app)
client.__enter__()  # garante que o evento de startup (migrações) rode antes dos testes
PROTECTED_HEADERS = {"X-Mistica-Api-Key": TEST_API_KEY}


def test_health_online():
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "online"
    assert data["app"] == "Mística Presentes"


def test_status_online():
    response = client.get("/api/status")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "online"
    assert data["api"] == "mistica"
    assert data["app"] == "Mística Presentes"
    assert "timestamp" in data
    assert "data_hora" in data


def test_diagnostico_sistema_responde():
    response = client.get("/api/diagnostico/sistema", headers=PROTECTED_HEADERS)
    assert response.status_code == 200
    data = response.json()
    assert data["app"] == "Mística Presentes"
    assert data["status"] in ["ok", "verificar"]
    assert "banco" in data
    assert "tabelas" in data


def test_backup_status_responde():
    response = client.get("/api/backup/status", headers=PROTECTED_HEADERS)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "banco_existe" in data
    assert "backup_dir" in data
    assert "ultimos_backups" in data


def test_playlist_ambiente_responde():
    response = client.get("/api/site/playlist-ambiente")
    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is True
    assert "links" in data
    assert isinstance(data["links"], list)


def test_playlist_ambiente_salva_links_youtube():
    payload = {"links": ["https://www.youtube.com/watch?v=abc123", "https://example.com/ignorar"]}
    response = client.post("/api/site/playlist-ambiente", json=payload, headers=PROTECTED_HEADERS)
    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is True
    assert data["links"] == ["https://www.youtube.com/watch?v=abc123"]

    response_get = client.get("/api/site/playlist-ambiente")
    assert response_get.status_code == 200
    assert response_get.json()["links"] == ["https://www.youtube.com/watch?v=abc123"]


def test_listagem_musicas_ambiente_responde():
    response = client.get("/api/uploads/musicas")
    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is True
    assert "musicas" in data
    assert isinstance(data["musicas"], list)


def test_upload_musica_ambiente_responde_rapido_e_salva_arquivo():
    response = client.post(
        "/api/uploads/musicas",
        files={"arquivo": ("teste.mp3", b"ID3teste", "audio/mpeg")},
        data={"nome_base": "teste-ambiente"},
        headers=PROTECTED_HEADERS,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is True
    assert data["armazenamento"] == "arquivo+backup_banco"
    assert data["url"].startswith("/api/uploads/musicas/arquivo-local/")

    arquivo = client.get(data["url"])
    assert arquivo.status_code == 200
    assert arquivo.content == b"ID3teste"


def test_listar_clientes_exige_chave_api():
    response = client.get("/api/clientes")
    assert response.status_code == 403

    response = client.get("/api/clientes", headers={"X-Mistica-Api-Key": "chave-errada"})
    assert response.status_code == 403

    response = client.get("/api/clientes", headers=PROTECTED_HEADERS)
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_listar_vendas_exige_chave_api():
    response = client.get("/api/vendas")
    assert response.status_code == 403

    response = client.get("/api/vendas", headers={"X-Mistica-Api-Key": "chave-errada"})
    assert response.status_code == 403

    response = client.get("/api/vendas", headers=PROTECTED_HEADERS)
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_links_audio_ambiente_salva_apenas_audio_direto():
    payload = {
        "links": [
            "https://cdn.exemplo.com/ambiente.mp3",
            "https://cdn.exemplo.com/ambiente.wav?versao=1",
            "https://example.com/pagina",
        ]
    }
    response = client.post("/api/uploads/musicas/links", json=payload, headers=PROTECTED_HEADERS)
    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is True
    assert data["links"] == [
        "https://cdn.exemplo.com/ambiente.mp3",
        "https://cdn.exemplo.com/ambiente.wav?versao=1",
    ]

    response_get = client.get("/api/uploads/musicas/links")
    assert response_get.status_code == 200
    assert response_get.json()["links"] == data["links"]
