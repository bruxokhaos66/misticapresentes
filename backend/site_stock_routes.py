from __future__ import annotations

import os
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field

from backend.database import conectar, listar

router = APIRouter(prefix="/api", tags=["site-estoque"])

STATUS_PEDIDO = {
    "Aguardando pagamento",
    "Pagamento confirmado",
    "Separando pedido",
    "Pronto para retirada",
    "Entregue",
    "Cancelado",
    "Concluído",
}


class ItemEstoqueSite(BaseModel):
    produto_id: Optional[int] = None
    codigo_p: Optional[str] = None
    nome_p: Optional[str] = None
    quantidade: int = Field(gt=0)
    custo_unitario: float = 0.0
    valor_unitario: float = 0.0
    valor_total: float = 0.0


class ReservaEstoqueSite(BaseModel):
    origem: str = "site"
    venda_id: Optional[str] = None
    itens: list[ItemEstoqueSite] = Field(default_factory=list)


class VendaSiteIn(BaseModel):
    origem: str = "site"
    cliente: str = "Pedido site/celular"
    subtotal: float = 0.0
    desconto: float = 0.0
    taxa: float = 0.0
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


def validar_site_api_key(chave_recebida: str | None):
    chave = os.environ.get("MISTICA_SITE_API_KEY", "").strip()
    if not chave:
        print("[API] Aviso: MISTICA_SITE_API_KEY não configurada. Endpoints sensíveis em modo desenvolvimento.")
        return
    if chave_recebida != chave:
        raise HTTPException(status_code=403, detail="Chave da API do site inválida.")


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


def validar_itens_e_estoque(conn, itens: list[ItemEstoqueSite]):
    if not itens:
        raise HTTPException(status_code=400, detail="Nenhum item informado.")
    produtos_validados = []
    for item in itens:
        produto = buscar_produto(conn, item)
        if not produto:
            raise HTTPException(status_code=404, detail=f"Produto não encontrado: {item.codigo_p or item.nome_p or item.produto_id}")
        estoque_atual = int(produto["quantidade"] or 0)
        if estoque_atual < item.quantidade:
            raise HTTPException(status_code=409, detail=f"Estoque insuficiente para {produto['nome']}. Disponível: {estoque_atual}")
        produtos_validados.append((item, produto, estoque_atual))
    return produtos_validados


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


@router.post("/vendas")
def registrar_venda_site(venda: VendaSiteIn, x_mistica_api_key: str | None = Header(default=None)):
    validar_site_api_key(x_mistica_api_key)
    if venda.status not in STATUS_PEDIDO:
        venda.status = "Aguardando pagamento"

    agora = datetime.now()
    data_iso = venda.data_iso or agora.isoformat(timespec="seconds")
    data_venda = venda.data_venda or agora.strftime("%d/%m/%Y %H:%M:%S")
    dia_operacional = venda.dia_operacional or agora.strftime("%Y-%m-%d")

    with conectar() as conn:
        try:
            produtos_validados = validar_itens_e_estoque(conn, venda.itens) if venda.baixa_estoque else []

            cur = conn.execute(
                """
                INSERT INTO vendas (
                    cliente, data_venda, subtotal, desconto, taxa, total_final,
                    forma_pagamento, vendedor, status, data_iso, dia_operacional,
                    origem_sync, local_id
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    venda.cliente,
                    data_venda,
                    venda.subtotal,
                    venda.desconto,
                    venda.taxa,
                    venda.total_final,
                    venda.forma_pagamento,
                    venda.vendedor,
                    venda.status,
                    data_iso,
                    dia_operacional,
                    venda.origem,
                    None,
                ),
            )
            venda_id = int(cur.lastrowid)

            for item in venda.itens:
                produto = buscar_produto(conn, item)
                conn.execute(
                    """
                    INSERT INTO vendas_itens
                    (venda_id, codigo_p, nome_p, quantidade, custo_unitario, valor_unitario, valor_total)
                    VALUES (?,?,?,?,?,?,?)
                    """,
                    (
                        venda_id,
                        produto["codigo_p"] if produto else item.codigo_p,
                        produto["nome"] if produto else item.nome_p,
                        item.quantidade,
                        item.custo_unitario,
                        item.valor_unitario,
                        item.valor_total,
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
                        usuario=venda.vendedor or "Site/Celular",
                        estoque_anterior=estoque_anterior,
                        estoque_posterior=estoque_posterior,
                        venda_id=venda_id,
                    )

            conn.commit()
        except Exception:
            conn.rollback()
            raise

    return {"ok": True, "id": venda_id, "status": "criado", "estoque_baixado": venda.baixa_estoque}


@router.post("/estoque/reservar")
def reservar_estoque_site(payload: ReservaEstoqueSite, x_mistica_api_key: str | None = Header(default=None)):
    validar_site_api_key(x_mistica_api_key)
    if not payload.itens:
        raise HTTPException(status_code=400, detail="Nenhum item informado para baixa de estoque.")

    with conectar() as conn:
        baixados = []
        produtos_validados = validar_itens_e_estoque(conn, payload.itens)
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
    with conectar() as conn:
        garantir_tabela_playlist_ambiente(conn)
        row = conn.execute("SELECT links, atualizado_em FROM site_playlist_ambiente WHERE id=1").fetchone()

    links = []
    atualizado_em = None
    if row:
        links = [item for item in str(row["links"] or "").split("\n") if item]
        atualizado_em = row["atualizado_em"]

    return {
        "ok": True,
        "links": limpar_links_playlist(links),
        "atualizado_em": atualizado_em,
        "data_hora": datetime.now().isoformat(timespec="seconds"),
    }


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

    return {"ok": True, "id": acesso_id, "status": "registrado", "data_hora": criado_em}


@router.get("/site/acessos/resumo")
def resumo_acessos_site(x_mistica_api_key: str | None = Header(default=None)):
    validar_site_api_key(x_mistica_api_key)
    hoje = datetime.now().strftime("%Y-%m-%d")

    with conectar() as conn:
        garantir_tabela_acessos_site(conn)
        total = conn.execute("SELECT COUNT(*) AS total FROM site_acessos").fetchone()["total"] or 0
        hoje_total = conn.execute("SELECT COUNT(*) AS total FROM site_acessos WHERE dia=?", (hoje,)).fetchone()["total"] or 0
        unicos = conn.execute("SELECT COUNT(DISTINCT COALESCE(user_agent,'visitante')) AS total FROM site_acessos").fetchone()["total"] or 0
        ultimo = conn.execute("SELECT MAX(criado_em) AS ultimo FROM site_acessos").fetchone()["ultimo"]
        rows = conn.execute(
            """
            SELECT criado_em AS at, path, referrer, user_agent AS userAgent
            FROM site_acessos
            ORDER BY id DESC
            LIMIT 50
            """
        ).fetchall()
        visitas = [dict(row) for row in rows]

    return {
        "mode": "remote",
        "total": int(total),
        "today": int(hoje_total),
        "uniqueVisitors": int(unicos),
        "lastAccess": ultimo,
        "visits": visitas,
        "acessos_total": int(total),
        "acessos_hoje": int(hoje_total),
        "visitantes_unicos": int(unicos),
        "ultimo_acesso": ultimo,
        "acessos_recentes": visitas,
        "data_hora": datetime.now().isoformat(timespec="seconds"),
    }
