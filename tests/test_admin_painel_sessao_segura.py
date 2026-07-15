"""Regressão do PR fix/sessao-admin-segura.

Cobre os dois achados corrigidos:
- api/painel.html: token de API deixou de ser persistido em localStorage.
- painel-operacional.html: sessão completa deixou de ser persistida em
  sessionStorage.

E o novo fluxo de sessão por cookie HttpOnly de api/app_auth.py /
api/main.py (login, painel/"me", logout, CSRF).
"""
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.environ.setdefault("MISTICA_API_TOKEN", "test-token-local-smoke")

from fastapi.testclient import TestClient  # noqa: E402
from starlette.requests import Request  # noqa: E402

from config import hash_password_pbkdf2  # noqa: E402
from database import query_db  # noqa: E402
import api.security as security  # noqa: E402
from api.main import app  # noqa: E402

# Outro módulo de teste (tests/api_smoke_test.py) também pode ter feito
# setdefault antes deste; ler de volta o valor efetivo evita testes
# quebrarem por ordem de coleta do pytest.
TEST_TOKEN = os.environ["MISTICA_API_TOKEN"]
TOKEN_HEADER = {"X-Mistica-Token": TEST_TOKEN}
ORIGIN_HEADER = {"Origin": "http://localhost"}
LOGIN_TESTE = "teste_sessao_admin_segura"
SENHA_TESTE = "senha-forte-123"


# ---------------------------------------------------------------------------
# Checagem estática: as chaves proibidas não podem voltar a existir no HTML
# administrativo real (não é uma lista incompleta de nomes de arquivo — lê o
# conteúdo de ambos os arquivos apontados nos dois achados do PR).
# ---------------------------------------------------------------------------

PAINEL_HTML = (ROOT / "api" / "painel.html").read_text(encoding="utf-8")
PAINEL_OPERACIONAL_HTML = (ROOT / "painel-operacional.html").read_text(encoding="utf-8")


def test_api_painel_nao_grava_token_em_localstorage():
    assert "localStorage.setItem('MISTICA_API_TOKEN'" not in PAINEL_HTML
    assert 'localStorage.setItem("MISTICA_API_TOKEN"' not in PAINEL_HTML
    assert "localStorage.getItem('MISTICA_API_TOKEN')" not in PAINEL_HTML
    assert "localStorage.setItem('MISTICA_APP_PERFIL'" not in PAINEL_HTML
    assert "localStorage.setItem('MISTICA_APP_NOME'" not in PAINEL_HTML


def test_api_painel_remove_chaves_legadas_sem_usar_o_valor():
    script = PAINEL_HTML.split("<script>", 1)[1]
    bloco_limpeza = script.split("const params = new URLSearchParams", 1)[0]
    assert "localStorage.removeItem('MISTICA_API_TOKEN')" in bloco_limpeza
    assert "localStorage.removeItem('MISTICA_APP_NOME')" in bloco_limpeza
    assert "localStorage.removeItem('MISTICA_APP_PERFIL')" in bloco_limpeza


def test_api_painel_usa_cookie_sem_header_de_token_construido_do_storage():
    assert "credentials:'include'" in PAINEL_HTML or "credentials: 'include'" in PAINEL_HTML
    assert "'X-Mistica-Token':token()" not in PAINEL_HTML
    assert "headers:{'X-Mistica-Token'" not in PAINEL_HTML


def test_painel_operacional_nao_grava_sessao_completa_em_sessionstorage():
    assert 'sessionStorage.setItem("misticaPainelSessao"' not in PAINEL_OPERACIONAL_HTML


def test_painel_operacional_continua_usando_endpoint_de_sessao_autoritativo():
    assert '/api/auth/me' in PAINEL_OPERACIONAL_HTML
    assert 'credentials: "include"' in PAINEL_OPERACIONAL_HTML


# ---------------------------------------------------------------------------
# Comportamento: fluxo de login/sessão/logout via cookie HttpOnly no
# subsistema local (api/).
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module", autouse=True)
def usuario_teste():
    with TestClient(app) as client:
        salt = "salt-teste-sessao-admin"
        query_db(
            "DELETE FROM usuarios WHERE login=?",
            (LOGIN_TESTE,),
            commit=True,
        )
        query_db(
            "INSERT INTO usuarios (nome, login, senha_hash, senha_salt, perfil, ativo) VALUES (?,?,?,?,?,?)",
            (
                "Usuária de Teste",
                LOGIN_TESTE,
                hash_password_pbkdf2(SENHA_TESTE, salt.encode("utf-8")),
                salt,
                "adm",
                1,
            ),
            commit=True,
        )
        yield client
        query_db("DELETE FROM usuarios WHERE login=?", (LOGIN_TESTE,), commit=True)


def test_login_exige_token_de_rede_local(usuario_teste):
    r = usuario_teste.post("/api/app/login", json={"login": LOGIN_TESTE, "senha": SENHA_TESTE}, headers=ORIGIN_HEADER)
    assert r.status_code == 401


def test_login_correto_nao_devolve_o_token_de_sessao_no_corpo(usuario_teste):
    r = usuario_teste.post(
        "/api/app/login",
        json={"login": LOGIN_TESTE, "senha": SENHA_TESTE},
        headers={**TOKEN_HEADER, **ORIGIN_HEADER},
    )
    assert r.status_code == 200
    corpo = r.json()
    assert "sessao" not in corpo
    assert corpo["usuario"]["perfil"] == "adm"
    assert r.headers.get("cache-control", "").startswith("no-store")
    cookie = r.cookies.get(security.APP_SESSION_COOKIE)
    assert cookie
    usuario_teste.cookies.clear()


def test_login_com_senha_errada_retorna_erro_generico(usuario_teste):
    r = usuario_teste.post(
        "/api/app/login",
        json={"login": LOGIN_TESTE, "senha": "senha-errada"},
        headers={**TOKEN_HEADER, **ORIGIN_HEADER},
    )
    assert r.status_code == 401
    assert r.json()["detail"] == "Usuário ou senha incorretos."


def test_painel_sem_cookie_e_negado(usuario_teste):
    usuario_teste.cookies.clear()
    r = usuario_teste.get("/api/app/painel")
    assert r.status_code == 401
    assert r.headers.get("cache-control", "").startswith("no-store")


def test_reload_usa_cookie_de_sessao_e_recebe_dados_do_perfil(usuario_teste):
    usuario_teste.cookies.clear()
    login = usuario_teste.post(
        "/api/app/login",
        json={"login": LOGIN_TESTE, "senha": SENHA_TESTE},
        headers={**TOKEN_HEADER, **ORIGIN_HEADER},
    )
    assert login.status_code == 200

    r = usuario_teste.get("/api/app/painel")
    assert r.status_code == 200
    data = r.json()
    assert data["usuario"]["login"] == LOGIN_TESTE
    assert data["usuario"]["perfil"] == "adm"
    assert "vendas_hoje" in data  # dado escopado por perfil adm


def test_logout_revoga_a_sessao_no_servidor(usuario_teste):
    usuario_teste.cookies.clear()
    login = usuario_teste.post(
        "/api/app/login",
        json={"login": LOGIN_TESTE, "senha": SENHA_TESTE},
        headers={**TOKEN_HEADER, **ORIGIN_HEADER},
    )
    assert login.status_code == 200
    assert usuario_teste.get("/api/app/painel").status_code == 200

    logout = usuario_teste.post("/api/app/logout", headers=ORIGIN_HEADER)
    assert logout.status_code == 200

    r = usuario_teste.get("/api/app/painel")
    assert r.status_code == 401


def test_cookie_invalido_apos_logout_nao_da_acesso(usuario_teste):
    usuario_teste.cookies.set(security.APP_SESSION_COOKIE, "sessao-forjada-invalida")
    r = usuario_teste.get("/api/app/painel")
    assert r.status_code == 401
    usuario_teste.cookies.clear()


def test_sessao_vendedor_nao_recebe_dados_de_admin(usuario_teste):
    usuario_teste.cookies.clear()
    salt = "salt-vendedor-teste"
    query_db("DELETE FROM usuarios WHERE login='vendedor_teste_sessao'", commit=True)
    query_db(
        "INSERT INTO usuarios (nome, login, senha_hash, senha_salt, perfil, ativo) VALUES (?,?,?,?,?,?)",
        ("Vendedor Teste", "vendedor_teste_sessao", hash_password_pbkdf2("outra-senha-forte", salt.encode("utf-8")), salt, "vendedor", 1),
        commit=True,
    )
    try:
        login = usuario_teste.post(
            "/api/app/login",
            json={"login": "vendedor_teste_sessao", "senha": "outra-senha-forte"},
            headers={**TOKEN_HEADER, **ORIGIN_HEADER},
        )
        assert login.status_code == 200
        r = usuario_teste.get("/api/app/painel")
        assert r.status_code == 200
        data = r.json()
        assert data["usuario"]["perfil"] == "vendedor"
        assert "vendas_hoje" not in data
        assert "ultimas_vendas" not in data
        assert "estoque_baixo" not in data
    finally:
        usuario_teste.cookies.clear()
        query_db("DELETE FROM usuarios WHERE login='vendedor_teste_sessao'", commit=True)


# ---------------------------------------------------------------------------
# CSRF: Origin/Referer nas mutações do subsistema de sessão do app.
# ---------------------------------------------------------------------------


def _request_com_origem(origem: str | None) -> Request:
    headers = [(b"user-agent", b"pytest")]
    if origem:
        headers.append((b"origin", origem.encode()))
    return Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/api/app/login",
            "headers": headers,
            "client": ("127.0.0.1", 12345),
            "scheme": "http",
            "server": ("testserver", 80),
        }
    )


def test_csrf_rejeita_origem_externa(monkeypatch):
    monkeypatch.setattr(security, "_origens_permitidas", lambda: ["http://localhost"])
    with pytest.raises(Exception) as exc:
        security.validar_origem_csrf(_request_com_origem("http://atacante.example"))
    assert getattr(exc.value, "status_code", None) == 403


def test_csrf_aceita_origem_permitida(monkeypatch):
    monkeypatch.setattr(security, "_origens_permitidas", lambda: ["http://localhost"])
    security.validar_origem_csrf(_request_com_origem("http://localhost"))  # não deve levantar


def test_csrf_nao_bloqueia_get(monkeypatch):
    monkeypatch.setattr(security, "_origens_permitidas", lambda: ["http://localhost"])
    req = _request_com_origem("http://atacante.example")
    req.scope["method"] = "GET"
    security.validar_origem_csrf(req)  # GET não é mutável, não deve levantar
