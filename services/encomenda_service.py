from repositories import encomendas


def criar_encomenda(cliente, produto, quantidade=1, origem="", custo_estimado=0.0, preco_sugerido=0.0, margem=0.0, observacao=""):
    encomendas.criar(cliente, produto, quantidade, origem, custo_estimado, preco_sugerido, margem, observacao)
    return "Encomenda salva como pendente."


def listar_pendentes():
    return encomendas.listar("Pendente", 50)
