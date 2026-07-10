"""Teste basico da API local (api/main.py).

Roda dentro da suite pytest (tests/api_smoke_test.py).
"""
import json
import os

from fastapi.testclient import TestClient

TEST_TOKEN = "test-token-local-smoke"
os.environ.setdefault("MISTICA_API_TOKEN", TEST_TOKEN)

from api.main import app

client = TestClient(app)
client.__enter__()  # garante que o evento de startup (init_db) rode antes dos testes
TOKEN_HEADER = {"X-Mistica-Token": TEST_TOKEN}


def test_health_local():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json().get("ok") is True


def test_server_status_informa_seguranca():
    response = client.get("/api/server/status")
    assert response.status_code == 200
    assert "seguranca" in response.json()


def test_app_android_com_token():
    response = client.get("/api/app/android", headers=TOKEN_HEADER)
    assert response.status_code == 200
    app_info = response.json()
    assert app_info.get("latest_version"), "Versao Android ausente"
    assert app_info.get("latest_version_code", 0) >= 1, "Version code Android invalido"


def test_dashboard_com_token_retorna_campos_esperados():
    response = client.get("/api/dashboard", headers=TOKEN_HEADER)
    assert response.status_code == 200
    data = response.json()
    for chave in ["vendas_hoje", "caixa", "ultimas_vendas", "estoque_baixo", "alertas_isis", "seguranca"]:
        assert chave in data, f"Campo ausente no dashboard: {chave}"


def test_dashboard_sem_token_e_negado():
    response = client.get("/api/dashboard")
    assert response.status_code == 401, "API deveria exigir token nas rotas protegidas"


def test_websocket_dashboard_com_token():
    with client.websocket_connect(f"/ws/dashboard?token={TEST_TOKEN}") as ws:
        ws_data = json.loads(ws.receive_text())
        assert "vendas_hoje" in ws_data, "WebSocket precisa enviar dashboard"
