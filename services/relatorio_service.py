from reports.estoque_report import valoracao_estoque
from reports.financeiro_report import dre_periodo
from reports.produtos_vendidos_report import produtos_mais_vendidos
from reports.vendas_report import lucro_liquido_periodo, ranking_clientes, vendas_por_filtro


def relatorio_vendas_periodo(filtro):
    return vendas_por_filtro(filtro)


def relatorio_lucro_liquido(mes, ano):
    return lucro_liquido_periodo(mes, ano)


def relatorio_valoracao_estoque():
    return valoracao_estoque()


def relatorio_produtos_mais_vendidos(limite=15):
    return produtos_mais_vendidos(limite)


def relatorio_ranking_clientes(limite=10):
    return ranking_clientes(limite)


def calcular_dre_periodo(mes, ano):
    return dre_periodo(mes, ano)
