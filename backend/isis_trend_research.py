"""Camada desacoplada de pesquisa de tendências (Isis 2.0 — Fase 3).

Combina provedores independentes de `TrendResearchProvider`
(`backend.isis_ai_providers`). Nesta fase só o provedor interno (histórico
de vendas/buscas do próprio site) está implementado; Google Trends e
outras tendências públicas ficam como integrações futuras, encaixáveis sem
alterar `backend.isis_content_scoring` nem `backend.isis_content_studio` --
ambos consomem apenas a lista combinada de `PesquisaTendencias.pesquisar`.

Nunca faz scraping (nenhuma requisição HTTP a terceiros nesta fase) e trata
qualquer fonte externa como não confiável até validação: cada item
retornado carrega `confiavel`, e o chamador nunca deve usar um dado
`confiavel=False` para decidir preço, estoque ou existência de produto --
só para sinal de popularidade/sazonalidade, com peso limitado.

Todo método aqui aceita um `conn` opcional (uma conexão já aberta por
`backend.database.conectar`) e o reaproveita em vez de abrir uma conexão
própria -- essencial para ser chamado de dentro de uma transação já em
andamento (como o orquestrador diário em `backend.isis_content_studio`),
onde abrir uma segunda conexão para escrita se travaria esperando o lock
da primeira."""
from __future__ import annotations

from datetime import datetime, timedelta

from backend.database import conectar
from backend.isis_ai_providers import TrendResearchProvider


class HistoricoInternoTrendProvider(TrendResearchProvider):
    """Tendência interna: frequência de vendas por categoria nos últimos 30
    dias. Fonte primária (nosso próprio banco) -- por isso `confiavel=True`."""

    nome = "historico_interno"
    confiavel = True

    def pesquisar(self, *, categorias: list[str] | None = None, conn=None) -> list[dict]:
        desde = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
        sql = """
            SELECT p.categoria AS categoria, COUNT(*) AS vendas
            FROM vendas_itens vi
            JOIN produtos p ON p.codigo_p = vi.codigo_p
            JOIN vendas v ON v.id = vi.venda_id
            WHERE COALESCE(v.data_iso, '') >= ?
            GROUP BY p.categoria
            ORDER BY vendas DESC
        """
        if conn is not None:
            linhas = conn.execute(sql, (desde,)).fetchall()
        else:
            with conectar() as conexao_propria:
                linhas = conexao_propria.execute(sql, (desde,)).fetchall()
        resultado = [
            {"categoria": (linha["categoria"] or "").strip(), "peso": int(linha["vendas"] or 0), "fonte": self.nome, "confiavel": True}
            for linha in linhas
            if (linha["categoria"] or "").strip()
        ]
        if categorias:
            categorias_lower = {c.lower() for c in categorias}
            resultado = [item for item in resultado if item["categoria"].lower() in categorias_lower]
        return resultado


class SemFontesExternasTrendProvider(TrendResearchProvider):
    """Placeholder explícito para Google Trends / tendências públicas.

    Não faz nenhuma requisição de rede -- existe só para documentar o ponto
    de extensão e devolver uma lista vazia de forma previsível enquanto a
    integração real não é implementada (respeitando termos de uso de cada
    fonte, o que exige revisão caso a caso antes de ligar)."""

    nome = "externo_nao_configurado"
    confiavel = False

    def pesquisar(self, *, categorias: list[str] | None = None, conn=None) -> list[dict]:
        return []


class PesquisaTendencias:
    """Combina os provedores disponíveis. Uso: `PesquisaTendencias().pesquisar()`."""

    def __init__(self, provedores: list[TrendResearchProvider] | None = None):
        self.provedores = provedores if provedores is not None else [
            HistoricoInternoTrendProvider(),
            SemFontesExternasTrendProvider(),
        ]

    def pesquisar(self, *, categorias: list[str] | None = None, conn=None) -> list[dict]:
        combinado: list[dict] = []
        for provedor in self.provedores:
            try:
                combinado.extend(provedor.pesquisar(categorias=categorias, conn=conn))
            except Exception:
                # Uma fonte de tendência instável nunca deve interromper a
                # geração diária -- ela é só um sinal auxiliar de pontuação.
                continue
        return combinado

    def pesos_por_categoria(self, *, conn=None) -> dict[str, float]:
        """Pré-calcula o peso normalizado (0..1) de todas as categorias de
        uma vez, evitando repetir a consulta por produto."""
        itens_confiaveis = [item for item in self.pesquisar(conn=conn) if item.get("confiavel")]
        maior = max((item.get("peso", 0) for item in itens_confiaveis), default=0)
        if maior <= 0:
            return {}
        pesos: dict[str, float] = {}
        for item in itens_confiaveis:
            categoria = item.get("categoria", "").lower()
            pesos[categoria] = pesos.get(categoria, 0) + item.get("peso", 0)
        return {categoria: min(1.0, peso / maior) for categoria, peso in pesos.items()}

    def peso_por_categoria(self, categoria: str, *, conn=None) -> float:
        return self.pesos_por_categoria(conn=conn).get((categoria or "").lower(), 0.0)
