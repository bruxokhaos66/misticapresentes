RELEASE_VERSION = "1.0.503"
RELEASE_TITLE = "Bloqueio de pagamento misto sem fechamento"
RELEASE_NOTES = "A venda mista agora so finaliza quando a soma das formas de pagamento fechar exatamente o valor base da venda."
RELEASE_CHANGES = [
    "Bloqueia venda mista quando falta valor.",
    "Bloqueia venda mista quando passa do valor total.",
    "Mostra aviso informando quanto falta ou quanto passou.",
    "Reforca a validacao antes de abrir a conferencia da venda.",
    "Reforca a validacao no servico antes de gravar no banco.",
]
