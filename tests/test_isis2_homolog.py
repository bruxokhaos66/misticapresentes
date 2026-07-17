"""Isis 2.0 — Homologação Controlada.

Cobre a autorização real de servidor por trás de GET /api/isis2/homolog-config
e a administração da allowlist fechada (backend/isis2_homolog.py):

- produção continua desligada por padrão (interruptor global e allowlist
  vazios são o estado inicial da tabela, sem nenhuma ação);
- query string / header / cookie forjado não contornam a autorização;
- só sessão admin válida OU sessão de aluno autorizado (allowlist) com o
  interruptor global ligado habilita a Isis 2.0;
- logout, sessão expirada e revogação desativam imediatamente;
- qualquer erro leva a "desativado" (fail closed), nunca a "ativado";
- os endpoints de administração da allowlist exigem perfil admin e sofrem a
  mesma defesa CSRF (Origin) que as demais rotas mutáveis do painel.
"""
import importlib
import os
import uuid

from fastapi.testclient import TestClient

TEST_API_KEY = "test-api-key-isis2-homolog"
ORIGIN_HEADER = {"Origin": "http://localhost:3000"}
os.environ.setdefault("MISTICA_SITE_API_KEY", TEST_API_KEY)
os.environ.setdefault("MISTICA_SYNC_KEY", TEST_API_KEY)

main = importlib.import_module("backend.main")
isis2_homolog = importlib.import_module("backend.isis2_homolog")
client = TestClient(main.app)
client.__enter__()

CONFIG_DESATIVADA = {"enabled": False, "escola": False, "refinamento": False, "homologacao": False}
CONFIG_ATIVADA = {"enabled": True, "escola": True, "refinamento": True, "homologacao": True}


def ip_unico() -> str:
    n = uuid.uuid4().int
    return f"198.{(n >> 16) % 256}.{(n >> 8) % 256}.{n % 256}"


def criar_admin_com_sessao() -> None:
    """Cria um usuário admin e faz login via TestClient (o jar do client fica
    com o cookie mistica_painel_sessao); devolve o login para eventual reuso."""
    from config import hash_password_pbkdf2
    from backend.database import conectar

    login = f"admin-isis2-homolog-{uuid.uuid4().hex[:8]}"
    senha = "senha-forte-Teste123!"
    salt = "teste-isis2-homolog"
    senha_hash = hash_password_pbkdf2(senha, salt.encode("utf-8"))
    with conectar() as conn:
        conn.execute(
            "INSERT INTO usuarios (nome, login, senha_hash, senha_salt, perfil, ativo) VALUES (?,?,?,?,?,1)",
            (login, login, senha_hash, salt, "adm"),
        )
    resposta = client.post(
        "/api/auth/login",
        json={"login": login, "senha": senha},
        headers={"X-Forwarded-For": ip_unico()},
    )
    assert resposta.status_code == 200, resposta.text
    return login


def criar_aluno_com_sessao() -> tuple[int, str]:
    from backend.aluno_auth import garantir_tabelas_alunos
    from backend.database import conectar

    email = f"aluno-isis2-homolog-{uuid.uuid4().hex[:8]}@exemplo.com"
    token = uuid.uuid4().hex
    agora = "2026-01-01 00:00:00"
    expira = "2099-01-01 00:00:00"
    with conectar() as conn:
        garantir_tabelas_alunos(conn)
        cur = conn.execute(
            "INSERT INTO alunos (nome, email, criado_em) VALUES (?,?,?)",
            ("Aluna Teste Homolog", email, agora),
        )
        aluno_id = int(cur.lastrowid)
        conn.execute(
            "INSERT INTO alunos_sessoes (token, aluno_id, criada_em, expira_em) VALUES (?,?,?,?)",
            (token, aluno_id, agora, expira),
        )
    return aluno_id, token


def limpar_estado_homolog() -> None:
    from backend.database import conectar

    with conectar() as conn:
        isis2_homolog.garantir_tabelas_isis2_homolog(conn)
        conn.execute("DELETE FROM isis2_homolog_testers")
        conn.execute("DELETE FROM isis2_homolog_config")


# ---------------------------------------------------------------------------
# 1. Estado inicial / produção: nada configurado -> desligado.
# ---------------------------------------------------------------------------


def test_sem_nenhuma_configuracao_fica_desligado():
    limpar_estado_homolog()
    client.cookies.clear()
    resposta = client.get("/api/isis2/homolog-config")
    assert resposta.status_code == 200
    assert resposta.json() == CONFIG_DESATIVADA


def test_visitante_anonimo_fica_desligado_mesmo_com_interruptor_ligado():
    limpar_estado_homolog()
    from backend.database import conectar

    with conectar() as conn:
        isis2_homolog.garantir_tabelas_isis2_homolog(conn)
        isis2_homolog._definir_ativo(conn, True)
    client.cookies.clear()
    resposta = client.get("/api/isis2/homolog-config")
    assert resposta.status_code == 200
    assert resposta.json() == CONFIG_DESATIVADA


# ---------------------------------------------------------------------------
# 2. Query string / header / cookie forjado não contornam.
# ---------------------------------------------------------------------------


def test_query_string_nao_ativa():
    limpar_estado_homolog()
    from backend.database import conectar

    with conectar() as conn:
        isis2_homolog.garantir_tabelas_isis2_homolog(conn)
        isis2_homolog._definir_ativo(conn, True)
    client.cookies.clear()
    resposta = client.get("/api/isis2/homolog-config?isis2=true&enabled=true&homolog=1")
    assert resposta.json() == CONFIG_DESATIVADA


def test_header_customizado_nao_ativa():
    limpar_estado_homolog()
    from backend.database import conectar

    with conectar() as conn:
        isis2_homolog.garantir_tabelas_isis2_homolog(conn)
        isis2_homolog._definir_ativo(conn, True)
    client.cookies.clear()
    resposta = client.get(
        "/api/isis2/homolog-config",
        headers={"X-Isis2-Homolog": "true", "X-Debug-Enable-Isis2": "1"},
    )
    assert resposta.json() == CONFIG_DESATIVADA


def test_cookie_de_sessao_forjado_nao_ativa():
    limpar_estado_homolog()
    from backend.database import conectar

    with conectar() as conn:
        isis2_homolog.garantir_tabelas_isis2_homolog(conn)
        isis2_homolog._definir_ativo(conn, True)
    client.cookies.clear()
    resposta = client.get(
        "/api/isis2/homolog-config",
        cookies={"mistica_painel_sessao": "token-inventado-que-nao-existe-no-banco"},
    )
    assert resposta.json() == CONFIG_DESATIVADA
    client.cookies.clear()


# ---------------------------------------------------------------------------
# 3. Admin autenticado + interruptor ligado -> ativado. Interruptor desligado
#    -> mesmo admin autenticado continua desligado.
# ---------------------------------------------------------------------------


def test_admin_autenticado_com_interruptor_ligado_ativa():
    limpar_estado_homolog()
    from backend.database import conectar

    with conectar() as conn:
        isis2_homolog.garantir_tabelas_isis2_homolog(conn)
        isis2_homolog._definir_ativo(conn, True)
    client.cookies.clear()
    criar_admin_com_sessao()
    resposta = client.get("/api/isis2/homolog-config")
    assert resposta.json() == CONFIG_ATIVADA
    client.cookies.clear()


def test_admin_autenticado_com_interruptor_desligado_fica_desligado():
    limpar_estado_homolog()
    client.cookies.clear()
    criar_admin_com_sessao()
    resposta = client.get("/api/isis2/homolog-config")
    assert resposta.json() == CONFIG_DESATIVADA
    client.cookies.clear()


def test_logout_do_admin_desativa_imediatamente():
    limpar_estado_homolog()
    from backend.database import conectar

    with conectar() as conn:
        isis2_homolog.garantir_tabelas_isis2_homolog(conn)
        isis2_homolog._definir_ativo(conn, True)
    client.cookies.clear()
    criar_admin_com_sessao()
    assert client.get("/api/isis2/homolog-config").json() == CONFIG_ATIVADA

    resposta_logout = client.post("/api/auth/logout")
    assert resposta_logout.status_code == 200
    resposta_depois = client.get("/api/isis2/homolog-config")
    assert resposta_depois.json() == CONFIG_DESATIVADA


# ---------------------------------------------------------------------------
# 4. Aluno: só ativa se estiver na allowlist E o interruptor estiver ligado.
# ---------------------------------------------------------------------------


def test_aluno_fora_da_allowlist_fica_desligado():
    limpar_estado_homolog()
    from backend.database import conectar

    with conectar() as conn:
        isis2_homolog.garantir_tabelas_isis2_homolog(conn)
        isis2_homolog._definir_ativo(conn, True)
    client.cookies.clear()
    _aluno_id, token = criar_aluno_com_sessao()
    resposta = client.get("/api/isis2/homolog-config", cookies={"mistica_aluno_sessao": token})
    assert resposta.json() == CONFIG_DESATIVADA


def test_aluno_na_allowlist_ativa():
    limpar_estado_homolog()
    from backend.database import conectar

    with conectar() as conn:
        isis2_homolog.garantir_tabelas_isis2_homolog(conn)
        isis2_homolog._definir_ativo(conn, True)
    aluno_id, token = criar_aluno_com_sessao()
    with conectar() as conn:
        conn.execute(
            "INSERT INTO isis2_homolog_testers (aluno_id, adicionado_por, adicionado_em) VALUES (?,?,?)",
            (aluno_id, "teste", "2026-01-01 00:00:00"),
        )
    resposta = client.get("/api/isis2/homolog-config", cookies={"mistica_aluno_sessao": token})
    assert resposta.json() == CONFIG_ATIVADA


def test_aluno_na_allowlist_mas_interruptor_desligado_fica_desligado():
    limpar_estado_homolog()
    aluno_id, token = criar_aluno_com_sessao()
    from backend.database import conectar

    with conectar() as conn:
        isis2_homolog.garantir_tabelas_isis2_homolog(conn)
        conn.execute(
            "INSERT INTO isis2_homolog_testers (aluno_id, adicionado_por, adicionado_em) VALUES (?,?,?)",
            (aluno_id, "teste", "2026-01-01 00:00:00"),
        )
    resposta = client.get("/api/isis2/homolog-config", cookies={"mistica_aluno_sessao": token})
    assert resposta.json() == CONFIG_DESATIVADA


def test_sessao_de_aluno_expirada_fica_desligada():
    limpar_estado_homolog()
    from backend.database import conectar
    from backend.aluno_auth import garantir_tabelas_alunos

    with conectar() as conn:
        isis2_homolog.garantir_tabelas_isis2_homolog(conn)
        isis2_homolog._definir_ativo(conn, True)
        garantir_tabelas_alunos(conn)
        cur = conn.execute(
            "INSERT INTO alunos (nome, email, criado_em) VALUES (?,?,?)",
            ("Aluna Expirada", f"expirada-{uuid.uuid4().hex[:8]}@exemplo.com", "2020-01-01 00:00:00"),
        )
        aluno_id = int(cur.lastrowid)
        token = uuid.uuid4().hex
        conn.execute(
            "INSERT INTO alunos_sessoes (token, aluno_id, criada_em, expira_em) VALUES (?,?,?,?)",
            (token, aluno_id, "2020-01-01 00:00:00", "2020-01-02 00:00:00"),
        )
        conn.execute(
            "INSERT INTO isis2_homolog_testers (aluno_id, adicionado_por, adicionado_em) VALUES (?,?,?)",
            (aluno_id, "teste", "2020-01-01 00:00:00"),
        )
    resposta = client.get("/api/isis2/homolog-config", cookies={"mistica_aluno_sessao": token})
    assert resposta.json() == CONFIG_DESATIVADA


def test_troca_de_conta_revalida_autorizacao():
    """Aluno A está na allowlist; aluno B não. Reaproveitar a mesma requisição
    do gate com o cookie de B (troca de conta) não herda a autorização de A."""
    limpar_estado_homolog()
    from backend.database import conectar

    with conectar() as conn:
        isis2_homolog.garantir_tabelas_isis2_homolog(conn)
        isis2_homolog._definir_ativo(conn, True)
    aluno_a, token_a = criar_aluno_com_sessao()
    aluno_b, token_b = criar_aluno_com_sessao()
    with conectar() as conn:
        conn.execute(
            "INSERT INTO isis2_homolog_testers (aluno_id, adicionado_por, adicionado_em) VALUES (?,?,?)",
            (aluno_a, "teste", "2026-01-01 00:00:00"),
        )
    assert client.get("/api/isis2/homolog-config", cookies={"mistica_aluno_sessao": token_a}).json() == CONFIG_ATIVADA
    assert client.get("/api/isis2/homolog-config", cookies={"mistica_aluno_sessao": token_b}).json() == CONFIG_DESATIVADA


# ---------------------------------------------------------------------------
# 5. Falha da API / estado inesperado -> desligado, nunca exceção 500.
# ---------------------------------------------------------------------------


def test_erro_interno_ao_avaliar_configuracao_fica_desligado(monkeypatch):
    limpar_estado_homolog()

    def _explode(*args, **kwargs):
        raise RuntimeError("falha simulada de infraestrutura")

    monkeypatch.setattr(isis2_homolog, "homolog_ativo", _explode)
    client.cookies.clear()
    resposta = client.get("/api/isis2/homolog-config")
    assert resposta.status_code == 200
    assert resposta.json() == CONFIG_DESATIVADA


# ---------------------------------------------------------------------------
# 6. Métodos GET-only para consulta de configuração.
# ---------------------------------------------------------------------------


def test_config_so_aceita_get():
    for metodo in ("post", "put", "delete", "patch"):
        resposta = getattr(client, metodo)("/api/isis2/homolog-config")
        assert resposta.status_code in (404, 405)


# ---------------------------------------------------------------------------
# 7. Administração da allowlist: exige perfil admin.
# ---------------------------------------------------------------------------


def test_endpoints_administrativos_exigem_sessao_admin():
    client.cookies.clear()
    assert client.get("/api/isis2/homolog-testers").status_code == 401
    assert client.get("/api/isis2/homolog/estado").status_code == 401
    assert client.post("/api/isis2/homolog/ativar").status_code == 401
    assert client.post("/api/isis2/homolog/desativar").status_code == 401
    assert client.post("/api/isis2/homolog-testers/1").status_code == 401
    assert client.delete("/api/isis2/homolog-testers/1").status_code == 401
    assert client.post("/api/isis2/homolog-testers/revogar-todos").status_code == 401
    assert client.get("/api/isis2/homolog/buscar-alunos?q=ab").status_code == 401


def test_usuario_comum_aluno_nao_administra():
    """Sessão de aluno (não admin) não passa em exigir_perfil('adm') --
    mesmo um aluno já autorizado como testador não pode se auto-promover a
    administrador da homologação."""
    limpar_estado_homolog()
    _aluno_id, token = criar_aluno_com_sessao()
    resposta = client.get(
        "/api/isis2/homolog-testers", cookies={"mistica_aluno_sessao": token}
    )
    assert resposta.status_code == 401
    client.cookies.clear()


def test_admin_consulta_estado():
    limpar_estado_homolog()
    client.cookies.clear()
    criar_admin_com_sessao()
    resposta = client.get("/api/isis2/homolog/estado")
    assert resposta.status_code == 200
    assert resposta.json() == {"ativo": False, "total_testadores": 0}
    client.cookies.clear()


def test_adicionar_testador_com_id_inexistente_devolve_404():
    limpar_estado_homolog()
    client.cookies.clear()
    criar_admin_com_sessao()
    resposta = client.post("/api/isis2/homolog-testers/999999999", headers=ORIGIN_HEADER)
    assert resposta.status_code == 404
    client.cookies.clear()


def test_conta_com_matricula_suspensa_pode_ser_buscada_e_autorizada():
    """Suspensão (alunos_cursos.suspenso) é por curso, não uma flag global
    do aluno -- a homologação é uma autorização independente da matrícula
    (mesmo um aluno sem nenhum curso ativo pode ser testador). Confirma que
    a busca/inclusão não quebra nem se comporta de forma diferente para uma
    conta com curso suspenso."""
    limpar_estado_homolog()
    from backend.database import conectar
    from backend.aluno_auth import garantir_tabelas_alunos

    client.cookies.clear()
    criar_admin_com_sessao()
    aluno_id, token = criar_aluno_com_sessao()
    with conectar() as conn:
        garantir_tabelas_alunos(conn)
        conn.execute(
            "INSERT INTO alunos_cursos (aluno_id, slug, liberado_em, suspenso) VALUES (?,?,?,1)",
            (aluno_id, "xamanismo-introducao", "2026-01-01 00:00:00"),
        )
        email_aluno = conn.execute("SELECT email FROM alunos WHERE id=?", (aluno_id,)).fetchone()["email"]

    # Busca pelo e-mail (único por teste, ao contrário do nome genérico
    # compartilhado por criar_aluno_com_sessao) -- evita que o LIMIT 20 da
    # busca corte o resultado quando a suíte já acumulou muitos alunos com
    # o mesmo nome "Aluna Teste Homolog".
    resposta_busca = client.get(f"/api/isis2/homolog/buscar-alunos?q={email_aluno}")
    assert resposta_busca.status_code == 200
    assert any(item["aluno_id"] == aluno_id for item in resposta_busca.json())

    resposta_add = client.post(f"/api/isis2/homolog-testers/{aluno_id}", headers=ORIGIN_HEADER)
    assert resposta_add.status_code == 200

    client.post("/api/isis2/homolog/ativar", headers=ORIGIN_HEADER)
    client.cookies.clear()
    resposta_config = client.get("/api/isis2/homolog-config", cookies={"mistica_aluno_sessao": token})
    assert resposta_config.json() == CONFIG_ATIVADA


def test_sessao_admin_expirada_nao_administra():
    limpar_estado_homolog()
    from backend.database import conectar

    login = criar_admin_com_sessao()
    with conectar() as conn:
        conn.execute(
            "UPDATE painel_sessoes SET expira_em='2000-01-01 00:00:00' WHERE login=?",
            (login,),
        )
    resposta = client.get("/api/isis2/homolog/estado")
    assert resposta.status_code == 401
    client.cookies.clear()


def test_busca_termo_curto_nao_devolve_lista(monkeypatch):
    limpar_estado_homolog()
    client.cookies.clear()
    criar_admin_com_sessao()
    resposta = client.get("/api/isis2/homolog/buscar-alunos?q=a")
    assert resposta.status_code == 200
    assert resposta.json() == []
    client.cookies.clear()


def test_busca_por_nome_ou_email_nunca_quebra_com_payload_de_xss():
    """O backend devolve o nome/e-mail crus em JSON (nunca HTML) -- a
    sanitização acontece no render do painel (isis2-homolog-admin.js). Aqui
    só confirmamos que o payload malicioso não quebra a busca nem é alterado
    silenciosamente pelo servidor."""
    limpar_estado_homolog()
    from backend.database import conectar
    from backend.aluno_auth import garantir_tabelas_alunos

    client.cookies.clear()
    criar_admin_com_sessao()
    nome_malicioso = '<img src=x onerror="window.__xss=1">Aluna XSS'
    with conectar() as conn:
        garantir_tabelas_alunos(conn)
        cur = conn.execute(
            "INSERT INTO alunos (nome, email, criado_em) VALUES (?,?,?)",
            (nome_malicioso, f"xss-{uuid.uuid4().hex[:8]}@exemplo.com", "2026-01-01 00:00:00"),
        )
        aluno_id = int(cur.lastrowid)

    resposta = client.get("/api/isis2/homolog/buscar-alunos?q=Aluna XSS")
    assert resposta.status_code == 200
    encontrado = next(item for item in resposta.json() if item["aluno_id"] == aluno_id)
    assert encontrado["nome"] == nome_malicioso
    client.cookies.clear()


def test_falha_ao_carregar_estado_nunca_reporta_ativo(monkeypatch):
    """Mesmo com sessão admin válida, se homolog_ativo() explodir, o
    endpoint de estado responde 200 com ativo=False (fail-safe) -- nunca
    deixa escapar uma exceção que o painel (ou um script mais simples)
    pudesse interpretar como sucesso/ativo por omissão."""
    limpar_estado_homolog()
    client.cookies.clear()
    criar_admin_com_sessao()

    def _explode(*args, **kwargs):
        raise RuntimeError("falha simulada de infraestrutura")

    monkeypatch.setattr(isis2_homolog, "homolog_ativo", _explode)
    resposta = client.get("/api/isis2/homolog/estado")
    assert resposta.status_code == 200
    assert resposta.json() == {"ativo": False, "total_testadores": 0}
    client.cookies.clear()


def test_admin_gerencia_allowlist_fim_a_fim():
    limpar_estado_homolog()
    client.cookies.clear()
    criar_admin_com_sessao()
    aluno_id, token_aluno = criar_aluno_com_sessao()

    resposta_ativar = client.post("/api/isis2/homolog/ativar", headers=ORIGIN_HEADER)
    assert resposta_ativar.status_code == 200
    assert resposta_ativar.json()["ativo"] is True

    resposta_add = client.post(f"/api/isis2/homolog-testers/{aluno_id}", headers=ORIGIN_HEADER)
    assert resposta_add.status_code == 200

    resposta_lista = client.get("/api/isis2/homolog-testers")
    assert resposta_lista.status_code == 200
    ids = [item["aluno_id"] for item in resposta_lista.json()]
    assert aluno_id in ids

    resposta_estado = client.get("/api/isis2/homolog/estado")
    assert resposta_estado.json() == {"ativo": True, "total_testadores": 1}

    client.cookies.clear()
    assert client.get("/api/isis2/homolog-config", cookies={"mistica_aluno_sessao": token_aluno}).json() == CONFIG_ATIVADA

    criar_admin_com_sessao()
    resposta_remove = client.delete(f"/api/isis2/homolog-testers/{aluno_id}", headers=ORIGIN_HEADER)
    assert resposta_remove.status_code == 200
    client.cookies.clear()
    assert client.get("/api/isis2/homolog-config", cookies={"mistica_aluno_sessao": token_aluno}).json() == CONFIG_DESATIVADA


def test_botao_de_desligamento_imediato_desativa_todos_sem_novo_deploy():
    limpar_estado_homolog()
    client.cookies.clear()
    criar_admin_com_sessao()
    aluno_id, token_aluno = criar_aluno_com_sessao()
    client.post("/api/isis2/homolog/ativar", headers=ORIGIN_HEADER)
    client.post(f"/api/isis2/homolog-testers/{aluno_id}", headers=ORIGIN_HEADER)
    client.cookies.clear()
    assert client.get("/api/isis2/homolog-config", cookies={"mistica_aluno_sessao": token_aluno}).json() == CONFIG_ATIVADA

    criar_admin_com_sessao()
    resposta_desligar = client.post("/api/isis2/homolog/desativar", headers=ORIGIN_HEADER)
    assert resposta_desligar.status_code == 200
    assert resposta_desligar.json()["ativo"] is False
    client.cookies.clear()

    assert client.get("/api/isis2/homolog-config", cookies={"mistica_aluno_sessao": token_aluno}).json() == CONFIG_DESATIVADA
    assert client.get("/api/isis2/homolog-config").json() == CONFIG_DESATIVADA


def test_revogar_todos_remove_a_allowlist_inteira():
    limpar_estado_homolog()
    client.cookies.clear()
    criar_admin_com_sessao()
    client.post("/api/isis2/homolog/ativar", headers=ORIGIN_HEADER)
    aluno_1, token_1 = criar_aluno_com_sessao()
    aluno_2, token_2 = criar_aluno_com_sessao()
    client.post(f"/api/isis2/homolog-testers/{aluno_1}", headers=ORIGIN_HEADER)
    client.post(f"/api/isis2/homolog-testers/{aluno_2}", headers=ORIGIN_HEADER)

    resposta = client.post("/api/isis2/homolog-testers/revogar-todos", headers=ORIGIN_HEADER)
    assert resposta.status_code == 200

    client.cookies.clear()
    assert client.get("/api/isis2/homolog-config", cookies={"mistica_aluno_sessao": token_1}).json() == CONFIG_DESATIVADA
    assert client.get("/api/isis2/homolog-config", cookies={"mistica_aluno_sessao": token_2}).json() == CONFIG_DESATIVADA


def test_mutacao_administrativa_com_origem_desconhecida_e_bloqueada():
    limpar_estado_homolog()
    client.cookies.clear()
    criar_admin_com_sessao()
    resposta = client.post(
        "/api/isis2/homolog/ativar",
        headers={"Origin": "https://site-malicioso.exemplo"},
    )
    assert resposta.status_code == 403
    client.cookies.clear()


def test_resposta_nunca_contem_dado_sensivel_de_aluno():
    limpar_estado_homolog()
    from backend.database import conectar

    with conectar() as conn:
        isis2_homolog.garantir_tabelas_isis2_homolog(conn)
        isis2_homolog._definir_ativo(conn, True)
    aluno_id, token = criar_aluno_com_sessao()
    with conectar() as conn:
        conn.execute(
            "INSERT INTO isis2_homolog_testers (aluno_id, adicionado_por, adicionado_em) VALUES (?,?,?)",
            (aluno_id, "teste", "2026-01-01 00:00:00"),
        )
    resposta = client.get("/api/isis2/homolog-config", cookies={"mistica_aluno_sessao": token})
    corpo = resposta.json()
    assert set(corpo.keys()) == {"enabled", "escola", "refinamento", "homologacao"}
    assert "@" not in str(corpo)
    assert "email" not in corpo
    assert "nome" not in corpo
    assert token not in str(corpo)
