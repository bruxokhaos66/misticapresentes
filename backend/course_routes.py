from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field

from backend.database import conectar
from backend.product_routes import validar_site_api_key

router = APIRouter(prefix="/api", tags=["cursos"])

TIPOS_VALIDOS = {"pdf", "ppt", "video"}


class CursoMaterialIn(BaseModel):
    titulo: str = Field(min_length=1)
    categoria: str = Field(min_length=1)
    tipo: str = "pdf"
    descricao: Optional[str] = None
    url: str = Field(min_length=1)


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
def listar_materiais_curso():
    with conectar() as conn:
        garantir_tabela_cursos(conn)
        rows = conn.execute(
            "SELECT id, titulo, categoria, tipo, descricao, url, criado_em FROM cursos_materiais ORDER BY id DESC LIMIT 200"
        ).fetchall()
    return [dict(row) for row in rows]


@router.post("/cursos")
def criar_material_curso(material: CursoMaterialIn, x_mistica_api_key: str | None = Header(default=None)):
    validar_site_api_key(x_mistica_api_key)
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
def excluir_material_curso(material_id: int, x_mistica_api_key: str | None = Header(default=None)):
    validar_site_api_key(x_mistica_api_key)
    with conectar() as conn:
        garantir_tabela_cursos(conn)
        existente = conn.execute("SELECT id FROM cursos_materiais WHERE id=?", (material_id,)).fetchone()
        if not existente:
            raise HTTPException(status_code=404, detail="Material não encontrado")
        conn.execute("DELETE FROM cursos_materiais WHERE id=?", (material_id,))
    return {"ok": True, "id": material_id, "status": "excluido"}
