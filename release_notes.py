RELEASE_VERSION = "1.0.511"
RELEASE_TITLE = "Correcao de taxas no pagamento misto"
RELEASE_NOTES = "Corrige a soma das taxas de Debito e Credito no pagamento misto e melhora a leitura dos valores digitados com ponto e virgula."
RELEASE_CHANGES = [
    "Taxa de Debito e Credito agora soma corretamente no total do pagamento misto.",
    "Fluxo do caixa registra a forma normalizada: Debito, Credito 1x, Credito 2x e Credito 3x.",
    "Fechamento de caixa soma formas com ou sem acento.",
    "Melhora a leitura de valores como 80,00, 80.00, 1.000,50 e 1000,50.",
    "Resumo do pagamento misto passa a destacar taxa e total final.",
]
