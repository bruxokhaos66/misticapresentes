from __future__ import annotations

import os
import secrets
import sqlite3
import time
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel, Field

from backend.audit import registrar_auditoria
from backend.api_security import validar_site_api_key as validar_chave_api
from backend.database import conectar, listar
from backend.idempotency import resposta_idempotente_existente, salvar_resposta_idempotente
from backend.order_status_routes import MINUTOS_EXPIRACAO_PEDIDO_PENDENTE, STATUS_PEDIDO
from backend.rate_limit import _client_ip, limitar_requisicoes
from config import DB_PATH

router = APIRouter(prefix="/api", tags=["site-estoque"])

limitar_criacao_venda = limitar_requisicoes("criar_venda_site", limite=20, janela_segundos=60)


class ItemEstoqueSite(BaseModel):
    produto_id: Optional[int] = None
    codigo_p: Optional[str] = None
    nome_p: Optional[str] = None
    quantidade: int = Field(gt=0)
    # custo_unitario/valor_unitario/valor_total podem ser enviados pelo cliente por
    # compatibilidade, mas NUNCA são usados para gravar preço: o servidor sempre
    # recalcula a partir do produto salvo no banco (ver recalcular_item_venda).
    custo_unitario: float = Field(default=0.0, ge=0)
    valor_unitario: float = Field(default=0.0, ge=0)
    valor_total: float = Field(default=0.0, ge=0)


class ReservaEstoqueSite(BaseModel):
    origem: str = "site"
    venda_id: Optional[str] = None
    itens: list[ItemEstoqueSite] = Field(default_factory=list)


class VendaSiteIn(BaseModel):
    origem: str = "site"
    cliente: str = "Pedido site/celular"
    # subtotal/desconto/taxa/total_final são aceitos por compatibilidade com clientes
    # antigos, mas o servidor sempre recalcula esses valores a partir do preço do
    # produto no banco antes de gravar a venda (ver recalcular_venda_site).
    subtotal: float = 0.0
    desconto: float = Field(default=0.0, ge=0)
    taxa: float = Field(default=0.0, ge=0)
    total_final: float = 0.0
    forma_pagamento: str = "Pix site/celular"
    vendedor: str = "Site/Celular"
    status: str = "Aguardando pagamento"
    data_venda: Optional[str] = None
    data_iso: Optional[str] = None
    dia_operacional: Optional[str] = None
    baixa_estoque: bool = True
    itens: list[ItemEstoqueSite] = Field(default_factory=list)


class AcessoSiteIn(BaseModel):
    path: Optional[str] = "/"
    referrer: Optional[str] = "direto"
    userAgent: Optional[str] = None
    origem: Optional[str] = "site"


class PlaylistAmbienteIn(BaseModel):
    links: list[str] = Field(default_factory=list)


def log_playlist(etapa: str, inicio: float, detalhe: str = ""):
    duracao_ms = int((time.perf_counter() - inicio) * 1000)
    sufixo = f" | {detalhe}" if detalhe else ""
    print(f"[API][playlist-ambiente] {etapa}: {duracao_ms}ms{sufixo}")


def conectar_rapido(timeout: float = 0.35):
    conn = sqlite3.connect(DB_PATH, timeout=timeout)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA query_only = ON")
    return conn


def validar_site_api_key(chave_recebida: str | None):
    validar_chave_api(chave_recebida, "Configure MISTICA_SITE_API_KEY ou MISTICA_SYNC_KEY para permitir escrita pela API.")


def buscar_produto(conn, item: ItemEstoqueSite):
    if item.produto_id:
        produto = conn.execute(
            "SELECT id, codigo_p, nome, quantidade, preco, custo, COALESCE(ativo,1) AS ativo FROM produtos WHERE id=? AND COALESCE(ativo,1)=1",
            (item.produto_id,),
        ).fetchone()
        if produto:
            return produto

    if item.codigo_p:
        produto = conn.execute(
            "SELECT id, codigo_p, nome, quantidade, preco, custo, COALESCE(ativo,1) AS ativo FROM produtos WHERE codigo_p=? AND COALESCE(ativo,1)=1",
            (item.codigo_p,),
        ).fetchone()
        if produto:
            return produto

    return None


def validar_itens_e_estoque(conn, itens: list[ItemEstoqueSite], *, exigir_estoque: bool):
    """Busca cada produto no banco, confirma que está ativo e (opcionalmente) que há
    estoque suficiente. Retorna sempre o preço/custo vindos do banco, nunca os
    valores enviados pelo cliente, para que a venda seja gravada com um retrato
    fiel do preço real do produto."""
    if not itens:
        raise HTTPException(status_code=400, detail="Nenhum item informado.")
    produtos_validados = []
    for item in itens:
        produto = buscar_produto(conn, item)
        if not produto:
            raise HTTPException(status_code=404, detail=f"Produto não encontrado ou inativo: {item.codigo_p or item.nome_p or item.produto_id}")
        estoque_atual = int(produto["quantidade"] or 0)
        if exigir_estoque and estoque_atual < item.quantidade:
            raise HTTPException(status_code=409, detail=f"Estoque insuficiente para {produto['nome']}. Disponível: {estoque_atual}")
        produtos_validados.append((item, produto, estoque_atual))
    return produtos_validados


def recalcular_venda_site(produtos_validados):
    """Ignora subtotal/desconto/taxa/total_final/valor_unitario enviados pelo cliente
    e recalcula tudo a partir do preco salvo no produto (retrato de preço da venda)."""
    itens_calculados = []
    subtotal = 0.0
    for item, produto, _estoque_atual in produtos_validados:
        preco = float(produto["preco"] or 0)
        custo = float(produto["custo"] or 0)
        valor_total_item = round(preco * item.quantidade, 2)
        subtotal += valor_total_item
        itens_calculados.append(
            {
                "produto": produto,
                "quantidade": item.quantidade,
                "custo_unitario": custo,
                "valor_unitario": preco,
                "valor_total": valor_total_item,
            }
        )
    subtotal = round(subtotal, 2)
    return itens_calculados, subtotal


def registrar_movimento(conn, *, produto, quantidade, motivo, usuario, estoque_anterior, estoque_posterior, venda_id):
    conn.execute(
        """
        INSERT INTO movimentacao_estoque
        (codigo_p, produto, quantidade, tipo, motivo, usuario, data_hora, estoque_anterior, estoque_posterior, venda_id)
        VALUES (?,?,?,?,?,?,?,?,?,?)
        """,
        (
            produto["codigo_p"],
            produto["nome"],
            quantidade,
            "saida",
            motivo,
            usuario,
            datetime.now().isoformat(timespec="seconds"),
            estoque_anterior,
            estoque_posterior,
            venda_id,
        ),
    )


def garantir_tabela_acessos_site(conn):
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS site_acessos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            path TEXT,
            referrer TEXT,
            user_agent TEXT,
            origem TEXT,
            criado_em TEXT NOT NULL,
            dia TEXT NOT NULL
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_site_acessos_dia ON site_acessos(dia)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_site_acessos_criado_em ON site_acessos(criado_em)")


def garantir_tabela_playlist_ambiente(conn):
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS site_playlist_ambiente (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            links TEXT NOT NULL DEFAULT '',
            atualizado_em TEXT NOT NULL
        )
        """
    )


def limitar_texto(valor: str | None, limite: int, padrao: str = "") -> str:
    texto = str(valor or padrao).strip()
    return texto[:limite]


def normalizar_link_youtube(valor: str | None) -> str:
    texto = limitar_texto(valor, 520, "")
    if not texto.startswith(("https://www.youtube.com/", "https://youtube.com/", "https://youtu.be/", "https://music.youtube.com/")):
        return ""
    return texto


def limpar_links_playlist(links: list[str]) -> list[str]:
    limpos = []
    for item in links:
        link = normalizar_link_youtube(item)
        if link and link not in limpos:
            limpos.append(link)
        if len(limpos) >= 12:
            break
    return limpos


@router.post("/vendas", dependencies=[Depends(limitar_criacao_venda)])
def registrar_venda_site(
    venda: VendaSiteIn,
    request: Request,
    x_mistica_api_key: str | None = Header(default=None),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
):
    validar_site_api_key(x_mistica_api_key)

    with conectar() as conn_check:
        resposta_existente = resposta_idempotente_existente(conn_check, "criar_pedido", idempotency_key)
    if resposta_existente is not None:
        return resposta_existente

    if venda.status not in STATUS_PEDIDO:
        venda.status = "Aguardando pagamento"
    if venda.baixa_estoque and venda.status == "Aguardando pagamento":
        # Pagamento ainda não confirmado: nunca baixar estoque neste momento, mesmo que
        # o cliente peça baixa_estoque=true. A baixa definitiva só acontece quando o
        # pedido avança para "Pagamento confirmado"/"Separando pedido" (ver
        # backend/order_status_routes.py::baixar_estoque_do_pedido).
        venda.baixa_estoque = False

    agora = datetime.now()
    data_iso = venda.data_iso or agora.isoformat(timespec="seconds")
    data_venda = venda.data_venda or agora.strftime("%d/%m/%Y %H:%M:%S")
    dia_operacional = venda.dia_operacional or agora.strftime("%Y-%m-%d")
    ip_origem = _client_ip(request)
    expira_em = None
    if venda.status == "Aguardando pagamento":
        expira_em = (agora + timedelta(minutes=MINUTOS_EXPIRACAO_PEDIDO_PENDENTE)).isoformat(timespec="seconds")

    with conectar() as conn:
        try:
            produtos_validados = validar_itens_e_estoque(conn, venda.itens, exigir_estoque=venda.baixa_estoque)
            itens_calculados, subtotal = recalcular_venda_site(produtos_validados)
            total_final = subtotal

            cur = conn.execute(
                """
                INSERT INTO pedidos (
                    cliente, data_venda, subtotal, desconto, taxa, total_final,
                    forma_pagamento, vendedor, status, data_iso, dia_operacional,
                    origem, expira_em
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    venda.cliente,
                    data_venda,
                    subtotal,
                    0.0,
                    0.0,
                    total_final,
                    venda.forma_pagamento,
                    venda.vendedor,
                    venda.status,
                    data_iso,
                    dia_operacional,
                    venda.origem,
                    expira_em,
                ),
            )
            venda_id = int(cur.lastrowid)

            for calculado in itens_calculados:
                produto = calculado["produto"]
                conn.execute(
                    """
                    INSERT INTO pedidos_itens
                    (pedido_id, codigo_p, nome_p, quantidade, custo_unitario, valor_unitario, valor_total)
                    VALUES (?,?,?,?,?,?,?)
                    """,
                    (
                        venda_id,
                        produto["codigo_p"],
                        produto["nome"],
                        calculado["quantidade"],
                        calculado["custo_unitario"],
                        calculado["valor_unitario"],
                        calculado["valor_total"],
                    ),
                )

            if venda.baixa_estoque:
                for item, produto, estoque_anterior in produtos_validados:
                    estoque_posterior = estoque_anterior - item.quantidade
                    conn.execute("UPDATE produtos SET quantidade=? WHERE id=?", (estoque_posterior, produto["id"]))
                    registrar_movimento(
                        conn,
                        produto=produto,
                        quantidade=item.quantidade,
                        motivo="Venda site" if venda.origem == "site" else "Venda programa",
                        usuario=f"{venda.vendedor or 'Site/Celular'} (IP {ip_origem})",
                        estoque_anterior=estoque_anterior,
                        estoque_posterior=estoque_posterior,
                        venda_id=venda_id,
                    )
                conn.execute(
                    "UPDATE pedidos SET estoque_baixado=1, estoque_baixado_em=? WHERE id=?",
                    (data_iso, venda_id),
                )

            resposta = {"ok": True, "id": venda_id, "status": "criado", "subtotal": subtotal, "total_final": total_final, "estoque_baixado": venda.baixa_estoque}
            registrar_auditoria(conn, "pedido", venda_id, "criar", venda.vendedor, depois={"total_final": total_final, "itens": len(itens_calculados), "status": venda.status})
            salvar_resposta_idempotente(conn, "criar_pedido", idempotency_key, resposta)
            conn.commit()
        except Exception:
            conn.rollback()
            raise

    return resposta


@router.post("/estoque/reservar")
def reservar_estoque_site(payload: ReservaEstoqueSite, x_mistica_api_key: str | None = Header(default=None)):
    validar_site_api_key(x_mistica_api_key)
    if not payload.itens:
        raise HTTPException(status_code=400, detail="Nenhum item informado para baixa de estoque.")

    with conectar() as conn:
        baixados = []
        produtos_validados = validar_itens_e_estoque(conn, payload.itens, exigir_estoque=True)
        for item, produto, estoque_anterior in produtos_validados:
            estoque_posterior = estoque_anterior - item.quantidade
            conn.execute("UPDATE produtos SET quantidade=? WHERE id=?", (estoque_posterior, produto["id"]))
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


@router.get("/site/playlist-ambiente")
def obter_playlist_ambiente():
    inicio = time.perf_counter()
    log_playlist("inicio", inicio)
    links = []
    atualizado_em = None
    erro_banco = None

    try:
        conn = conectar_rapido(timeout=0.35)
        try:
            row = conn.execute("SELECT links, atualizado_em FROM site_playlist_ambiente WHERE id=1").fetchone()
        finally:
            conn.close()
        if row:
            links = [item for item in str(row["links"] or "").split("\n") if item]
            atualizado_em = row["atualizado_em"]
        log_playlist("consulta_banco", inicio, f"{len(links)} link(s)")
    except Exception as exc:
        erro_banco = str(exc)
        log_playlist("consulta_banco_falhou", inicio, erro_banco)

    resposta = {
        "ok": True,
        "links": limpar_links_playlist(links),
        "total": len(limpar_links_playlist(links)),
        "atualizado_em": atualizado_em,
        "banco_erro": erro_banco,
        "data_hora": datetime.now().isoformat(timespec="seconds"),
    }
    log_playlist("fim_resposta", inicio, f"total={resposta['total']}")
    return resposta


@router.post("/site/playlist-ambiente")
def salvar_playlist_ambiente(payload: PlaylistAmbienteIn, x_mistica_api_key: str | None = Header(default=None)):
    validar_site_api_key(x_mistica_api_key)
    links = limpar_links_playlist(payload.links)
    atualizado_em = datetime.now().isoformat(timespec="seconds")

    with conectar() as conn:
        garantir_tabela_playlist_ambiente(conn)
        conn.execute(
            """
            INSERT INTO site_playlist_ambiente (id, links, atualizado_em)
            VALUES (1, ?, ?)
            ON CONFLICT(id) DO UPDATE SET links=excluded.links, atualizado_em=excluded.atualizado_em
            """,
            ("\n".join(links), atualizado_em),
        )
        conn.commit()

    return {
        "ok": True,
        "links": links,
        "total": len(links),
        "atualizado_em": atualizado_em,
    }


@router.post("/site/acessos")
def registrar_acesso_site(payload: AcessoSiteIn, x_mistica_api_key: str | None = Header(default=None)):
    validar_site_api_key(x_mistica_api_key)
    agora = datetime.now()
    criado_em = agora.isoformat(timespec="seconds")
    dia = agora.strftime("%Y-%m-%d")

    with conectar() as conn:
        garantir_tabela_acessos_site(conn)
        cur = conn.execute(
            """
            INSERT INTO site_acessos (path, referrer, user_agent, origem, criado_em, dia)
            VALUES (?,?,?,?,?,?)
            """,
            (
                limitar_texto(payload.path, 260, "/"),
                limitar_texto(payload.referrer, 360, "direto"),
                limitar_texto(payload.userAgent, 520, "visitante"),
                limitar_texto(payload.origem, 40, "site"),
                criado_em,
                dia,
            ),
        )
        conn.commit()
        acesso_id = int(cur.lastrowid)

    return {"ok": True, "id": acesso_id, "data_hora": criado_em}


@router.get("/site/acessos/resumo")
def resumo_acessos_site():
    hoje = datetime.now().strftime("%Y-%m-%d")
    with conectar() as conn:
        garantir_tabela_acessos_site(conn)
        total = conn.execute("SELECT COUNT(*) AS total FROM site_acessos").fetchone()["total"]
        hoje_total = conn.execute("SELECT COUNT(*) AS total FROM site_acessos WHERE dia=?", (hoje,)).fetchone()["total"]
        visitantes_unicos = conn.execute("SELECT COUNT(DISTINCT COALESCE(user_agent,'')) AS total FROM site_acessos").fetchone()["total"]
        ultimo = conn.execute(
            """
            SELECT path, referrer, user_agent, origem, criado_em, dia
            FROM site_acessos
            ORDER BY id DESC
            LIMIT 1
            """
        ).fetchone()

    return {
        "ok": True,
        "total": int(total or 0),
        "acessos_total": int(total or 0),
        "today": int(hoje_total or 0),
        "acessos_hoje": int(hoje_total or 0),
        "uniqueVisitors": int(visitantes_unicos or 0),
        "visitantes_unicos": int(visitantes_unicos or 0),
        "lastAccess": dict(ultimo) if ultimo else None,
        "ultimo_acesso": dict(ultimo) if ultimo else None,
        "data_hora": datetime.now().isoformat(timespec="seconds"),
    }
