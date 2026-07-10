from __future__ import annotations

import json
import os
import secrets
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from pydantic import BaseModel, Field

from backend.database import conectar
from backend.rate_limit import limitar_requisicoes
from backend.site_stock_routes import VendaSiteIn, registrar_venda_site

router = APIRouter(prefix="/api", tags=["produtos-completos"])
limitar_checkout_publico = limitar_requisicoes("checkout_publico", limite=12, janela_segundos=60)


class ProdutoCompletoIn(BaseModel):
    codigo_p: Optional[str] = None
    nome: str = Field(min_length=1)
    marca: Optional[str] = None
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
        raise HTTPException(status_code=503, detail="Configure o segredo de integração somente no ambiente do servidor.")
    if not chave_recebida or not secrets.compare_digest(str(chave_recebida), chave):
        raise HTTPException(status_code=403, detail="Chave da API inválida.")


def _chave_interna_checkout() -> str:
    """Lê o segredo apenas no backend para intermediar o checkout público.

    O valor nunca é devolvido ao navegador nem aceito no payload/header público.
    """
    chave = os.environ.get("MISTICA_SITE_API_KEY", "").strip() or os.environ.get("MISTICA_SYNC_KEY", "").strip()
    if not chave:
        raise HTTPException(status_code=503, detail="Checkout temporariamente indisponível.")
    return chave


def produto_row_to_dict(row):
    data = dict(row)
    imagens = []
    try:
        imagens = json.loads(data.get("imagens_json") or "[]")
    except Exception:
        imagens = []
    data["marca"] = data.get("marca") or ""
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
        if busca.strip():
            rows = conn.execute(
                """
                SELECT id, codigo_p, nome, marca, preco, quantidade, categoria, custo, lucro,
                       estoque_minimo, descricao, imagem_url, imagens_json, link_externo, selo, atualizado_em
                FROM produtos
                WHERE COALESCE(ativo,1)=1
                  AND (nome LIKE ? OR codigo_p LIKE ? OR categoria LIKE ? OR marca LIKE ? OR descricao LIKE ? OR selo LIKE ?)
                ORDER BY nome COLLATE NOCASE
                LIMIT ?
                """,
                (termo, termo, termo, termo, termo, termo, limite),
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT id, codigo_p, nome, marca, preco, quantidade, categoria, custo, lucro,
                       estoque_minimo, descricao, imagem_url, imagens_json, link_externo, selo, atualizado_em
                FROM produtos
                WHERE COALESCE(ativo,1)=1
                ORDER BY nome COLLATE NOCASE
                LIMIT ?
                """,
                (limite,),
            ).fetchall()
    return [produto_row_to_dict(row) for row in rows]


@router.post("/checkout/pedidos", dependencies=[Depends(limitar_checkout_publico)])
def criar_pedido_checkout_publico(venda: VendaSiteIn, request: Request):
    """Endpoint público mínimo: o navegador envia somente os itens do pedido.

    A chave global permanece no ambiente do servidor e é usada apenas na chamada
    interna da rotina validada de criação de venda. Preços são recalculados no
    backend e pedidos pendentes não baixam estoque.
    """
    venda.origem = "site"
    venda.status = "Aguardando pagamento"
    venda.baixa_estoque = False
    venda.vendedor = "Site/Celular"
    venda.forma_pagamento = "Pix site/celular"
    return registrar_venda_site(venda, request, _chave_interna_checkout())


@router.post("/produtos")
def criar_produto_completo(produto: ProdutoCompletoIn, x_mistica_api_key: str | None = Header(default=None)):
    validar_site_api_key(x_mistica_api_key)
    agora = datetime.now().isoformat(timespec="seconds")
    imagens_json = json.dumps(produto.imagens or [], ensure_ascii=False)
    with conectar() as conn:
        cur = conn.execute(
            """
            INSERT INTO produtos (
                codigo_p, nome, marca, preco, quantidade, categoria, custo, lucro, estoque_minimo,
                descricao, imagem_url, imagens_json, link_externo, selo, atualizado_em, ativo
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,1)
            """,
            (
                produto.codigo_p,
                produto.nome,
                produto.marca,
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
        existente = conn.execute("SELECT id FROM produtos WHERE id=?", (produto_id,)).fetchone()
        if not existente:
            raise HTTPException(status_code=404, detail="Produto não encontrado")
        conn.execute(
            """
            UPDATE produtos
               SET codigo_p=?, nome=?, marca=?, preco=?, quantidade=?, categoria=?, custo=?, lucro=?, estoque_minimo=?,
                   descricao=?, imagem_url=?, imagens_json=?, link_externo=?, selo=?, atualizado_em=?, ativo=1
             WHERE id=?
            """,
            (
                produto.codigo_p,
                produto.nome,
                produto.marca,
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
        existente = conn.execute("SELECT id FROM produtos WHERE id=?", (produto_id,)).fetchone()
        if not existente:
            raise HTTPException(status_code=404, detail="Produto não encontrado")
        conn.execute("UPDATE produtos SET ativo=0, atualizado_em=? WHERE id=?", (datetime.now().isoformat(timespec="seconds"), produto_id))
        conn.commit()
    return {"ok": True, "id": produto_id, "status": "excluido"}
