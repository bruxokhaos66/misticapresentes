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


def test_csrf_end_to_end_login_sem_origin_e_negado(usuario_teste):
    """CSRF real (não só a função isolada): POST /api/app/login sem Origin,
    quando MISTICA_ALLOWED_ORIGINS está configurado, é rejeitado com 403."""
    usuario_teste.cookies.clear()
    r = usuario_teste.post("/api/app/login", json={"login": LOGIN_TESTE, "senha": SENHA_TESTE}, headers=TOKEN_HEADER)
    assert r.status_code == 403


def test_csrf_end_to_end_logout_com_origem_externa_e_negado(usuario_teste):
    usuario_teste.cookies.clear()
    login = usuario_teste.post(
        "/api/app/login",
        json={"login": LOGIN_TESTE, "senha": SENHA_TESTE},
        headers={**TOKEN_HEADER, **ORIGIN_HEADER},
    )
    assert login.status_code == 200
    r = usuario_teste.post("/api/app/logout", headers={"Origin": "http://atacante.example"})
    assert r.status_code == 403
    # a sessão não deve ter sido revogada por uma tentativa de logout com origem forjada
    assert usuario_teste.get("/api/app/painel").status_code == 200
    usuario_teste.cookies.clear()


# ---------------------------------------------------------------------------
# Perfil: sempre do servidor, nunca do cliente.
# ---------------------------------------------------------------------------


def test_perfil_enviado_pelo_cliente_no_login_e_ignorado(usuario_teste):
    """LoginAppRequest só aceita login/senha; um campo 'perfil' extra no
    corpo não pode elevar o vendedor a admin."""
    usuario_teste.cookies.clear()
    salt = "salt-vendedor-elevacao"
    query_db("DELETE FROM usuarios WHERE login='vendedor_tenta_elevar'", commit=True)
    query_db(
        "INSERT INTO usuarios (nome, login, senha_hash, senha_salt, perfil, ativo) VALUES (?,?,?,?,?,?)",
        ("Vendedor Tenta Elevar", "vendedor_tenta_elevar", hash_password_pbkdf2("senha-vendedor-1", salt.encode("utf-8")), salt, "vendedor", 1),
        commit=True,
    )
    try:
        r = usuario_teste.post(
            "/api/app/login",
            json={"login": "vendedor_tenta_elevar", "senha": "senha-vendedor-1", "perfil": "adm", "usuario": "adm"},
            headers={**TOKEN_HEADER, **ORIGIN_HEADER},
        )
        assert r.status_code == 200
        assert r.json()["usuario"]["perfil"] == "vendedor"
        painel = usuario_teste.get("/api/app/painel")
        assert painel.json()["usuario"]["perfil"] == "vendedor"
        assert "vendas_hoje" not in painel.json()
    finally:
        usuario_teste.cookies.clear()
        query_db("DELETE FROM usuarios WHERE login='vendedor_tenta_elevar'", commit=True)


def test_cookie_de_sessao_nao_pode_ser_forjado_para_elevar_perfil(usuario_teste):
    """Um cookie com valor arbitrário (não emitido pelo servidor) nunca é
    aceito como sessão válida, mesmo que o atacante tente adivinhar um
    formato plausível."""
    usuario_teste.cookies.clear()
    usuario_teste.cookies.set(security.APP_SESSION_COOKIE, "adm-eu-mesmo-decidi-que-sou-admin")
    r = usuario_teste.get("/api/app/painel")
    assert r.status_code == 401
    usuario_teste.cookies.clear()


# ---------------------------------------------------------------------------
# Suspensão/demoção: precisam valer imediatamente, sem esperar expirar.
# ---------------------------------------------------------------------------


def test_usuario_suspenso_perde_acesso_imediatamente(usuario_teste):
    usuario_teste.cookies.clear()
    salt = "salt-suspenso-teste"
    query_db("DELETE FROM usuarios WHERE login='usuario_suspenso_teste'", commit=True)
    query_db(
        "INSERT INTO usuarios (nome, login, senha_hash, senha_salt, perfil, ativo) VALUES (?,?,?,?,?,?)",
        ("Usuario Suspenso", "usuario_suspenso_teste", hash_password_pbkdf2("senha-suspenso-1", salt.encode("utf-8")), salt, "adm", 1),
        commit=True,
    )
    try:
        login = usuario_teste.post(
            "/api/app/login",
            json={"login": "usuario_suspenso_teste", "senha": "senha-suspenso-1"},
            headers={**TOKEN_HEADER, **ORIGIN_HEADER},
        )
        assert login.status_code == 200
        assert usuario_teste.get("/api/app/painel").status_code == 200

        # suspensão acontece no cadastro, sem logout explícito
        query_db("UPDATE usuarios SET ativo=0 WHERE login='usuario_suspenso_teste'", commit=True)

        r = usuario_teste.get("/api/app/painel")
        assert r.status_code == 401
    finally:
        usuario_teste.cookies.clear()
        query_db("DELETE FROM usuarios WHERE login='usuario_suspenso_teste'", commit=True)


def test_democao_de_perfil_vale_na_proxima_requisicao_sem_novo_login(usuario_teste):
    usuario_teste.cookies.clear()
    salt = "salt-democao-teste"
    query_db("DELETE FROM usuarios WHERE login='usuario_democao_teste'", commit=True)
    query_db(
        "INSERT INTO usuarios (nome, login, senha_hash, senha_salt, perfil, ativo) VALUES (?,?,?,?,?,?)",
        ("Usuario Democao", "usuario_democao_teste", hash_password_pbkdf2("senha-democao-1", salt.encode("utf-8")), salt, "adm", 1),
        commit=True,
    )
    try:
        login = usuario_teste.post(
            "/api/app/login",
            json={"login": "usuario_democao_teste", "senha": "senha-democao-1"},
            headers={**TOKEN_HEADER, **ORIGIN_HEADER},
        )
        assert login.status_code == 200
        assert usuario_teste.get("/api/app/painel").json()["usuario"]["perfil"] == "adm"

        query_db("UPDATE usuarios SET perfil='vendedor' WHERE login='usuario_democao_teste'", commit=True)

        r = usuario_teste.get("/api/app/painel")
        assert r.status_code == 200
        assert r.json()["usuario"]["perfil"] == "vendedor"
        assert "vendas_hoje" not in r.json()
    finally:
        usuario_teste.cookies.clear()
        query_db("DELETE FROM usuarios WHERE login='usuario_democao_teste'", commit=True)


# ---------------------------------------------------------------------------
# Atributos do cookie de sessão.
# ---------------------------------------------------------------------------


def test_atributos_do_cookie_de_sessao(usuario_teste):
    usuario_teste.cookies.clear()
    r = usuario_teste.post(
        "/api/app/login",
        json={"login": LOGIN_TESTE, "senha": SENHA_TESTE},
        headers={**TOKEN_HEADER, **ORIGIN_HEADER},
    )
    assert r.status_code == 200
    set_cookie = r.headers.get("set-cookie", "")
    assert f"{security.APP_SESSION_COOKIE}=" in set_cookie
    assert "httponly" in set_cookie.lower()
    assert "samesite=lax" in set_cookie.lower()
    assert "path=/" in set_cookie.lower()
    assert "max-age=" in set_cookie.lower()
    # ambiente de teste roda com APP_ENV != production: Secure não é setado,
    # o que é o comportamento correto para desenvolvimento local sem HTTPS.
    from api import main as api_main
    assert api_main.IS_PRODUCTION is False
    assert "secure" not in set_cookie.lower()
    usuario_teste.cookies.clear()


def test_logout_expira_cookie_com_mesmo_path(usuario_teste):
    usuario_teste.cookies.clear()
    login = usuario_teste.post(
        "/api/app/login",
        json={"login": LOGIN_TESTE, "senha": SENHA_TESTE},
        headers={**TOKEN_HEADER, **ORIGIN_HEADER},
    )
    assert login.status_code == 200
    r = usuario_teste.post("/api/app/logout", headers=ORIGIN_HEADER)
    assert r.status_code == 200
    set_cookie = r.headers.get("set-cookie", "")
    assert f"{security.APP_SESSION_COOKIE}=" in set_cookie
    assert "path=/" in set_cookie.lower()
    # Max-Age=0 ou data no passado indica remoção
    assert "max-age=0" in set_cookie.lower() or "1970" in set_cookie
    usuario_teste.cookies.clear()


def test_nao_existe_segundo_cookie_de_sessao_no_login(usuario_teste):
    usuario_teste.cookies.clear()
    r = usuario_teste.post(
        "/api/app/login",
        json={"login": LOGIN_TESTE, "senha": SENHA_TESTE},
        headers={**TOKEN_HEADER, **ORIGIN_HEADER},
    )
    assert r.status_code == 200
    cookies_no_jar = [c for c in usuario_teste.cookies.jar]
    nomes = {c.name for c in cookies_no_jar}
    assert nomes == {security.APP_SESSION_COOKIE}
    usuario_teste.cookies.clear()


# ---------------------------------------------------------------------------
# WebSocket: handshake autenticado por cookie, sem token na URL.
# ---------------------------------------------------------------------------


def test_websocket_sem_credenciais_e_recusado(usuario_teste):
    with pytest.raises(Exception):
        with usuario_teste.websocket_connect("/ws/dashboard"):
            pass


def test_websocket_com_cookie_de_sessao_valido_e_aceito(usuario_teste):
    usuario_teste.cookies.clear()
    login = usuario_teste.post(
        "/api/app/login",
        json={"login": LOGIN_TESTE, "senha": SENHA_TESTE},
        headers={**TOKEN_HEADER, **ORIGIN_HEADER},
    )
    assert login.status_code == 200
    with usuario_teste.websocket_connect("/ws/dashboard", headers=ORIGIN_HEADER) as ws:
        data = ws.receive_json()
        assert data["usuario"]["perfil"] == "adm"
        assert "vendas_hoje" in data
    usuario_teste.cookies.clear()


def test_websocket_com_cookie_invalido_e_recusado(usuario_teste):
    usuario_teste.cookies.clear()
    usuario_teste.cookies.set(security.APP_SESSION_COOKIE, "cookie-forjado-invalido")
    with pytest.raises(Exception):
        with usuario_teste.websocket_connect("/ws/dashboard"):
            pass
    usuario_teste.cookies.clear()


def test_websocket_com_origem_externa_e_recusado(usuario_teste):
    usuario_teste.cookies.clear()
    login = usuario_teste.post(
        "/api/app/login",
        json={"login": LOGIN_TESTE, "senha": SENHA_TESTE},
        headers={**TOKEN_HEADER, **ORIGIN_HEADER},
    )
    assert login.status_code == 200
    with pytest.raises(Exception):
        with usuario_teste.websocket_connect("/ws/dashboard", headers={"Origin": "http://atacante.example"}):
            pass
    usuario_teste.cookies.clear()


def test_websocket_nao_expoe_token_na_url_do_frontend():
    assert "ws/dashboard?token=" not in PAINEL_HTML
    assert "new WebSocket(`${proto}://${location.host}/ws/dashboard`)" in PAINEL_HTML


# ---------------------------------------------------------------------------
# BroadcastChannel: só sinaliza logout, nunca carrega dado sensível.
# ---------------------------------------------------------------------------


def test_broadcastchannel_so_transmite_evento_de_logout_sem_payload_sensivel():
    for arquivo in (PAINEL_HTML, PAINEL_OPERACIONAL_HTML):
        for chave_proibida in ("token", "senha", "perfil", "usuario", "cookie", security.APP_SESSION_COOKIE):
            for match_inicio in _ocorrencias(arquivo, "postMessage("):
                trecho = arquivo[match_inicio: match_inicio + 80]
                assert chave_proibida not in trecho.lower(), f"BroadcastChannel.postMessage parece incluir '{chave_proibida}': {trecho}"


def _ocorrencias(texto: str, alvo: str):
    inicio = 0
    while True:
        idx = texto.find(alvo, inicio)
        if idx == -1:
            return
        yield idx
        inicio = idx + 1
