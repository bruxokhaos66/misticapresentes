RELEASE_VERSION = "1.0.515"
RELEASE_TITLE = "Correcao do carregamento de modulos do Launcher"
RELEASE_NOTES = "Corrige o Launcher para priorizar os modulos da versao atualizada e nao reutilizar servicos antigos empacotados no executavel."
RELEASE_CHANGES = [
    "Launcher limpa modulos antigos antes de abrir a versao atualizada.",
    "Prioriza services, database, repositories, isis e reports da pasta updates.",
    "Evita abrir services.caixa_service antigo do Temp/_MEI.",
    "Corrige erro persistente cannot import name excluir_conta quando a atualizacao ja possui a funcao.",
    "Mantem as correcoes anteriores de contas a pagar e pagamento misto com taxas.",
]
