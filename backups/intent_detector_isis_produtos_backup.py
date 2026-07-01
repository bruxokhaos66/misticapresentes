import re


def normalizar(texto):
    mapa = str.maketrans("áàãâäéèêëíìîïóòõôöúùûüçÁÀÃÂÄÉÈÊËÍÌÎÏÓÒÕÔÖÚÙÛÜÇ", "aaaaaeeeeiiiiooooouuuucAAAAAEEEEIIIIOOOOOUUUUC")
    return str(texto or "").translate(mapa).lower().strip()


def detectar(texto):
    p = normalizar(texto)
    if p in ["sim", "confirmo", "pode confirmar", "confirmar", "pode fazer", "fazer agora"]:
        return {"intent": "confirmacao_sim", "confidence": 1}
    if p in ["nao", "não", "cancelar", "cancela", "deixa quieto"]:
        return {"intent": "confirmacao_nao", "confidence": 1}
    if any(x in p for x in ["pesquisa na", "pesquise na", "buscar online", "shopee", "mercado livre"]):
        return {"intent": "pesquisa_produto", "confidence": 0.9}
    if any(x in p for x in ["cria encomenda", "criar encomenda", "salva essa pesquisa como encomenda", "lista encomendas", "encomendas pendentes"]):
        return {"intent": "encomenda", "confidence": 0.9}
    if any(x in p for x in ["acende a luz", "desliga a luz", "ar condicionado", "ar-condicionado", "musica", "música", "volume"]):
        return {"intent": "automacao", "confidence": 0.9}
    if "calcula preco" in p or "calcular preco" in p or "margem" in p:
        return {"intent": "calculo_margem", "confidence": 0.9}
    if any(x in p for x in ["realiza venda", "fazer venda", "vende ", "venda de "]):
        return {"intent": "venda_texto", "confidence": 0.9}
    if any(x in p for x in ["cadastra", "cadastre", "novo produto"]):
        return {"intent": "cadastro_produto", "confidence": 0.85}
    if any(x in p for x in ["aumenta o estoque", "adiciona estoque", "entrada de estoque", "no estoque"]):
        return {"intent": "entrada_estoque", "confidence": 0.85}
    if any(x in p for x in ["altera o preco", "alterar preco", "muda o preco", "preco para"]):
        return {"intent": "alterar_preco", "confidence": 0.85}
    if any(x in p for x in ["estoque", "produto acabando", "preciso comprar", "produtos parados"]):
        return {"intent": "consulta_estoque", "confidence": 0.8}
    if any(x in p for x in ["quanto vendi", "vendas de hoje", "mostre vendas", "produto mais vendido", "lucro do mes"]):
        return {"intent": "consulta_vendas", "confidence": 0.8}
    if any(x in p for x in ["como esta o caixa", "como está o caixa", "caixa", "saldo"]):
        return {"intent": "consulta_caixa", "confidence": 0.8}
    return {"intent": "conversa", "confidence": 0.2}


def numeros(texto):
    return [float(x.replace(".", "").replace(",", ".")) for x in re.findall(r"\d+[\d\.,]*", texto or "")]
