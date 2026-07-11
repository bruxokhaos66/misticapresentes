import sqlite3

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from backend import panel_sessions


def _request(ip: str) -> Request:
    return Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/api/auth/login",
            "headers": [(b"user-agent", b"pytest")],
            "client": (ip, 12345),
            "scheme": "https",
            "server": ("testserver", 443),
        }
    )


@pytest.fixture()
def banco_login(tmp_path, monkeypatch):
    caminho = tmp_path / "login.db"

    def conectar_teste():
        conn = sqlite3.connect(caminho)
        conn.row_factory = sqlite3.Row
        return conn

    monkeypatch.setattr(panel_sessions, "conectar", conectar_teste)
    monkeypatch.setattr(panel_sessions.time, "sleep", lambda _segundos: None)
    monkeypatch.setattr(panel_sessions, "LOGIN_MAX_TENTATIVAS", 5)
    monkeypatch.setattr(panel_sessions, "LOGIN_JANELA_MINUTOS", 10)
    return conectar_teste


def test_bloqueia_na_quinta_falha_e_cria_alerta(banco_login):
    request = _request("203.0.113.10")

    for _ in range(4):
        panel_sessions.registrar_tentativa_login("admin", request, sucesso=False)

    with pytest.raises(HTTPException) as exc:
        panel_sessions.registrar_tentativa_login("admin", request, sucesso=False)

    assert exc.value.status_code == 429
    assert int(exc.value.headers["Retry-After"]) > 0

    with banco_login() as conn:
        falhas = conn.execute(
            "SELECT COUNT(*) AS total FROM painel_login_tentativas WHERE login='admin' AND sucesso=0"
        ).fetchone()["total"]
        alertas = conn.execute(
            "SELECT COUNT(*) AS total FROM painel_alertas_seguranca WHERE tipo='login_suspeito'"
        ).fetchone()["total"]
    assert falhas == 5
    assert alertas == 1


def test_limite_tambem_e_por_ip_com_usuarios_diferentes(banco_login):
    request = _request("203.0.113.20")

    for indice in range(4):
        panel_sessions.registrar_tentativa_login(f"usuario-{indice}", request, sucesso=False)

    with pytest.raises(HTTPException) as exc:
        panel_sessions.registrar_tentativa_login("outro-usuario", request, sucesso=False)

    assert exc.value.status_code == 429


def test_login_correto_continua_bloqueado_durante_penalidade(banco_login):
    request = _request("203.0.113.30")

    for _ in range(4):
        panel_sessions.registrar_tentativa_login("admin", request, sucesso=False)
    with pytest.raises(HTTPException):
        panel_sessions.registrar_tentativa_login("admin", request, sucesso=False)

    with pytest.raises(HTTPException) as exc:
        panel_sessions.registrar_tentativa_login("admin", request, sucesso=True)
    assert exc.value.status_code == 429


def test_politica_de_senha_forte():
    assert panel_sessions._senha_forte("SenhaForte#2026") is True
    assert panel_sessions._senha_forte("senha-fraca") is False
    assert panel_sessions._senha_forte("SEMMINUSCULA#2026") is False
    assert panel_sessions._senha_forte("SemNumero#Senha") is False
