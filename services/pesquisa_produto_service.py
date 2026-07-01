from isis.product_research import pesquisar_produto
from repositories import pesquisas_online


def pesquisar(consulta, usuario="Sistema", salvar=False):
    dados = pesquisar_produto(consulta)
    if salvar:
        pesquisas_online.salvar(consulta, dados.get("resultados", []), usuario, 1)
    return dados
