"""Testes da Escola Mística hierárquica (LMS): acesso, progressão e avaliação.

Cobre os cenários obrigatórios da especificação: aluno sem compra não acessa;
aluno comprado acessa só o curso certo; 1º módulo liberado e demais bloqueados;
avaliação só abre após conteúdos obrigatórios; nota calculada no backend;
reprovação não libera / aprovação libera o próximo módulo; nota não pode ser
forjada pelo navegador; módulo bloqueado não abre pela URL; matrícula idempotente;
progresso persiste; admin gerencia; usuário comum não acessa rotas de admin.

Cada teste usa um slug de curso próprio (isolamento) e cria a sessão de aluno
direto no banco para não esbarrar no rate limit de login compartilhado.
"""

import importlib
import os
import secrets
import uuid

from fastapi.testclient import TestClient

TEST_API_KEY = "test-api-key"
os.environ.setdefault("MISTICA_SITE_API_KEY", TEST_API_KEY)
os.environ.setdefault("MISTICA_SYNC_KEY", TEST_API_KEY)

main = importlib.import_module("backend.main")
client = TestClient(main.app)
client.__enter__()
ADMIN = {"X-Mistica-Api-Key": TEST_API_KEY}

CATALOGO_PAGO = "rape-uso-tradicao"  # curso pago real do catálogo existente
OUTRO_PAGO = "ayahuasca-fundamentos"  # outro curso pago (não comprado)


def _slug() -> str:
    return f"curso-teste-{uuid.uuid4().hex[:10]}"


def _aluno_logado(slug: str | None = None):
    """Cria uma conta de aluno + sessão direto no banco e devolve um cliente já
    autenticado (cookie de sessão). Se ``slug`` for informado, matricula o aluno."""
    from backend.aluno_auth import COOKIE_NOME, garantir_tabelas_alunos
    from backend.database import conectar

    email = f"{uuid.uuid4().hex[:8]}@ex.com"
    token = secrets.token_urlsafe(32)
    with conectar() as conn:
        garantir_tabelas_alunos(conn)
        aid = int(conn.execute(
            "INSERT INTO alunos (nome, email, criado_em) VALUES (?,?,?)",
            ("Aluno Teste", email, "2026-01-01 00:00:00"),
        ).lastrowid)
        conn.execute(
            "INSERT INTO alunos_sessoes (token, aluno_id, criada_em, expira_em) VALUES (?,?,?,?)",
            (token, aid, "2026-01-01 00:00:00", "2099-01-01 00:00:00"),
        )
        if slug:
            conn.execute(
                "INSERT OR IGNORE INTO alunos_cursos (aluno_id, slug, liberado_em) VALUES (?,?,?)",
                (aid, slug, "2026-01-01 00:00:00"),
            )
    c = TestClient(main.app)
    c.cookies.set(COOKIE_NOME, token)
    return c, aid, email


def _criar_modulo(slug, titulo, ordem):
    r = client.post("/api/admin/escola/modulos", json={"slug": slug, "titulo": titulo, "ordem": ordem, "publicado": True}, headers=ADMIN)
    assert r.status_code == 200, r.text
    return r.json()["id"]


def _criar_aula(modulo_id, titulo, ordem, obrigatoria=True, tipo="texto"):
    r = client.post(
        "/api/admin/escola/aulas",
        json={"modulo_id": modulo_id, "titulo": titulo, "ordem": ordem, "tipo": tipo, "conteudo": "c", "obrigatoria": obrigatoria, "publicado": True},
        headers=ADMIN,
    )
    assert r.status_code == 200, r.text
    return r.json()["id"]


def _criar_quiz(modulo_id, nota_minima=70):
    r = client.put(
        "/api/admin/escola/quizzes",
        json={"modulo_id": modulo_id, "nota_minima": nota_minima, "max_tentativas": 5, "embaralhar_perguntas": False, "embaralhar_opcoes": False},
        headers=ADMIN,
    )
    assert r.status_code == 200, r.text
    return r.json()["id"]


def _criar_pergunta(quiz_id, enunciado, correta_idx=0):
    opcoes = [{"texto": f"op{i}", "correta": (i == correta_idx)} for i in range(3)]
    r = client.post("/api/admin/escola/perguntas", json={"quiz_id": quiz_id, "enunciado": enunciado, "tipo": "unica", "explicacao": "pq", "opcoes": opcoes}, headers=ADMIN)
    assert r.status_code == 200, r.text
    return r.json()["id"]


def _curso_demo(slug):
    """2 módulos, 2 aulas cada, 1 avaliação por módulo, nota mínima 70%."""
    client.put(f"/api/admin/escola/cursos/{slug}", json={"titulo": "Curso Demo", "descricao": "d", "nota_minima": 70, "certificado": True, "publicado": True}, headers=ADMIN)
    m1 = _criar_modulo(slug, "Módulo 1", 0)
    a1 = _criar_aula(m1, "Introdução", 0)
    a2 = _criar_aula(m1, "Conteúdo principal", 1)
    q1 = _criar_quiz(m1)
    _criar_pergunta(q1, "1+1?")
    _criar_pergunta(q1, "2+2?")
    m2 = _criar_modulo(slug, "Módulo 2", 1)
    b1 = _criar_aula(m2, "Aula 2.1", 0)
    b2 = _criar_aula(m2, "Aula 2.2", 1)
    q2 = _criar_quiz(m2)
    _criar_pergunta(q2, "3+3?")
    return {"m1": m1, "a1": a1, "a2": a2, "q1": q1, "m2": m2, "b1": b1, "b2": b2, "q2": q2}


def _concluir_modulo1(aluno, ids):
    aluno.post(f"/api/escola/aulas/{ids['a1']}/progresso", json={"status": "concluida", "percentual": 100})
    aluno.post(f"/api/escola/aulas/{ids['a2']}/progresso", json={"status": "concluida", "percentual": 100})


def _modulos_por_titulo(aluno, slug):
    arvore = aluno.get(f"/api/escola/cursos/{slug}").json()
    return {m["titulo"]: m for m in arvore["modulos"]}


# --- Cenários -------------------------------------------------------------

def test_aluno_sem_login_nao_acessa():
    assert client.get(f"/api/escola/cursos/{_slug()}").status_code == 401


def test_compra_aprovada_gera_matricula_e_acesso_so_ao_curso_certo():
    """Integração real com o fluxo de pagamento: checkout → confirmar → acesso."""
    email = f"comprador-{uuid.uuid4().hex[:8]}@ex.com"
    ipheader = {"X-Forwarded-For": "203.0.113.9"}
    pedido = client.post("/api/checkout/cursos", json={"slug": CATALOGO_PAGO, "nome": "C", "email": email}, headers=ipheader).json()
    confirm = client.post(f"/api/checkout/cursos/{pedido['id']}/confirmar", headers=ADMIN).json()
    aluno = TestClient(main.app, headers=ipheader)
    token = confirm["link_acesso"].split("acesso=")[1]
    assert aluno.post("/api/alunos/definir-senha", json={"token": token, "senha": "senhaforte123"}).status_code == 200
    # Acessa o curso comprado, mas não outro curso pago não comprado.
    assert aluno.get(f"/api/escola/cursos/{CATALOGO_PAGO}").status_code == 200
    assert aluno.get(f"/api/escola/cursos/{OUTRO_PAGO}").status_code == 403


def test_primeiro_modulo_liberado_e_segundo_bloqueado():
    slug = _slug()
    ids = _curso_demo(slug)
    aluno, _, _ = _aluno_logado(slug)
    mods = _modulos_por_titulo(aluno, slug)
    assert mods["Módulo 1"]["liberado"] is True
    assert mods["Módulo 2"]["liberado"] is False
    # Módulo bloqueado não entrega o conteúdo das aulas (anti-vazamento).
    assert "conteudo" not in mods["Módulo 2"]["aulas"][0]
    assert "conteudo" in mods["Módulo 1"]["aulas"][0]


def test_modulo_bloqueado_nao_abre_pela_url():
    slug = _slug()
    ids = _curso_demo(slug)
    aluno, _, _ = _aluno_logado(slug)
    assert aluno.post(f"/api/escola/aulas/{ids['b1']}/progresso", json={"status": "concluida", "percentual": 100}).status_code == 403
    assert aluno.get(f"/api/escola/quizzes/{ids['q2']}/iniciar").status_code == 403


def test_avaliacao_nao_abre_antes_das_aulas_obrigatorias():
    slug = _slug()
    ids = _curso_demo(slug)
    aluno, _, _ = _aluno_logado(slug)
    assert aluno.get(f"/api/escola/quizzes/{ids['q1']}/iniciar").status_code == 403
    aluno.post(f"/api/escola/aulas/{ids['a1']}/progresso", json={"status": "concluida", "percentual": 100})
    assert aluno.get(f"/api/escola/quizzes/{ids['q1']}/iniciar").status_code == 403
    aluno.post(f"/api/escola/aulas/{ids['a2']}/progresso", json={"status": "concluida", "percentual": 100})
    assert aluno.get(f"/api/escola/quizzes/{ids['q1']}/iniciar").status_code == 200


def test_reprovacao_nao_libera_proximo_modulo():
    slug = _slug()
    ids = _curso_demo(slug)
    aluno, _, _ = _aluno_logado(slug)
    _concluir_modulo1(aluno, ids)
    sessao = aluno.get(f"/api/escola/quizzes/{ids['q1']}/iniciar").json()
    respostas = [{"pergunta_id": p["id"], "opcao_id": p["opcoes"][1]["id"]} for p in sessao["perguntas"]]
    res = aluno.post(f"/api/escola/quizzes/{ids['q1']}/enviar", json={"sessao_id": sessao["sessao_id"], "respostas": respostas}).json()
    assert res["aprovado"] is False and res["nota"] < 70
    assert _modulos_por_titulo(aluno, slug)["Módulo 2"]["liberado"] is False


def test_aprovacao_libera_proximo_modulo_e_nota_no_backend():
    slug = _slug()
    ids = _curso_demo(slug)
    aluno, _, _ = _aluno_logado(slug)
    _concluir_modulo1(aluno, ids)
    sessao = aluno.get(f"/api/escola/quizzes/{ids['q1']}/iniciar").json()
    respostas = [{"pergunta_id": p["id"], "opcao_id": p["opcoes"][0]["id"]} for p in sessao["perguntas"]]
    res = aluno.post(f"/api/escola/quizzes/{ids['q1']}/enviar", json={"sessao_id": sessao["sessao_id"], "respostas": respostas}).json()
    assert res["aprovado"] is True and res["nota"] == 100
    mods = _modulos_por_titulo(aluno, slug)
    assert mods["Módulo 1"]["concluido"] is True
    assert mods["Módulo 2"]["liberado"] is True


def test_nota_nao_pode_ser_forjada_pelo_navegador():
    slug = _slug()
    ids = _curso_demo(slug)
    aluno, _, _ = _aluno_logado(slug)
    _concluir_modulo1(aluno, ids)
    sessao = aluno.get(f"/api/escola/quizzes/{ids['q1']}/iniciar").json()
    respostas = [{"pergunta_id": p["id"], "opcao_id": p["opcoes"][1]["id"]} for p in sessao["perguntas"]]
    res = aluno.post(
        f"/api/escola/quizzes/{ids['q1']}/enviar",
        json={"sessao_id": sessao["sessao_id"], "respostas": respostas, "nota": 100, "aprovado": True},
    ).json()
    assert res["nota"] == 0 and res["aprovado"] is False


def test_iniciar_quiz_nao_revela_gabarito():
    slug = _slug()
    ids = _curso_demo(slug)
    aluno, _, _ = _aluno_logado(slug)
    _concluir_modulo1(aluno, ids)
    sessao = aluno.get(f"/api/escola/quizzes/{ids['q1']}/iniciar").json()
    for p in sessao["perguntas"]:
        for o in p["opcoes"]:
            assert "correta" not in o  # o campo de gabarito nunca é enviado


def test_sessao_de_tentativa_e_uso_unico():
    slug = _slug()
    ids = _curso_demo(slug)
    aluno, _, _ = _aluno_logado(slug)
    _concluir_modulo1(aluno, ids)
    sessao = aluno.get(f"/api/escola/quizzes/{ids['q1']}/iniciar").json()
    respostas = [{"pergunta_id": p["id"], "opcao_id": p["opcoes"][0]["id"]} for p in sessao["perguntas"]]
    body = {"sessao_id": sessao["sessao_id"], "respostas": respostas}
    assert aluno.post(f"/api/escola/quizzes/{ids['q1']}/enviar", json=body).status_code == 200
    assert aluno.post(f"/api/escola/quizzes/{ids['q1']}/enviar", json=body).status_code == 409


def test_progresso_persiste_apos_relogin():
    slug = _slug()
    ids = _curso_demo(slug)
    aluno, aid, _ = _aluno_logado(slug)
    aluno.post(f"/api/escola/aulas/{ids['a1']}/progresso", json={"status": "concluida", "percentual": 100})
    # Nova sessão (novo cookie) para o mesmo aluno: progresso segue salvo.
    from backend.aluno_auth import COOKIE_NOME, garantir_tabelas_alunos
    from backend.database import conectar

    token = secrets.token_urlsafe(32)
    with conectar() as conn:
        garantir_tabelas_alunos(conn)
        conn.execute("INSERT INTO alunos_sessoes (token, aluno_id, criada_em, expira_em) VALUES (?,?,?,?)", (token, aid, "2026-01-01 00:00:00", "2099-01-01 00:00:00"))
    outro = TestClient(main.app)
    outro.cookies.set(COOKIE_NOME, token)
    arvore = outro.get(f"/api/escola/cursos/{slug}").json()
    assert arvore["modulos"][0]["aulas"][0]["status"] == "concluida"


def test_matricula_nao_e_duplicada():
    from backend.aluno_auth import conceder_acesso_curso, garantir_tabelas_alunos, obter_ou_criar_aluno_sem_senha
    from backend.database import conectar

    email = f"dup-{uuid.uuid4().hex[:8]}@ex.com"
    with conectar() as conn:
        garantir_tabelas_alunos(conn)
        aid = obter_ou_criar_aluno_sem_senha(conn, nome="Dup", email=email)
        conceder_acesso_curso(conn, aluno_id=aid, slug=CATALOGO_PAGO)
        conceder_acesso_curso(conn, aluno_id=aid, slug=CATALOGO_PAGO)
        n = conn.execute("SELECT COUNT(*) AS n FROM alunos_cursos WHERE aluno_id=? AND slug=?", (aid, CATALOGO_PAGO)).fetchone()["n"]
    assert n == 1


def test_usuario_comum_nao_acessa_rotas_admin():
    aluno, _, _ = _aluno_logado()
    assert aluno.post("/api/admin/escola/modulos", json={"slug": _slug(), "titulo": "X"}).status_code in (401, 403)
    assert client.post("/api/admin/escola/modulos", json={"slug": _slug(), "titulo": "X"}).status_code in (401, 403)


def test_admin_gerencia_curso():
    slug = _slug()
    assert client.get(f"/api/admin/escola/cursos/{slug}", headers=ADMIN).status_code == 200
    mid = _criar_modulo(slug, "Módulo admin", 0)
    arvore = client.get(f"/api/admin/escola/cursos/{slug}", headers=ADMIN).json()
    assert any(m["id"] == mid for m in arvore["modulos"])


def test_excluir_modulo_com_progresso_e_bloqueado():
    slug = _slug()
    ids = _curso_demo(slug)
    aluno, _, _ = _aluno_logado(slug)
    aluno.post(f"/api/escola/aulas/{ids['a1']}/progresso", json={"status": "concluida", "percentual": 100})
    # Módulo com progresso de aluno não pode ser excluído (protege histórico).
    assert client.delete(f"/api/admin/escola/modulos/{ids['m1']}", headers=ADMIN).status_code == 409


def test_suspender_acesso_bloqueia_curso():
    slug = _slug()
    _curso_demo(slug)
    aluno, aid, email = _aluno_logado(slug)
    assert aluno.get(f"/api/escola/cursos/{slug}").status_code == 200
    assert client.post("/api/admin/escola/alunos/suspender", json={"aluno_id": aid, "slug": slug}, headers=ADMIN).status_code == 200
    assert aluno.get(f"/api/escola/cursos/{slug}").status_code == 403
    # Reativar libera de novo.
    client.post("/api/admin/escola/alunos/liberar-curso", json={"aluno_id": aid, "slug": slug}, headers=ADMIN)
    assert aluno.get(f"/api/escola/cursos/{slug}").status_code == 200


def test_liberacao_manual_de_modulo():
    slug = _slug()
    ids = _curso_demo(slug)
    aluno, aid, _ = _aluno_logado(slug)
    assert client.post("/api/admin/escola/alunos/liberar-modulo", json={"aluno_id": aid, "modulo_id": ids["m2"]}, headers=ADMIN).status_code == 200
    assert _modulos_por_titulo(aluno, slug)["Módulo 2"]["liberado"] is True
