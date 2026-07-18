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
    # e quebre a execução seguinte. Variando os 3 últimos octetos (~16M
    # combinações) em vez de só o último (250), a chance de dois testes desta
    # mesma suíte sortearem o mesmo IP fica desprezível — com só o último
    # octeto já se viu colisão ocasional derrubar test_rate_limit_login_*.
    n = uuid.uuid4().int
    return f"203.{(n >> 16) % 256}.{(n >> 8) % 256}.{n % 256}"


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


def test_upload_imagem_produto_rejeita_conteudo_que_nao_e_imagem_real():
    # O content-type "image/png" vem do navegador do cliente e pode ser
    # forjado; texto puro disfarçado de PNG deve ser rejeitado mesmo
    # apresentando o header correto.
    resposta = client.post(
        "/api/uploads/produtos",
        files={"arquivo": ("produto.png", b"nao sou uma imagem de verdade", "image/png")},
        headers={"X-Mistica-Api-Key": TEST_API_KEY},
    )
    assert resposta.status_code == 400


def test_upload_musica_ambiente_rejeita_conteudo_que_nao_e_audio_real():
    resposta = client.post(
        "/api/uploads/musicas",
        files={"arquivo": ("ambiente.mp3", b"nao sou um mp3 de verdade", "audio/mpeg")},
        data={"nome_base": "teste-invalido"},
        headers={"X-Mistica-Api-Key": TEST_API_KEY},
    )
    assert resposta.status_code == 400


def test_resumo_acessos_site_exige_sessao_ou_chave_api():
    client.cookies.clear()
    resposta_sem_credencial = client.get("/api/site/acessos/resumo")
    assert resposta_sem_credencial.status_code == 401

    resposta_com_chave = client.get(
        "/api/site/acessos/resumo", headers={"X-Mistica-Api-Key": TEST_API_KEY}
    )
    assert resposta_com_chave.status_code == 200


def test_estoque_baixo_exige_sessao_ou_chave_api():
    # Dado interno (quantidade em estoque e estoque mínimo por produto) --
    # antes servido sem nenhuma credencial em GET /api/estoque/baixo.
    client.cookies.clear()
    resposta_sem_credencial = client.get("/api/estoque/baixo")
    assert resposta_sem_credencial.status_code == 401

    resposta_com_chave = client.get(
        "/api/estoque/baixo", headers={"X-Mistica-Api-Key": TEST_API_KEY}
    )
    assert resposta_com_chave.status_code == 200


def test_mutacao_com_sessao_de_cookie_e_origem_desconhecida_e_bloqueada(monkeypatch):
    monkeypatch.delenv("MISTICA_DEFAULT_PANEL_PASSWORD", raising=False)
    login = f"usuario-csrf-{uuid.uuid4().hex[:8]}"
    senha = "senha-correta-789"
    criar_usuario_teste(login, senha)

    resposta_login = client.post(
        "/api/auth/login",
        json={"login": login, "senha": senha},
        headers={"X-Forwarded-For": ip_unico()},
    )
    assert resposta_login.status_code == 200

    resposta = client.post(
        "/api/uploads/produtos",
        files={"arquivo": ("produto.png", b"nao importa, deve bloquear antes", "image/png")},
        headers={"Origin": "https://site-malicioso.exemplo"},
    )
    assert resposta.status_code == 403
    client.cookies.clear()


def criar_aluno_com_sessao(*, slug_com_acesso: str | None = None) -> str:
    """Cria um aluno de teste e devolve o token de sessão dele. Se
    slug_com_acesso for informado, libera o acesso a esse curso."""
    from backend.aluno_auth import garantir_tabelas_alunos
    from backend.database import conectar

    email = f"aluno-teste-{uuid.uuid4().hex[:8]}@exemplo.com"
    token = uuid.uuid4().hex
    agora = "2026-01-01 00:00:00"
    expira = "2099-01-01 00:00:00"
    with conectar() as conn:
        garantir_tabelas_alunos(conn)
        cur = conn.execute(
            "INSERT INTO alunos (nome, email, criado_em) VALUES (?,?,?)",
            ("Aluno Teste", email, agora),
        )
        aluno_id = int(cur.lastrowid)
        conn.execute(
            "INSERT INTO alunos_sessoes (token, aluno_id, criada_em, expira_em) VALUES (?,?,?,?)",
            (token, aluno_id, agora, expira),
        )
        if slug_com_acesso:
            conn.execute(
                "INSERT INTO alunos_cursos (aluno_id, slug, liberado_em) VALUES (?,?,?)",
                (aluno_id, slug_com_acesso, agora),
            )
    return token


def test_material_de_curso_pago_nao_e_servido_pelo_mount_estatico_publico():
    from backend.upload_routes import CURSOS_DIR

    CURSOS_DIR.mkdir(parents=True, exist_ok=True)
    nome = f"material-teste-{uuid.uuid4().hex[:8]}.pdf"
    (CURSOS_DIR / nome).write_bytes(b"conteudo pago de teste")
    try:
        client.cookies.clear()
        resposta = client.get(f"/uploads/cursos/{nome}")
        assert resposta.status_code == 401
    finally:
        (CURSOS_DIR / nome).unlink(missing_ok=True)


def test_material_de_curso_pago_exige_aluno_com_acesso_liberado():
    from backend.database import conectar
    from backend.course_routes import garantir_tabela_cursos
    from backend.upload_routes import CURSOS_DIR

    CURSOS_DIR.mkdir(parents=True, exist_ok=True)
    nome = f"material-teste-{uuid.uuid4().hex[:8]}.pdf"
    (CURSOS_DIR / nome).write_bytes(b"conteudo pago de teste")
    slug = f"curso-teste-{uuid.uuid4().hex[:8]}"
    url_arquivo = f"/uploads/cursos/{nome}"

    try:
        with conectar() as conn:
            garantir_tabela_cursos(conn)
            conn.execute(
                "INSERT INTO cursos_materiais (titulo, categoria, tipo, descricao, url, criado_em) VALUES (?,?,?,?,?,?)",
                ("Material Teste", slug, "pdf", None, url_arquivo, "2026-01-01 00:00:00"),
            )

        client.cookies.clear()

        # aluno logado mas sem acesso liberado a este curso -> 403
        token_sem_acesso = criar_aluno_com_sessao()
        client.cookies.set("mistica_aluno_sessao", token_sem_acesso)
        resposta_negada = client.get(url_arquivo)
        assert resposta_negada.status_code == 403
        client.cookies.clear()

        # aluno logado com acesso liberado a este curso -> 200
        token_com_acesso = criar_aluno_com_sessao(slug_com_acesso=slug)
        client.cookies.set("mistica_aluno_sessao", token_com_acesso)
        resposta_liberada = client.get(url_arquivo)
        assert resposta_liberada.status_code == 200
        assert resposta_liberada.content == b"conteudo pago de teste"
        client.cookies.clear()

        # chave de API do painel também deve funcionar (integrações servidor-a-servidor)
        resposta_api_key = client.get(url_arquivo, headers={"X-Mistica-Api-Key": TEST_API_KEY})
        assert resposta_api_key.status_code == 200
    finally:
        (CURSOS_DIR / nome).unlink(missing_ok=True)


def test_headers_de_seguranca_incluem_csp_e_permissions_policy():
    resposta = client.get("/api/health")
    assert resposta.headers.get("content-security-policy") == "default-src 'none'; frame-ancestors 'none'"
    assert "geolocation=()" in resposta.headers.get("permissions-policy", "")
    assert resposta.headers.get("cross-origin-opener-policy") == "same-origin"
    assert resposta.headers.get("origin-agent-cluster") == "?1"


def test_login_admin_padrao_criado_via_env_var_admin_login(monkeypatch):
    # MISTICA_ADMIN_LOGIN permite renomear o usuário administrativo
    # provisionado automaticamente; sem a variável, o comportamento
    # (login "admin") continua igual ao de antes desta mudança.
    from backend.database import conectar

    login_customizado = f"admin-teste-{uuid.uuid4().hex[:8]}"
    monkeypatch.setenv("MISTICA_ADMIN_LOGIN", login_customizado)
    monkeypatch.setenv("MISTICA_ADMIN_PASSWORD", "Senha-Forte-123!")
    try:
        main.garantir_admin_api()
        with conectar() as conn:
            usuario = conn.execute(
                "SELECT login, perfil, ativo FROM usuarios WHERE login=?", (login_customizado,)
            ).fetchone()
        assert usuario is not None
        assert usuario["perfil"] == "adm"
        assert usuario["ativo"] == 1
    finally:
        with conectar() as conn:
            conn.execute("DELETE FROM usuarios WHERE login=?", (login_customizado,))


def test_imagem_de_produto_continua_publica_no_mount_estatico():
    from backend.upload_routes import UPLOAD_DIR

    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    nome = f"produto-teste-{uuid.uuid4().hex[:8]}.png"
    (UPLOAD_DIR / nome).write_bytes(b"imagem de produto de teste")
    try:
        client.cookies.clear()
        resposta = client.get(f"/uploads/produtos/{nome}")
        assert resposta.status_code == 200
        assert resposta.content == b"imagem de produto de teste"
    finally:
        (UPLOAD_DIR / nome).unlink(missing_ok=True)
