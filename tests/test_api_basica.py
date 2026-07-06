import importlib

from fastapi.testclient import TestClient


main = importlib.import_module("backend.main")
client = TestClient(main.app)


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
    assert "produtos" in data
    assert "clientes" in data
    assert "vendas" in data


def test_diagnostico_sistema_responde():
    response = client.get("/api/diagnostico/sistema")
    assert response.status_code == 200
    data = response.json()
    assert data["app"] == "Mística Presentes"
    assert data["status"] in ["ok", "verificar"]
    assert "banco" in data
    assert "tabelas" in data


def test_backup_status_responde():
    response = client.get("/api/backup/status")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "banco_existe" in data
    assert "backup_dir" in data
    assert "ultimos_backups" in data
