from database import query_db
from reports.estoque_report import valoracao_estoque
from reports.financeiro_report import dre_periodo
from reports.vendas_report import lucro_liquido_periodo, ranking_clientes, vendas_por_filtro

try:
    from reports.produtos_vendidos_report import produtos_mais_vendidos as _produtos_mais_vendidos_modulo
except Exception:
    _produtos_mais_vendidos_modulo = None


def _produtos_mais_vendidos_fallback(limite=15):
    return query_db(
        """
        SELECT vi.codigo_p, vi.nome_p, SUM(vi.quantidade), SUM(vi.valor_total)
        FROM vendas_itens vi
        JOIN vendas v ON vi.venda_id = v.id
        WHERE COALESCE(v.status,'Concluido') != 'Cancelado'
        GROUP BY vi.codigo_p, vi.nome_p
        ORDER BY SUM(vi.quantidade) DESC
        LIMIT ?
        """,
        (int(limite),),
    )


def relatorio_vendas_periodo(filtro):
    return vendas_por_filtro(filtro)


def relatorio_lucro_liquido(mes, ano):
    return lucro_liquido_periodo(mes, ano)


def relatorio_valoracao_estoque():
    return valoracao_estoque()


def relatorio_produtos_mais_vendidos(limite=15):
    if _produtos_mais_vendidos_modulo:
        return _produtos_mais_vendidos_modulo(limite)
    return _produtos_mais_vendidos_fallback(limite)


def relatorio_ranking_clientes(limite=10):
    return ranking_clientes(limite)


def calcular_dre_periodo(mes, ano):
    return dre_periodo(mes, ano)
