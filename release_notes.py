RELEASE_VERSION = "1.0.513"
RELEASE_TITLE = "Correcao de compatibilidade do caixa"
RELEASE_NOTES = "Corrige erro ao abrir o Launcher causado por importacao antiga da funcao caixa_abertos_count no servico de caixa."
RELEASE_CHANGES = [
    "Adiciona a funcao caixa_abertos_count em services.caixa_service.",
    "Mantem compatibilidade com modulos antigos da Isis e servicos internos.",
    "Evita erro cannot import name caixa_abertos_count ao abrir o Launcher.",
    "Mantem as correcoes anteriores do pagamento misto com taxas.",
]
