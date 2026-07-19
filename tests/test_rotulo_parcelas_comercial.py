"""Regressões da apresentação comercial de parcelas na PR #371."""

from backend.pedido_comercial import rotulo_parcelas
from tests.test_pedido_unificado import (
    HEADERS,
    buscar_notificacoes,
    client,
    criar_pedido_publico,
    pagar_cartao,
    resultado_mp,
)


def test_rotulo_parcelas_padronizado():
    assert rotulo_parcelas(1) == "À vista"
    assert rotulo_parcelas(2) == "2x"
    assert rotulo_parcelas(6) == "6x"


def test_retorno_imediato_cartao_a_vista_nao_grava_1x():
    pedido = criar_pedido_publico(81.0)
    resultado = resultado_mp(
        pedido,
        payment_type_id="credit_card",
        payment_method_id="visa",
        installments=1,
    )

    resposta = pagar_cartao(pedido, resultado, installments=1)
    assert resposta.status_code == 200, resposta.text

    detalhe = client.get(f"/api/pedidos/{pedido['id']}", headers=HEADERS).json()
    assert detalhe["forma_pagamento"] == "Crédito · Visa, À vista"
    assert "1x" not in detalhe["forma_pagamento"]

    notificacao = next(p for p in buscar_notificacoes() if p["id"] == pedido["id"])
    assert notificacao["forma_pagamento"] == "Crédito · Visa, À vista"
    assert "1x" not in notificacao["forma_pagamento"]


def test_retorno_imediato_cartao_parcelado_mantem_numero_de_parcelas():
    pedido = criar_pedido_publico(240.0)
    resultado = resultado_mp(
        pedido,
        payment_type_id="credit_card",
        payment_method_id="visa",
        installments=6,
    )

    resposta = pagar_cartao(pedido, resultado, installments=6)
    assert resposta.status_code == 200, resposta.text

    detalhe = client.get(f"/api/pedidos/{pedido['id']}", headers=HEADERS).json()
    assert detalhe["forma_pagamento"] == "Crédito · Visa, 6x"
    assert detalhe["parcelas"] == 6


def test_webhook_cartao_a_vista_usa_mesmo_rotulo_do_retorno_imediato():
    from tests.test_mercadopago_webhook import enviar_webhook

    pedido = criar_pedido_publico(92.0)
    resultado = resultado_mp(
        pedido,
        payment_type_id="debit_card",
        payment_method_id="master",
        installments=1,
    )

    resposta = enviar_webhook(resultado.id, resultado=resultado)
    assert resposta.status_code == 200, resposta.text

    detalhe = client.get(f"/api/pedidos/{pedido['id']}", headers=HEADERS).json()
    assert detalhe["forma_pagamento"] == "Débito · Mastercard, À vista"
    assert detalhe["parcelas"] == 1
    assert "1x" not in detalhe["forma_pagamento"]
