from __future__ import annotations

import json
import os
import secrets
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Header, HTTPException, Query
from pydantic import BaseModel, Field

from backend.database import conectar

router = APIRouter(prefix="/api", tags=["produtos-completos"])


class ProdutoCompletoIn(BaseModel):
    codigo_p: Optional[str] = None
    nome: str = Field(min_length=1)
    preco: float = 0.0
    quantidade: int = 0
    categoria: Optional[str] = None
    custo: float = 0.0
    lucro: float = 0.0
    estoque_minimo: int = 0
    descricao: Optional[str] = None
    imagem_url: Optional[str] = None
    imagens: list[str] = Field(default_factory=list)
    link_externo: Optional[str] = None
    selo: Optional[str] = None


def validar_site_api_key(chave_recebida: str | None):
    chave = os.environ.get("MISTICA_SITE_API_KEY", "").strip() or os.environ.get("MISTICA_SYNC_KEY", "").strip()
    if not chave:
        raise HTTPException(status_code=503, detail="Configure MISTICA_SITE_API_KEY ou MISTICA_SYNC_KEY para permitir escrita pela API.")
    if not chave_recebida or not secrets.compare_digest(str(chave_recebida), chave):
        raise HTTPException(status_code=403, detail="Chave da API inválida.")


def garantir_colunas_produto(conn):
    comandos = [
        "ALTER TABLE produtos ADD COLUMN descricao TEXT",
        "ALTER TABLE produtos ADD COLUMN imagem_url TEXT",
        "ALTER TABLE produtos ADD COLUMN imagens_json TEXT",
        "ALTER TABLE produtos ADD COLUMN link_externo TEXT",
        "ALTER TABLE produtos ADD COLUMN selo TEXT",
        "ALTER TABLE produtos ADD COLUMN atualizado_em TEXT",
    ]
    for sql in comandos:
        try:
            conn.execute(sql)
        except Exception:
            pass


def produto_row_to_dict(row):
    data = dict(row)
    imagens = []
    try:
        imagens = json.loads(data.get("imagens_json") or "[]")
    except Exception:
        imagens = []
    data["descricao"] = data.get("descricao") or ""
    data["imagem_url"] = data.get("imagem_url") or ""
    data["imagens"] = imagens
    data["link_externo"] = data.get("link_externo") or ""
    data["selo"] = data.get("selo") or ""
    return data


@router.get("/produtos")
def listar_produtos_completos(busca: str = "", limite: int = Query(100, ge=1, le=500)):
    termo = f"%{busca.strip()}%"
    with conectar() as conn:
        garantir_colunas_produto(conn)
        if busca.strip():
            rows = conn.execute(
                """
                SELECT id, codigo_p, nome, preco, quantidade, categoria, custo, lucro,
                       estoque_minimo, descricao, imagem_url, imagens_json, link_externo, selo, atualizado_em
                FROM produtos
                WHERE COALESCE(ativo,1)=1
                  AND (nome LIKE ? OR codigo_p LIKE ? OR categoria LIKE ? OR descricao LIKE ? OR selo LIKE ?)
                ORDER BY nome COLLATE NOCASE
                LIMIT ?
                """,
                (termo, termo, termo, termo, termo, limite),
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT id, codigo_p, nome, preco, quantidade, categoria, custo, lucro,
                       estoque_minimo, descricao, imagem_url, imagens_json, link_externo, selo, atualizado_em
                FROM produtos
                WHERE COALESCE(ativo,1)=1
                ORDER BY nome COLLATE NOCASE
                LIMIT ?
                """,
                (limite,),
            ).fetchall()
    return [produto_row_to_dict(row) for row in rows]


@router.post("/produtos")
def criar_produto_completo(produto: ProdutoCompletoIn, x_mistica_api_key: str | None = Header(default=None)):
    validar_site_api_key(x_mistica_api_key)
    agora = datetime.now().isoformat(timespec="seconds")
    imagens_json = json.dumps(produto.imagens or [], ensure_ascii=False)
    with conectar() as conn:
        garantir_colunas_produto(conn)
        cur = conn.execute(
            """
            INSERT INTO produtos (
                codigo_p, nome, preco, quantidade, categoria, custo, lucro, estoque_minimo,
                descricao, imagem_url, imagens_json, link_externo, selo, atualizado_em, ativo
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,1)
            """,
            (
                produto.codigo_p,
                produto.nome,
                produto.preco,
                produto.quantidade,
                produto.categoria,
                produto.custo,
                produto.lucro,
                produto.estoque_minimo,
                produto.descricao,
                produto.imagem_url,
                imagens_json,
                produto.link_externo,
                produto.selo,
                agora,
            ),
        )
        produto_id = int(cur.lastrowid)
        conn.commit()
    return {"ok": True, "id": produto_id, "status": "criado", "atualizado_em": agora}


@router.put("/produtos/{produto_id}")
def atualizar_produto_completo(produto_id: int, produto: ProdutoCompletoIn, x_mistica_api_key: str | None = Header(default=None)):
    validar_site_api_key(x_mistica_api_key)
    agora = datetime.now().isoformat(timespec="seconds")
    imagens_json = json.dumps(produto.imagens or [], ensure_ascii=False)
    with conectar() as conn:
        garantir_colunas_produto(conn)
        existente = conn.execute("SELECT id FROM produtos WHERE id=?", (produto_id,)).fetchone()
        if not existente:
            raise HTTPException(status_code=404, detail="Produto não encontrado")
        conn.execute(
            """
            UPDATE produtos
               SET codigo_p=?, nome=?, preco=?, quantidade=?, categoria=?, custo=?, lucro=?, estoque_minimo=?,
                   descricao=?, imagem_url=?, imagens_json=?, link_externo=?, selo=?, atualizado_em=?, ativo=1
             WHERE id=?
            """,
            (
                produto.codigo_p,
                produto.nome,
                produto.preco,
                produto.quantidade,
                produto.categoria,
                produto.custo,
                produto.lucro,
                produto.estoque_minimo,
                produto.descricao,
                produto.imagem_url,
                imagens_json,
                produto.link_externo,
                produto.selo,
                agora,
                produto_id,
            ),
        )
        conn.commit()
    return {"ok": True, "id": produto_id, "status": "atualizado", "atualizado_em": agora}


@router.delete("/produtos/{produto_id}")
def excluir_produto_completo(produto_id: int, x_mistica_api_key: str | None = Header(default=None)):
    validar_site_api_key(x_mistica_api_key)
    with conectar() as conn:
        garantir_colunas_produto(conn)
        existente = conn.execute("SELECT id FROM produtos WHERE id=?", (produto_id,)).fetchone()
        if not existente:
            raise HTTPException(status_code=404, detail="Produto não encontrado")
        conn.execute("UPDATE produtos SET ativo=0, atualizado_em=? WHERE id=?", (datetime.now().isoformat(timespec="seconds"), produto_id))
        conn.commit()
    return {"ok": True, "id": produto_id, "status": "excluido"}
