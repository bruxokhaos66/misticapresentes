RELEASE_VERSION = "1.0.520"
RELEASE_TITLE = "Preparar sistema para producao"
RELEASE_NOTES = "Adiciona uma ferramenta segura na aba Manutencao para limpar dados de teste, criar backup automatico e deixar o sistema pronto para uso real na loja."
RELEASE_CHANGES = [
    "Adiciona services/producao_service.py para limpeza segura de dados de teste.",
    "Aba Manutencao recebe o botao Preparar Sistema para Producao.",
    "Antes de limpar, o sistema cria backup automatico do banco.",
    "A limpeza exige confirmacao digitando CONFIRMAR.",
    "Permite escolher se apaga produtos ficticios ou apenas zera estoque.",
    "Permite apagar clientes e fornecedores de teste.",
    "Limpa vendas, itens de venda, caixa, fluxo, contas, movimentacoes, encomendas e logs.",
    "Preserva configuracoes, Launcher, atualizador e usuario admin.",
    "Gera relatorio em Documentos/Mistica_Relatorios_Manutencao.",
]
