from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.database import conectar, listar

router = APIRouter(prefix="/api", tags=["site-estoque"])


class ItemEstoqueSite(BaseModel):
    produto_id: Optional[int] = None
    codigo_p: Optional[str] = None
    nome_p: Optional[str] = None
    quantidade: int = Field(gt=0)


class ReservaEstoqueSite(BaseModel):
    origem: str = "site"
    venda_id: Optional[str] = None
    itens: list[ItemEstoqueSite] = Field(default_factory=list)


def buscar_produto(conn, item: ItemEstoqueSite):
    if item.produto_id:
        produto = conn.execute(
            "SELECT id, codigo_p, nome, quantidade FROM produtos WHERE id=? AND COALESCE(ativo,1)=1",
            (item.produto_id,),
        ).fetchone()
        if produto:
            return produto

    if item.codigo_p:
        produto = conn.execute(
            "SELECT id, codigo_p, nome, quantidade FROM produtos WHERE codigo_p=? AND COALESCE(ativo,1)=1",
            (item.codigo_p,),
        ).fetchone()
        if produto:
            return produto

    return None


@router.post("/estoque/reservar")
def reservar_estoque_site(payload: ReservaEstoqueSite):
    if not payload.itens:
        raise HTTPException(status_code=400, detail="Nenhum item informado para baixa de estoque.")

    with conectar() as conn:
        baixados = []

        for item in payload.itens:
            produto = buscar_produto(conn, item)
            if not produto:
                raise HTTPException(
                    status_code=404,
                    detail=f"Produto não encontrado: {item.codigo_p or item.nome_p or item.produto_id}",
                )

            estoque_atual = int(produto["quantidade"] or 0)
            if estoque_atual < item.quantidade:
                raise HTTPException(
                    status_code=409,
                    detail=f"Estoque insuficiente para {produto['nome']}. Disponível: {estoque_atual}",
                )

        for item in payload.itens:
            produto = buscar_produto(conn, item)
            conn.execute(
                "UPDATE produtos SET quantidade = quantidade - ? WHERE id = ?",
                (item.quantidade, produto["id"]),
            )
            baixados.append(
                {
                    "produto_id": produto["id"],
                    "codigo_p": produto["codigo_p"],
                    "nome": produto["nome"],
                    "quantidade_baixada": item.quantidade,
                }
            )

        conn.commit()

    return {
        "ok": True,
        "origem": payload.origem,
        "venda_id": payload.venda_id,
        "reservado": True,
        "estoque_baixado": True,
        "itens": baixados,
    }


@router.get("/estoque/site")
def estoque_site():
    return listar(
        """
        SELECT id, codigo_p, nome, quantidade, preco, categoria
        FROM produtos
        WHERE COALESCE(ativo,1)=1
        ORDER BY nome COLLATE NOCASE
        """
    )
