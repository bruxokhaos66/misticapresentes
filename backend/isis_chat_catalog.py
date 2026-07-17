"""Camada 4 — busca no catálogo (fonte de verdade única) do Chat da Isis 2.0.

Única leitura do catálogo real: produtos ativos (tabela `produtos`, mesma
usada por `backend.product_routes`) e cursos ativos (mesmo catálogo real
usado por `backend.course_routes`: `CATALOGO_CURSOS_PAGOS` + materiais
gratuitos publicados em `cursos_materiais`). Nunca inventa produto, preço,
estoque, promoção, desconto, curso ou certificação -- se um campo não
existir no banco, o dicionário devolvido simplesmente não o preenche (o
chamador decide como comunicar a ausência).
"""
from __future__ import annotations

import json


def buscar_produtos_ativos(conn, *, termo: str = "", limite: int = 50) -> list[dict]:
    limite = max(1, min(int(limite), 200))
    if termo.strip():
        padrao = f"%{termo.strip()}%"
        linhas = conn.execute(
            """
            SELECT id, nome, marca, preco, quantidade, categoria, descricao, imagem_url,
                   imagens_json, link_externo, selo, sob_encomenda
            FROM produtos
            WHERE COALESCE(ativo,1)=1
              AND (nome LIKE ? OR categoria LIKE ? OR descricao LIKE ? OR marca LIKE ? OR selo LIKE ?)
            ORDER BY nome COLLATE NOCASE
            LIMIT ?
            """,
            (padrao, padrao, padrao, padrao, padrao, limite),
        ).fetchall()
    else:
        linhas = conn.execute(
            """
            SELECT id, nome, marca, preco, quantidade, categoria, descricao, imagem_url,
                   imagens_json, link_externo, selo, sob_encomenda
            FROM produtos
            WHERE COALESCE(ativo,1)=1
            ORDER BY nome COLLATE NOCASE
            LIMIT ?
            """,
            (limite,),
        ).fetchall()
    return [_produto_para_dict(dict(linha)) for linha in linhas]


def obter_produto_ativo(conn, produto_id: int) -> dict | None:
    linha = conn.execute(
        """
        SELECT id, nome, marca, preco, quantidade, categoria, descricao, imagem_url,
               imagens_json, link_externo, selo, sob_encomenda
        FROM produtos WHERE id=? AND COALESCE(ativo,1)=1
        """,
        (produto_id,),
    ).fetchone()
    return _produto_para_dict(dict(linha)) if linha else None


def _produto_para_dict(dados: dict) -> dict:
    try:
        imagens = json.loads(dados.get("imagens_json") or "[]")
    except Exception:
        imagens = []
    disponivel = bool((dados.get("quantidade") or 0) > 0 or dados.get("sob_encomenda"))
    return {
        "id": dados["id"],
        "nome": dados.get("nome") or "",
        "marca": dados.get("marca") or "",
        "preco": float(dados.get("preco") or 0),
        "categoria": dados.get("categoria") or "",
        "descricao": dados.get("descricao") or "",
        "imagem_url": dados.get("imagem_url") or (imagens[0] if imagens else ""),
        "link_externo": dados.get("link_externo") or "",
        "selo": dados.get("selo") or "",
        "disponivel": disponivel,
        "quantidade": int(dados.get("quantidade") or 0),
        "sob_encomenda": bool(dados.get("sob_encomenda")),
    }


def produto_url(produto: dict, *, base_url: str = "") -> str:
    """URL real do produto no site: prioriza o link direto já cadastrado
    (`link_externo`); sem ele, a página padrão de produto (`produto.html`)
    com o ID -- nunca uma URL inventada fora desse padrão."""
    if produto.get("link_externo"):
        return produto["link_externo"]
    base = base_url.rstrip("/") if base_url else ""
    return f"{base}/produto.html?id={produto['id']}"


def buscar_cursos_ativos(conn, *, termo: str = "") -> list[dict]:
    """Cursos ativos: os pagos do catálogo real (`CATALOGO_CURSOS_PAGOS`,
    mesma fonte de `backend.course_routes`) mais as categorias com material
    gratuito publicado -- nunca um curso inventado."""
    from backend.course_routes import CATALOGO_CURSOS_PAGOS, garantir_tabela_cursos

    cursos = [
        {"slug": slug, "titulo": info["titulo"], "preco": info["preco"], "tipo": "pago"}
        for slug, info in CATALOGO_CURSOS_PAGOS.items()
    ]

    garantir_tabela_cursos(conn)
    categorias_gratuitas = conn.execute(
        "SELECT DISTINCT categoria FROM cursos_materiais WHERE categoria NOT IN "
        f"({','.join('?' * len(CATALOGO_CURSOS_PAGOS)) or 'NULL'})",
        tuple(CATALOGO_CURSOS_PAGOS.keys()),
    ).fetchall()
    for linha in categorias_gratuitas:
        categoria = linha["categoria"]
        if categoria:
            cursos.append({"slug": categoria, "titulo": categoria, "preco": 0.0, "tipo": "gratuito"})

    if termo.strip():
        termo_lower = termo.strip().lower()
        cursos = [curso for curso in cursos if termo_lower in curso["titulo"].lower()]
    return cursos


def curso_url(curso: dict, *, base_url: str = "") -> str:
    from urllib.parse import quote

    base = base_url.rstrip("/") if base_url else ""
    return f"{base}/escola-curso.html?curso={quote(str(curso['slug']), safe='')}"
