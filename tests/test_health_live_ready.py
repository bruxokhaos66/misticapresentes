"""Regressão dos endpoints /api/health/live e /api/health/ready (Fase C).

`live` só confirma que o processo responde (sem tocar banco/disco).
`ready` precisa recusar tráfego (503) quando o banco estiver inacessível,
não gravável ou faltando alguma tabela essencial -- nunca retornar 200 com
o banco inutilizável.
"""
import importlib

from fastapi.testclient import TestClient

main = importlib.import_module("backend.main")
client = TestClient(main.app)
client.__enter__()


def test_health_live_sempre_ok():
    response = client.get("/api/health/live")
    assert response.status_code == 200
    corpo = response.json()
    assert corpo["status"] == "ok"


def test_health_ready_ok_com_banco_valido():
    response = client.get("/api/health/ready")
    assert response.status_code == 200
    corpo = response.json()
    assert corpo["status"] == "ok"
    assert corpo["banco_acessivel"] is True
    assert corpo["migrations_aplicadas"] is True
    assert corpo["banco_gravavel"] is True


def test_health_ready_nao_expoe_caminho_ou_stacktrace():
    response = client.get("/api/health/ready")
    corpo = response.text
    assert ".db" not in corpo
    assert "Traceback" not in corpo
    assert "/data" not in corpo and "/home" not in corpo


def test_health_ready_retorna_503_quando_banco_inacessivel(monkeypatch):
    import backend.system_status_routes as system_status_routes

    monkeypatch.setattr(system_status_routes, "banco_acessivel", lambda: False)

    response = client.get("/api/health/ready")

    assert response.status_code == 503
    corpo = response.json()
    assert corpo["status"] == "error"
    assert corpo["banco_acessivel"] is False


def test_health_ready_retorna_503_quando_banco_nao_gravavel(monkeypatch):
    import backend.system_status_routes as system_status_routes

    monkeypatch.setattr(system_status_routes, "escrita_disco_segura", lambda: (False, "sem_espaco"))

    response = client.get("/api/health/ready")

    assert response.status_code == 503
    corpo = response.json()
    assert corpo["status"] == "error"
    assert corpo["banco_gravavel"] is False


def test_health_ready_retorna_503_quando_migration_pendente(monkeypatch):
    import backend.system_status_routes as system_status_routes

    monkeypatch.setattr(
        system_status_routes,
        "TABELAS_MIGRATIONS_OBRIGATORIAS",
        ["produtos", "tabela_que_nao_existe_ainda"],
    )

    response = client.get("/api/health/ready")

    assert response.status_code == 503
    corpo = response.json()
    assert corpo["migrations_aplicadas"] is False
