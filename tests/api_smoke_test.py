"""Teste basico da API local.

Execute na raiz do projeto:
    python tests/api_smoke_test.py
"""
from pathlib import Path
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient
from api.main import app

TOKEN = {"X-Mistica-Token": "mistica-local"}


def main():
    client = TestClient(app)

    r = client.get("/health")
    assert r.status_code == 200, r.text
    assert r.json().get("ok") is True

    r = client.get("/api/server/status")
    assert r.status_code == 200, r.text
    status = r.json()
    assert "seguranca" in status, "Status precisa informar seguranca"

    r = client.get("/api/app/android", headers=TOKEN)
    assert r.status_code == 200, r.text
    app_info = r.json()
    assert app_info.get("latest_version"), "Versao Android ausente"
    assert app_info.get("latest_version_code", 0) >= 1, "Version code Android invalido"

    r = client.get("/api/dashboard", headers=TOKEN)
    assert r.status_code == 200, r.text
    data = r.json()
    for chave in ["vendas_hoje", "caixa", "ultimas_vendas", "estoque_baixo", "alertas_isis", "seguranca"]:
        assert chave in data, f"Campo ausente no dashboard: {chave}"

    r = client.get("/api/dashboard")
    assert r.status_code == 401, "API deveria exigir token nas rotas protegidas"

    with client.websocket_connect("/ws/dashboard?token=mistica-local") as ws:
        ws_data = json.loads(ws.receive_text())
        assert "vendas_hoje" in ws_data, "WebSocket precisa enviar dashboard"

    print("OK - API local respondeu corretamente.")


if __name__ == "__main__":
    main()
