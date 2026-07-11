"""Testes de segurança que cobrem lacunas reais não exercitadas em
tests/fase1_security_test.py (que testa o pacote legado api/) nem em
tests/test_api_basica.py (que foca em exigir chave de API): CORS do
backend/main.py atual, rate limit de login, flags do cookie de sessão do
painel, mensagem genérica contra enumeração de usuário e a defesa contra
path traversal no endpoint de música ambiente.
"""
import importlib
import os
import uuid

from fastapi.testclient import TestClient

TEST_API_KEY = "test-api-key"
os.environ.setdefault("MISTICA_SITE_API_KEY", TEST_API_KEY)
os.environ.setdefault("MISTICA_SYNC_KEY", TEST_API_KEY)

main = importlib.import_module("backend.main")
client = TestClient(main.app)
client.__enter__()


def ip_unico() -> str:
    # O banco de tentativas de login (painel_login_tentativas) é persistente
    # entre execuções da suite (mesmo arquivo real, sem isolamento por
    # tmp_path), e o bloqueio por força bruta é contado por login+IP. Um IP
    # novo a cada teste evita que uma execução anterior deixe o IP bloqueado
    # e quebre a execução seguinte.
    return f"203.0.113.{uuid.uuid4().int % 250 + 1}"


def criar_usuario_teste(login: str, senha: str, perfil: str = "adm") -> None:
    """Semeia um usuário direto no banco com senha conhecida, sem depender do
    provisionamento automático de bruxo/bruxa (que exige MISTICA_DEFAULT_PANEL_PASSWORD
    e é compartilhado entre execuções da suite)."""
    from config import hash_password_pbkdf2
    from backend.database import conectar

    salt = "teste-seguranca-reforcada"
    senha_hash = hash_password_pbkdf2(senha, salt.encode("utf-8"))
    with conectar() as conn:
        conn.execute(
            """
            INSERT INTO usuarios (nome, login, senha_hash, senha_salt, perfil, ativo)
            VALUES (?,?,?,?,?,1)
            ON CONFLICT(login) DO UPDATE SET senha_hash=excluded.senha_hash, senha_salt=excluded.senha_salt, ativo=1
            """,
            (login, login, senha_hash, salt, perfil),
        )


def test_cors_backend_main_nao_e_wildcard():
    cors_middleware = next(
        m for m in main.app.user_middleware if m.cls.__name__ == "CORSMiddleware"
    )
    origens = cors_middleware.kwargs.get("allow_origins", [])
    assert "*" not in origens
    assert origens, "CORS deveria ter uma lista explícita de origens permitidas"


def test_login_usuario_inexistente_e_senha_errada_tem_resposta_identica(monkeypatch):
    monkeypatch.delenv("MISTICA_DEFAULT_PANEL_PASSWORD", raising=False)
    login_existente = f"usuario-teste-{uuid.uuid4().hex[:8]}"
    criar_usuario_teste(login_existente, "senha-correta-123")

    resposta_usuario_inexistente = client.post(
        "/api/auth/login",
        json={"login": f"usuario-que-nao-existe-{uuid.uuid4().hex[:8]}", "senha": "qualquer"},
        headers={"X-Forwarded-For": ip_unico()},
    )
    assert resposta_usuario_inexistente.status_code == 401
    assert resposta_usuario_inexistente.json()["detail"] == "Login ou senha inválidos"

    resposta_senha_errada = client.post(
        "/api/auth/login",
        json={"login": login_existente, "senha": "senha-errada"},
        headers={"X-Forwarded-For": ip_unico()},
    )
    assert resposta_senha_errada.status_code == 401
    assert resposta_senha_errada.json()["detail"] == resposta_usuario_inexistente.json()["detail"]


def test_login_bem_sucedido_seta_cookie_com_flags_seguras(monkeypatch):
    monkeypatch.delenv("MISTICA_DEFAULT_PANEL_PASSWORD", raising=False)
    login = f"usuario-cookie-{uuid.uuid4().hex[:8]}"
    senha = "senha-correta-456"
    criar_usuario_teste(login, senha)

    resposta = client.post(
        "/api/auth/login",
        json={"login": login, "senha": senha},
        headers={"X-Forwarded-For": ip_unico()},
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
    # Além do rate limit por IP em backend/rate_limit.py (10/60s), o painel tem
    # um bloqueio por força bruta em backend/panel_sessions.py: a tentativa que
    # atinge LOGIN_MAX_TENTATIVAS falhas na janela já responde 429 (em vez do
    # 401 de "credenciais inválidas"), e as tentativas seguintes continuam
    # bloqueadas.
    from backend.panel_sessions import LOGIN_MAX_TENTATIVAS

    monkeypatch.delenv("MISTICA_DEFAULT_PANEL_PASSWORD", raising=False)
    ip = ip_unico()
    payload = {"login": f"usuario-rate-limit-{uuid.uuid4().hex[:8]}", "senha": "errada"}

    respostas = [
        client.post("/api/auth/login", json=payload, headers={"X-Forwarded-For": ip})
        for _ in range(LOGIN_MAX_TENTATIVAS + 2)
    ]

    assert all(r.status_code == 401 for r in respostas[: LOGIN_MAX_TENTATIVAS - 1])
    assert all(r.status_code == 429 for r in respostas[LOGIN_MAX_TENTATIVAS - 1 :])


def test_download_musica_local_ignora_tentativa_de_path_traversal():
    resposta = client.get("/api/uploads/musicas/arquivo-local/..%2f..%2f..%2f..%2fetc%2fpasswd")
    assert resposta.status_code in (400, 404)
    assert b"root:" not in resposta.content
