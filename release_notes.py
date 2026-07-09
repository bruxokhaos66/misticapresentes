RELEASE_VERSION = "1.0.514"
RELEASE_TITLE = "Correcao de contas a pagar no caixa"
RELEASE_NOTES = "Corrige erro ao abrir o Launcher causado por funcoes antigas de contas a pagar que faltavam no servico de caixa."
RELEASE_CHANGES = [
    "Adiciona a funcao marcar_conta_paga em services.caixa_service.",
    "Adiciona a funcao excluir_conta em services.caixa_service.",
    "Mantem compatibilidade com a tela de contas a pagar do app principal.",
    "Evita erro cannot import name excluir_conta ao abrir o Launcher.",
    "Mantem as correcoes anteriores do pagamento misto com taxas.",
]
