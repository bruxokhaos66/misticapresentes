from __future__ import annotations

import json
import math
import os
import re
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field, field_validator

from backend.audit import registrar_auditoria
from backend.api_security import validar_site_api_key as validar_chave_api
from backend.database import conectar
from backend.panel_sessions import exigir_sessao_ou_chave_api
from backend.preorder_checkout import registrar_checkout_publico
from backend.product_commercial_rules import (
    LIMITE_ENCOMENDA_MAXIMO,
    LIMITE_ENCOMENDA_PADRAO,
    garantir_colunas_comerciais,
    normalizar_regra_encomenda,
)
from backend.rate_limit import limitar_requisicoes
from backend.site_stock_routes import VendaSiteIn

router = APIRouter(prefix="/api", tags=["produtos-completos"])
limitar_checkout_publico = limitar_requisicoes("checkout_publico", limite=12, janela_segundos=60)

CODIGO_MAX = 64
NOME_MAX = 160
MARCA_MAX = 100
CATEGORIA_MAX = 100
DESCRICAO_MAX = 4000
SELO_MAX = 80
URL_MAX = 1000
VALOR_MAX = 1_000_000.00
ESTOQUE_MAX = 1_000_000


def _texto_limpo(valor: Optional[str], *, limite: int, vazio_como_none: bool = True) -> Optional[str]:
    if valor is None:
        return None
    texto = re.sub(r"\s+", " ", str(valor)).strip()
    if not texto and vazio_como_none:
        return None
    if len(texto) > limite:
        raise ValueError(f"Texto excede o limite de {limite} caracteres.")
    return texto


def normalizar_codigo_produto(valor: Optional[str]) -> Optional[str]:
    texto = _texto_limpo(valor, limite=CODIGO_MAX)
    return texto.upper() if texto else None


def _validar_url_https(valor: Optional[str], *, campo: str) -> Optional[str]:
    texto = _texto_limpo(valor, limite=URL_MAX)
    if texto is None:
        return None
    parsed = urlparse(texto)
    if parsed.scheme.lower() != "https" or not parsed.netloc or parsed.username or parsed.password:
        raise ValueError(f"{campo} deve ser uma URL HTTPS absoluta e sem credenciais.")
    return texto


def _decimal_monetario(valor: float, *, campo: str) -> float:
    numero = float(valor)
    if not math.isfinite(numero):
        raise ValueError(f"{campo} deve ser um número finito.")
    if numero < 0 or numero > VALOR_MAX:
        raise ValueError(f"{campo} deve estar entre 0 e {VALOR_MAX:.2f}.")
    decimal = Decimal(str(numero))
    if decimal.as_tuple().exponent < -2:
        raise ValueError(f"{campo} deve ter no máximo duas casas decimais.")
    return float(decimal.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


class ProdutoCompletoIn(BaseModel):
    codigo_p: Optional[str] = None
    nome: str = Field(min_length=1, max_length=NOME_MAX)
    marca: Optional[str] = Field(default=None, max_length=MARCA_MAX)
    preco: float = 0.0
    quantidade: int = Field(default=0, ge=0, le=ESTOQUE_MAX)
    categoria: Optional[str] = Field(default=None, max_length=CATEGORIA_MAX)
    custo: float = 0.0
    lucro: float = 0.0
    estoque_minimo: int = Field(default=0, ge=0, le=ESTOQUE_MAX)
    descricao: Optional[str] = Field(default=None, max_length=DESCRICAO_MAX)
    imagem_url: Optional[str] = Field(default=None, max_length=URL_MAX)
    imagens: list[str] = Field(default_factory=list, max_length=12)
    link_externo: Optional[str] = Field(default=None, max_length=URL_MAX)
    selo: Optional[str] = Field(default=None, max_length=SELO_MAX)
    sob_encomenda: bool = False
    limite_encomenda: int = Field(default=LIMITE_ENCOMENDA_PADRAO, ge=1, le=LIMITE_ENCOMENDA_MAXIMO)

    @field_validator("codigo_p")
    @classmethod
    def _normalizar_codigo(cls, valor):
        return normalizar_codigo_produto(valor)

    @field_validator("nome")
    @classmethod
    def _normalizar_nome(cls, valor):
        texto = _texto_limpo(valor, limite=NOME_MAX, vazio_como_none=False)
        if not texto:
            raise ValueError("Nome do produto é obrigatório.")
        return texto

    @field_validator("marca")
    @classmethod
    def _normalizar_marca(cls, valor):
        return _texto_limpo(valor, limite=MARCA_MAX)

    @field_validator("categoria")
    @classmethod
    def _normalizar_categoria(cls, valor):
        return _texto_limpo(valor, limite=CATEGORIA_MAX)

    @field_validator("descricao")
    @classmethod
    def _normalizar_descricao(cls, valor):
        if valor is None:
            return None
        texto = str(valor).strip()
        if len(texto) > DESCRICAO_MAX:
            raise ValueError(f"Descrição excede o limite de {DESCRICAO_MAX} caracteres.")
        return texto or None

    @field_validator("selo")
    @classmethod
    def _normalizar_selo(cls, valor):
        return _texto_limpo(valor, limite=SELO_MAX)

    @field_validator("preco")
    @classmethod
    def _validar_preco(cls, valor):
        return _decimal_monetario(valor, campo="Preço")

    @field_validator("custo")
    @classmethod
    def _validar_custo(cls, valor):
        return _decimal_monetario(valor, campo="Custo")

    @field_validator("lucro")
    @classmethod
    def _ignorar_lucro_cliente(cls, valor):
        numero = float(valor)
        if not math.isfinite(numero):
            raise ValueError("Lucro deve ser um número finito.")
        return numero

    @field_validator("imagem_url")
    @classmethod
    def _validar_imagem_principal(cls, valor):
        return _validar_url_https(valor, campo="Imagem principal")

    @field_validator("link_externo")
    @classmethod
    def _validar_link_externo(cls, valor):
        return _validar_url_https(valor, campo="Link externo")

    @field_validator("imagens")
    @classmethod
    def _validar_imagens(cls, valores):
        limpas = []
        for valor in valores:
            url = _validar_url_https(valor, campo="Imagem")
            if url and url not in limpas:
                limpas.append(url)
        return limpas


class CheckoutPublicoIn(VendaSiteIn):
    ciente_sob_encomenda: bool = False


def validar_site_api_key(chave_recebida: str | None):
    validar_chave_api(chave_recebida, "Configure o segredo de integração somente no ambiente do servidor.")


def _chave_interna_checkout() -> str:
    chave = os.environ.get("MISTICA_SITE_API_KEY", "").strip() or os.environ.get("MISTICA_SYNC_KEY", "").strip()
    if not chave:
        raise HTTPException(status_code=503, detail="Checkout temporariamente indisponível.")
    return chave


def produto_row_to_dict(row):
    data = dict(row)
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
    data["sob_encomenda"] = bool(data.get("sob_encomenda"))
    data["limite_encomenda"] = int(data.get("limite_encomenda") or LIMITE_ENCOMENDA_PADRAO)
    data["avaliacoes_total"] = data.get("avaliacoes_total") or 0
    data["avaliacoes_media"] = data.get("avaliacoes_media") or 0
    return data


_CAMPOS_PRODUTO_PUBLICO = """p.id, p.codigo_p, p.nome, p.marca, p.preco, p.quantidade, p.categoria,
                       p.descricao, p.imagem_url, p.imagens_json, p.link_externo, p.selo,
                       p.sob_encomenda, p.limite_encomenda, p.atualizado_em"""
_CAMPOS_PRODUTO_ADMIN = """p.id, p.codigo_p, p.nome, p.marca, p.preco, p.quantidade, p.categoria, p.custo, p.lucro,
                       p.estoque_minimo, p.descricao, p.imagem_url, p.imagens_json, p.link_externo, p.selo,
                       p.sob_encomenda, p.limite_encomenda, p.atualizado_em"""
_JOIN_AVALIACOES = """
LEFT JOIN (
    SELECT produto_id, COUNT(*) AS total, AVG(nota) AS media
    FROM avaliacoes_produtos
    WHERE COALESCE(aprovado, 1) = 1
    GROUP BY produto_id
) a ON a.produto_id = p.id"""


def _buscar_produtos(campos: str, busca: str, limite: int):
    termo = f"%{busca.strip()}%"
    with conectar() as conn:
        garantir_colunas_comerciais(conn)
        if busca.strip():
            rows = conn.execute(
                f"""SELECT {campos}, COALESCE(a.total,0) AS avaliacoes_total, ROUND(a.media,1) AS avaliacoes_media
                FROM produtos p{_JOIN_AVALIACOES}
                WHERE COALESCE(p.ativo,1)=1
                  AND (p.nome LIKE ? OR p.codigo_p LIKE ? OR p.categoria LIKE ? OR p.marca LIKE ? OR p.descricao LIKE ? OR p.selo LIKE ?)
                ORDER BY p.nome COLLATE NOCASE LIMIT ?""",
                (termo, termo, termo, termo, termo, termo, limite),
            ).fetchall()
        else:
            rows = conn.execute(
                f"""SELECT {campos}, COALESCE(a.total,0) AS avaliacoes_total, ROUND(a.media,1) AS avaliacoes_media
                FROM produtos p{_JOIN_AVALIACOES}
                WHERE COALESCE(p.ativo,1)=1 ORDER BY p.nome COLLATE NOCASE LIMIT ?""",
                (limite,),
            ).fetchall()
    return [produto_row_to_dict(row) for row in rows]


@router.get("/produtos")
def listar_produtos_completos(busca: str = "", limite: int = Query(100, ge=1, le=500)):
    return _buscar_produtos(_CAMPOS_PRODUTO_PUBLICO, busca, limite)


@router.get("/produtos/admin")
def listar_produtos_admin(busca: str = "", limite: int = Query(100, ge=1, le=500), sessao: dict = Depends(exigir_sessao_ou_chave_api())):
    return _buscar_produtos(_CAMPOS_PRODUTO_ADMIN, busca, limite)


@router.post("/checkout/pedidos", dependencies=[Depends(limitar_checkout_publico)])
def criar_pedido_checkout_publico(venda: CheckoutPublicoIn, request: Request):
    venda.origem = "site"
    venda.status = "Aguardando pagamento"
    venda.vendedor = "Site/Celular"
    venda.forma_pagamento = "Pix site/celular"
    idempotency_key = request.headers.get("Idempotency-Key")
    return registrar_checkout_publico(venda, request, _chave_interna_checkout(), idempotency_key)


def _codigo_duplicado(conn, codigo: Optional[str], *, excluir_id: Optional[int] = None):
    if not codigo:
        return None
    sql = "SELECT id FROM produtos WHERE UPPER(TRIM(codigo_p))=? AND COALESCE(ativo,1)=1"
    parametros = [codigo]
    if excluir_id is not None:
        sql += " AND id<>?"
        parametros.append(excluir_id)
    return conn.execute(sql, tuple(parametros)).fetchone()


def _lucro_calculado(preco: float, custo: float) -> float:
    return float((Decimal(str(preco)) - Decimal(str(custo))).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


@router.post("/produtos")
def criar_produto_completo(produto: ProdutoCompletoIn, sessao: dict = Depends(exigir_sessao_ou_chave_api())):
    agora = datetime.now().isoformat(timespec="seconds")
    imagens_json = json.dumps(produto.imagens or [], ensure_ascii=False)
    lucro = _lucro_calculado(produto.preco, produto.custo)
    sob_encomenda, limite_encomenda = normalizar_regra_encomenda(
        sob_encomenda=produto.sob_encomenda,
        limite_encomenda=produto.limite_encomenda,
    )
    with conectar() as conn:
        garantir_colunas_comerciais(conn)
        if _codigo_duplicado(conn, produto.codigo_p):
            raise HTTPException(status_code=409, detail=f"Já existe um produto ativo com o código '{produto.codigo_p}'")
        cur = conn.execute(
            """INSERT INTO produtos (
                codigo_p, nome, marca, preco, quantidade, categoria, custo, lucro, estoque_minimo,
                descricao, imagem_url, imagens_json, link_externo, selo, sob_encomenda,
                limite_encomenda, atualizado_em, ativo
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,1)""",
            (produto.codigo_p, produto.nome, produto.marca, produto.preco, produto.quantidade, produto.categoria,
             produto.custo, lucro, produto.estoque_minimo, produto.descricao, produto.imagem_url, imagens_json,
             produto.link_externo, produto.selo, sob_encomenda, limite_encomenda, agora),
        )
        produto_id = int(cur.lastrowid)
        depois = produto.model_dump()
        depois.update({"lucro": lucro, "sob_encomenda": bool(sob_encomenda), "limite_encomenda": limite_encomenda})
        registrar_auditoria(conn, "produto", produto_id, "criar", depois=depois)
        conn.commit()
    return {"ok": True, "id": produto_id, "status": "criado", "lucro": lucro,
            "sob_encomenda": bool(sob_encomenda), "limite_encomenda": limite_encomenda,
            "atualizado_em": agora}


@router.put("/produtos/{produto_id}")
def atualizar_produto_completo(produto_id: int, produto: ProdutoCompletoIn, sessao: dict = Depends(exigir_sessao_ou_chave_api())):
    agora = datetime.now().isoformat(timespec="seconds")
    imagens_json = json.dumps(produto.imagens or [], ensure_ascii=False)
    lucro = _lucro_calculado(produto.preco, produto.custo)
    sob_encomenda, limite_encomenda = normalizar_regra_encomenda(
        sob_encomenda=produto.sob_encomenda,
        limite_encomenda=produto.limite_encomenda,
    )
    with conectar() as conn:
        garantir_colunas_comerciais(conn)
        existente = conn.execute("SELECT * FROM produtos WHERE id=?", (produto_id,)).fetchone()
        if not existente:
            raise HTTPException(status_code=404, detail="Produto não encontrado")
        if _codigo_duplicado(conn, produto.codigo_p, excluir_id=produto_id):
            raise HTTPException(status_code=409, detail=f"Já existe um produto ativo com o código '{produto.codigo_p}'")
        conn.execute(
            """UPDATE produtos
               SET codigo_p=?, nome=?, marca=?, preco=?, quantidade=?, categoria=?, custo=?, lucro=?, estoque_minimo=?,
                   descricao=?, imagem_url=?, imagens_json=?, link_externo=?, selo=?, sob_encomenda=?,
                   limite_encomenda=?, atualizado_em=?, ativo=1
             WHERE id=?""",
            (produto.codigo_p, produto.nome, produto.marca, produto.preco, produto.quantidade, produto.categoria,
             produto.custo, lucro, produto.estoque_minimo, produto.descricao, produto.imagem_url, imagens_json,
             produto.link_externo, produto.selo, sob_encomenda, limite_encomenda, agora, produto_id),
        )
        depois = produto.model_dump()
        depois.update({"lucro": lucro, "sob_encomenda": bool(sob_encomenda), "limite_encomenda": limite_encomenda})
        registrar_auditoria(conn, "produto", produto_id, "atualizar", antes=dict(existente), depois=depois)
        conn.commit()
    return {"ok": True, "id": produto_id, "status": "atualizado", "lucro": lucro,
            "sob_encomenda": bool(sob_encomenda), "limite_encomenda": limite_encomenda,
            "atualizado_em": agora}


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
