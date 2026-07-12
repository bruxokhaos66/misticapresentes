from __future__ import annotations

import os
import secrets
import sqlite3
import time
from datetime import datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel, Field

from backend.audit import registrar_auditoria
from backend.api_security import validar_site_api_key as validar_chave_api
from backend.database import conectar, listar
from backend.idempotency import resposta_idempotente_existente, salvar_resposta_idempotente
from backend.logging_config import get_logger
from backend.order_status_routes import MINUTOS_EXPIRACAO_PEDIDO_PENDENTE, STATUS_PEDIDO
from backend.panel_sessions import exigir_sessao_ou_chave_api
from backend.pix import gerar_pix_do_pedido
from backend.rate_limit import _client_ip, limitar_requisicoes
from config import DB_PATH

logger = get_logger(__name__)

router = APIRouter(prefix="/api", tags=["site-estoque"])

limitar_criacao_venda = limitar_requisicoes("criar_venda_site", limite=20, janela_segundos=60)
limitar_reserva_estoque = limitar_requisicoes("reservar_estoque_site", limite=20, janela_segundos=60)


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
    # Identificação mínima do cliente: telefone/WhatsApp, usado para localizar o
    # pedido e enviar o link de acompanhamento/status. Opcional para não travar
    # quem ainda não digitou o contato.
    telefone: Optional[str] = None
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
    # Código de cupom opcional. O desconto NUNCA é aceito do cliente: se houver
    # cupom, o servidor busca a campanha vigente e recalcula o desconto.
    cupom: Optional[str] = None
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
    logger.info(
        "playlist-ambiente %s",
        etapa,
        extra={"evento": "playlist_ambiente", "etapa": etapa, "duracao_ms": duracao_ms, "detalhe": detalhe or None},
    )


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


def _centavos(valor) -> Decimal:
    """Converte para Decimal arredondado em centavos (ROUND_HALF_UP), evitando o
    erro de representação binária do float ao somar valores monetários."""
    return Decimal(str(valor or 0)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def recalcular_venda_site(produtos_validados):
    """Ignora subtotal/desconto/taxa/total_final/valor_unitario enviados pelo cliente
    e recalcula tudo a partir do preco salvo no produto (retrato de preço da venda).
    Usa Decimal internamente para que a soma dos itens não acumule erro de
    ponto flutuante antes de virar float para gravar nas colunas REAL."""
    itens_calculados = []
    subtotal = Decimal("0.00")
    for item, produto, _estoque_atual in produtos_validados:
        preco = _centavos(produto["preco"])
        custo = _centavos(produto["custo"])
        valor_total_item = _centavos(preco * item.quantidade)
        subtotal += valor_total_item
        itens_calculados.append(
            {
                "produto": produto,
                "quantidade": item.quantidade,
                "custo_unitario": float(custo),
                "valor_unitario": float(preco),
                "valor_total": float(valor_total_item),
            }
        )
    return itens_calculados, float(_centavos(subtotal))


def baixar_estoque_atomico(conn, *, produto_id: int, nome_produto: str, quantidade: int) -> tuple[int, int]:
    """Decrementa o estoque de forma atômica (a checagem de saldo e a escrita
    acontecem no mesmo UPDATE), para não depender de um SELECT anterior que
    pode estar desatualizado quando duas requisições concorrem pelo mesmo
    produto (ver tests que reproduzem a corrida com dois checkouts simultâneos
    disputando a última unidade)."""
    cur = conn.execute(
        "UPDATE produtos SET quantidade = quantidade - ? WHERE id=? AND quantidade >= ?",
        (quantidade, produto_id, quantidade),
    )
    if cur.rowcount == 0:
        atual = conn.execute("SELECT quantidade FROM produtos WHERE id=?", (produto_id,)).fetchone()
        disponivel = int(atual["quantidade"] or 0) if atual else 0
        raise HTTPException(status_code=409, detail=f"Estoque insuficiente para {nome_produto}. Disponível: {disponivel}")
    posterior = conn.execute("SELECT quantidade FROM produtos WHERE id=?", (produto_id,)).fetchone()["quantidade"]
    return int(posterior) + quantidade, int(posterior)


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
    pedido_pendente = venda.status == "Aguardando pagamento"
    if pedido_pendente:
        # Reserva de estoque: o pedido pendente já baixa o estoque no momento da
        # criação (para não vender o mesmo último item para dois clientes enquanto
        # o Pix não é confirmado). Se o pagamento expirar ou o pedido for
        # cancelado, o estoque reservado é devolvido (ver
        # order_status_routes.py::expirar_pedidos_pendentes/cancelar_com_reposicao).
        venda.baixa_estoque = True
    telefone = "".join(ch for ch in str(venda.telefone or "") if ch.isdigit() or ch in "+ ").strip()[:32]

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

            # Aplicação de cupom no servidor: o desconto é derivado da campanha
            # vigente, nunca de um valor enviado pelo cliente (ver
            # backend/campaign_routes.py::calcular_desconto_cupom).
            desconto = 0.0
            cupom_info = None
            codigo_cupom = str(venda.cupom or "").strip().upper()
            if codigo_cupom:
                from backend.campaign_routes import buscar_cupom_ativo, calcular_desconto_cupom

                campanha = buscar_cupom_ativo(conn, codigo_cupom)
                if not campanha:
                    raise HTTPException(status_code=400, detail="Cupom inválido ou expirado.")
                cupom_info = calcular_desconto_cupom(campanha, subtotal)
                desconto = cupom_info["desconto"]
            total_final = float(_centavos(subtotal - desconto))

            cur = conn.execute(
                """
                INSERT INTO pedidos (
                    cliente, telefone, data_venda, subtotal, desconto, taxa, total_final,
                    forma_pagamento, vendedor, status, data_iso, dia_operacional,
                    origem, expira_em, cupom
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    venda.cliente,
                    telefone or None,
                    data_venda,
                    subtotal,
                    desconto,
                    0.0,
                    total_final,
                    venda.forma_pagamento,
                    venda.vendedor,
                    venda.status,
                    data_iso,
                    dia_operacional,
                    venda.origem,
                    expira_em,
                    codigo_cupom or None,
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
                motivo = "Reserva de estoque (pedido aguardando pagamento)" if pedido_pendente else ("Venda site" if venda.origem == "site" else "Venda programa")
                for item, produto, _estoque_anterior_visto in produtos_validados:
                    estoque_anterior, estoque_posterior = baixar_estoque_atomico(
                        conn, produto_id=produto["id"], nome_produto=produto["nome"], quantidade=item.quantidade
                    )
                    registrar_movimento(
                        conn,
                        produto=produto,
                        quantidade=item.quantidade,
                        motivo=motivo,
                        usuario=f"{venda.vendedor or 'Site/Celular'} (IP {ip_origem})",
                        estoque_anterior=estoque_anterior,
                        estoque_posterior=estoque_posterior,
                        venda_id=venda_id,
                    )
                conn.execute(
                    "UPDATE pedidos SET estoque_baixado=1, estoque_baixado_em=?, estoque_reservado=? WHERE id=?",
                    (data_iso, 1 if pedido_pendente else 0, venda_id),
                )

            pix = None
            if pedido_pendente:
                pix = gerar_pix_do_pedido(venda_id, total_final)
                if pix:
                    conn.execute(
                        "UPDATE pedidos SET pix_txid=?, pix_copia_cola=? WHERE id=?",
                        (pix["txid"], pix["copia_cola"], venda_id),
                    )

            resposta = {
                "ok": True,
                "id": venda_id,
                "status": "criado",
                "subtotal": subtotal,
                "desconto": desconto,
                "cupom": codigo_cupom or None,
                "frete_gratis": bool(cupom_info["frete_gratis"]) if cupom_info else False,
                "total_final": total_final,
                "estoque_baixado": venda.baixa_estoque,
                "estoque_reservado": pedido_pendente and venda.baixa_estoque,
                "expira_em": expira_em,
                "pix_txid": pix["txid"] if pix else None,
                "pix_copia_cola": pix["copia_cola"] if pix else None,
            }
            registrar_auditoria(conn, "pedido", venda_id, "criar", venda.vendedor, depois={"total_final": total_final, "itens": len(itens_calculados), "status": venda.status})
            salvar_resposta_idempotente(conn, "criar_pedido", idempotency_key, resposta)
            conn.commit()
        except Exception:
            conn.rollback()
            raise

    return resposta


@router.post("/estoque/reservar", dependencies=[Depends(limitar_reserva_estoque)])
def reservar_estoque_site(payload: ReservaEstoqueSite, x_mistica_api_key: str | None = Header(default=None)):
    validar_site_api_key(x_mistica_api_key)
    if not payload.itens:
        raise HTTPException(status_code=400, detail="Nenhum item informado para baixa de estoque.")

    with conectar() as conn:
        baixados = []
        produtos_validados = validar_itens_e_estoque(conn, payload.itens, exigir_estoque=True)
        for item, produto, _estoque_anterior_visto in produtos_validados:
            baixar_estoque_atomico(conn, produto_id=produto["id"], nome_produto=produto["nome"], quantidade=item.quantidade)
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
def resumo_acessos_site(sessao: dict = Depends(exigir_sessao_ou_chave_api())):
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
