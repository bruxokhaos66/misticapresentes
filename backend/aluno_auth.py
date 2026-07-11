from __future__ import annotations

import secrets
from datetime import datetime, timedelta

from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response
from pydantic import BaseModel, EmailStr, Field

from backend.database import conectar
from backend.panel_sessions import exigir_sessao_ou_chave_api
from backend.rate_limit import limitar_requisicoes
from config import hash_password_pbkdf2

router = APIRouter(prefix="/api", tags=["alunos"])

COOKIE_NOME = "mistica_aluno_sessao"
DURACAO_SESSAO_HORAS = 24 * 30

limitar_login_aluno = limitar_requisicoes("login_aluno", limite=10, janela_segundos=60)


def _agora() -> datetime:
    return datetime.now()


def _txt(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def garantir_tabelas_alunos(conn) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS alunos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            senha_hash TEXT NOT NULL,
            senha_salt TEXT NOT NULL,
            criado_em TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS alunos_cursos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            aluno_id INTEGER NOT NULL,
            slug TEXT NOT NULL,
            liberado_em TEXT NOT NULL,
            UNIQUE(aluno_id, slug)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS alunos_sessoes (
            token TEXT PRIMARY KEY,
            aluno_id INTEGER NOT NULL,
            criada_em TEXT NOT NULL,
            expira_em TEXT NOT NULL
        )
        """
    )


def criar_ou_atualizar_aluno(conn, *, nome: str, email: str, senha: str) -> int:
    """Cria a conta do aluno no momento da compra (ou reaproveita uma já existente
    pelo e-mail, atualizando a senha informada). A senha só é conhecida em texto
    puro aqui, dentro da requisição; é hasheada com PBKDF2 antes de gravar."""
    email_normalizado = email.strip().lower()
    salt = secrets.token_hex(16)
    senha_hash = hash_password_pbkdf2(senha, salt.encode("utf-8"))
    agora = _txt(_agora())
    existente = conn.execute("SELECT id FROM alunos WHERE email=?", (email_normalizado,)).fetchone()
    if existente:
        conn.execute(
            "UPDATE alunos SET nome=?, senha_hash=?, senha_salt=? WHERE id=?",
            (nome.strip(), senha_hash, salt, existente["id"]),
        )
        return int(existente["id"])
    cur = conn.execute(
        "INSERT INTO alunos (nome, email, senha_hash, senha_salt, criado_em) VALUES (?,?,?,?,?)",
        (nome.strip(), email_normalizado, senha_hash, salt, agora),
    )
    return int(cur.lastrowid)


def conceder_acesso_curso(conn, *, aluno_id: int, slug: str) -> None:
    conn.execute(
        "INSERT OR IGNORE INTO alunos_cursos (aluno_id, slug, liberado_em) VALUES (?,?,?)",
        (aluno_id, slug, _txt(_agora())),
    )


def aluno_tem_acesso(conn, *, aluno_id: int, slug: str) -> bool:
    linha = conn.execute(
        "SELECT id FROM alunos_cursos WHERE aluno_id=? AND slug=?", (aluno_id, slug)
    ).fetchone()
    return linha is not None


class AlunoLoginIn(BaseModel):
    email: EmailStr
    senha: str = Field(min_length=1)


def _validar_sessao_aluno(token: str | None) -> dict | None:
    if not token:
        return None
    with conectar() as conn:
        garantir_tabelas_alunos(conn)
        linha = conn.execute(
            """
            SELECT s.token, s.aluno_id, s.expira_em, a.nome, a.email
            FROM alunos_sessoes s JOIN alunos a ON a.id = s.aluno_id
            WHERE s.token=?
            """,
            (token,),
        ).fetchone()
        if not linha:
            return None
        agora = _agora()
        try:
            expira = datetime.strptime(linha["expira_em"], "%Y-%m-%d %H:%M:%S")
        except Exception:
            expira = None
        if not expira or expira < agora:
            conn.execute("DELETE FROM alunos_sessoes WHERE token=?", (token,))
            return None
        return dict(linha)


def sessao_aluno_atual(mistica_aluno_sessao: str | None = Cookie(default=None)) -> dict:
    dados = _validar_sessao_aluno(mistica_aluno_sessao)
    if not dados:
        raise HTTPException(status_code=401, detail="Faça login para acessar o conteúdo do curso.")
    return dados


def sessao_aluno_opcional(mistica_aluno_sessao: str | None = Cookie(default=None)) -> dict | None:
    return _validar_sessao_aluno(mistica_aluno_sessao)


@router.post("/alunos/login", dependencies=[Depends(limitar_login_aluno)])
def login_aluno(payload: AlunoLoginIn, request: Request, response: Response):
    email = payload.email.strip().lower()
    with conectar() as conn:
        garantir_tabelas_alunos(conn)
        aluno = conn.execute(
            "SELECT id, nome, email, senha_hash, senha_salt FROM alunos WHERE email=?", (email,)
        ).fetchone()
    senha_confere = False
    if aluno:
        calculado = hash_password_pbkdf2(payload.senha, str(aluno["senha_salt"]).encode("utf-8"))
        senha_confere = secrets.compare_digest(str(calculado), str(aluno["senha_hash"]))
    if not aluno or not senha_confere:
        raise HTTPException(status_code=401, detail="E-mail ou senha inválidos.")

    token = secrets.token_urlsafe(32)
    agora = _agora()
    expira = agora + timedelta(hours=DURACAO_SESSAO_HORAS)
    with conectar() as conn:
        garantir_tabelas_alunos(conn)
        conn.execute(
            "INSERT INTO alunos_sessoes (token, aluno_id, criada_em, expira_em) VALUES (?,?,?,?)",
            (token, aluno["id"], _txt(agora), _txt(expira)),
        )
    https = request.url.scheme == "https"
    response.set_cookie(
        key=COOKIE_NOME,
        value=token,
        httponly=True,
        # A Escola Mística é servida em domínio estático (GitHub Pages /
        # domínio próprio) enquanto esta API roda em outro domínio (Render),
        # ou seja, é uma chamada cross-site de verdade — não apenas
        # cross-subdomínio como o painel administrativo. SameSite=Lax não
        # trafega em fetch() cross-site, então aqui é preciso None+Secure.
        secure=https,
        samesite="none" if https else "lax",
        max_age=DURACAO_SESSAO_HORAS * 3600,
        path="/",
    )
    return {"ok": True, "nome": aluno["nome"], "email": aluno["email"]}


@router.post("/alunos/logout")
def logout_aluno(response: Response, mistica_aluno_sessao: str | None = Cookie(default=None)):
    if mistica_aluno_sessao:
        with conectar() as conn:
            garantir_tabelas_alunos(conn)
            conn.execute("DELETE FROM alunos_sessoes WHERE token=?", (mistica_aluno_sessao,))
    response.delete_cookie(COOKIE_NOME, path="/")
    return {"ok": True}


@router.get("/alunos/me")
def aluno_atual(sessao: dict = Depends(sessao_aluno_atual)):
    with conectar() as conn:
        garantir_tabelas_alunos(conn)
        cursos = conn.execute(
            "SELECT slug FROM alunos_cursos WHERE aluno_id=?", (sessao["aluno_id"],)
        ).fetchall()
    return {"nome": sessao["nome"], "email": sessao["email"], "cursos": [c["slug"] for c in cursos]}


@router.get("/cursos/{slug}/conteudo")
def conteudo_curso(slug: str, sessao: dict | None = Depends(sessao_aluno_opcional)):
    from backend.course_routes import CATALOGO_CURSOS_PAGOS, garantir_tabela_cursos

    with conectar() as conn:
        garantir_tabelas_alunos(conn)
        if slug in CATALOGO_CURSOS_PAGOS:
            if not sessao:
                raise HTTPException(status_code=401, detail="Faça login para acessar o conteúdo deste curso.")
            if not aluno_tem_acesso(conn, aluno_id=sessao["aluno_id"], slug=slug):
                raise HTTPException(status_code=403, detail="Você ainda não tem acesso a este curso.")
        garantir_tabela_cursos(conn)
        rows = conn.execute(
            "SELECT id, titulo, categoria, tipo, descricao, url, criado_em FROM cursos_materiais WHERE categoria=? ORDER BY id",
            (slug,),
        ).fetchall()
    return [dict(row) for row in rows]


@router.get("/checkout/cursos")
def listar_pedidos_cursos(sessao: dict = Depends(exigir_sessao_ou_chave_api())):
    from backend.course_routes import garantir_tabela_pedidos_cursos

    with conectar() as conn:
        garantir_tabela_pedidos_cursos(conn)
        rows = conn.execute(
            """
            SELECT id, slug, titulo, preco, status, nome, email, criado_em
            FROM pedidos_cursos ORDER BY id DESC LIMIT 200
            """
        ).fetchall()
    return [dict(row) for row in rows]


@router.post("/checkout/cursos/{pedido_id}/confirmar")
def confirmar_pagamento_curso(pedido_id: int, sessao: dict = Depends(exigir_sessao_ou_chave_api("adm"))):
    from backend.course_routes import garantir_tabela_pedidos_cursos

    with conectar() as conn:
        garantir_tabela_pedidos_cursos(conn)
        garantir_tabelas_alunos(conn)
        pedido = conn.execute(
            "SELECT id, slug, aluno_id, status FROM pedidos_cursos WHERE id=?", (pedido_id,)
        ).fetchone()
        if not pedido:
            raise HTTPException(status_code=404, detail="Pedido não encontrado.")
        if not pedido["aluno_id"]:
            raise HTTPException(status_code=409, detail="Pedido sem cadastro de aluno vinculado.")
        conn.execute("UPDATE pedidos_cursos SET status='Pago' WHERE id=?", (pedido_id,))
        conceder_acesso_curso(conn, aluno_id=pedido["aluno_id"], slug=pedido["slug"])
    return {"ok": True, "id": pedido_id, "status": "Pago"}
