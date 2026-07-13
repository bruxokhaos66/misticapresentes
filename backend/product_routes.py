from __future__ import annotations

import json
import os
import secrets
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field, field_validator

from backend.audit import registrar_auditoria
from backend.api_security import validar_site_api_key as validar_chave_api
from backend.database import conectar
from backend.panel_sessions import exigir_sessao_ou_chave_api
from backend.rate_limit import limitar_requisicoes
from backend.site_stock_routes import VendaSiteIn, registrar_venda_site

router = APIRouter(prefix="/api", tags=["produtos-completos"])
limitar_checkout_publico = limitar_requisicoes("checkout_publico", limite=12, janela_segundos=60)


class ProdutoCompletoIn(BaseModel):
    codigo_p: Optional[str] = None
    nome: str = Field(min_length=1)
    marca: Optional[str] = None
    preco: float = Field(default=0.0, ge=0)
    quantidade: int = Field(default=0, ge=0)
    categoria: Optional[str] = None
    custo: float = Field(default=0.0, ge=0)
    lucro: float = 0.0
    estoque_minimo: int = Field(default=0, ge=0)
    descricao: Optional[str] = None
    imagem_url: Optional[str] = None
    imagens: list[str] = Field(default_factory=list)
    link_externo: Optional[str] = None
    selo: Optional[str] = None

    @field_validator("link_externo")
    @classmethod
    def _validar_link_externo(cls, valor: Optional[str]) -> Optional[str]:
        """Sanitiza o link do fornecedor guardado no produto.

        Só aceita URLs http(s); protocolos perigosos (javascript:, data:, file:,
        vbscript: e afins) são bloqueados. Valor vazio/ausente é preservado para
        não quebrar produtos antigos sem link.
        """
        if valor is None:
            return None
        texto = valor.strip()
        if not texto:
            return None
        inicio = texto.lower()
        if not (inicio.startswith("https://") or inicio.startswith("http://")):
            raise ValueError("O link externo deve começar com https:// (ou http://).")
        return texto


def validar_site_api_key(chave_recebida: str | None):
    validar_chave_api(chave_recebida, "Configure o segredo de integração somente no ambiente do servidor.")


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
    data["avaliacoes_total"] = data.get("avaliacoes_total") or 0
    data["avaliacoes_media"] = data.get("avaliacoes_media") or 0
    return data


_CAMPOS_PRODUTO_PUBLICO = """p.id, p.codigo_p, p.nome, p.marca, p.preco, p.quantidade, p.categoria,
                       p.descricao, p.imagem_url, p.imagens_json, p.link_externo, p.selo, p.atualizado_em"""
_CAMPOS_PRODUTO_ADMIN = """p.id, p.codigo_p, p.nome, p.marca, p.preco, p.quantidade, p.categoria, p.custo, p.lucro,
                       p.estoque_minimo, p.descricao, p.imagem_url, p.imagens_json, p.link_externo, p.selo, p.atualizado_em"""
_JOIN_AVALIACOES = """
                LEFT JOIN (
                    SELECT produto_id, COUNT(*) AS total, AVG(nota) AS media
                    FROM avaliacoes_produtos
                    WHERE COALESCE(aprovado, 1) = 1
                    GROUP BY produto_id
                ) a ON a.produto_id = p.id"""


def _buscar_produtos(campos: str, busca: str, limite: int):
    # avaliacoes_total/avaliacoes_media vêm de um LEFT JOIN agregado para que o
    # catálogo mostre prova social (nota média + nº de avaliações) sem uma
    # requisição extra por produto (ver product-reviews.js/review_routes.py).
    termo = f"%{busca.strip()}%"
    with conectar() as conn:
        if busca.strip():
            rows = conn.execute(
                f"""
                SELECT {campos},
                       COALESCE(a.total, 0) AS avaliacoes_total,
                       ROUND(a.media, 1) AS avaliacoes_media
                FROM produtos p{_JOIN_AVALIACOES}
                WHERE COALESCE(p.ativo,1)=1
                  AND (p.nome LIKE ? OR p.codigo_p LIKE ? OR p.categoria LIKE ? OR p.marca LIKE ? OR p.descricao LIKE ? OR p.selo LIKE ?)
                ORDER BY p.nome COLLATE NOCASE
                LIMIT ?
                """,
                (termo, termo, termo, termo, termo, termo, limite),
            ).fetchall()
        else:
            rows = conn.execute(
                f"""
                SELECT {campos},
                       COALESCE(a.total, 0) AS avaliacoes_total,
                       ROUND(a.media, 1) AS avaliacoes_media
                FROM produtos p{_JOIN_AVALIACOES}
                WHERE COALESCE(p.ativo,1)=1
                ORDER BY p.nome COLLATE NOCASE
                LIMIT ?
                """,
                (limite,),
            ).fetchall()
    return [produto_row_to_dict(row) for row in rows]


@router.get("/produtos")
def listar_produtos_completos(busca: str = "", limite: int = Query(100, ge=1, le=500)):
    """Catálogo público: não inclui custo, lucro nem estoque mínimo, que são
    informações comerciais internas (ver GET /produtos/admin para o painel)."""
    return _buscar_produtos(_CAMPOS_PRODUTO_PUBLICO, busca, limite)


@router.get("/produtos/admin")
def listar_produtos_admin(
    busca: str = "",
    limite: int = Query(100, ge=1, le=500),
    sessao: dict = Depends(exigir_sessao_ou_chave_api()),
):
    """Mesma listagem, mas autenticada e com os campos internos (custo, lucro,
    estoque mínimo) usados pelo painel administrativo."""
    return _buscar_produtos(_CAMPOS_PRODUTO_ADMIN, busca, limite)


@router.post("/checkout/pedidos", dependencies=[Depends(limitar_checkout_publico)])
def criar_pedido_checkout_publico(venda: VendaSiteIn, request: Request):
    """Endpoint público mínimo: o navegador envia somente os itens do pedido.

    A chave global permanece no ambiente do servidor e é usada apenas na chamada
    interna da rotina validada de criação de venda. Preços são recalculados no
    backend e o estoque do pedido é reservado (baixado) já na criação, sendo
    devolvido automaticamente se o pedido expirar ou for cancelado. Sem headers: nenhum segredo
    nem chave de idempotência é aceito do navegador nesta rota pública (ver
    tests/test_no_browser_api_secret.py); quem quiser idempotência deve chamar
    POST /api/vendas autenticado, que aceita Idempotency-Key.
    """
    venda.origem = "site"
    venda.status = "Aguardando pagamento"
    # registrar_venda_site decide a baixa/reserva de estoque a partir do status do
    # pedido (reserva imediata enquanto "Aguardando pagamento"); não sobrescrever
    # aqui para não desativar a reserva de estoque do checkout público.
    venda.vendedor = "Site/Celular"
    venda.forma_pagamento = "Pix site/celular"
    return registrar_venda_site(venda, request, _chave_interna_checkout(), None)


@router.post("/produtos")
def criar_produto_completo(produto: ProdutoCompletoIn, sessao: dict = Depends(exigir_sessao_ou_chave_api())):
    agora = datetime.now().isoformat(timespec="seconds")
    imagens_json = json.dumps(produto.imagens or [], ensure_ascii=False)
    with conectar() as conn:
        if produto.codigo_p:
            duplicado = conn.execute(
                "SELECT id FROM produtos WHERE codigo_p=? AND COALESCE(ativo,1)=1",
                (produto.codigo_p,),
            ).fetchone()
            if duplicado:
                raise HTTPException(
                    status_code=409,
                    detail=f"Já existe um produto ativo com o código '{produto.codigo_p}'",
                )
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
        registrar_auditoria(conn, "produto", produto_id, "criar", depois=produto.model_dump())
        conn.commit()
    return {"ok": True, "id": produto_id, "status": "criado", "atualizado_em": agora}


@router.put("/produtos/{produto_id}")
def atualizar_produto_completo(produto_id: int, produto: ProdutoCompletoIn, sessao: dict = Depends(exigir_sessao_ou_chave_api())):
    agora = datetime.now().isoformat(timespec="seconds")
    imagens_json = json.dumps(produto.imagens or [], ensure_ascii=False)
    with conectar() as conn:
        existente = conn.execute("SELECT * FROM produtos WHERE id=?", (produto_id,)).fetchone()
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
        registrar_auditoria(conn, "produto", produto_id, "atualizar", antes=dict(existente), depois=produto.model_dump())
        conn.commit()
    return {"ok": True, "id": produto_id, "status": "atualizado", "atualizado_em": agora}


@router.delete("/produtos/{produto_id}")
def excluir_produto_completo(produto_id: int, sessao: dict = Depends(exigir_sessao_ou_chave_api())):
    with conectar() as conn:
        existente = conn.execute("SELECT id FROM produtos WHERE id=?", (produto_id,)).fetchone()
        if not existente:
            raise HTTPException(status_code=404, detail="Produto não encontrado")
        conn.execute("UPDATE produtos SET ativo=0, atualizado_em=? WHERE id=?", (datetime.now().isoformat(timespec="seconds"), produto_id))
        registrar_auditoria(conn, "produto", produto_id, "excluir")
        conn.commit()
    return {"ok": True, "id": produto_id, "status": "excluido"}
