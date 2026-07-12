from __future__ import annotations

import secrets
from datetime import datetime, timedelta

from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response
from pydantic import BaseModel, EmailStr, Field

from backend.database import conectar
from backend.panel_sessions import exigir_sessao_ou_chave_api
from backend.rate_limit import limitar_requisicoes
from config import OFFICIAL_DOMAIN, hash_password_pbkdf2

router = APIRouter(prefix="/api", tags=["alunos"])

COOKIE_NOME = "mistica_aluno_sessao"
DURACAO_SESSAO_HORAS = 24 * 30
DURACAO_CONVITE_HORAS = 24 * 7

limitar_login_aluno = limitar_requisicoes("login_aluno", limite=10, janela_segundos=60)
limitar_definir_senha = limitar_requisicoes("definir_senha_aluno", limite=10, janela_segundos=60)


def _agora() -> datetime:
    return datetime.now()


def _txt(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def _escape_certificado(valor) -> str:
    return (
        str(valor if valor is not None else "")
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def garantir_tabelas_alunos(conn) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS alunos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            senha_hash TEXT,
            senha_salt TEXT,
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
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS alunos_convites (
            token TEXT PRIMARY KEY,
            aluno_id INTEGER NOT NULL,
            criado_em TEXT NOT NULL,
            expira_em TEXT NOT NULL,
            usado_em TEXT
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS alunos_progresso (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            aluno_id INTEGER NOT NULL,
            slug TEXT NOT NULL,
            material_id INTEGER NOT NULL,
            concluido_em TEXT NOT NULL,
            UNIQUE(aluno_id, material_id)
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_alunos_progresso_aluno_slug ON alunos_progresso(aluno_id, slug)")


def obter_ou_criar_aluno_sem_senha(conn, *, nome: str, email: str) -> int:
    """Registra o comprador no momento da compra (nome + e-mail), sem senha
    ainda: a senha só é criada depois que o pagamento é confirmado, através do
    link de convite (ver criar_convite_acesso / definir_senha_aluno)."""
    email_normalizado = email.strip().lower()
    agora = _txt(_agora())
    existente = conn.execute("SELECT id FROM alunos WHERE email=?", (email_normalizado,)).fetchone()
    if existente:
        conn.execute("UPDATE alunos SET nome=? WHERE id=?", (nome.strip(), existente["id"]))
        return int(existente["id"])
    cur = conn.execute(
        "INSERT INTO alunos (nome, email, criado_em) VALUES (?,?,?)",
        (nome.strip(), email_normalizado, agora),
    )
    return int(cur.lastrowid)


def criar_convite_acesso(conn, *, aluno_id: int) -> str:
    """Gera um link de uso único para o aluno criar a própria senha depois que
    o pagamento é confirmado. O admin envia esse link manualmente pelo
    WhatsApp (não há envio de e-mail configurado no projeto)."""
    token = secrets.token_urlsafe(24)
    agora = _agora()
    expira = agora + timedelta(hours=DURACAO_CONVITE_HORAS)
    conn.execute(
        "INSERT INTO alunos_convites (token, aluno_id, criado_em, expira_em) VALUES (?,?,?,?)",
        (token, aluno_id, _txt(agora), _txt(expira)),
    )
    return token


def link_convite_acesso(token: str) -> str:
    return f"https://www.{OFFICIAL_DOMAIN}/escola.html?acesso={token}"


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


class AlunoDefinirSenhaIn(BaseModel):
    token: str = Field(min_length=1)
    senha: str = Field(min_length=8)


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


def _cookie_kwargs(request: Request) -> dict:
    https = request.url.scheme == "https"
    return dict(
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


def _criar_sessao_aluno(conn, *, aluno_id: int) -> str:
    token = secrets.token_urlsafe(32)
    agora = _agora()
    expira = agora + timedelta(hours=DURACAO_SESSAO_HORAS)
    conn.execute(
        "INSERT INTO alunos_sessoes (token, aluno_id, criada_em, expira_em) VALUES (?,?,?,?)",
        (token, aluno_id, _txt(agora), _txt(expira)),
    )
    return token


@router.post("/alunos/login", dependencies=[Depends(limitar_login_aluno)])
def login_aluno(payload: AlunoLoginIn, request: Request, response: Response):
    email = payload.email.strip().lower()
    with conectar() as conn:
        garantir_tabelas_alunos(conn)
        aluno = conn.execute(
            "SELECT id, nome, email, senha_hash, senha_salt FROM alunos WHERE email=?", (email,)
        ).fetchone()
        if aluno and not aluno["senha_hash"]:
            raise HTTPException(
                status_code=401,
                detail="Sua senha ainda não foi criada. Use o link de acesso enviado após a confirmação do pagamento.",
            )
        senha_confere = False
        if aluno:
            calculado = hash_password_pbkdf2(payload.senha, str(aluno["senha_salt"]).encode("utf-8"))
            senha_confere = secrets.compare_digest(str(calculado), str(aluno["senha_hash"]))
        if not aluno or not senha_confere:
            raise HTTPException(status_code=401, detail="E-mail ou senha inválidos.")
        token = _criar_sessao_aluno(conn, aluno_id=aluno["id"])

    response.set_cookie(key=COOKIE_NOME, value=token, **_cookie_kwargs(request))
    return {"ok": True, "nome": aluno["nome"], "email": aluno["email"]}


@router.post("/alunos/definir-senha", dependencies=[Depends(limitar_definir_senha)])
def definir_senha_aluno(payload: AlunoDefinirSenhaIn, request: Request, response: Response):
    """Usado pelo link de convite enviado após a confirmação do pagamento: o
    aluno cria a própria senha e já é autenticado em seguida."""
    with conectar() as conn:
        garantir_tabelas_alunos(conn)
        convite = conn.execute(
            "SELECT token, aluno_id, expira_em, usado_em FROM alunos_convites WHERE token=?",
            (payload.token,),
        ).fetchone()
        if not convite:
            raise HTTPException(status_code=404, detail="Link de acesso inválido.")
        if convite["usado_em"]:
            raise HTTPException(status_code=409, detail="Este link de acesso já foi usado. Faça login normalmente.")
        try:
            expira = datetime.strptime(convite["expira_em"], "%Y-%m-%d %H:%M:%S")
        except Exception:
            expira = None
        if not expira or expira < _agora():
            raise HTTPException(status_code=410, detail="Este link de acesso expirou. Peça um novo pelo WhatsApp.")

        salt = secrets.token_hex(16)
        senha_hash = hash_password_pbkdf2(payload.senha, salt.encode("utf-8"))
        conn.execute(
            "UPDATE alunos SET senha_hash=?, senha_salt=? WHERE id=?",
            (senha_hash, salt, convite["aluno_id"]),
        )
        conn.execute(
            "UPDATE alunos_convites SET usado_em=? WHERE token=?", (_txt(_agora()), payload.token)
        )
        aluno = conn.execute(
            "SELECT id, nome, email FROM alunos WHERE id=?", (convite["aluno_id"],)
        ).fetchone()
        token = _criar_sessao_aluno(conn, aluno_id=aluno["id"])

    response.set_cookie(key=COOKIE_NOME, value=token, **_cookie_kwargs(request))
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


class ProgressoIn(BaseModel):
    material_id: int = Field(gt=0)
    concluido: bool = True


def _garantir_acesso_curso(conn, sessao: dict, slug: str) -> None:
    """Para cursos pagos exige acesso liberado; cursos gratuitos bastam sessão."""
    from backend.course_routes import CATALOGO_CURSOS_PAGOS

    if slug in CATALOGO_CURSOS_PAGOS and not aluno_tem_acesso(conn, aluno_id=sessao["aluno_id"], slug=slug):
        raise HTTPException(status_code=403, detail="Você ainda não tem acesso a este curso.")


def _resumo_progresso(conn, *, aluno_id: int, slug: str) -> dict:
    from backend.course_routes import garantir_tabela_cursos

    garantir_tabela_cursos(conn)
    materiais = conn.execute(
        "SELECT id FROM cursos_materiais WHERE categoria=? ORDER BY id", (slug,)
    ).fetchall()
    ids_materiais = [int(m["id"]) for m in materiais]
    total = len(ids_materiais)
    concluidos = [
        int(row["material_id"])
        for row in conn.execute(
            "SELECT material_id FROM alunos_progresso WHERE aluno_id=? AND slug=?", (aluno_id, slug)
        ).fetchall()
        if int(row["material_id"]) in ids_materiais
    ]
    feitos = len(concluidos)
    percentual = round((feitos / total) * 100) if total else 0
    return {
        "slug": slug,
        "total": total,
        "concluidos": feitos,
        "percentual": percentual,
        "completo": total > 0 and feitos >= total,
        "materiais_concluidos": concluidos,
    }


@router.get("/cursos/{slug}/progresso")
def obter_progresso_curso(slug: str, sessao: dict = Depends(sessao_aluno_atual)):
    with conectar() as conn:
        garantir_tabelas_alunos(conn)
        _garantir_acesso_curso(conn, sessao, slug)
        return _resumo_progresso(conn, aluno_id=sessao["aluno_id"], slug=slug)


@router.post("/cursos/{slug}/progresso")
def marcar_progresso_curso(slug: str, payload: ProgressoIn, sessao: dict = Depends(sessao_aluno_atual)):
    """Marca (ou desmarca) uma aula/material como concluído para o aluno logado.
    Base da retenção: barra de progresso, 'continuar estudando' e certificado."""
    from backend.course_routes import garantir_tabela_cursos

    with conectar() as conn:
        garantir_tabelas_alunos(conn)
        _garantir_acesso_curso(conn, sessao, slug)
        garantir_tabela_cursos(conn)
        material = conn.execute(
            "SELECT id FROM cursos_materiais WHERE id=? AND categoria=?", (payload.material_id, slug)
        ).fetchone()
        if not material:
            raise HTTPException(status_code=404, detail="Aula não encontrada neste curso.")
        if payload.concluido:
            conn.execute(
                "INSERT OR IGNORE INTO alunos_progresso (aluno_id, slug, material_id, concluido_em) VALUES (?,?,?,?)",
                (sessao["aluno_id"], slug, payload.material_id, _txt(_agora())),
            )
        else:
            conn.execute(
                "DELETE FROM alunos_progresso WHERE aluno_id=? AND material_id=?",
                (sessao["aluno_id"], payload.material_id),
            )
        resumo = _resumo_progresso(conn, aluno_id=sessao["aluno_id"], slug=slug)
    return {"ok": True, **resumo}


@router.get("/cursos/{slug}/certificado")
def certificado_curso(slug: str, sessao: dict = Depends(sessao_aluno_atual)):
    """Gera um certificado imprimível quando o aluno concluiu 100% do curso.
    Retenção: recompensa concreta ao final da trilha."""
    from fastapi.responses import HTMLResponse

    from backend.course_routes import CATALOGO_CURSOS_PAGOS

    with conectar() as conn:
        garantir_tabelas_alunos(conn)
        _garantir_acesso_curso(conn, sessao, slug)
        resumo = _resumo_progresso(conn, aluno_id=sessao["aluno_id"], slug=slug)
    if not resumo["completo"]:
        raise HTTPException(status_code=403, detail="Conclua todas as aulas para emitir o certificado.")

    titulo_curso = (CATALOGO_CURSOS_PAGOS.get(slug) or {}).get("titulo") or slug.replace("-", " ").title()
    nome = _escape_certificado(sessao["nome"])
    curso = _escape_certificado(titulo_curso)
    data = _agora().strftime("%d/%m/%Y")
    html = f"""<!doctype html><html lang="pt-BR"><head><meta charset="utf-8">
<title>Certificado - {curso}</title><style>
body{{font-family:Georgia,'Times New Roman',serif;margin:0;background:#0b0a10;color:#1c150a}}
.cert{{max-width:900px;margin:32px auto;padding:56px;background:linear-gradient(135deg,#fff8e6,#f3e6c4);
border:6px double #b8862f;border-radius:14px;text-align:center;box-shadow:0 24px 80px rgba(0,0,0,.5)}}
.mark{{font-size:3rem;color:#b8862f}} h1{{font-size:2.2rem;margin:8px 0;letter-spacing:.04em}}
.nome{{font-size:2rem;margin:24px 0 8px;color:#5a3d0a}} .curso{{font-size:1.4rem;font-weight:bold;margin:8px 0 24px}}
.rodape{{margin-top:36px;display:flex;justify-content:space-between;font-size:.95rem;color:#4a3a1a}}
@media print{{body{{background:#fff}} .cert{{box-shadow:none;margin:0}}}}
</style></head><body><div class="cert">
<div class="mark">☾</div><p>Escola Mística • Mística Presentes</p>
<h1>Certificado de Conclusão</h1>
<p>Certificamos que</p><div class="nome">{nome}</div>
<p>concluiu com dedicação o curso</p><div class="curso">{curso}</div>
<div class="rodape"><span>Emitido em {data}</span><span>Escola Mística</span></div>
</div><p style="text-align:center"><button onclick="window.print()">Imprimir certificado</button></p>
</body></html>"""
    return HTMLResponse(content=html)


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
    """Confirma o pagamento e libera o acesso do aluno ao curso. Se o aluno
    ainda não tem senha (primeira compra), gera um link de convite de uso
    único para o admin enviar pelo WhatsApp; o aluno cria a senha nesse link.
    Se o aluno já tem conta (comprou outro curso antes), não é necessário
    convite novo -- ele já acessa com o login existente."""
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

        aluno = conn.execute("SELECT senha_hash FROM alunos WHERE id=?", (pedido["aluno_id"],)).fetchone()
        link_acesso = None
        if not aluno or not aluno["senha_hash"]:
            token = criar_convite_acesso(conn, aluno_id=pedido["aluno_id"])
            link_acesso = link_convite_acesso(token)

    return {"ok": True, "id": pedido_id, "status": "Pago", "link_acesso": link_acesso}
