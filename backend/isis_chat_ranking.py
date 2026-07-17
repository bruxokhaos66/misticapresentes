"""Camadas 5 e 6 — busca no catálogo + ranqueamento explicável.

Pontuação simples e auditável (soma de fatores, cada um documentado),
nunca uma pontuação "mágica" de um modelo de IA. O score nunca é exposto
ao cliente -- só o `motivo` textual, construído a partir dos mesmos
fatores.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ProdutoRankeado:
    produto: dict
    score: float
    fatores: dict = field(default_factory=dict)
    motivo: str = ""


def _correspondencia_texto(campo: str, termos: list[str]) -> float:
    campo = (campo or "").lower()
    if not campo or not termos:
        return 0.0
    acertos = sum(1 for termo in termos if termo and termo in campo)
    return acertos / max(1, len(termos))


def pontuar_produto(produto: dict, *, termos: list[str], aroma: str | None, finalidade: str | None,
                     preco_min: float | None, preco_max: float | None) -> ProdutoRankeado:
    fatores: dict[str, float] = {}

    fatores["correspondencia_nome"] = _correspondencia_texto(produto.get("nome", ""), termos) * 3.0
    fatores["correspondencia_categoria"] = _correspondencia_texto(produto.get("categoria", ""), termos) * 2.0
    fatores["correspondencia_descricao"] = _correspondencia_texto(produto.get("descricao", ""), termos) * 1.0

    if aroma:
        texto_produto = f"{produto.get('nome', '')} {produto.get('descricao', '')} {produto.get('categoria', '')}".lower()
        fatores["aroma"] = 2.5 if aroma in texto_produto else 0.0
    if finalidade:
        texto_produto = f"{produto.get('nome', '')} {produto.get('descricao', '')} {produto.get('categoria', '')}".lower()
        fatores["finalidade"] = 2.0 if finalidade in texto_produto else 0.0

    preco = float(produto.get("preco") or 0)
    dentro_da_faixa = True
    if preco_min is not None and preco < preco_min:
        dentro_da_faixa = False
    if preco_max is not None and preco > preco_max:
        dentro_da_faixa = False
    fatores["faixa_preco"] = 1.5 if dentro_da_faixa else -3.0

    fatores["produto_ativo"] = 1.0  # só produtos ativos chegam até aqui (fonte de verdade)
    fatores["produto_com_imagem"] = 0.5 if produto.get("imagem_url") else 0.0
    fatores["disponibilidade"] = 1.0 if produto.get("disponivel") else -1.0
    fatores["selo_promocao_real"] = 0.5 if produto.get("selo") else 0.0

    score = sum(fatores.values())
    motivo = _construir_motivo(produto, fatores, aroma=aroma, finalidade=finalidade)
    return ProdutoRankeado(produto=produto, score=score, fatores=fatores, motivo=motivo)


def _construir_motivo(produto: dict, fatores: dict, *, aroma: str | None, finalidade: str | None) -> str:
    partes = []
    if aroma and fatores.get("aroma", 0) > 0:
        partes.append(f"aroma de {aroma}")
    if finalidade and fatores.get("finalidade", 0) > 0:
        partes.append(f"indicado para {finalidade}")
    if fatores.get("correspondencia_categoria", 0) > 0 and produto.get("categoria"):
        partes.append(f"categoria {produto['categoria']}")
    if not produto.get("disponivel"):
        partes.append("disponibilidade a confirmar")
    if not partes:
        partes.append("corresponde à sua busca no catálogo")
    return "; ".join(partes).capitalize()


def _diversidade_ok(escolhidos: list[ProdutoRankeado], candidato: ProdutoRankeado) -> bool:
    """Evita recomendar vários produtos praticamente iguais: bloqueia um
    segundo item da mesma categoria com nome muito parecido (mesmas 2
    primeiras palavras) já presente na lista."""
    nome_candidato = candidato.produto.get("nome", "").lower().split()[:2]
    categoria_candidato = candidato.produto.get("categoria", "")
    for escolhido in escolhidos:
        nome_escolhido = escolhido.produto.get("nome", "").lower().split()[:2]
        if categoria_candidato == escolhido.produto.get("categoria", "") and nome_candidato == nome_escolhido:
            return False
    return True


def rankear_produtos(produtos: list[dict], *, termo_busca: str = "", aroma: str | None = None,
                      finalidade: str | None = None, preco_min: float | None = None,
                      preco_max: float | None = None, limite: int = 3) -> list[ProdutoRankeado]:
    termos = [t for t in (termo_busca or "").lower().split() if len(t) > 2]
    exige_relevancia_textual = bool(termos or aroma or finalidade)

    ranqueados = [
        pontuar_produto(produto, termos=termos, aroma=aroma, finalidade=finalidade, preco_min=preco_min, preco_max=preco_max)
        for produto in produtos
    ]
    ranqueados.sort(key=lambda item: item.score, reverse=True)

    escolhidos: list[ProdutoRankeado] = []
    for candidato in ranqueados:
        if candidato.score <= 0:
            continue
        # Sem nenhum sinal textual/aroma/finalidade real, um produto não
        # pode ser recomendado só pelos fatores de base (ativo, com
        # imagem, disponível) -- isso evitaria "inventar" resultado para
        # uma busca sem nenhuma correspondência no catálogo.
        if exige_relevancia_textual:
            relevancia = (
                candidato.fatores.get("correspondencia_nome", 0)
                + candidato.fatores.get("correspondencia_categoria", 0)
                + candidato.fatores.get("correspondencia_descricao", 0)
                + candidato.fatores.get("aroma", 0)
                + candidato.fatores.get("finalidade", 0)
            )
            if relevancia <= 0:
                continue
        if not _diversidade_ok(escolhidos, candidato):
            continue
        escolhidos.append(candidato)
        if len(escolhidos) >= limite:
            break
    return escolhidos


def _centavos(valor: float) -> int:
    """Converte para centavos com arredondamento bancário-simples (padrão
    `round`), evitando que a soma acumulada em float (ex.: 19.9 + 25.1
    pode chegar a 44.99999999999999 em ponto flutuante) exclua por engano
    um item que deveria caber exatamente no orçamento, ou aceite por
    engano um item que estoura o orçamento por uma fração de centavo."""
    return round((valor or 0) * 100)


def montar_kit(produtos: list[dict], *, orcamento_max: float, limite_itens: int = 4) -> dict | None:
    """Kit sugerido: composição temporária de produtos ativos que respeita
    o orçamento informado, sem exceder, sem inventar desconto -- só a soma
    real dos preços. Não cria produto nem pedido."""
    orcamento_centavos = _centavos(orcamento_max)
    disponiveis = sorted((p for p in produtos if p.get("disponivel")), key=lambda p: p.get("preco") or 0)
    escolhidos: list[dict] = []
    total_centavos = 0
    for produto in disponiveis:
        preco_centavos = _centavos(produto.get("preco") or 0)
        if preco_centavos <= 0:
            continue
        if total_centavos + preco_centavos > orcamento_centavos:
            continue
        categorias_no_kit = {p.get("categoria") for p in escolhidos}
        if produto.get("categoria") in categorias_no_kit:
            continue
        escolhidos.append(produto)
        total_centavos += preco_centavos
        if len(escolhidos) >= limite_itens:
            break
    if not escolhidos:
        return None
    return {"itens": escolhidos, "valor_total": total_centavos / 100, "orcamento_max": orcamento_max}


def comparar_produtos(produtos: list[dict]) -> dict:
    """Comparação objetiva: só campos cadastrados, sem alegação médica ou
    terapêutica fora do que já está na descrição do produto."""
    campos = []
    for produto in produtos:
        campos.append(
            {
                "id": produto["id"],
                "nome": produto.get("nome"),
                "categoria": produto.get("categoria"),
                "preco": produto.get("preco"),
                "descricao": produto.get("descricao"),
                "disponivel": produto.get("disponivel"),
            }
        )
    return {"itens": campos}
