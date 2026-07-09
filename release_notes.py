RELEASE_VERSION = "1.0.516"
RELEASE_TITLE = "Compatibilidade completa dos imports do caixa"
RELEASE_NOTES = "Realiza correcao ampla no servico de caixa para incluir todas as funcoes importadas pelo app principal relacionadas a caixa e contas a pagar."
RELEASE_CHANGES = [
    "Adiciona listar_contas em services.caixa_service.",
    "Mantem salvar_conta, obter_conta, marcar_conta_paga e excluir_conta no mesmo servico.",
    "Evita erro cannot import name listar_contas ao abrir o Launcher.",
    "Mantem compatibilidade com a tela de contas a pagar do app principal.",
    "Mantem as correcoes anteriores do Launcher e do pagamento misto com taxas.",
]
