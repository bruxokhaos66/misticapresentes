"""Testes do pagamento com cartão de crédito via Mercado Pago
(backend/mercadopago_routes.py), preservando o Pix já existente.

Nunca chama a API real do Mercado Pago: `criar_pagamento_cartao` é sempre
mockado (unittest.mock.patch), como exigido -- nenhum teste automatizado
pode gerar cobrança real.
"""

import importlib
import os
import uuid
from unittest.mock import patch

from fastapi.testclient import TestClient

os.environ.setdefault("MISTICA_SITE_API_KEY", "test-api-key")
os.environ.setdefault("MISTICA_SYNC_KEY", "test-api-key")
os.environ.setdefault("MISTICA_PIX_KEY", "49999999999")
os.environ.setdefault("MERCADO_PAGO_ENABLED", "true")
os.environ.setdefault("MERCADO_PAGO_ACCESS_TOKEN", "TEST-access-token")
os.environ.setdefault("MERCADO_PAGO_PUBLIC_KEY", "TEST-public-key")
os.environ.setdefault("MERCADO_PAGO_WEBHOOK_SECRET", "test-mp-webhook-secret")

main = importlib.import_module("backend.main")
client = TestClient(main.app)
client.__enter__()

TEST_API_KEY = os.environ["MISTICA_SITE_API_KEY"]
HEADERS = {"X-Mistica-Api-Key": TEST_API_KEY}


def ip_unico() -> str:
    return f"203.0.{uuid.uuid4().int % 256}.{uuid.uuid4().int % 256}"


def codigo_unico(prefixo: str) -> str:
    return f"{prefixo}-{uuid.uuid4().hex[:10]}"


def criar_produto(preco: float, quantidade: int = 20) -> dict:
    resposta = client.post(
        "/api/produtos",
        json={"nome": "Produto MP Teste", "codigo_p": codigo_unico("MPC"), "preco": preco, "quantidade": quantidade, "categoria": "Testes"},
        headers=HEADERS,
    )
    assert resposta.status_code == 200, resposta.text
    return resposta.json()


def criar_pedido_publico(preco: float, quantidade: int = 1) -> dict:
    produto = criar_produto(preco, quantidade=quantidade + 10)
    resposta = client.post(
        "/api/checkout/pedidos",
        json={"cliente": "Cliente MP", "telefone": "5599999999999", "itens": [{"produto_id": produto["id"], "quantidade": quantidade}]},
        headers={"X-Forwarded-For": ip_unico()},
    )
    assert resposta.status_code == 200, resposta.text
    return resposta.json()


def resultado_mp(pedido, *, status="approved", status_detail="accredited", payment_id=None, valor=None, installments=1, payment_method_id="visa"):
    from backend.mercadopago_client import ResultadoPagamentoMP

    # Cada pagamento no Mercado Pago tem um id único de verdade; nos testes,
    # um valor fixo faria dois pedidos distintos colidirem na constraint
    # UNIQUE(provedor, provider_payment_id) de tentativas_pagamento.
    if payment_id is None:
        payment_id = f"mp-{uuid.uuid4().hex[:12]}"
    return ResultadoPagamentoMP(
        id=payment_id,
        status=status,
        status_detail=status_detail,
        transaction_amount=valor if valor is not None else pedido["total_final"],
        installments=installments,
        payment_method_id=payment_method_id,
        payment_type_id="credit_card",
        external_reference=str(pedido["id"]),
        currency_id="BRL",
        collector_id="1" if payment_id else None,
    )


def pagar_cartao(pedido, resultado, idempotency_key=None, installments=1, **overrides):
    body = {
        "pedido_id": pedido["id"],
        "txid": pedido["pix_txid"],
        "token": "card_token_" + uuid.uuid4().hex,
        "payment_method_id": "visa",
        "installments": installments,
        "payer": {"email": "cliente@example.com", "documento_numero": "12345678900"},
    }
    body.update(overrides)
    headers = {"Idempotency-Key": idempotency_key or str(uuid.uuid4()), "X-Forwarded-For": ip_unico()}
    with patch("backend.mercadopago_routes.criar_pagamento_cartao", return_value=resultado):
        return client.post("/api/payments/mercadopago/card", json=body, headers=headers)


def test_calculo_servidor_nunca_confia_no_frontend():
    """O schema de entrada não tem campo de valor: o servidor sempre cobra
    pedidos.total_final, recalculado na criação do pedido -- não há forma de
    o cliente informar um valor a pagar."""
    pedido = criar_pedido_publico(199.90)
    resultado = resultado_mp(pedido)
    resposta = pagar_cartao(pedido, resultado)
    assert resposta.status_code == 200, resposta.text
    assert resposta.json()["valor"] == pedido["total_final"] == 199.90


def test_tentativa_adulterar_valor_pelo_frontend_e_ignorada():
    """Mesmo que o corpo da requisição contenha um campo extra 'valor', ele é
    ignorado pela validação Pydantic (campos desconhecidos não afetam o
    schema) -- a cobrança usa sempre pedidos.total_final."""
    pedido = criar_pedido_publico(50.0)
    resultado = resultado_mp(pedido)
    resposta = pagar_cartao(pedido, resultado, valor=1.00)
    assert resposta.status_code == 200, resposta.text
    assert resposta.json()["valor"] == 50.0


def test_pagamento_aprovado_confirma_pedido_e_baixa_estoque_uma_vez():
    pedido = criar_pedido_publico(80.0)
    resultado = resultado_mp(pedido, status="approved")
    resposta = pagar_cartao(pedido, resultado)
    assert resposta.status_code == 200
    assert resposta.json()["status"] == "aprovado"
    detalhe = client.get(f"/api/pedidos/{pedido['id']}", headers=HEADERS).json()
    assert detalhe["status"] == "Pagamento confirmado"
    assert detalhe["estoque_baixado"] == 1


def test_pagamento_pendente_move_para_em_analise_sem_pedir_pagar_de_novo():
    pedido = criar_pedido_publico(60.0)
    resultado = resultado_mp(pedido, status="in_process", status_detail="pending_review_manual", payment_id="mp-pending-1")
    resposta = pagar_cartao(pedido, resultado)
    assert resposta.status_code == 200
    assert resposta.json()["status"] == "pendente"
    detalhe = client.get(f"/api/pedidos/{pedido['id']}", headers=HEADERS).json()
    assert detalhe["status"] == "Pagamento em análise"
    assert detalhe["estoque_baixado"] == 1  # já reservado na criação, não mexe de novo


def test_pagamento_recusado_permite_nova_tentativa_no_mesmo_pedido():
    pedido = criar_pedido_publico(30.0)
    recusado = resultado_mp(pedido, status="rejected", status_detail="cc_rejected_insufficient_amount", payment_id="")
    resposta = pagar_cartao(pedido, recusado)
    assert resposta.status_code == 200
    assert resposta.json()["status"] == "recusado"
    detalhe = client.get(f"/api/pedidos/{pedido['id']}", headers=HEADERS).json()
    assert detalhe["status"] == "Aguardando pagamento"  # nunca cancela, nunca reabre outro pedido

    aprovado = resultado_mp(pedido, status="approved", payment_id="mp-retry-1")
    resposta2 = pagar_cartao(pedido, aprovado)
    assert resposta2.status_code == 200
    assert resposta2.json()["status"] == "aprovado"
    detalhe2 = client.get(f"/api/pedidos/{pedido['id']}", headers=HEADERS).json()
    assert detalhe2["status"] == "Pagamento confirmado"


def test_pagamento_cancelado_nao_confirma_pedido():
    pedido = criar_pedido_publico(40.0)
    resultado = resultado_mp(pedido, status="cancelled", payment_id="mp-cancel-1")
    resposta = pagar_cartao(pedido, resultado)
    assert resposta.status_code == 200
    assert resposta.json()["status"] == "cancelado"
    detalhe = client.get(f"/api/pedidos/{pedido['id']}", headers=HEADERS).json()
    assert detalhe["status"] != "Pagamento confirmado"


def test_idempotencia_clique_duplo_no_mesmo_pedido():
    pedido = criar_pedido_publico(120.0)
    resultado = resultado_mp(pedido, status="approved", payment_id="mp-double-click")
    idem = str(uuid.uuid4())
    body = {
        "pedido_id": pedido["id"],
        "txid": pedido["pix_txid"],
        "token": "card_token_" + uuid.uuid4().hex,
        "payment_method_id": "visa",
        "installments": 1,
        "payer": {"email": "cliente@example.com", "documento_numero": "12345678900"},
    }
    with patch("backend.mercadopago_routes.criar_pagamento_cartao", return_value=resultado) as mock_criar:
        r1 = client.post("/api/payments/mercadopago/card", json=body, headers={"Idempotency-Key": idem})
        r2 = client.post("/api/payments/mercadopago/card", json=body, headers={"Idempotency-Key": idem})
    assert r1.status_code == 200 and r2.status_code == 200
    assert r1.json() == r2.json()
    assert mock_criar.call_count == 1, "clique duplo não deve gerar uma segunda cobrança no Mercado Pago"


def test_idempotency_key_ausente_e_rejeitada():
    pedido = criar_pedido_publico(20.0)
    resultado = resultado_mp(pedido)
    with patch("backend.mercadopago_routes.criar_pagamento_cartao", return_value=resultado):
        resposta = client.post(
            "/api/payments/mercadopago/card",
            json={
                "pedido_id": pedido["id"], "txid": pedido["pix_txid"], "token": "card_token_x",
                "payment_method_id": "visa", "installments": 1,
                "payer": {"email": "c@example.com", "documento_numero": "12345678900"},
            },
        )
    assert resposta.status_code == 400


def test_pedido_inexistente():
    with patch("backend.mercadopago_routes.criar_pagamento_cartao"):
        resposta = client.post(
            "/api/payments/mercadopago/card",
            json={
                "pedido_id": 999999999, "txid": "qualquer", "token": "card_token_x",
                "payment_method_id": "visa", "installments": 1,
                "payer": {"email": "c@example.com", "documento_numero": "12345678900"},
            },
            headers={"Idempotency-Key": str(uuid.uuid4()), "X-Forwarded-For": ip_unico()},
        )
    assert resposta.status_code == 404


def test_acesso_pedido_sem_txid_correto_e_negado():
    pedido = criar_pedido_publico(20.0)
    with patch("backend.mercadopago_routes.criar_pagamento_cartao"):
        resposta = client.post(
            "/api/payments/mercadopago/card",
            json={
                "pedido_id": pedido["id"], "txid": "txid-errado-000", "token": "card_token_x",
                "payment_method_id": "visa", "installments": 1,
                "payer": {"email": "c@example.com", "documento_numero": "12345678900"},
            },
            headers={"Idempotency-Key": str(uuid.uuid4()), "X-Forwarded-For": ip_unico()},
        )
    assert resposta.status_code == 403


def test_mercado_pago_temporariamente_indisponivel():
    from backend.mercadopago_client import MercadoPagoIndisponivel

    pedido = criar_pedido_publico(20.0)
    with patch("backend.mercadopago_routes.criar_pagamento_cartao", side_effect=MercadoPagoIndisponivel("timeout")):
        resposta = client.post(
            "/api/payments/mercadopago/card",
            json={
                "pedido_id": pedido["id"], "txid": pedido["pix_txid"], "token": "card_token_x",
                "payment_method_id": "visa", "installments": 1,
                "payer": {"email": "c@example.com", "documento_numero": "12345678900"},
            },
            headers={"Idempotency-Key": str(uuid.uuid4()), "X-Forwarded-For": ip_unico()},
        )
    assert resposta.status_code == 503


def test_integracao_desativada_falha_graciosamente():
    pedido = criar_pedido_publico(20.0)
    os.environ["MERCADO_PAGO_ENABLED"] = "false"
    try:
        resposta = client.post(
            "/api/payments/mercadopago/card",
            json={
                "pedido_id": pedido["id"], "txid": pedido["pix_txid"], "token": "card_token_x",
                "payment_method_id": "visa", "installments": 1,
                "payer": {"email": "c@example.com", "documento_numero": "12345678900"},
            },
            headers={"Idempotency-Key": str(uuid.uuid4()), "X-Forwarded-For": ip_unico()},
        )
    finally:
        os.environ["MERCADO_PAGO_ENABLED"] = "true"
    assert resposta.status_code == 503
    assert "pix" in resposta.json()["detail"].lower() or "indispon" in resposta.json()["detail"].lower()


def test_credenciais_ausentes_mantem_config_publica_desabilitada():
    token_original = os.environ.pop("MERCADO_PAGO_ACCESS_TOKEN", None)
    try:
        resposta = client.get("/api/payments/mercadopago/config")
        assert resposta.status_code == 200
        assert resposta.json() == {"enabled": False}
    finally:
        if token_original is not None:
            os.environ["MERCADO_PAGO_ACCESS_TOKEN"] = token_original


def test_config_publica_nunca_expoe_access_token():
    resposta = client.get("/api/payments/mercadopago/config")
    corpo = resposta.text
    assert os.environ["MERCADO_PAGO_ACCESS_TOKEN"] not in corpo
    assert "access_token" not in corpo.lower()


def test_pedido_ja_pago_nao_aceita_nova_cobranca():
    pedido = criar_pedido_publico(70.0)
    aprovado = resultado_mp(pedido, status="approved", payment_id="mp-already-paid")
    r1 = pagar_cartao(pedido, aprovado)
    assert r1.status_code == 200 and r1.json()["status"] == "aprovado"

    outra_tentativa = resultado_mp(pedido, status="approved", payment_id="mp-second-charge-attempt")
    r2 = pagar_cartao(pedido, outra_tentativa)
    assert r2.status_code == 409


def test_tentativas_listadas_no_painel_admin():
    pedido = criar_pedido_publico(45.0)
    recusado = resultado_mp(pedido, status="rejected", status_detail="cc_rejected_bad_filled_security_code", payment_id="")
    pagar_cartao(pedido, recusado)
    resposta = client.get(f"/api/payments/mercadopago/tentativas/{pedido['id']}", headers=HEADERS)
    assert resposta.status_code == 200
    tentativas = resposta.json()
    assert len(tentativas) == 1
    assert tentativas[0]["status_interno"] == "recusado"
    assert tentativas[0]["provedor"] == "mercadopago"


def test_pix_continua_funcionando_sem_regressao():
    """Confirma que criar um pedido e confirmar o pagamento via Pix continua
    funcionando normalmente, sem qualquer interferência da integração com o
    Mercado Pago (dois provedores coexistindo)."""
    pedido = criar_pedido_publico(33.0)
    assert pedido["pix_copia_cola"]
    resposta = client.post(
        "/api/pagamentos",
        json={"venda_id": pedido["id"], "forma": "Pix", "valor": pedido["total_final"], "status": "Confirmado"},
        headers={**HEADERS, "X-Forwarded-For": ip_unico(), "Idempotency-Key": str(uuid.uuid4())},
    )
    assert resposta.status_code == 200
    assert resposta.json()["status_conciliacao"] == "ok"
    detalhe = client.get(f"/api/pedidos/{pedido['id']}", headers=HEADERS).json()
    assert detalhe["status"] == "Pagamento confirmado"
    assert detalhe["payment_provider"] == "manual_pix"
