CRITICAL_INTENTS = {"venda_texto", "cadastro_produto", "entrada_estoque", "alterar_preco", "salvar_pesquisa", "criar_encomenda"}
BLOCKED_TERMS = ["senha", "cartao", "cartão", "cvv", "comprar agora", "finalizar compra online"]


def precisa_confirmacao(intent):
    return intent in CRITICAL_INTENTS


def contem_bloqueio(texto):
    p = (texto or "").lower()
    return any(t in p for t in BLOCKED_TERMS)
