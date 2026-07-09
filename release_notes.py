RELEASE_VERSION = "1.0.512"
RELEASE_TITLE = "Validacao final do pagamento misto com taxas"
RELEASE_NOTES = "O pagamento misto agora exige que o valor digitado represente o total que o cliente realmente paga, incluindo as taxas de Debito e Credito."
RELEASE_CHANGES = [
    "Pagamento misto valida contra o total final com taxas.",
    "Se a compra for R$ 8,00 no Debito, o cliente precisa pagar R$ 9,50.",
    "Se informar apenas R$ 8,00 no Debito, o sistema bloqueia e avisa que falta R$ 1,50.",
    "Botao Completar Restante agora inclui a taxa quando a forma escolhida for Debito ou Credito.",
    "Valores digitados no misto representam o valor pago pelo cliente naquela forma.",
]
