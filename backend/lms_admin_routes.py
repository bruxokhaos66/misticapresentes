"""Gestão administrativa da Escola Mística hierárquica.

Reaproveita a autenticação administrativa já existente
(``exigir_sessao_ou_chave_api("adm")``) e o log de auditoria unificado
(``registrar_auditoria``). Cobre cursos, módulos, aulas, avaliações (perguntas e
opções) e a gestão de alunos (liberar/suspender/resetar), sempre validando no
backend e registrando as alterações administrativas relevantes.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from backend.audit import registrar_auditoria
from backend.database import conectar
from backend.lms import TIPOS_AULA, TIPOS_PERGUNTA, garantir_tabelas_lms
from backend.panel_sessions import exigir_sessao_ou_chave_api

router = APIRouter(prefix="/api/admin/escola", tags=["escola-admin"])

exigir_admin = exigir_sessao_ou_chave_api("adm")


def _agora() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _usuario(sessao: dict) -> str:
    return sessao.get("login") or sessao.get("nome") or "admin"


# ---------------------------------------------------------------------------
# Curso (configuração) + árvore completa para a administração
# ---------------------------------------------------------------------------

class CursoConfigIn(BaseModel):
    titulo: Optional[str] = None
    descricao: Optional[str] = None
    imagem: Optional[str] = None
    nota_minima: int = Field(default=70, ge=0, le=100)
    certificado: bool = True
    publicado: bool = True


@router.put("/cursos/{slug}")
def salvar_config_curso(slug: str, payload: CursoConfigIn, sessao: dict = Depends(exigir_admin)):
    slug = slug.strip()
    if not slug:
        raise HTTPException(status_code=422, detail="Slug do curso é obrigatório.")
    with conectar() as conn:
        garantir_tabelas_lms(conn)
        conn.execute(
            """
            INSERT INTO curso_config (slug, titulo, descricao, imagem, nota_minima, certificado, publicado, atualizado_em)
            VALUES (?,?,?,?,?,?,?,?)
            ON CONFLICT(slug) DO UPDATE SET
                titulo=excluded.titulo, descricao=excluded.descricao, imagem=excluded.imagem,
                nota_minima=excluded.nota_minima, certificado=excluded.certificado,
                publicado=excluded.publicado, atualizado_em=excluded.atualizado_em
            """,
            (
                slug,
                payload.titulo,
                payload.descricao,
                payload.imagem,
                int(payload.nota_minima),
                1 if payload.certificado else 0,
                1 if payload.publicado else 0,
                _agora(),
            ),
        )
        registrar_auditoria(conn, "curso_config", slug, "salvar", _usuario(sessao), depois=payload.model_dump())
    return {"ok": True, "slug": slug}


@router.get("/cursos/{slug}")
def arvore_admin(slug: str, sessao: dict = Depends(exigir_admin)):
    """Árvore completa (inclui rascunhos e o gabarito) para a administração."""
    with conectar() as conn:
        garantir_tabelas_lms(conn)
        cfg = conn.execute("SELECT * FROM curso_config WHERE slug=?", (slug,)).fetchone()
        modulos = []
        for m in conn.execute(
            "SELECT * FROM curso_modulos WHERE slug=? ORDER BY ordem, id", (slug,)
        ).fetchall():
            aulas = [
                dict(a)
                for a in conn.execute(
                    "SELECT * FROM curso_aulas WHERE modulo_id=? ORDER BY ordem, id", (m["id"],)
                ).fetchall()
            ]
            quiz = conn.execute("SELECT * FROM curso_quizzes WHERE modulo_id=?", (m["id"],)).fetchone()
            quiz_out = dict(quiz) if quiz else None
            if quiz_out:
                perguntas = []
                for p in conn.execute(
                    "SELECT * FROM quiz_perguntas WHERE quiz_id=? ORDER BY ordem, id", (quiz["id"],)
                ).fetchall():
                    opcoes = [
                        dict(o)
                        for o in conn.execute(
                            "SELECT * FROM quiz_opcoes WHERE pergunta_id=? ORDER BY ordem, id", (p["id"],)
                        ).fetchall()
                    ]
                    perguntas.append({**dict(p), "opcoes": opcoes})
                quiz_out["perguntas"] = perguntas
            modulos.append({**dict(m), "aulas": aulas, "quiz": quiz_out})
    return {"slug": slug, "config": dict(cfg) if cfg else None, "modulos": modulos}


# ---------------------------------------------------------------------------
# Módulos
# ---------------------------------------------------------------------------

class ModuloIn(BaseModel):
    slug: str = Field(min_length=1)
    titulo: str = Field(min_length=1)
    descricao: Optional[str] = None
    ordem: int = 0
    nota_minima: Optional[int] = Field(default=None, ge=0, le=100)
    publicado: bool = True
    # Acesso público (sem login/matrícula). Default False: exige ação explícita
    # de um admin autenticado para abrir um módulo ao visitante anônimo.
    acesso_publico: bool = False


@router.post("/modulos")
def criar_modulo(payload: ModuloIn, sessao: dict = Depends(exigir_admin)):
    with conectar() as conn:
        garantir_tabelas_lms(conn)
        cur = conn.execute(
            "INSERT INTO curso_modulos (slug, titulo, descricao, ordem, nota_minima, publicado, acesso_publico, criado_em) VALUES (?,?,?,?,?,?,?,?)",
            (
                payload.slug.strip(),
                payload.titulo.strip(),
                payload.descricao,
                int(payload.ordem),
                payload.nota_minima,
                1 if payload.publicado else 0,
                1 if payload.acesso_publico else 0,
                _agora(),
            ),
        )
        mid = int(cur.lastrowid)
        registrar_auditoria(conn, "curso_modulo", mid, "criar", _usuario(sessao), depois=payload.model_dump())
    return {"ok": True, "id": mid}


@router.put("/modulos/{modulo_id}")
def editar_modulo(modulo_id: int, payload: ModuloIn, sessao: dict = Depends(exigir_admin)):
    with conectar() as conn:
        garantir_tabelas_lms(conn)
        existente = conn.execute("SELECT id FROM curso_modulos WHERE id=?", (modulo_id,)).fetchone()
        if not existente:
            raise HTTPException(status_code=404, detail="Módulo não encontrado.")
        conn.execute(
            "UPDATE curso_modulos SET titulo=?, descricao=?, ordem=?, nota_minima=?, publicado=?, acesso_publico=? WHERE id=?",
            (
                payload.titulo.strip(),
                payload.descricao,
                int(payload.ordem),
                payload.nota_minima,
                1 if payload.publicado else 0,
                1 if payload.acesso_publico else 0,
                modulo_id,
            ),
        )
        registrar_auditoria(conn, "curso_modulo", modulo_id, "editar", _usuario(sessao), depois=payload.model_dump())
    return {"ok": True, "id": modulo_id}


@router.delete("/modulos/{modulo_id}")
def excluir_modulo(modulo_id: int, sessao: dict = Depends(exigir_admin)):
    """Exclui módulo com validação: só permite se não houver progresso de aluno
    registrado nas aulas do módulo (evita apagar histórico do aluno)."""
    with conectar() as conn:
        garantir_tabelas_lms(conn)
        existente = conn.execute("SELECT id FROM curso_modulos WHERE id=?", (modulo_id,)).fetchone()
        if not existente:
            raise HTTPException(status_code=404, detail="Módulo não encontrado.")
        com_progresso = conn.execute(
            """
            SELECT COUNT(*) AS n FROM aluno_aula_progresso p
            JOIN curso_aulas a ON a.id = p.aula_id WHERE a.modulo_id=?
            """,
            (modulo_id,),
        ).fetchone()["n"]
        if int(com_progresso) > 0:
            raise HTTPException(
                status_code=409,
                detail="Há alunos com progresso neste módulo. Despublique-o em vez de excluir.",
            )
        aula_ids = [r["id"] for r in conn.execute("SELECT id FROM curso_aulas WHERE modulo_id=?", (modulo_id,)).fetchall()]
        quiz = conn.execute("SELECT id FROM curso_quizzes WHERE modulo_id=?", (modulo_id,)).fetchone()
        if quiz:
            perg_ids = [r["id"] for r in conn.execute("SELECT id FROM quiz_perguntas WHERE quiz_id=?", (quiz["id"],)).fetchall()]
            for pid in perg_ids:
                conn.execute("DELETE FROM quiz_opcoes WHERE pergunta_id=?", (pid,))
            conn.execute("DELETE FROM quiz_perguntas WHERE quiz_id=?", (quiz["id"],))
            conn.execute("DELETE FROM curso_quizzes WHERE id=?", (quiz["id"],))
        for aid in aula_ids:
            conn.execute("DELETE FROM curso_aulas WHERE id=?", (aid,))
        conn.execute("DELETE FROM curso_modulos WHERE id=?", (modulo_id,))
        registrar_auditoria(conn, "curso_modulo", modulo_id, "excluir", _usuario(sessao))
    return {"ok": True, "id": modulo_id, "status": "excluido"}


@router.post("/modulos/{modulo_id}/duplicar")
def duplicar_modulo(modulo_id: int, sessao: dict = Depends(exigir_admin)):
    with conectar() as conn:
        garantir_tabelas_lms(conn)
        mod = conn.execute("SELECT * FROM curso_modulos WHERE id=?", (modulo_id,)).fetchone()
        if not mod:
            raise HTTPException(status_code=404, detail="Módulo não encontrado.")
        cur = conn.execute(
            "INSERT INTO curso_modulos (slug, titulo, descricao, ordem, nota_minima, publicado, criado_em) VALUES (?,?,?,?,?,?,?)",
            (mod["slug"], f"{mod['titulo']} (cópia)", mod["descricao"], int(mod["ordem"]) + 1, mod["nota_minima"], 0, _agora()),
        )
        novo_id = int(cur.lastrowid)
        for a in conn.execute("SELECT * FROM curso_aulas WHERE modulo_id=? ORDER BY ordem, id", (modulo_id,)).fetchall():
            conn.execute(
                """
                INSERT INTO curso_aulas
                (modulo_id, titulo, descricao, tipo, conteudo, video_url, capa_url, material_url, ordem, duracao_min, obrigatoria, percentual_minimo, publicado, criado_em)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    novo_id, a["titulo"], a["descricao"], a["tipo"], a["conteudo"], a["video_url"], a["capa_url"],
                    a["material_url"], a["ordem"], a["duracao_min"], a["obrigatoria"], a["percentual_minimo"], 0, _agora(),
                ),
            )
        registrar_auditoria(conn, "curso_modulo", novo_id, "duplicar", _usuario(sessao), antes={"de": modulo_id})
    return {"ok": True, "id": novo_id}


class ReordenarIn(BaseModel):
    ids: list[int] = Field(default_factory=list)


@router.post("/modulos/reordenar")
def reordenar_modulos(payload: ReordenarIn, sessao: dict = Depends(exigir_admin)):
    with conectar() as conn:
        garantir_tabelas_lms(conn)
        for ordem, mid in enumerate(payload.ids):
            conn.execute("UPDATE curso_modulos SET ordem=? WHERE id=?", (ordem, int(mid)))
    return {"ok": True}


# ---------------------------------------------------------------------------
# Aulas
# ---------------------------------------------------------------------------

class AulaIn(BaseModel):
    modulo_id: int
    titulo: str = Field(min_length=1)
    descricao: Optional[str] = None
    tipo: str = "texto"
    conteudo: Optional[str] = None
    video_url: Optional[str] = None
    capa_url: Optional[str] = None
    material_url: Optional[str] = None
    ordem: int = 0
    duracao_min: Optional[int] = None
    obrigatoria: bool = True
    percentual_minimo: Optional[int] = Field(default=None, ge=0, le=100)
    publicado: bool = True


def _tipo_aula(tipo: str) -> str:
    return tipo if tipo in TIPOS_AULA else "texto"


@router.post("/aulas")
def criar_aula(payload: AulaIn, sessao: dict = Depends(exigir_admin)):
    with conectar() as conn:
        garantir_tabelas_lms(conn)
        if not conn.execute("SELECT id FROM curso_modulos WHERE id=?", (payload.modulo_id,)).fetchone():
            raise HTTPException(status_code=404, detail="Módulo não encontrado.")
        cur = conn.execute(
            """
            INSERT INTO curso_aulas
            (modulo_id, titulo, descricao, tipo, conteudo, video_url, capa_url, material_url, ordem, duracao_min, obrigatoria, percentual_minimo, publicado, criado_em)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                payload.modulo_id, payload.titulo.strip(), payload.descricao, _tipo_aula(payload.tipo),
                payload.conteudo, payload.video_url, payload.capa_url, payload.material_url, int(payload.ordem),
                payload.duracao_min, 1 if payload.obrigatoria else 0, payload.percentual_minimo,
                1 if payload.publicado else 0, _agora(),
            ),
        )
        aid = int(cur.lastrowid)
        registrar_auditoria(conn, "curso_aula", aid, "criar", _usuario(sessao), depois={"titulo": payload.titulo})
    return {"ok": True, "id": aid}


@router.put("/aulas/{aula_id}")
def editar_aula(aula_id: int, payload: AulaIn, sessao: dict = Depends(exigir_admin)):
    with conectar() as conn:
        garantir_tabelas_lms(conn)
        if not conn.execute("SELECT id FROM curso_aulas WHERE id=?", (aula_id,)).fetchone():
            raise HTTPException(status_code=404, detail="Aula não encontrada.")
        conn.execute(
            """
            UPDATE curso_aulas SET titulo=?, descricao=?, tipo=?, conteudo=?, video_url=?, capa_url=?,
            material_url=?, ordem=?, duracao_min=?, obrigatoria=?, percentual_minimo=?, publicado=? WHERE id=?
            """,
            (
                payload.titulo.strip(), payload.descricao, _tipo_aula(payload.tipo), payload.conteudo,
                payload.video_url, payload.capa_url, payload.material_url, int(payload.ordem), payload.duracao_min,
                1 if payload.obrigatoria else 0, payload.percentual_minimo, 1 if payload.publicado else 0, aula_id,
            ),
        )
        registrar_auditoria(conn, "curso_aula", aula_id, "editar", _usuario(sessao))
    return {"ok": True, "id": aula_id}


@router.delete("/aulas/{aula_id}")
def excluir_aula(aula_id: int, sessao: dict = Depends(exigir_admin)):
    with conectar() as conn:
        garantir_tabelas_lms(conn)
        if not conn.execute("SELECT id FROM curso_aulas WHERE id=?", (aula_id,)).fetchone():
            raise HTTPException(status_code=404, detail="Aula não encontrada.")
        conn.execute("DELETE FROM aluno_aula_progresso WHERE aula_id=?", (aula_id,))
        conn.execute("DELETE FROM curso_aulas WHERE id=?", (aula_id,))
        registrar_auditoria(conn, "curso_aula", aula_id, "excluir", _usuario(sessao))
    return {"ok": True, "id": aula_id, "status": "excluido"}


@router.post("/aulas/reordenar")
def reordenar_aulas(payload: ReordenarIn, sessao: dict = Depends(exigir_admin)):
    with conectar() as conn:
        garantir_tabelas_lms(conn)
        for ordem, aid in enumerate(payload.ids):
            conn.execute("UPDATE curso_aulas SET ordem=? WHERE id=?", (ordem, int(aid)))
    return {"ok": True}


# ---------------------------------------------------------------------------
# Avaliações (quiz, perguntas, opções)
# ---------------------------------------------------------------------------

class QuizIn(BaseModel):
    modulo_id: int
    titulo: Optional[str] = None
    nota_minima: Optional[int] = Field(default=None, ge=0, le=100)
    num_perguntas: Optional[int] = Field(default=None, ge=1)
    max_tentativas: Optional[int] = Field(default=None, ge=1)
    intervalo_min: int = 0
    embaralhar_perguntas: bool = True
    embaralhar_opcoes: bool = True
    publicado: bool = True


@router.put("/quizzes")
def salvar_quiz(payload: QuizIn, sessao: dict = Depends(exigir_admin)):
    """Cria ou atualiza a avaliação do módulo (relação 1:1 com o módulo)."""
    with conectar() as conn:
        garantir_tabelas_lms(conn)
        if not conn.execute("SELECT id FROM curso_modulos WHERE id=?", (payload.modulo_id,)).fetchone():
            raise HTTPException(status_code=404, detail="Módulo não encontrado.")
        existente = conn.execute("SELECT id FROM curso_quizzes WHERE modulo_id=?", (payload.modulo_id,)).fetchone()
        if existente:
            conn.execute(
                """
                UPDATE curso_quizzes SET titulo=?, nota_minima=?, num_perguntas=?, max_tentativas=?,
                intervalo_min=?, embaralhar_perguntas=?, embaralhar_opcoes=?, publicado=? WHERE id=?
                """,
                (
                    payload.titulo, payload.nota_minima, payload.num_perguntas, payload.max_tentativas,
                    int(payload.intervalo_min), 1 if payload.embaralhar_perguntas else 0,
                    1 if payload.embaralhar_opcoes else 0, 1 if payload.publicado else 0, existente["id"],
                ),
            )
            qid = int(existente["id"])
        else:
            cur = conn.execute(
                """
                INSERT INTO curso_quizzes
                (modulo_id, titulo, nota_minima, num_perguntas, max_tentativas, intervalo_min, embaralhar_perguntas, embaralhar_opcoes, publicado, criado_em)
                VALUES (?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    payload.modulo_id, payload.titulo, payload.nota_minima, payload.num_perguntas, payload.max_tentativas,
                    int(payload.intervalo_min), 1 if payload.embaralhar_perguntas else 0,
                    1 if payload.embaralhar_opcoes else 0, 1 if payload.publicado else 0, _agora(),
                ),
            )
            qid = int(cur.lastrowid)
        registrar_auditoria(conn, "curso_quiz", qid, "salvar", _usuario(sessao))
    return {"ok": True, "id": qid}


class OpcaoIn(BaseModel):
    texto: str = Field(min_length=1)
    correta: bool = False


class PerguntaIn(BaseModel):
    quiz_id: int
    enunciado: str = Field(min_length=1)
    tipo: str = "unica"
    explicacao: Optional[str] = None
    ordem: int = 0
    ativa: bool = True
    opcoes: list[OpcaoIn] = Field(default_factory=list)


def _validar_pergunta(payload: PerguntaIn) -> None:
    tipo = payload.tipo if payload.tipo in TIPOS_PERGUNTA else "unica"
    if tipo in ("unica", "verdadeiro_falso", "multipla"):
        if len(payload.opcoes) < 2:
            raise HTTPException(status_code=422, detail="Cadastre pelo menos duas alternativas.")
        corretas = sum(1 for o in payload.opcoes if o.correta)
        if tipo == "unica" and corretas != 1:
            raise HTTPException(status_code=422, detail="Marque exatamente uma alternativa correta.")
        if corretas < 1:
            raise HTTPException(status_code=422, detail="Marque ao menos uma alternativa correta.")


@router.post("/perguntas")
def criar_pergunta(payload: PerguntaIn, sessao: dict = Depends(exigir_admin)):
    tipo = payload.tipo if payload.tipo in TIPOS_PERGUNTA else "unica"
    _validar_pergunta(payload)
    with conectar() as conn:
        garantir_tabelas_lms(conn)
        if not conn.execute("SELECT id FROM curso_quizzes WHERE id=?", (payload.quiz_id,)).fetchone():
            raise HTTPException(status_code=404, detail="Avaliação não encontrada.")
        cur = conn.execute(
            "INSERT INTO quiz_perguntas (quiz_id, enunciado, tipo, explicacao, ordem, ativa, criado_em) VALUES (?,?,?,?,?,?,?)",
            (payload.quiz_id, payload.enunciado.strip(), tipo, payload.explicacao, int(payload.ordem), 1 if payload.ativa else 0, _agora()),
        )
        pid = int(cur.lastrowid)
        for ordem, op in enumerate(payload.opcoes):
            conn.execute(
                "INSERT INTO quiz_opcoes (pergunta_id, texto, correta, ordem) VALUES (?,?,?,?)",
                (pid, op.texto.strip(), 1 if op.correta else 0, ordem),
            )
        registrar_auditoria(conn, "quiz_pergunta", pid, "criar", _usuario(sessao))
    return {"ok": True, "id": pid}


@router.put("/perguntas/{pergunta_id}")
def editar_pergunta(pergunta_id: int, payload: PerguntaIn, sessao: dict = Depends(exigir_admin)):
    tipo = payload.tipo if payload.tipo in TIPOS_PERGUNTA else "unica"
    _validar_pergunta(payload)
    with conectar() as conn:
        garantir_tabelas_lms(conn)
        if not conn.execute("SELECT id FROM quiz_perguntas WHERE id=?", (pergunta_id,)).fetchone():
            raise HTTPException(status_code=404, detail="Pergunta não encontrada.")
        conn.execute(
            "UPDATE quiz_perguntas SET enunciado=?, tipo=?, explicacao=?, ordem=?, ativa=? WHERE id=?",
            (payload.enunciado.strip(), tipo, payload.explicacao, int(payload.ordem), 1 if payload.ativa else 0, pergunta_id),
        )
        conn.execute("DELETE FROM quiz_opcoes WHERE pergunta_id=?", (pergunta_id,))
        for ordem, op in enumerate(payload.opcoes):
            conn.execute(
                "INSERT INTO quiz_opcoes (pergunta_id, texto, correta, ordem) VALUES (?,?,?,?)",
                (pergunta_id, op.texto.strip(), 1 if op.correta else 0, ordem),
            )
        registrar_auditoria(conn, "quiz_pergunta", pergunta_id, "editar", _usuario(sessao))
    return {"ok": True, "id": pergunta_id}


@router.delete("/perguntas/{pergunta_id}")
def excluir_pergunta(pergunta_id: int, sessao: dict = Depends(exigir_admin)):
    with conectar() as conn:
        garantir_tabelas_lms(conn)
        if not conn.execute("SELECT id FROM quiz_perguntas WHERE id=?", (pergunta_id,)).fetchone():
            raise HTTPException(status_code=404, detail="Pergunta não encontrada.")
        conn.execute("DELETE FROM quiz_opcoes WHERE pergunta_id=?", (pergunta_id,))
        conn.execute("DELETE FROM quiz_perguntas WHERE id=?", (pergunta_id,))
        registrar_auditoria(conn, "quiz_pergunta", pergunta_id, "excluir", _usuario(sessao))
    return {"ok": True, "id": pergunta_id, "status": "excluido"}


# ---------------------------------------------------------------------------
# Gestão de alunos
# ---------------------------------------------------------------------------

@router.get("/alunos")
def listar_alunos(slug: Optional[str] = None, sessao: dict = Depends(exigir_admin)):
    """Lista matrículas com progresso resumido (opcionalmente filtrando por curso)."""
    with conectar() as conn:
        garantir_tabelas_lms(conn)
        if slug:
            rows = conn.execute(
                """
                SELECT ac.aluno_id, ac.slug, ac.liberado_em, COALESCE(ac.suspenso,0) AS suspenso, a.nome, a.email
                FROM alunos_cursos ac JOIN alunos a ON a.id=ac.aluno_id WHERE ac.slug=? ORDER BY a.nome
                """,
                (slug,),
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT ac.aluno_id, ac.slug, ac.liberado_em, COALESCE(ac.suspenso,0) AS suspenso, a.nome, a.email
                FROM alunos_cursos ac JOIN alunos a ON a.id=ac.aluno_id ORDER BY a.nome LIMIT 500
                """
            ).fetchall()
        saida = []
        for r in rows:
            feitas = conn.execute(
                "SELECT COUNT(*) AS n FROM aluno_aula_progresso WHERE aluno_id=? AND slug=? AND status='concluida'",
                (r["aluno_id"], r["slug"]),
            ).fetchone()["n"]
            saida.append({**dict(r), "aulas_concluidas": int(feitas)})
    return saida


@router.get("/alunos/{aluno_id}/cursos/{slug}/tentativas")
def tentativas_do_aluno(aluno_id: int, slug: str, sessao: dict = Depends(exigir_admin)):
    with conectar() as conn:
        garantir_tabelas_lms(conn)
        rows = conn.execute(
            """
            SELECT t.id, t.quiz_id, t.nota, t.aprovado, t.acertos, t.total_perguntas, t.finalizada_em, m.titulo AS modulo
            FROM quiz_tentativas t JOIN curso_quizzes q ON q.id=t.quiz_id JOIN curso_modulos m ON m.id=q.modulo_id
            WHERE t.aluno_id=? AND t.slug=? ORDER BY t.id DESC LIMIT 200
            """,
            (aluno_id, slug),
        ).fetchall()
    return [dict(r) for r in rows]


class MatriculaAcaoIn(BaseModel):
    aluno_id: int
    slug: str = Field(min_length=1)


@router.post("/alunos/liberar-curso")
def liberar_curso(payload: MatriculaAcaoIn, sessao: dict = Depends(exigir_admin)):
    """Libera o curso manualmente (matrícula administrativa), idempotente."""
    with conectar() as conn:
        garantir_tabelas_lms(conn)
        conn.execute(
            "INSERT OR IGNORE INTO alunos_cursos (aluno_id, slug, liberado_em) VALUES (?,?,?)",
            (payload.aluno_id, payload.slug.strip(), _agora()),
        )
        conn.execute(
            "UPDATE alunos_cursos SET suspenso=0 WHERE aluno_id=? AND slug=?",
            (payload.aluno_id, payload.slug.strip()),
        )
        registrar_auditoria(conn, "matricula", f"{payload.aluno_id}:{payload.slug}", "liberar", _usuario(sessao))
    return {"ok": True}


@router.post("/alunos/suspender")
def suspender_curso(payload: MatriculaAcaoIn, sessao: dict = Depends(exigir_admin)):
    with conectar() as conn:
        garantir_tabelas_lms(conn)
        conn.execute(
            "UPDATE alunos_cursos SET suspenso=1 WHERE aluno_id=? AND slug=?",
            (payload.aluno_id, payload.slug.strip()),
        )
        registrar_auditoria(conn, "matricula", f"{payload.aluno_id}:{payload.slug}", "suspender", _usuario(sessao))
    return {"ok": True}


class ModuloManualIn(BaseModel):
    aluno_id: int
    modulo_id: int


@router.post("/alunos/liberar-modulo")
def liberar_modulo(payload: ModuloManualIn, sessao: dict = Depends(exigir_admin)):
    with conectar() as conn:
        garantir_tabelas_lms(conn)
        if not conn.execute("SELECT id FROM curso_modulos WHERE id=?", (payload.modulo_id,)).fetchone():
            raise HTTPException(status_code=404, detail="Módulo não encontrado.")
        conn.execute(
            "INSERT OR IGNORE INTO aluno_modulo_liberado (aluno_id, modulo_id, liberado_em, origem) VALUES (?,?,?,?)",
            (payload.aluno_id, payload.modulo_id, _agora(), "admin"),
        )
        registrar_auditoria(conn, "modulo_liberado", f"{payload.aluno_id}:{payload.modulo_id}", "liberar", _usuario(sessao))
    return {"ok": True}


class ResetTentativasIn(BaseModel):
    aluno_id: int
    quiz_id: int
    confirmar: bool = False


@router.post("/alunos/resetar-tentativas")
def resetar_tentativas(payload: ResetTentativasIn, sessao: dict = Depends(exigir_admin)):
    if not payload.confirmar:
        raise HTTPException(status_code=400, detail="Confirmação obrigatória para resetar tentativas.")
    with conectar() as conn:
        garantir_tabelas_lms(conn)
        tentativas = conn.execute(
            "SELECT id FROM quiz_tentativas WHERE aluno_id=? AND quiz_id=?",
            (payload.aluno_id, payload.quiz_id),
        ).fetchall()
        for t in tentativas:
            conn.execute("DELETE FROM quiz_respostas WHERE tentativa_id=?", (t["id"],))
        conn.execute("DELETE FROM quiz_tentativas WHERE aluno_id=? AND quiz_id=?", (payload.aluno_id, payload.quiz_id))
        registrar_auditoria(conn, "quiz_tentativas", f"{payload.aluno_id}:{payload.quiz_id}", "resetar", _usuario(sessao))
    return {"ok": True, "removidas": len(tentativas)}


class ResetProgressoIn(BaseModel):
    aluno_id: int
    slug: str = Field(min_length=1)
    confirmar: bool = False


@router.post("/alunos/resetar-progresso")
def resetar_progresso(payload: ResetProgressoIn, sessao: dict = Depends(exigir_admin)):
    if not payload.confirmar:
        raise HTTPException(status_code=400, detail="Confirmação obrigatória para resetar o progresso.")
    with conectar() as conn:
        garantir_tabelas_lms(conn)
        conn.execute(
            "DELETE FROM aluno_aula_progresso WHERE aluno_id=? AND slug=?",
            (payload.aluno_id, payload.slug.strip()),
        )
        conn.execute(
            "DELETE FROM quiz_tentativas WHERE aluno_id=? AND slug=?",
            (payload.aluno_id, payload.slug.strip()),
        )
        conn.execute(
            """
            DELETE FROM aluno_modulo_liberado WHERE aluno_id=? AND modulo_id IN
            (SELECT id FROM curso_modulos WHERE slug=?)
            """,
            (payload.aluno_id, payload.slug.strip()),
        )
        registrar_auditoria(conn, "progresso", f"{payload.aluno_id}:{payload.slug}", "resetar", _usuario(sessao))
    return {"ok": True}
