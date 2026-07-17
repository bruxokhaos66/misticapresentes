"""Pontuação de produtos para o "Produto do dia" (Isis 2.0 — Fase 3).

Função pura (sem I/O) para ser fácil de testar isoladamente: recebe os
produtos e sinais já carregados e devolve uma lista ordenada com a
pontuação e a justificativa de cada um. Quem chama (`backend.isis_content_studio`)
é responsável por carregar os sinais do banco e da camada de tendências
(`backend.isis_trend_research`).

Regras de exclusão (nunca contornáveis por pontuação alta):
- produto inativo (`ativo == 0`);
- produto oculto para a Isis (`isis_oculto == 1`);
- produto sem estoque, a menos que `permitir_sem_estoque=True` seja passado
  explicitamente pelo chamador (regra explícita, nunca o padrão);
- preço/desconto nunca são inventados aqui -- a função só lê
  `produto["preco"]`/`produto["desconto"]`; se ausentes, ficam ausentes no
  resultado (o gerador de legenda não deve supor um valor).

Sinais aceitos (todos opcionais, tratados como 0 quando ausentes -- a
integração real de views/favoritos/carrinho é um ponto de extensão futuro
da camada de analytics, fora do escopo desta fase):
`vendas_recentes`, `visualizacoes`, `favoritos`, `carrinhos`,
`campanhas_anteriores` (contagem), `dias_desde_ultima_divulgacao`,
`tendencia_categoria` (0..1, ver `PesquisaTendencias.peso_por_categoria`).
"""
from __future__ import annotations

from dataclasses import dataclass, field

PESOS = {
    "estoque": 0.10,
    "vendas_recentes": 0.20,
    "visualizacoes": 0.10,
    "favoritos": 0.10,
    "carrinhos": 0.10,
    "sazonalidade": 0.10,
    "campanhas_anteriores": 0.05,
    "rotacao": 0.15,  # tempo desde a última divulgação (favorece rotação)
    "tendencia_nicho": 0.05,
    "margem": 0.03,  # peso deliberadamente limitado
    "produto_novo": 0.02,
}

DIAS_ROTACAO_MAXIMA = 30
DIAS_PRODUTO_NOVO = 21


@dataclass(frozen=True)
class ProdutoPontuado:
    produto: dict
    score: float
    motivos: list[str] = field(default_factory=list)


def _normalizar(valor: float, maximo: float) -> float:
    if maximo <= 0:
        return 0.0
    return max(0.0, min(1.0, valor / maximo))


def elegivel(produto: dict, *, permitir_sem_estoque: bool = False) -> tuple[bool, str | None]:
    if not int(produto.get("ativo", 1) or 0):
        return False, "produto inativo"
    if int(produto.get("isis_oculto", 0) or 0):
        return False, "produto oculto para divulgação automática"
    estoque = produto.get("quantidade")
    if not permitir_sem_estoque and (estoque is None or int(estoque) <= 0):
        return False, "produto sem estoque"
    return True, None


def pontuar_produto(produto: dict, sinais: dict, *, maximos: dict) -> ProdutoPontuado:
    motivos: list[str] = []
    total = 0.0

    estoque_score = _normalizar(float(produto.get("quantidade") or 0), maximos.get("quantidade", 1))
    total += PESOS["estoque"] * estoque_score
    if estoque_score > 0.5:
        motivos.append("bom nível de estoque")

    vendas_score = _normalizar(float(sinais.get("vendas_recentes") or 0), maximos.get("vendas_recentes", 1))
    total += PESOS["vendas_recentes"] * vendas_score
    if vendas_score > 0:
        motivos.append("boas vendas recentes")

    vis_score = _normalizar(float(sinais.get("visualizacoes") or 0), maximos.get("visualizacoes", 1))
    total += PESOS["visualizacoes"] * vis_score

    fav_score = _normalizar(float(sinais.get("favoritos") or 0), maximos.get("favoritos", 1))
    total += PESOS["favoritos"] * fav_score
    if fav_score > 0.3:
        motivos.append("muitos favoritos")

    carrinho_score = _normalizar(float(sinais.get("carrinhos") or 0), maximos.get("carrinhos", 1))
    total += PESOS["carrinhos"] * carrinho_score
    if carrinho_score > 0.3:
        motivos.append("presente em vários carrinhos")

    sazonalidade_score = max(0.0, min(1.0, float(sinais.get("tendencia_categoria") or 0.0)))
    total += PESOS["sazonalidade"] * sazonalidade_score
    total += PESOS["tendencia_nicho"] * sazonalidade_score
    if sazonalidade_score > 0.4:
        motivos.append("categoria em alta")

    campanhas_score = _normalizar(float(sinais.get("campanhas_anteriores") or 0), maximos.get("campanhas_anteriores", 1))
    total += PESOS["campanhas_anteriores"] * campanhas_score

    dias_desde = sinais.get("dias_desde_ultima_divulgacao")
    if dias_desde is None:
        rotacao_score = 1.0
        motivos.append("nunca divulgado pela Isis")
    else:
        rotacao_score = _normalizar(float(dias_desde), DIAS_ROTACAO_MAXIMA)
        if dias_desde >= DIAS_ROTACAO_MAXIMA:
            motivos.append("não divulgado há mais de 30 dias")
    total += PESOS["rotacao"] * rotacao_score

    dias_cadastro = sinais.get("dias_desde_cadastro")
    if dias_cadastro is not None and dias_cadastro <= DIAS_PRODUTO_NOVO:
        total += PESOS["produto_novo"]
        motivos.append("produto novo no catálogo")

    margem = sinais.get("margem_percentual")
    if margem is not None:
        margem_score = _normalizar(float(margem), maximos.get("margem_percentual", 1))
        total += PESOS["margem"] * margem_score

    if not motivos:
        motivos.append("selecionado por rotação do catálogo")

    return ProdutoPontuado(produto=produto, score=round(total, 6), motivos=motivos)


def selecionar_produto_do_dia(
    produtos: list[dict],
    sinais_por_produto: dict[int, dict],
    *,
    excluir_ids: set[int] | None = None,
    permitir_sem_estoque: bool = False,
) -> ProdutoPontuado | None:
    """Retorna o produto elegível com maior pontuação, ou None se nenhum
    produto do catálogo for elegível hoje."""
    excluir_ids = excluir_ids or set()
    candidatos = []
    for produto in produtos:
        produto_id = produto.get("id")
        if produto_id in excluir_ids:
            continue
        pode, _motivo_exclusao = elegivel(produto, permitir_sem_estoque=permitir_sem_estoque)
        if not pode:
            continue
        candidatos.append(produto)

    if not candidatos:
        return None

    maximos = {
        "quantidade": max((float(p.get("quantidade") or 0) for p in candidatos), default=1) or 1,
        "vendas_recentes": max((float(sinais_por_produto.get(p.get("id"), {}).get("vendas_recentes") or 0) for p in candidatos), default=1) or 1,
        "visualizacoes": max((float(sinais_por_produto.get(p.get("id"), {}).get("visualizacoes") or 0) for p in candidatos), default=1) or 1,
        "favoritos": max((float(sinais_por_produto.get(p.get("id"), {}).get("favoritos") or 0) for p in candidatos), default=1) or 1,
        "carrinhos": max((float(sinais_por_produto.get(p.get("id"), {}).get("carrinhos") or 0) for p in candidatos), default=1) or 1,
        "campanhas_anteriores": max((float(sinais_por_produto.get(p.get("id"), {}).get("campanhas_anteriores") or 0) for p in candidatos), default=1) or 1,
        "margem_percentual": max((float(sinais_por_produto.get(p.get("id"), {}).get("margem_percentual") or 0) for p in candidatos), default=1) or 1,
    }

    pontuados = [
        pontuar_produto(produto, sinais_por_produto.get(produto.get("id"), {}), maximos=maximos)
        for produto in candidatos
    ]
    pontuados.sort(key=lambda item: item.score, reverse=True)
    return pontuados[0]
