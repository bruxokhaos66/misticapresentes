"""Testes de segurança que cobrem lacunas reais não exercitadas em
tests/fase1_security_test.py (que testa o pacote legado api/) nem em
tests/test_api_basica.py (que foca em exigir chave de API): CORS do
backend/main.py atual, rate limit de login, flags do cookie de sessão do
painel, mensagem genérica contra enumeração de usuário e a defesa contra
path traversal no endpoint de música ambiente.
"""
import importlib
import os

from fastapi.testclient import TestClient

TEST_API_KEY = "test-api-key"
os.environ.setdefault("MISTICA_SITE_API_KEY", TEST_API_KEY)
os.environ.setdefault("MISTICA_SYNC_KEY", TEST_API_KEY)

main = importlib.import_module("backend.main")
client = TestClient(main.app)
client.__enter__()


def test_cors_backend_main_nao_e_wildcard():
    cors_middleware = next(
        m for m in main.app.user_middleware if m.cls.__name__ == "CORSMiddleware"
    )
    origens = cors_middleware.kwargs.get("allow_origins", [])
    assert "*" not in origens
    assert origens, "CORS deveria ter uma lista explícita de origens permitidas"


def test_login_usuario_inexistente_e_senha_errada_tem_resposta_identica(monkeypatch):
    monkeypatch.delenv("MISTICA_DEFAULT_PANEL_PASSWORD", raising=False)
    ip = "203.0.113.10"

    resposta_usuario_inexistente = client.post(
        "/api/auth/login",
        json={"login": "usuario-que-nao-existe-xyz", "senha": "qualquer"},
        headers={"X-Forwarded-For": ip},
    )
    assert resposta_usuario_inexistente.status_code == 401
    assert resposta_usuario_inexistente.json()["detail"] == "Login ou senha inválidos"

    # Cria um usuário real via provisionamento padrão para comparar com senha errada.
    monkeypatch.setenv("MISTICA_DEFAULT_PANEL_PASSWORD", "senha-padrao-teste-123")
    client.post(
        "/api/auth/login",
        json={"login": "bruxo", "senha": "senha-padrao-teste-123"},
        headers={"X-Forwarded-For": ip},
    )
    resposta_senha_errada = client.post(
        "/api/auth/login",
        json={"login": "bruxo", "senha": "senha-errada"},
        headers={"X-Forwarded-For": ip},
    )
    assert resposta_senha_errada.status_code == 401
    assert resposta_senha_errada.json()["detail"] == resposta_usuario_inexistente.json()["detail"]


def test_login_bem_sucedido_seta_cookie_com_flags_seguras(monkeypatch):
    monkeypatch.setenv("MISTICA_DEFAULT_PANEL_PASSWORD", "senha-cookie-teste-456")
    ip = "203.0.113.20"

    resposta = client.post(
        "/api/auth/login",
        json={"login": "bruxa", "senha": "senha-cookie-teste-456"},
        headers={"X-Forwarded-For": ip},
    )
    assert resposta.status_code == 200
    cookie_header = resposta.headers.get("set-cookie", "")
    assert "mistica_painel_sessao=" in cookie_header
    assert "httponly" in cookie_header.lower()
    assert "samesite=lax" in cookie_header.lower()


def test_rota_protegida_sem_sessao_retorna_401():
    # O TestClient retém cookies entre chamadas; um teste anterior pode ter
    # feito login com sucesso, então limpamos o jar para simular um visitante
    # sem sessão de fato.
    client.cookies.clear()
    resposta = client.get("/api/auth/me")
    assert resposta.status_code == 401


def test_rate_limit_login_bloqueia_apos_o_limite(monkeypatch):
    monkeypatch.delenv("MISTICA_DEFAULT_PANEL_PASSWORD", raising=False)
    ip = "203.0.113.30"
    payload = {"login": "usuario-inexistente-rate-limit", "senha": "errada"}

    respostas = [
        client.post("/api/auth/login", json=payload, headers={"X-Forwarded-For": ip})
        for _ in range(11)
    ]

    assert all(r.status_code == 401 for r in respostas[:10])
    assert respostas[10].status_code == 429


def test_download_musica_local_ignora_tentativa_de_path_traversal():
    resposta = client.get("/api/uploads/musicas/arquivo-local/..%2f..%2f..%2f..%2fetc%2fpasswd")
    assert resposta.status_code in (400, 404)
    assert b"root:" not in resposta.content
