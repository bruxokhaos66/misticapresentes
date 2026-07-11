from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, EmailStr, Field

from backend.database import conectar
from backend.panel_sessions import exigir_sessao_ou_chave_api
from backend.pix import config_pix, montar_payload_pix
from backend.rate_limit import limitar_requisicoes

router = APIRouter(prefix="/api", tags=["cursos"])

TIPOS_VALIDOS = {"pdf", "ppt", "video"}

# Catálogo autoritativo dos cursos pagos: preço nunca vem do navegador, só
# daqui. Precisa ficar em sincronia manual com a lista `cursos` em escola.js.
CATALOGO_CURSOS_PAGOS = {
    "rape-uso-tradicao": {"titulo": "Rapé: Uso e Tradição", "preco": 97.0},
    "ayahuasca-fundamentos": {"titulo": "Ayahuasca: Fundamentos", "preco": 127.0},
    "origem-universo-dias-atuais": {"titulo": "Origem do Universo até os Dias Atuais", "preco": 147.0},
}

limitar_checkout_curso = limitar_requisicoes("checkout_curso", limite=12, janela_segundos=60)


class CursoMaterialIn(BaseModel):
    titulo: str = Field(min_length=1)
    categoria: str = Field(min_length=1)
    tipo: str = "pdf"
    descricao: Optional[str] = None
    url: str = Field(min_length=1)


class CursoCheckoutIn(BaseModel):
    slug: str = Field(min_length=1)
    nome: str = Field(min_length=1)
    email: EmailStr


def garantir_tabela_pedidos_cursos(conn):
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS pedidos_cursos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            slug TEXT NOT NULL,
            titulo TEXT NOT NULL,
            preco REAL NOT NULL,
            status TEXT NOT NULL,
            pix_txid TEXT,
            pix_copia_cola TEXT,
            criado_em TEXT NOT NULL,
            aluno_id INTEGER,
            nome TEXT,
            email TEXT
        )
        """
    )
    for sql in (
        "ALTER TABLE pedidos_cursos ADD COLUMN aluno_id INTEGER",
        "ALTER TABLE pedidos_cursos ADD COLUMN nome TEXT",
        "ALTER TABLE pedidos_cursos ADD COLUMN email TEXT",
    ):
        try:
            conn.execute(sql)
        except Exception:
            pass
    conn.execute("CREATE INDEX IF NOT EXISTS idx_pedidos_cursos_criado ON pedidos_cursos(criado_em)")


def _montar_pix_curso(pedido_id: int, valor: float) -> dict | None:
    cfg = config_pix()
    if not cfg["chave"] or valor <= 0:
        return None
    txid = f"ESCOLA{pedido_id:09d}"[:25]
    try:
        payload = montar_payload_pix(chave=cfg["chave"], nome=cfg["nome"], cidade=cfg["cidade"], valor=valor, txid=txid)
    except ValueError:
        return None
    return {"txid": txid, "copia_cola": payload}


@router.post("/checkout/cursos", dependencies=[Depends(limitar_checkout_curso)])
def criar_pedido_curso(payload: CursoCheckoutIn):
    """Endpoint público de compra de curso: o navegador envia o slug e os dados
    de identificação do comprador (nome, e-mail). Preço e título vêm do
    catálogo do servidor (CATALOGO_CURSOS_PAGOS) e o Pix é gerado aqui com a
    chave real do ambiente (ver backend/pix.py) -- nunca no navegador. O
    cadastro do aluno é criado sem senha nesta etapa; a senha só é definida
    pelo próprio aluno através do link de acesso enviado depois que um
    administrador confirma o pagamento (ver backend/aluno_auth.py)."""
    from backend.aluno_auth import garantir_tabelas_alunos, obter_ou_criar_aluno_sem_senha

    curso = CATALOGO_CURSOS_PAGOS.get(payload.slug.strip())
    if not curso:
        raise HTTPException(status_code=404, detail="Curso não encontrado ou não é pago.")

    agora = datetime.now().isoformat(timespec="seconds")
    email = payload.email.strip().lower()
    with conectar() as conn:
        garantir_tabela_pedidos_cursos(conn)
        garantir_tabelas_alunos(conn)
        aluno_id = obter_ou_criar_aluno_sem_senha(conn, nome=payload.nome, email=email)
        cur = conn.execute(
            "INSERT INTO pedidos_cursos (slug, titulo, preco, status, criado_em, aluno_id, nome, email) VALUES (?,?,?,?,?,?,?,?)",
            (payload.slug.strip(), curso["titulo"], curso["preco"], "Aguardando pagamento", agora, aluno_id, payload.nome.strip(), email),
        )
        pedido_id = int(cur.lastrowid)
        pix = _montar_pix_curso(pedido_id, curso["preco"])
        if pix:
            conn.execute(
                "UPDATE pedidos_cursos SET pix_txid=?, pix_copia_cola=? WHERE id=?",
                (pix["txid"], pix["copia_cola"], pedido_id),
            )

    return {
        "ok": True,
        "id": pedido_id,
        "slug": payload.slug.strip(),
        "titulo": curso["titulo"],
        "preco": curso["preco"],
        "pix_txid": pix["txid"] if pix else None,
        "pix_copia_cola": pix["copia_cola"] if pix else None,
    }


def garantir_tabela_cursos(conn):
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS cursos_materiais (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            titulo TEXT NOT NULL,
            categoria TEXT NOT NULL,
            tipo TEXT NOT NULL,
            descricao TEXT,
            url TEXT NOT NULL,
            criado_em TEXT NOT NULL
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_cursos_materiais_criado ON cursos_materiais(criado_em)")


@router.get("/cursos")
def listar_materiais_curso(request: Request):
    """Lista pública dos materiais dos cursos GRATUITOS apenas. Materiais de
    cursos pagos ficam de fora daqui para não vazar conteúdo para quem não
    comprou -- eles são servidos por /api/cursos/{slug}/conteudo (exige login
    de aluno com acesso liberado) ou, para o painel administrativo gerenciar
    todos os materiais, por uma sessão de administrador válida."""
    with conectar() as conn:
        garantir_tabela_cursos(conn)
        rows = conn.execute(
            "SELECT id, titulo, categoria, tipo, descricao, url, criado_em FROM cursos_materiais ORDER BY id DESC LIMIT 200"
        ).fetchall()
    materiais = [dict(row) for row in rows]

    from backend.panel_sessions import validar_sessao

    sessao = validar_sessao(request.cookies.get("mistica_painel_sessao"))
    if sessao:
        return materiais
    return [item for item in materiais if item["categoria"] not in CATALOGO_CURSOS_PAGOS]


@router.post("/cursos")
def criar_material_curso(material: CursoMaterialIn, sessao: dict = Depends(exigir_sessao_ou_chave_api())):
    tipo = material.tipo if material.tipo in TIPOS_VALIDOS else "pdf"
    agora = datetime.now().isoformat(timespec="seconds")
    with conectar() as conn:
        garantir_tabela_cursos(conn)
        cur = conn.execute(
            """
            INSERT INTO cursos_materiais (titulo, categoria, tipo, descricao, url, criado_em)
            VALUES (?,?,?,?,?,?)
            """,
            (material.titulo.strip(), material.categoria.strip(), tipo, material.descricao, material.url.strip(), agora),
        )
        material_id = int(cur.lastrowid)
    return {"ok": True, "id": material_id, "status": "criado", "criado_em": agora}


@router.delete("/cursos/{material_id}")
def excluir_material_curso(material_id: int, sessao: dict = Depends(exigir_sessao_ou_chave_api())):
    with conectar() as conn:
        garantir_tabela_cursos(conn)
        existente = conn.execute("SELECT id FROM cursos_materiais WHERE id=?", (material_id,)).fetchone()
        if not existente:
            raise HTTPException(status_code=404, detail="Material não encontrado")
        conn.execute("DELETE FROM cursos_materiais WHERE id=?", (material_id,))
    return {"ok": True, "id": material_id, "status": "excluido"}
