"""Catálogo Comercial na Central de Atendimento WhatsApp -- busca, seleção e
envio de produtos reais do catálogo (tabela `produtos`, mesma fonte de
backend/product_routes.py e backend/isis_chat_catalog.py). Nunca cria uma
segunda fonte de produtos: todo campo devolvido aqui vem direto do banco,
nada é inventado.

Nenhuma função aqui abre sua própria conexão (mesmo padrão de
backend/atendimento_repository.py): todo caller controla a transação."""
from __future__ import annotations

import ipaddress
import json
import re
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any
from urllib.parse import urlsplit

from backend.isis_chat_catalog import produto_url as _produto_url_base
from backend.product_commercial_rules import garantir_colunas_comerciais
from backend.whatsapp_catalog_flags import (
    atendimento_catalog_allowed_image_hosts,
    atendimento_catalog_limite_estoque_baixo,
)

PAGE_SIZE_PADRAO = 20
PAGE_SIZE_MAXIMO = 60
RECENTES_LIMITE_PADRAO = 10
RECENTES_LIMITE_MAXIMO = 30

ACOES_CATALOGO_VALIDAS = {
    "product_sent",
    "product_batch_sent",
    "product_send_failed",
    "unavailable_product_blocked",
}


def _agora() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _like_termo(busca: str) -> str:
    """Normaliza espaços extras e escapa `%`/`_`/`\\` para evitar wildcard
    abusivo em LIKE (item 5 -- 'evitar wildcard abusivo'). O parâmetro do
    LIKE é sempre passado via bind (?), nunca concatenado na string SQL --
    proteção padrão contra SQL injection."""
    texto = re.sub(r"\s+", " ", str(busca or "")).strip()
    texto = texto.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{texto}%"


def estoque_status(*, quantidade: int, sob_encomenda: bool, ativo: bool) -> str:
    """Normaliza estoque em available/low_stock/unavailable -- nunca expõe a
    quantidade exata (item 6 da especificação)."""
    if not ativo:
        return "unavailable"
    if quantidade <= 0:
        return "available" if sob_encomenda else "unavailable"
    if quantidade <= atendimento_catalog_limite_estoque_baixo():
        return "low_stock"
    return "available"


_PORTAS_HTTPS_PERMITIDAS = {None, 443}


def _host_permitido(host: str, *, hosts_exatos: frozenset[str], sufixos_wildcard: frozenset[str]) -> bool:
    """Comparação sempre por host exato ou por sufixo com fronteira de ponto
    explícita -- nunca `endswith` sem fronteira (isso aceitaria
    'evilmisticaesotericos.com.br' para o sufixo
    'misticaesotericos.com.br') e nunca um wildcard global."""
    if host in hosts_exatos:
        return True
    for sufixo in sufixos_wildcard:
        if host == sufixo or host.endswith("." + sufixo):
            return True
    return False


def validar_url_imagem_catalogo(url: str | None) -> str | None:
    """Função central e única de validação de URL de imagem comercial do
    Catálogo (item 2/3 da correção de segurança) -- usada por
    `produto_linha_publica` (e, por consequência, por toda rota que exibe
    ou envia imagem de produto: busca, recentes, envio único e em lote).
    Nunca duplicar esta regra em outro arquivo.

    Devolve a própria URL quando ela é seguramente utilizável (esquema
    https, sem credenciais embutidas, hostname presente e não literal de
    IP/localhost, porta padrão, host dentro da allowlist) ou `None` quando
    não -- o chamador deve tratar `None` como "sem imagem" (fallback de
    texto), nunca como erro."""
    texto = str(url or "").strip()
    if not texto:
        return None
    if any(ord(ch) < 32 for ch in texto):
        return None

    try:
        partes = urlsplit(texto)
    except ValueError:
        return None

    if partes.scheme.lower() != "https":
        return None
    if partes.username is not None or partes.password is not None:
        return None

    host = partes.hostname
    if not host:
        return None
    host = host.lower().rstrip(".")
    if host == "localhost":
        return None

    try:
        ipaddress.ip_address(host)
    except ValueError:
        pass
    else:
        # Nunca aceita host literal de IP (cobre 127.0.0.0/8, ::1, IPs
        # privados/link-local/reservados de uma vez -- nenhum host real da
        # allowlist é um endereço IP).
        return None

    try:
        porta = partes.port
    except ValueError:
        return None
    if porta not in _PORTAS_HTTPS_PERMITIDAS:
        return None

    hosts_exatos, sufixos_wildcard = atendimento_catalog_allowed_image_hosts()
    if not _host_permitido(host, hosts_exatos=hosts_exatos, sufixos_wildcard=sufixos_wildcard):
        return None

    return texto


def _produto_url_segura(produto_row: dict, *, base_url: str) -> str:
    """URL pública do produto -- sempre gerada pelo backend a partir do
    padrão real do site (produto.html?id=... ou link_externo já cadastrado),
    nunca aceita de uma requisição do navegador (item 7). Reaproveita
    backend.isis_chat_catalog.produto_url, a mesma função já usada pelo Chat
    da Isis, para nunca ter uma segunda implementação desse padrão."""
    return _produto_url_base(produto_row, base_url=base_url)


def produto_linha_publica(row: dict, *, base_url: str) -> dict:
    """Converte uma linha da tabela `produtos` no formato público devolvido
    ao atendente -- só os campos necessários (item 6): nunca custo, lucro,
    fornecedor ou campos administrativos."""
    try:
        imagens = json.loads(row.get("imagens_json") or "[]")
    except Exception:
        imagens = []
    ativo = bool(row.get("ativo") if row.get("ativo") is not None else 1)
    quantidade = int(row.get("quantidade") or 0)
    sob_encomenda = bool(row.get("sob_encomenda"))
    imagem_bruta = row.get("imagem_url") or (imagens[0] if imagens else "") or ""
    imagem_validada = validar_url_imagem_catalogo(imagem_bruta)
    # Produto com imagem cadastrada mas host fora da allowlist: nunca
    # bloqueia o produto, só faz o card/mensagem cair no fallback de texto
    # (imagem_url vazia) -- ver rota de envio, que decide "com/sem imagem"
    # só olhando este campo, nunca reimplementando a checagem de host.
    imagem_bloqueada_por_host = bool(imagem_bruta) and imagem_validada is None
    produto_para_url = {"id": row["id"], "link_externo": row.get("link_externo") or ""}
    return {
        "id": row["id"],
        "nome": row.get("nome") or "",
        "sku": row.get("codigo_p") or "",
        "categoria": row.get("categoria") or "",
        "marca": row.get("marca") or "",
        "preco": float(row.get("preco") or 0),
        "preco_promocional": (
            float(row["preco_promocional"])
            if row.get("preco_promocional") not in (None, "")
            else None
        ),
        "moeda": "BRL",
        "estoque_status": estoque_status(quantidade=quantidade, sob_encomenda=sob_encomenda, ativo=ativo),
        "imagem_url": imagem_validada or "",
        "imagem_bloqueada_por_host": imagem_bloqueada_por_host,
        "url_publica": _produto_url_segura(produto_para_url, base_url=base_url),
        "ativo": ativo,
        "disponivel": estoque_status(quantidade=quantidade, sob_encomenda=sob_encomenda, ativo=ativo) != "unavailable",
    }


_CAMPOS_CATALOGO = (
    "p.id, p.nome, p.codigo_p, p.categoria, p.marca, p.preco, p.preco_promocional, "
    "p.quantidade, p.sob_encomenda, p.imagem_url, p.imagens_json, p.link_externo, "
    "COALESCE(p.ativo,1) AS ativo"
)


def buscar_produtos_catalogo(
    conn,
    *,
    base_url: str,
    q: str = "",
    categoria: str | None = None,
    marca: str | None = None,
    apenas_ativos: bool = True,
    apenas_em_estoque: bool = False,
    page: int = 1,
    page_size: int = PAGE_SIZE_PADRAO,
) -> tuple[list[dict], int]:
    """Busca paginada, case-insensitive, tolerante a espaços extras --
    ordenação estável: ativos primeiro, com estoque primeiro, depois nome
    (item 4). Nunca faz SELECT * nem consulta por item (uma única query
    paginada, sem N+1 -- item 19)."""
    garantir_colunas_comerciais(conn)

    page = max(1, int(page or 1))
    page_size = max(1, min(int(page_size or PAGE_SIZE_PADRAO), PAGE_SIZE_MAXIMO))

    condicoes: list[str] = []
    parametros: list[Any] = []

    if apenas_ativos:
        condicoes.append("COALESCE(p.ativo,1)=1")

    termo = re.sub(r"\s+", " ", str(q or "")).strip()
    if termo:
        padrao = _like_termo(termo)
        condicoes.append(
            "(p.nome LIKE ? ESCAPE '\\' OR p.codigo_p LIKE ? ESCAPE '\\' OR p.categoria LIKE ? ESCAPE '\\' "
            "OR p.marca LIKE ? ESCAPE '\\' OR p.descricao LIKE ? ESCAPE '\\' OR p.selo LIKE ? ESCAPE '\\')"
        )
        parametros.extend([padrao] * 6)

    if categoria:
        condicoes.append("p.categoria = ?")
        parametros.append(str(categoria).strip())

    if marca:
        condicoes.append("p.marca = ?")
        parametros.append(str(marca).strip())

    if apenas_em_estoque:
        condicoes.append("(p.quantidade > 0 OR COALESCE(p.sob_encomenda,0)=1)")

    where = f"WHERE {' AND '.join(condicoes)}" if condicoes else ""

    total_row = conn.execute(f"SELECT COUNT(*) AS n FROM produtos p {where}", parametros).fetchone()
    total = int(total_row["n"] if total_row else 0)

    offset = (page - 1) * page_size
    linhas = conn.execute(
        f"""
        SELECT {_CAMPOS_CATALOGO}
        FROM produtos p
        {where}
        ORDER BY COALESCE(p.ativo,1) DESC,
                 (p.quantidade > 0 OR COALESCE(p.sob_encomenda,0)=1) DESC,
                 p.nome COLLATE NOCASE ASC
        LIMIT ? OFFSET ?
        """,
        [*parametros, page_size, offset],
    ).fetchall()

    return [produto_linha_publica(dict(row), base_url=base_url) for row in linhas], total


def obter_produto_catalogo(conn, produto_id: int, *, base_url: str) -> dict | None:
    garantir_colunas_comerciais(conn)
    linha = conn.execute(
        f"SELECT {_CAMPOS_CATALOGO} FROM produtos p WHERE p.id=?",
        (produto_id,),
    ).fetchone()
    return produto_linha_publica(dict(linha), base_url=base_url) if linha else None


_MOEDA_FORMATO = {"BRL": "R$"}


def formatar_preco(valor: float, *, moeda: str = "BRL") -> str:
    numero = Decimal(str(valor)).quantize(Decimal("0.01"))
    inteiro, _, centavos = f"{numero:.2f}".partition(".")
    negativo = inteiro.startswith("-")
    if negativo:
        inteiro = inteiro[1:]
    grupos = []
    while len(inteiro) > 3:
        grupos.insert(0, inteiro[-3:])
        inteiro = inteiro[:-3]
    grupos.insert(0, inteiro)
    inteiro_formatado = ".".join(grupos)
    prefixo = _MOEDA_FORMATO.get(moeda, moeda)
    sinal = "-" if negativo else ""
    return f"{sinal}{prefixo} {inteiro_formatado},{centavos}"


_ROTULO_DISPONIBILIDADE = {
    "available": "Disponível",
    "low_stock": "Estoque baixo",
    "unavailable": "Indisponível",
}

_LIMITE_TEXTO_COMERCIAL = 1024  # limite de caption de mídia da Cloud API


def montar_texto_comercial(produto: dict) -> str:
    """Função central que monta o texto comercial de um produto -- nunca
    aceita texto arbitrário do frontend, sempre reconstrói a partir dos
    dados já validados do backend (item 11). Sem HTML, moeda brasileira,
    disponibilidade normalizada, link clicável, tamanho limitado."""
    nome = re.sub(r"\s+", " ", str(produto.get("nome") or "")).strip()[:160]
    preco_valor = produto.get("preco_promocional") if produto.get("preco_promocional") else produto.get("preco")
    preco_formatado = formatar_preco(float(preco_valor or 0))
    disponibilidade = _ROTULO_DISPONIBILIDADE.get(produto.get("estoque_status"), "Indisponível")
    url = produto.get("url_publica") or ""

    linhas = [
        f"✨ *{nome}*",
        "",
        f"💰 {preco_formatado}",
        f"📦 {disponibilidade}",
        "",
        "Conheça o produto:",
        url,
    ]
    texto = "\n".join(linhas)
    return texto[:_LIMITE_TEXTO_COMERCIAL]


@dataclass(frozen=True)
class RegistroEnvioProduto:
    conversation_id: int
    product_id: int
    message_id: int | None
    performed_by_user_id: int | None
    action: str
    price_at_send: float
    status: str
    idempotency_key_hash: str | None


def registrar_envio_produto(conn, registro: RegistroEnvioProduto) -> None:
    """Histórico append-only do Catálogo Comercial -- nunca grava token,
    Authorization, payload bruto da Meta, telefone completo, imagem binária
    ou segredo (item 12). Só ids, ação, preço no momento do envio e status."""
    if registro.action not in ACOES_CATALOGO_VALIDAS:
        raise ValueError(f"Ação de catálogo inválida: {registro.action!r}")
    conn.execute(
        """
        INSERT INTO whatsapp_catalog_sends
            (conversation_id, product_id, message_id, performed_by_user_id, action,
             price_at_send, status, idempotency_key_hash, created_at)
        VALUES (?,?,?,?,?,?,?,?,?)
        """,
        (
            registro.conversation_id,
            registro.product_id,
            registro.message_id,
            registro.performed_by_user_id,
            registro.action,
            registro.price_at_send,
            registro.status,
            registro.idempotency_key_hash,
            _agora(),
        ),
    )


def listar_produtos_recentes(conn, *, usuario_id: int, base_url: str, limite: int = RECENTES_LIMITE_PADRAO) -> list[dict]:
    """Produtos recentemente enviados por este atendente -- derivado do
    histórico de envio (item 13). Preço/estoque sempre revalidados na
    consulta atual (nunca reaproveita o preço antigo do histórico); produtos
    inativos não são oferecidos para reenvio."""
    garantir_colunas_comerciais(conn)
    limite = max(1, min(int(limite or RECENTES_LIMITE_PADRAO), RECENTES_LIMITE_MAXIMO))

    linhas = conn.execute(
        """
        SELECT product_id, MAX(created_at) AS ultimo_envio
        FROM whatsapp_catalog_sends
        WHERE performed_by_user_id = ? AND action IN ('product_sent','product_batch_sent')
        GROUP BY product_id
        ORDER BY ultimo_envio DESC
        LIMIT ?
        """,
        (usuario_id, limite * 2),
    ).fetchall()

    produtos: list[dict] = []
    vistos: set[int] = set()
    for linha in linhas:
        produto_id = int(linha["product_id"])
        if produto_id in vistos:
            continue
        vistos.add(produto_id)
        produto = obter_produto_catalogo(conn, produto_id, base_url=base_url)
        if not produto or not produto["ativo"]:
            continue
        produtos.append(produto)
        if len(produtos) >= limite:
            break
    return produtos
