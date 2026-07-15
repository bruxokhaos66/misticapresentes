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
XAMANISMO = "xamanismo-introducao"

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


def test_max_tentativas_respeitado_mesmo_com_sessoes_pre_abertas():
    """Regressão (M1): pré-abrir várias sessões não pode burlar max_tentativas.
    O limite é reavaliado no envio, ponto autoritativo."""
    slug = _slug()
    ids = _curso_demo(slug)
    # Reconfigura a avaliação do módulo 1 para 1 tentativa apenas.
    r = client.put("/api/admin/escola/quizzes", json={"modulo_id": ids["m1"], "nota_minima": 70, "max_tentativas": 1, "embaralhar_perguntas": False, "embaralhar_opcoes": False}, headers=ADMIN)
    assert r.status_code == 200
    aluno, _, _ = _aluno_logado(slug)
    _concluir_modulo1(aluno, ids)
    # Pré-abre 3 sessões (todas passam pois ainda não há tentativa registrada).
    sessoes = [aluno.get(f"/api/escola/quizzes/{ids['q1']}/iniciar").json() for _ in range(3)]
    def enviar(sess):
        respostas = [{"pergunta_id": p["id"], "opcao_id": p["opcoes"][1]["id"]} for p in sess["perguntas"]]
        return aluno.post(f"/api/escola/quizzes/{ids['q1']}/enviar", json={"sessao_id": sess["sessao_id"], "respostas": respostas})
    codes = [enviar(s).status_code for s in sessoes]
    assert codes[0] == 200  # primeira conta
    assert all(c == 429 for c in codes[1:])  # demais barradas pelo limite
    tentativas = aluno.get(f"/api/escola/quizzes/{ids['q1']}/tentativas").json()
    assert len(tentativas) == 1


def test_reenvio_da_mesma_sessao_apos_sucesso_e_bloqueado():
    """Regressão (M1): a mesma sessão consumida não pode ser reenviada."""
    slug = _slug()
    ids = _curso_demo(slug)
    aluno, _, _ = _aluno_logado(slug)
    _concluir_modulo1(aluno, ids)
    sess = aluno.get(f"/api/escola/quizzes/{ids['q1']}/iniciar").json()
    respostas = [{"pergunta_id": p["id"], "opcao_id": p["opcoes"][0]["id"]} for p in sess["perguntas"]]
    body = {"sessao_id": sess["sessao_id"], "respostas": respostas}
    assert aluno.post(f"/api/escola/quizzes/{ids['q1']}/enviar", json=body).status_code == 200
    assert aluno.post(f"/api/escola/quizzes/{ids['q1']}/enviar", json=body).status_code == 409


def test_suspensao_bloqueia_endpoint_legado_de_conteudo():
    """Regressão (M2): aluno suspenso não acessa nem o conteúdo plano legado."""
    from backend.database import conectar
    from backend.aluno_auth import COOKIE_NOME, garantir_tabelas_alunos

    tok = secrets.token_urlsafe(32)
    with conectar() as conn:
        garantir_tabelas_alunos(conn)
        aid = int(conn.execute("INSERT INTO alunos (nome, email, criado_em) VALUES (?,?,?)", ("Susp", f"susp-{uuid.uuid4().hex[:8]}@ex.com", "2026-01-01 00:00:00")).lastrowid)
        conn.execute("INSERT INTO alunos_sessoes (token, aluno_id, criada_em, expira_em) VALUES (?,?,?,?)", (tok, aid, "2026-01-01 00:00:00", "2099-01-01 00:00:00"))
        conn.execute("INSERT OR IGNORE INTO alunos_cursos (aluno_id, slug, liberado_em) VALUES (?,?,?)", (aid, CATALOGO_PAGO, "2026-01-01 00:00:00"))
    al = TestClient(main.app)
    al.cookies.set(COOKIE_NOME, tok)
    # Antes da suspensão: endpoint legado responde (não 403 por acesso).
    assert al.get(f"/api/cursos/{CATALOGO_PAGO}/conteudo").status_code == 200
    client.post("/api/admin/escola/alunos/suspender", json={"aluno_id": aid, "slug": CATALOGO_PAGO}, headers=ADMIN)
    # Depois: bloqueado no legado também.
    assert al.get(f"/api/cursos/{CATALOGO_PAGO}/conteudo").status_code == 403


def test_liberacao_manual_de_modulo():
    slug = _slug()
    ids = _curso_demo(slug)
    aluno, aid, _ = _aluno_logado(slug)
    assert client.post("/api/admin/escola/alunos/liberar-modulo", json={"aluno_id": aid, "modulo_id": ids["m2"]}, headers=ADMIN).status_code == 200
    assert _modulos_por_titulo(aluno, slug)["Módulo 2"]["liberado"] is True


def test_modulo_xamanismo_oficial_carrega_com_duas_aulas_e_dez_questoes():
    from backend.database import conectar
    from backend.lms_content_xamanismo import instalar_conteudo_xamanismo

    with conectar() as conn:
        instalar_conteudo_xamanismo(conn)
        modulo = conn.execute(
            "SELECT id, nota_minima FROM curso_modulos WHERE slug=? AND ordem=0", (XAMANISMO,)
        ).fetchone()
        assert modulo and modulo["nota_minima"] == 70
        aulas = conn.execute(
            "SELECT titulo, conteudo, duracao_min FROM curso_aulas WHERE modulo_id=? ORDER BY ordem",
            (modulo["id"],),
        ).fetchall()
        assert [a["titulo"] for a in aulas] == [
            "O que é o Xamanismo?",
            "Por que o Xamanismo ainda existe?",
        ]
        assert all(8 <= int(a["duracao_min"]) <= 15 for a in aulas)
        assert all(
            "Olhar da Ciência" in a["conteudo"] and "Respeito às Tradições" in a["conteudo"]
            for a in aulas
        )
        quiz = conn.execute(
            "SELECT id, nota_minima, num_perguntas FROM curso_quizzes WHERE modulo_id=?",
            (modulo["id"],),
        ).fetchone()
        total = conn.execute(
            "SELECT COUNT(*) AS n FROM quiz_perguntas WHERE quiz_id=?", (quiz["id"],)
        ).fetchone()["n"]
        assert quiz["nota_minima"] == 70 and quiz["num_perguntas"] == 10 and total == 10


def test_migration_reaplica_quando_versao_antiga_ja_marcada_sem_acesso_publico():
    """Reproduz o bug de produção: uma implantação anterior (antes da correção
    de acesso_publico/requer_matricula) já tinha marcado uma versão antiga da
    migração como aplicada, com o curso gravado sem acesso_publico. A versão
    atual precisa detectar que essa versão antiga é diferente da atual e
    reaplicar o conteúdo, sem duplicar módulos/aulas, sem trocar IDs e sem
    mexer em matrícula/progresso já existentes."""
    from backend.database import conectar
    from backend.lms_content_xamanismo import SLUG, VERSAO, instalar_conteudo_xamanismo

    with conectar() as conn:
        ids_antes = [
            (r["id"], r["ordem"])
            for r in conn.execute("SELECT id, ordem FROM curso_modulos WHERE slug=? ORDER BY ordem", (SLUG,)).fetchall()
        ]
        assert len(ids_antes) == 2  # pré-condição: conteúdo oficial já instalado no startup

        # Regride o banco ao estado deixado pela versão antiga (pré-#316):
        # curso com requer_matricula=1 e nenhum módulo com acesso_publico.
        conn.execute("UPDATE curso_config SET requer_matricula=1 WHERE slug=?", (SLUG,))
        conn.execute("UPDATE curso_modulos SET acesso_publico=0 WHERE slug=?", (SLUG,))
        conn.execute("DELETE FROM lms_content_versions WHERE versao=?", (VERSAO,))
        conn.execute(
            "INSERT OR REPLACE INTO lms_content_versions (versao,aplicada_em) VALUES (?,?)",
            ("xamanismo-modulo-1-v1", "2026-01-01 00:00:00"),
        )

    # Endpoint público falha exatamente como no relato: nenhum módulo público.
    assert client.get(f"/api/escola/publico/cursos/{SLUG}").status_code == 404

    with conectar() as conn:
        houve_mudanca = instalar_conteudo_xamanismo(conn)
    assert houve_mudanca is True

    r = client.get(f"/api/escola/publico/cursos/{SLUG}")
    assert r.status_code == 200
    body = r.json()
    assert body["slug"] == SLUG
    assert body["gratuito"] is True
    assert any(m.get("aulas") for m in body["modulos"])

    with conectar() as conn:
        cfg = conn.execute("SELECT requer_matricula, publicado FROM curso_config WHERE slug=?", (SLUG,)).fetchone()
        assert cfg["requer_matricula"] == 0 and cfg["publicado"] == 1
        ids_depois = [
            (r["id"], r["ordem"])
            for r in conn.execute("SELECT id, ordem, acesso_publico FROM curso_modulos WHERE slug=? ORDER BY ordem", (SLUG,)).fetchall()
        ]
        assert ids_depois == ids_antes  # mesmos módulos, mesmos ids (nada recriado)
        publicos = conn.execute("SELECT COUNT(*) AS n FROM curso_modulos WHERE slug=? AND acesso_publico=1", (SLUG,)).fetchone()["n"]
        assert publicos == 2


def test_xamanismo_e_gratuito_para_qualquer_aluno_logado_e_nao_revela_gabarito():
    """Curso gratuito: basta sessão de aluno, sem exigir matrícula manual
    (regra restaurada — ver aluno_matriculado em backend/lms.py). Suspensão
    administrativa continua bloqueando o acesso normalmente."""
    aluno_sem, _, _ = _aluno_logado()
    assert aluno_sem.get(f"/api/escola/cursos/{XAMANISMO}").status_code == 200

    aluno, aid, _ = _aluno_logado(XAMANISMO)
    arvore = aluno.get(f"/api/escola/cursos/{XAMANISMO}")
    assert arvore.status_code == 200
    m1 = arvore.json()["modulos"][0]
    assert len(m1["aulas"]) == 2 and m1["liberado"] is True
    assert arvore.json()["modulos"][1]["liberado"] is False

    for aula in m1["aulas"]:
        resposta = aluno.post(
            f"/api/escola/aulas/{aula['id']}/progresso",
            json={"status": "concluida", "percentual": 100},
        )
        assert resposta.status_code == 200
    sessao = aluno.get(f"/api/escola/quizzes/{m1['quiz']['id']}/iniciar").json()
    assert len(sessao["perguntas"]) == 10
    assert all("correta" not in opcao for p in sessao["perguntas"] for opcao in p["opcoes"])

    assert client.post(
        "/api/admin/escola/alunos/suspender",
        json={"aluno_id": aid, "slug": XAMANISMO},
        headers=ADMIN,
    ).status_code == 200
    assert aluno.get(f"/api/escola/cursos/{XAMANISMO}").status_code == 403


def _criar_modulo_publico(slug, titulo, ordem):
    r = client.post(
        "/api/admin/escola/modulos",
        json={"slug": slug, "titulo": titulo, "ordem": ordem, "publicado": True, "acesso_publico": True},
        headers=ADMIN,
    )
    assert r.status_code == 200, r.text
    return r.json()["id"]


def _curso_parcialmente_publico(slug):
    """Curso com 1 módulo público (com aula + material) e 1 módulo pago
    (com aula obrigatória e avaliação), imitando a regra partes 1-3 grátis /
    parte 4+ paga do xamanismo-introducao."""
    client.put(
        f"/api/admin/escola/cursos/{slug}",
        json={"titulo": "Curso Misto", "descricao": "d", "nota_minima": 70, "certificado": True, "publicado": True},
        headers=ADMIN,
    )
    m_pub = _criar_modulo_publico(slug, "Módulo público", 0)
    a_pub = _criar_aula(m_pub, "Aula pública", 0)
    m_pago = _criar_modulo(slug, "Módulo pago", 1)  # acesso_publico=False por padrão
    a_pago = _criar_aula(m_pago, "Aula paga", 0)
    q_pago = _criar_quiz(m_pago)
    _criar_pergunta(q_pago, "Pergunta paga?")
    return {"m_pub": m_pub, "a_pub": a_pub, "m_pago": m_pago, "a_pago": a_pago, "q_pago": q_pago}


# --- Acesso público (visitante anônimo, sem login/matrícula) --------------

def test_publico_xamanismo_acessivel_sem_sessao():
    r = client.get(f"/api/escola/publico/cursos/{XAMANISMO}")
    assert r.status_code == 200
    body = r.json()
    assert body["gratuito"] is True
    assert any(m.get("aulas") for m in body["modulos"])


def test_publico_entrega_apenas_modulos_marcados_e_bloqueia_o_resto():
    slug = _slug()
    ids = _curso_parcialmente_publico(slug)
    r = client.get(f"/api/escola/publico/cursos/{slug}")
    assert r.status_code == 200
    mods = {m["titulo"]: m for m in r.json()["modulos"]}

    publico = mods["Módulo público"]
    assert publico["bloqueado"] is False
    assert len(publico["aulas"]) == 1
    assert publico["aulas"][0]["conteudo"] == "c"

    pago = mods["Módulo pago"]
    assert pago["bloqueado"] is True
    assert set(pago.keys()) == {"id", "titulo", "imagem", "ordem", "publico", "bloqueado"}
    assert "aulas" not in pago
    assert "quiz" not in pago
    assert "conteudo" not in pago


def test_publico_nunca_inclui_avaliacao_nem_gabarito():
    slug = _slug()
    _curso_parcialmente_publico(slug)
    r = client.get(f"/api/escola/publico/cursos/{slug}").json()
    corpo_bruto = str(r)
    assert "quiz" not in corpo_bruto
    assert "correta" not in corpo_bruto
    assert "Pergunta paga?" not in corpo_bruto


def test_url_direta_para_aula_paga_e_bloqueada_anonimamente():
    slug = _slug()
    ids = _curso_parcialmente_publico(slug)
    # Sem sessão: nem a aula pública nem a paga aceitam marcar progresso.
    assert client.post(f"/api/escola/aulas/{ids['a_pago']}/progresso", json={"status": "concluida"}).status_code == 401
    assert client.get(f"/api/escola/quizzes/{ids['q_pago']}/iniciar").status_code == 401
    assert client.get(f"/api/escola/cursos/{slug}").status_code == 401


def test_publico_nao_cria_matricula_nem_aluno():
    from backend.database import conectar

    slug = _slug()
    _curso_parcialmente_publico(slug)
    with conectar() as conn:
        alunos_antes = conn.execute("SELECT COUNT(*) AS n FROM alunos").fetchone()["n"]
        matriculas_antes = conn.execute("SELECT COUNT(*) AS n FROM alunos_cursos WHERE slug=?", (slug,)).fetchone()["n"]
    for _ in range(3):
        assert client.get(f"/api/escola/publico/cursos/{slug}").status_code == 200
    with conectar() as conn:
        alunos_depois = conn.execute("SELECT COUNT(*) AS n FROM alunos").fetchone()["n"]
        matriculas_depois = conn.execute("SELECT COUNT(*) AS n FROM alunos_cursos WHERE slug=?", (slug,)).fetchone()["n"]
    assert alunos_depois == alunos_antes
    assert matriculas_depois == matriculas_antes == 0


def test_curso_sem_nenhum_modulo_publico_nao_aparece_no_endpoint_publico():
    """Garante que o marcador é opt-in: um curso comum (sem acesso_publico em
    nenhum módulo) não vaza nada pelo endpoint público."""
    slug = _slug()
    _curso_demo(slug)  # nenhum módulo criado aqui é público
    assert client.get(f"/api/escola/publico/cursos/{slug}").status_code == 404


def test_modulo_criado_sem_especificar_acesso_publico_e_privado_por_padrao():
    slug = _slug()
    client.put(f"/api/admin/escola/cursos/{slug}", json={"titulo": "T", "publicado": True}, headers=ADMIN)
    mid = _criar_modulo(slug, "Módulo", 0)
    with conectar_db() as conn:
        row = conn.execute("SELECT acesso_publico FROM curso_modulos WHERE id=?", (mid,)).fetchone()
    assert int(row["acesso_publico"] or 0) == 0


def conectar_db():
    from backend.database import conectar

    return conectar()


def test_editar_acesso_publico_exige_sessao_administrativa():
    slug = _slug()
    mid = _criar_modulo(slug, "Módulo", 0)
    payload = {"slug": slug, "titulo": "Módulo", "ordem": 0, "publicado": True, "acesso_publico": True}
    # Sem credenciais de admin: não consegue tornar o módulo público.
    assert client.put(f"/api/admin/escola/modulos/{mid}", json=payload).status_code in (401, 403)
    with conectar_db() as conn:
        row = conn.execute("SELECT acesso_publico FROM curso_modulos WHERE id=?", (mid,)).fetchone()
    assert int(row["acesso_publico"] or 0) == 0


def test_migration_acesso_publico_e_idempotente():
    from backend.database import conectar
    from backend.lms import garantir_tabelas_lms

    with conectar() as conn:
        garantir_tabelas_lms(conn)
        garantir_tabelas_lms(conn)
        garantir_tabelas_lms(conn)
        cols = [r["name"] for r in conn.execute("PRAGMA table_info(curso_modulos)").fetchall()]
    assert cols.count("acesso_publico") == 1


def test_outro_curso_pago_do_catalogo_nao_e_afetado_pela_mudanca():
    """CATALOGO_PAGO nunca foi tocado pela liberação do xamanismo: aluno sem
    matrícula continua sem acesso, e o endpoint público não expõe nada dele
    (nenhum módulo seu foi marcado acesso_publico)."""
    aluno_sem, _, _ = _aluno_logado()
    assert aluno_sem.get(f"/api/escola/cursos/{CATALOGO_PAGO}").status_code == 403
    assert client.get(f"/api/escola/publico/cursos/{CATALOGO_PAGO}").status_code == 404


def test_xamanismo_reprova_abaixo_de_70_e_aprova_com_70_desbloqueando_modulo_2():
    from backend.database import conectar

    aluno, _, _ = _aluno_logado(XAMANISMO)
    arvore = aluno.get(f"/api/escola/cursos/{XAMANISMO}").json()
    m1 = arvore["modulos"][0]
    for aula in m1["aulas"]:
        aluno.post(
            f"/api/escola/aulas/{aula['id']}/progresso",
            json={"status": "concluida", "percentual": 100},
        )

    def responder(qtd_corretas):
        tentativa = aluno.get(f"/api/escola/quizzes/{m1['quiz']['id']}/iniciar").json()
        respostas = []
        with conectar() as conn:
            for indice, pergunta in enumerate(tentativa["perguntas"]):
                opcoes = conn.execute(
                    "SELECT id, correta FROM quiz_opcoes WHERE pergunta_id=? ORDER BY id",
                    (pergunta["id"],),
                ).fetchall()
                escolhida = next(o for o in opcoes if bool(o["correta"]) == (indice < qtd_corretas))
                respostas.append({"pergunta_id": pergunta["id"], "opcao_id": escolhida["id"]})
        return aluno.post(
            f"/api/escola/quizzes/{m1['quiz']['id']}/enviar",
            json={"sessao_id": tentativa["sessao_id"], "respostas": respostas},
        ).json()

    reprovado = responder(6)
    assert reprovado["nota"] == 60 and reprovado["aprovado"] is False
    assert aluno.get(f"/api/escola/cursos/{XAMANISMO}").json()["modulos"][1]["liberado"] is False

    aprovado = responder(7)
    assert aprovado["nota"] == 70 and aprovado["aprovado"] is True
    assert aluno.get(f"/api/escola/cursos/{XAMANISMO}").json()["modulos"][1]["liberado"] is True


# --- Módulo 2 — As Origens e os Caminhos do Xamanismo ----------------------

def _instalar_modulo2():
    from backend.database import conectar
    from backend.lms_content_xamanismo import (
        instalar_conteudo_xamanismo,
        instalar_conteudo_modulo2_xamanismo,
    )

    with conectar() as conn:
        instalar_conteudo_xamanismo(conn)
        instalar_conteudo_modulo2_xamanismo(conn)
    return conn


def _modulo2_do_banco():
    from backend.database import conectar

    with conectar() as conn:
        modulo = conn.execute(
            "SELECT * FROM curso_modulos WHERE slug=? AND ordem=1", (XAMANISMO,)
        ).fetchone()
        assert modulo, "Módulo 2 do curso xamanismo-introducao não encontrado"
        aulas = conn.execute(
            "SELECT * FROM curso_aulas WHERE modulo_id=? ORDER BY ordem", (modulo["id"],)
        ).fetchall()
        return modulo, aulas


def test_modulo2_existe_com_titulo_oficial_e_acesso_publico():
    _instalar_modulo2()
    modulo, _ = _modulo2_do_banco()
    assert modulo["titulo"] == "Módulo 2 — As Origens e os Caminhos do Xamanismo"
    assert int(modulo["acesso_publico"]) == 1
    assert int(modulo["publicado"]) == 1


def test_modulo2_placeholder_foi_substituido_por_tres_aulas_completas():
    _instalar_modulo2()
    _, aulas = _modulo2_do_banco()
    assert len(aulas) == 3
    titulos = [a["titulo"] for a in aulas]
    assert titulos == [
        "A origem da palavra “xamã”",
        "Tradições semelhantes em diferentes regiões",
        "Como o xamanismo chegou ao mundo moderno",
    ]
    corpo_completo = " ".join(a["conteudo"] for a in aulas)
    assert "Em breve" not in corpo_completo
    assert "em preparação" not in corpo_completo.lower()
    # blocos pedagógicos obrigatórios presentes em pelo menos uma aula
    for bloco in [
        "Você sabia?",
        "Olhar da História",
        "Olhar da Ciência",
        "Respeito às Tradições",
        "Palavras importantes",
        "Para refletir",
    ]:
        assert bloco in corpo_completo, f"bloco pedagógico ausente: {bloco}"
    # leitura estimada por aula entre 10 e 15 minutos
    assert all(10 <= int(a["duracao_min"]) <= 15 for a in aulas)


def test_modulo2_nao_possui_quiz_oficial_nem_gabarito_persistido():
    _instalar_modulo2()
    modulo, _ = _modulo2_do_banco()
    from backend.database import conectar

    with conectar() as conn:
        quiz = conn.execute(
            "SELECT id FROM curso_quizzes WHERE modulo_id=?", (modulo["id"],)
        ).fetchone()
    assert quiz is None


def test_modulo2_publico_acessivel_sem_login_e_com_tres_aulas():
    _instalar_modulo2()
    r = client.get(f"/api/escola/publico/cursos/{XAMANISMO}")
    assert r.status_code == 200
    body = r.json()
    m2 = next(m for m in body["modulos"] if m["titulo"].startswith("Módulo 2"))
    assert m2["bloqueado"] is False
    assert len(m2["aulas"]) == 3
    for aula in m2["aulas"]:
        assert aula["conteudo"]
        assert "correta" not in aula


def test_modulo2_publico_nao_expoe_quiz_nem_gabarito():
    _instalar_modulo2()
    r = client.get(f"/api/escola/publico/cursos/{XAMANISMO}")
    corpo_bruto = str(r.json())
    assert "quiz" not in corpo_bruto.lower()
    assert '"correta"' not in corpo_bruto


def test_modulo2_publico_nao_cria_aluno_matricula_ou_sessao():
    from backend.database import conectar

    _instalar_modulo2()
    with conectar() as conn:
        alunos_antes = conn.execute("SELECT COUNT(*) AS n FROM alunos").fetchone()["n"]
        matriculas_antes = conn.execute(
            "SELECT COUNT(*) AS n FROM alunos_cursos WHERE slug=?", (XAMANISMO,)
        ).fetchone()["n"]
    for _ in range(3):
        r = client.get(f"/api/escola/publico/cursos/{XAMANISMO}")
        assert r.status_code == 200
        assert "session" not in {c.lower() for c in r.cookies.keys()}
    with conectar() as conn:
        alunos_depois = conn.execute("SELECT COUNT(*) AS n FROM alunos").fetchone()["n"]
        matriculas_depois = conn.execute(
            "SELECT COUNT(*) AS n FROM alunos_cursos WHERE slug=?", (XAMANISMO,)
        ).fetchone()["n"]
    assert alunos_depois == alunos_antes
    assert matriculas_depois == matriculas_antes


def test_modulo2_instalacao_e_idempotente_nao_duplica_aulas_nem_modulo():
    from backend.database import conectar
    from backend.lms_content_xamanismo import (
        instalar_conteudo_xamanismo,
        instalar_conteudo_modulo2_xamanismo,
    )

    with conectar() as conn:
        instalar_conteudo_xamanismo(conn)
        primeira = instalar_conteudo_modulo2_xamanismo(conn)
        segunda = instalar_conteudo_modulo2_xamanismo(conn)
        terceira = instalar_conteudo_modulo2_xamanismo(conn)
    assert segunda is False and terceira is False

    modulo, aulas = _modulo2_do_banco()
    assert len(aulas) == 3
    with conectar() as conn:
        total_modulos = conn.execute(
            "SELECT COUNT(*) AS n FROM curso_modulos WHERE slug=? AND ordem=1", (XAMANISMO,)
        ).fetchone()["n"]
    assert total_modulos == 1


def test_modulo2_atualizacao_de_banco_existente_preserva_progresso_de_aluno():
    """Simula um banco que só tinha o placeholder do Módulo 1 aplicado (banco
    persistente já em produção): ao aplicar a nova versão de conteúdo, a aula
    antiga sem progresso é substituída, mas o progresso de aluno registrado em
    aulas do Módulo 1 nunca é apagado."""
    from backend.database import conectar
    from backend.lms_content_xamanismo import instalar_conteudo_xamanismo, instalar_conteudo_modulo2_xamanismo

    with conectar() as conn:
        instalar_conteudo_xamanismo(conn)
        modulo1 = conn.execute(
            "SELECT id FROM curso_modulos WHERE slug=? AND ordem=0", (XAMANISMO,)
        ).fetchone()
        aula1 = conn.execute(
            "SELECT id FROM curso_aulas WHERE modulo_id=? ORDER BY ordem LIMIT 1", (modulo1["id"],)
        ).fetchone()
        progresso_antes = conn.execute(
            "SELECT COUNT(*) AS n FROM aluno_aula_progresso WHERE aula_id=?", (aula1["id"],)
        ).fetchone()["n"]

    aluno, _, _ = _aluno_logado(XAMANISMO)
    aluno.post(f"/api/escola/aulas/{aula1['id']}/progresso", json={"status": "concluida", "percentual": 100})

    with conectar() as conn:
        instalar_conteudo_modulo2_xamanismo(conn)
        progresso_depois = conn.execute(
            "SELECT COUNT(*) AS n FROM aluno_aula_progresso WHERE aula_id=?", (aula1["id"],)
        ).fetchone()["n"]
    assert progresso_depois >= progresso_antes + 1

    _, aulas_m2 = _modulo2_do_banco()
    assert len(aulas_m2) == 3


def test_modulo2_nao_altera_modulo1_nem_outros_cursos():
    from backend.database import conectar

    _instalar_modulo2()
    with conectar() as conn:
        m1 = conn.execute(
            "SELECT titulo, acesso_publico FROM curso_modulos WHERE slug=? AND ordem=0", (XAMANISMO,)
        ).fetchone()
    assert m1["titulo"] == "Módulo 1 — O Chamado do Xamanismo"
    assert int(m1["acesso_publico"]) == 1
    # outro curso pago do catálogo continua intocado
    assert client.get(f"/api/escola/publico/cursos/{CATALOGO_PAGO}").status_code == 404


def test_modulo2_nenhum_modulo_futuro_alem_do_2_e_publico():
    _instalar_modulo2()
    r = client.get(f"/api/escola/publico/cursos/{XAMANISMO}")
    body = r.json()
    assert len(body["modulos"]) == 2


def test_modulo2_html_das_aulas_nao_contem_tags_perigosas():
    _instalar_modulo2()
    _, aulas = _modulo2_do_banco()
    for aula in aulas:
        conteudo = aula["conteudo"]
        assert "<script" not in conteudo.lower()
        assert "onerror=" not in conteudo.lower()
        assert "javascript:" not in conteudo.lower()


def test_modulo2_imagens_possuem_alt_e_dimensoes():
    _instalar_modulo2()
    _, aulas = _modulo2_do_banco()
    import re

    for aula in aulas:
        for img in re.findall(r"<img[^>]*>", aula["conteudo"]):
            assert 'alt="' in img and 'alt=""' not in img
            assert 'width="' in img and 'height="' in img


def test_modulo2_atividade_de_revisao_e_apenas_local_sem_persistencia():
    """A atividade de revisão do Módulo 2 é só HTML nativo (<details>/<summary>),
    nunca envolve rota, sessão de quiz ou tabela oficial — evita duplicar o
    sistema de avaliação do LMS para o visitante anônimo."""
    _instalar_modulo2()
    _, aulas = _modulo2_do_banco()
    aula3 = aulas[2]
    assert "aula-revisao" in aula3["conteudo"]
    assert "atividade livre de revisão" in aula3["conteudo"].lower()
    assert "não substitui a avaliação oficial" in aula3["conteudo"].lower()
    assert "<script" not in aula3["conteudo"].lower()


# --- Migração para artes fotográficas oficiais (WebP) ----------------------

def _instalar_capas_fotograficas():
    from backend.database import conectar
    from backend.lms_content_xamanismo import (
        instalar_conteudo_xamanismo,
        instalar_conteudo_modulo2_xamanismo,
        instalar_capas_modulo1_xamanismo,
        instalar_capas_v2_modulo1_xamanismo,
        instalar_capas_modulo2_xamanismo,
        instalar_capas_modulos_xamanismo,
    )

    with conectar() as conn:
        instalar_conteudo_xamanismo(conn)
        instalar_conteudo_modulo2_xamanismo(conn)
        instalar_capas_modulo1_xamanismo(conn)
        instalar_capas_v2_modulo1_xamanismo(conn)
        instalar_capas_modulo2_xamanismo(conn)
        instalar_capas_modulos_xamanismo(conn)


def test_capas_fotograficas_substituem_svg_nas_aulas_esperadas():
    _instalar_capas_fotograficas()
    from backend.database import conectar

    with conectar() as conn:
        mod1 = conn.execute(
            "SELECT id FROM curso_modulos WHERE slug=? AND ordem=0", (XAMANISMO,)
        ).fetchone()
        aulas_m1 = conn.execute(
            "SELECT * FROM curso_aulas WHERE modulo_id=? ORDER BY ordem", (mod1["id"],)
        ).fetchall()
    assert "modulo-1-aula-1-capa.webp" in aulas_m1[0]["conteudo"]
    assert "modulo-1-aula-2-capa.webp" in aulas_m1[1]["conteudo"]
    assert "modulo-1-aula-1-capa.svg" not in aulas_m1[0]["conteudo"]
    assert "modulo-1-aula-2-capa.svg" not in aulas_m1[1]["conteudo"]

    _, aulas_m2 = _modulo2_do_banco()
    assert "aula-origem-termo-xama.svg" in aulas_m2[0]["conteudo"]  # não fotografada
    assert "aula-tradicoes-regioes.webp" in aulas_m2[1]["conteudo"]
    assert "aula-xamanismo-moderno.webp" in aulas_m2[2]["conteudo"]
    assert "aula-tradicoes-regioes.svg" not in aulas_m2[1]["conteudo"]
    assert "aula-xamanismo-moderno.svg" not in aulas_m2[2]["conteudo"]


def test_capas_de_modulo_instaladas_em_curso_modulos_imagem():
    _instalar_capas_fotograficas()
    from backend.database import conectar

    with conectar() as conn:
        mod1 = conn.execute(
            "SELECT imagem FROM curso_modulos WHERE slug=? AND ordem=0", (XAMANISMO,)
        ).fetchone()
        mod2 = conn.execute(
            "SELECT imagem FROM curso_modulos WHERE slug=? AND ordem=1", (XAMANISMO,)
        ).fetchone()
    assert mod1["imagem"] == "assets/escola/xamanismo/modulo-1-capa.webp"
    assert mod2["imagem"] == "assets/escola/xamanismo/modulo-2-capa.webp"


def test_capas_fotograficas_expostas_na_api_publica_e_autenticada():
    _instalar_capas_fotograficas()
    r = client.get(f"/api/escola/publico/cursos/{XAMANISMO}")
    assert r.status_code == 200
    modulos = r.json()["modulos"]
    assert modulos[0]["imagem"] == "assets/escola/xamanismo/modulo-1-capa.webp"

    aluno, _, _ = _aluno_logado(XAMANISMO)
    r2 = aluno.get(f"/api/escola/cursos/{XAMANISMO}")
    assert r2.status_code == 200
    modulos2 = r2.json()["modulos"]
    assert modulos2[0]["imagem"] == "assets/escola/xamanismo/modulo-1-capa.webp"
    assert modulos2[1]["imagem"] == "assets/escola/xamanismo/modulo-2-capa.webp"


def test_migracao_de_capas_fotograficas_e_idempotente_e_preserva_progresso():
    from backend.database import conectar
    from backend.lms_content_xamanismo import (
        instalar_capas_v2_modulo1_xamanismo,
        instalar_capas_modulo2_xamanismo,
        instalar_capas_modulos_xamanismo,
    )

    _instalar_capas_fotograficas()
    aluno, _, _ = _aluno_logado(XAMANISMO)
    with conectar() as conn:
        aula1 = conn.execute(
            "SELECT ca.id FROM curso_aulas ca JOIN curso_modulos cm ON cm.id=ca.modulo_id "
            "WHERE cm.slug=? AND cm.ordem=0 ORDER BY ca.ordem LIMIT 1",
            (XAMANISMO,),
        ).fetchone()
    aluno.post(f"/api/escola/aulas/{aula1['id']}/progresso", json={"status": "concluida", "percentual": 100})

    with conectar() as conn:
        progresso_antes = conn.execute(
            "SELECT COUNT(*) AS n FROM aluno_aula_progresso WHERE aula_id=?", (aula1["id"],)
        ).fetchone()["n"]
        segunda_v2 = instalar_capas_v2_modulo1_xamanismo(conn)
        segunda_m2 = instalar_capas_modulo2_xamanismo(conn)
        segunda_mod = instalar_capas_modulos_xamanismo(conn)
        progresso_depois = conn.execute(
            "SELECT COUNT(*) AS n FROM aluno_aula_progresso WHERE aula_id=?", (aula1["id"],)
        ).fetchone()["n"]

    assert segunda_v2 is False and segunda_m2 is False and segunda_mod is False
    assert progresso_depois == progresso_antes
