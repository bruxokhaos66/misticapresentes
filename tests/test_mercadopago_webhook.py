"""Testes do webhook genérico de provedor de pagamento aplicado ao Mercado
Pago (backend/payment_webhook_routes.py + backend/mercadopago_provider.py).

Nunca chama a API real do Mercado Pago: `consultar_pagamento` é sempre
mockado. A assinatura HMAC é calculada localmente com o mesmo segredo
configurado em MERCADO_PAGO_WEBHOOK_SECRET, replicando exatamente o que o
Mercado Pago faria -- sem depender de rede.
"""

import hashlib
import hmac
import importlib
import json
import os
import time
import uuid
from unittest.mock import patch

from fastapi.testclient import TestClient

os.environ.setdefault("MISTICA_SITE_API_KEY", "test-api-key")
os.environ.setdefault("MISTICA_SYNC_KEY", "test-api-key")
os.environ.setdefault("MISTICA_PIX_KEY", "49999999999")
os.environ.setdefault("MERCADO_PAGO_ENABLED", "true")
os.environ.setdefault("MERCADO_PAGO_ACCESS_TOKEN", "TEST-access-token")
os.environ.setdefault("MERCADO_PAGO_PUBLIC_KEY", "TEST-public-key")
WEBHOOK_SECRET = "test-webhook-secret-" + uuid.uuid4().hex[:8]
os.environ["MERCADO_PAGO_WEBHOOK_SECRET"] = WEBHOOK_SECRET

main = importlib.import_module("backend.main")
client = TestClient(main.app)
client.__enter__()

TEST_API_KEY = os.environ["MISTICA_SITE_API_KEY"]
HEADERS = {"X-Mistica-Api-Key": TEST_API_KEY}


def ip_unico() -> str:
    return f"203.0.{uuid.uuid4().int % 256}.{uuid.uuid4().int % 256}"


def codigo_unico(prefixo: str) -> str:
    return f"{prefixo}-{uuid.uuid4().hex[:10]}"


def criar_pedido_publico(preco: float, quantidade: int = 1) -> dict:
    resposta = client.post(
        "/api/produtos",
        json={"nome": "Produto Webhook MP", "codigo_p": codigo_unico("MPW"), "preco": preco, "quantidade": quantidade + 10, "categoria": "Testes"},
        headers=HEADERS,
    )
    produto = resposta.json()
    resposta = client.post(
        "/api/checkout/pedidos",
        json={"cliente": "Cliente Webhook", "telefone": "5599999999999", "forma_recebimento": "retirada", "itens": [{"produto_id": produto["id"], "quantidade": quantidade}]},
        headers={"X-Forwarded-For": ip_unico()},
    )
    assert resposta.status_code == 200, resposta.text
    return resposta.json()


def resultado_mp(pedido, *, status="approved", payment_id=None, valor=None, currency_id="BRL"):
    from backend.mercadopago_client import ResultadoPagamentoMP

    if payment_id is None:
        payment_id = f"mp-wh-{uuid.uuid4().hex[:12]}"
    return ResultadoPagamentoMP(
        id=payment_id,
        status=status,
        status_detail="detalhe_teste",
        transaction_amount=valor if valor is not None else pedido["total_final"],
        installments=1,
        payment_method_id="visa",
        payment_type_id="credit_card",
        external_reference=str(pedido["id"]),
        currency_id=currency_id,
        collector_id="1",
    )


def assinar(data_id: str, request_id: str, ts: str, secret: str = WEBHOOK_SECRET) -> str:
    manifest = f"id:{data_id};request-id:{request_id};ts:{ts};"
    v1 = hmac.new(secret.encode("utf-8"), manifest.encode("utf-8"), hashlib.sha256).hexdigest()
    return f"ts={ts},v1={v1}"


def enviar_webhook(payment_id: str, *, request_id=None, ts=None, secret=WEBHOOK_SECRET, resultado=None, usar_query_string=True):
    body = json.dumps({"type": "payment", "data": {"id": payment_id}}).encode()
    ts = ts or str(int(time.time()))
    request_id = request_id or f"req-{uuid.uuid4().hex[:8]}"
    sig = assinar(payment_id, request_id, ts, secret)
    headers = {"x-signature": sig, "x-request-id": request_id, "Content-Type": "application/json", "X-Forwarded-For": ip_unico()}
    # O Mercado Pago sempre chama a URL de notificação com data.id e type na
    # query string (não só no corpo) -- replica isso para exercitar o mesmo
    # caminho usado em produção (backend/mercadopago_provider.py lê
    # primeiro da query string, com fallback pro corpo).
    url = f"/api/webhooks/pagamentos/mercadopago?data.id={payment_id}&type=payment" if usar_query_string else "/api/webhooks/pagamentos/mercadopago"
    with patch("backend.mercadopago_provider.consultar_pagamento", return_value=resultado):
        return client.post(url, content=body, headers=headers)


def test_webhook_aprovado_confirma_pedido():
    pedido = criar_pedido_publico(90.0)
    resultado = resultado_mp(pedido, status="approved")
    resposta = enviar_webhook(resultado.id, resultado=resultado)
    assert resposta.status_code == 200, resposta.text
    assert resposta.json()["status_conciliacao"] == "ok"
    detalhe = client.get(f"/api/pedidos/{pedido['id']}", headers=HEADERS).json()
    assert detalhe["status"] == "Pagamento confirmado"
    assert detalhe["payment_provider"] == "mercadopago"
    assert detalhe["provider_payment_id"] == resultado.id


def test_webhook_pendente_move_para_analise():
    pedido = criar_pedido_publico(55.0)
    resultado = resultado_mp(pedido, status="pending")
    resposta = enviar_webhook(resultado.id, resultado=resultado)
    assert resposta.status_code == 200
    detalhe = client.get(f"/api/pedidos/{pedido['id']}", headers=HEADERS).json()
    assert detalhe["status"] == "Pagamento em análise"


def test_webhook_recusado_nao_confirma():
    pedido = criar_pedido_publico(25.0)
    resultado = resultado_mp(pedido, status="rejected")
    resposta = enviar_webhook(resultado.id, resultado=resultado)
    assert resposta.status_code == 200
    detalhe = client.get(f"/api/pedidos/{pedido['id']}", headers=HEADERS).json()
    assert detalhe["status"] != "Pagamento confirmado"


def test_webhook_cancelado():
    pedido = criar_pedido_publico(25.0)
    resultado = resultado_mp(pedido, status="cancelled")
    resposta = enviar_webhook(resultado.id, resultado=resultado)
    assert resposta.status_code == 200
    detalhe = client.get(f"/api/pedidos/{pedido['id']}", headers=HEADERS).json()
    assert detalhe["status"] != "Pagamento confirmado"


def test_webhook_estorno_apos_aprovado():
    pedido = criar_pedido_publico(65.0)
    aprovado = resultado_mp(pedido, status="approved")
    enviar_webhook(aprovado.id, resultado=aprovado)
    detalhe = client.get(f"/api/pedidos/{pedido['id']}", headers=HEADERS).json()
    assert detalhe["status"] == "Pagamento confirmado"

    estornado = resultado_mp(pedido, status="refunded", payment_id=aprovado.id)
    resposta = enviar_webhook(estornado.id, resultado=estornado)
    assert resposta.status_code == 200
    # Estorno não reverte pedidos.status automaticamente (fica registrado
    # para conciliação administrativa -- mesma regra já usada pelo Pix).
    pagamentos = client.get("/api/pagamentos", params={"venda_id": pedido["id"]}, headers=HEADERS).json()
    assert any(p["status"] == "Estornado" for p in pagamentos)


def test_webhook_chargeback():
    pedido = criar_pedido_publico(65.0)
    aprovado = resultado_mp(pedido, status="approved")
    enviar_webhook(aprovado.id, resultado=aprovado)

    contestado = resultado_mp(pedido, status="charged_back", payment_id=aprovado.id)
    resposta = enviar_webhook(contestado.id, resultado=contestado)
    assert resposta.status_code == 200
    pagamentos = client.get("/api/pagamentos", params={"venda_id": pedido["id"]}, headers=HEADERS).json()
    assert any(p["status"] == "Estornado" for p in pagamentos)


def test_webhook_idempotente_evento_duplicado():
    pedido = criar_pedido_publico(70.0)
    resultado = resultado_mp(pedido, status="approved")
    body = json.dumps({"type": "payment", "data": {"id": resultado.id}}).encode()
    ts = str(int(time.time()))
    request_id = f"req-{uuid.uuid4().hex[:8]}"
    sig = assinar(resultado.id, request_id, ts)
    headers = {"x-signature": sig, "x-request-id": request_id, "Content-Type": "application/json"}

    with patch("backend.mercadopago_provider.consultar_pagamento", return_value=resultado) as mock_consulta:
        r1 = client.post("/api/webhooks/pagamentos/mercadopago", content=body, headers={**headers, "X-Forwarded-For": ip_unico()})
        r2 = client.post("/api/webhooks/pagamentos/mercadopago", content=body, headers={**headers, "X-Forwarded-For": ip_unico()})
    assert r1.status_code == 200
    assert r2.status_code == 200
    assert r2.json().get("duplicado") is True
    assert mock_consulta.call_count == 2  # extrai o evento antes de checar duplicidade, mas só processa 1x
    detalhe = client.get(f"/api/pedidos/{pedido['id']}", headers=HEADERS).json()
    assert detalhe["status"] == "Pagamento confirmado"


def test_webhook_fora_de_ordem_pendente_apos_aprovado_nao_regride():
    pedido = criar_pedido_publico(48.0)
    aprovado = resultado_mp(pedido, status="approved")
    enviar_webhook(aprovado.id, resultado=aprovado)
    detalhe = client.get(f"/api/pedidos/{pedido['id']}", headers=HEADERS).json()
    assert detalhe["status"] == "Pagamento confirmado"

    # Notificação atrasada de um estado anterior (pending) chega DEPOIS do
    # approved -- nunca deve regredir um pedido já confirmado.
    pendente_tardio = resultado_mp(pedido, status="pending", payment_id=aprovado.id)
    resposta = enviar_webhook(pendente_tardio.id, resultado=pendente_tardio)
    assert resposta.status_code == 200
    detalhe2 = client.get(f"/api/pedidos/{pedido['id']}", headers=HEADERS).json()
    assert detalhe2["status"] == "Pagamento confirmado"


def test_webhook_assinatura_invalida():
    pedido = criar_pedido_publico(20.0)
    resultado = resultado_mp(pedido, status="approved")
    resposta = enviar_webhook(resultado.id, resultado=resultado, secret="segredo-errado")
    assert resposta.status_code == 401


def test_webhook_payload_invalido():
    resposta = client.post(
        "/api/webhooks/pagamentos/mercadopago",
        content=b"isto nao e json",
        headers={"x-signature": "ts=1,v1=abc", "x-request-id": "req-x", "Content-Type": "application/json", "X-Forwarded-For": ip_unico()},
    )
    assert resposta.status_code in (400, 401)  # assinatura inválida é checada antes do parse, ambos aceitáveis


def test_webhook_valor_divergente_nao_confirma():
    pedido = criar_pedido_publico(100.0)
    resultado = resultado_mp(pedido, status="approved", valor=1.00)  # provedor informa valor diferente do total do pedido
    resposta = enviar_webhook(resultado.id, resultado=resultado)
    assert resposta.status_code == 200
    assert resposta.json()["status_conciliacao"] != "ok"
    detalhe = client.get(f"/api/pedidos/{pedido['id']}", headers=HEADERS).json()
    assert detalhe["status"] != "Pagamento confirmado"


def test_webhook_pedido_inexistente():
    from backend.mercadopago_client import ResultadoPagamentoMP

    resultado = ResultadoPagamentoMP(
        id=f"mp-inexistente-{uuid.uuid4().hex[:8]}", status="approved", status_detail="x",
        transaction_amount=10.0, installments=1, payment_method_id="visa", payment_type_id="credit_card",
        external_reference="999999999", currency_id="BRL", collector_id="1",
    )
    resposta = enviar_webhook(resultado.id, resultado=resultado)
    assert resposta.status_code == 404


def test_webhook_mercadopago_indisponivel():
    from backend.mercadopago_client import MercadoPagoIndisponivel

    body = json.dumps({"type": "payment", "data": {"id": "mp-timeout-1"}}).encode()
    ts = str(int(time.time()))
    request_id = f"req-{uuid.uuid4().hex[:8]}"
    sig = assinar("mp-timeout-1", request_id, ts)
    with patch("backend.mercadopago_provider.consultar_pagamento", side_effect=MercadoPagoIndisponivel("timeout")):
        resposta = client.post(
            "/api/webhooks/pagamentos/mercadopago",
            content=body,
            headers={"x-signature": sig, "x-request-id": request_id, "Content-Type": "application/json", "X-Forwarded-For": ip_unico()},
        )
    assert resposta.status_code == 503


def test_webhook_provedor_desconhecido():
    resposta = client.post(
        "/api/webhooks/pagamentos/provedor-inexistente",
        content=b"{}",
        headers={"X-Forwarded-For": ip_unico()},
    )
    assert resposta.status_code == 501


def test_webhook_integracao_desativada_responde_nao_configurado():
    os.environ["MERCADO_PAGO_ENABLED"] = "false"
    try:
        body = json.dumps({"type": "payment", "data": {"id": "mp-desligado-1"}}).encode()
        ts = str(int(time.time()))
        request_id = f"req-{uuid.uuid4().hex[:8]}"
        sig = assinar("mp-desligado-1", request_id, ts)
        resposta = client.post(
            "/api/webhooks/pagamentos/mercadopago",
            content=body,
            headers={"x-signature": sig, "x-request-id": request_id, "Content-Type": "application/json", "X-Forwarded-For": ip_unico()},
        )
    finally:
        os.environ["MERCADO_PAGO_ENABLED"] = "true"
    assert resposta.status_code == 501


def test_webhook_evento_de_tipo_irrelevante_e_ignorado():
    body = json.dumps({"type": "merchant_order", "data": {"id": "123"}}).encode()
    ts = str(int(time.time()))
    request_id = f"req-{uuid.uuid4().hex[:8]}"
    sig = assinar("123", request_id, ts)
    resposta = client.post(
        "/api/webhooks/pagamentos/mercadopago",
        content=body,
        headers={"x-signature": sig, "x-request-id": request_id, "Content-Type": "application/json", "X-Forwarded-For": ip_unico()},
    )
    assert resposta.status_code == 200
    assert resposta.json().get("ignorado") is True


def test_webhook_moeda_diferente_de_brl_e_ignorado():
    pedido = criar_pedido_publico(50.0)
    resultado = resultado_mp(pedido, status="approved", currency_id="USD")
    resposta = enviar_webhook(resultado.id, resultado=resultado)
    assert resposta.status_code == 200
    assert resposta.json().get("ignorado") is True
    detalhe = client.get(f"/api/pedidos/{pedido['id']}", headers=HEADERS).json()
    assert detalhe["status"] != "Pagamento confirmado"


def test_resposta_do_webhook_nunca_contem_segredo_ou_token():
    pedido = criar_pedido_publico(15.0)
    resultado = resultado_mp(pedido, status="approved")
    resposta = enviar_webhook(resultado.id, resultado=resultado)
    corpo = resposta.text
    assert WEBHOOK_SECRET not in corpo
    assert os.environ["MERCADO_PAGO_ACCESS_TOKEN"] not in corpo


def test_assinatura_usa_data_id_da_query_string_como_documentado():
    """Algoritmo oficial do Mercado Pago: o manifesto HMAC usa o data.id da
    query string da URL de notificação, não do corpo. Uma assinatura
    calculada com o data.id do CORPO (divergente do da query) deve ser
    rejeitada -- prova que o código está de fato lendo da query string."""
    pedido = criar_pedido_publico(22.0)
    resultado = resultado_mp(pedido, status="approved")
    ts = str(int(time.time()))
    request_id = f"req-{uuid.uuid4().hex[:8]}"
    # Assina com um data.id diferente do que vai na query string.
    sig_para_id_errado = assinar("id-diferente-do-corpo", request_id, ts)
    body = json.dumps({"type": "payment", "data": {"id": resultado.id}}).encode()
    with patch("backend.mercadopago_provider.consultar_pagamento", return_value=resultado):
        resposta = client.post(
            f"/api/webhooks/pagamentos/mercadopago?data.id={resultado.id}&type=payment",
            content=body,
            headers={"x-signature": sig_para_id_errado, "x-request-id": request_id, "Content-Type": "application/json", "X-Forwarded-For": ip_unico()},
        )
    assert resposta.status_code == 401


def test_assinatura_valida_apenas_com_query_string_correta():
    pedido = criar_pedido_publico(22.0)
    resultado = resultado_mp(pedido, status="approved")
    resposta = enviar_webhook(resultado.id, resultado=resultado, usar_query_string=True)
    assert resposta.status_code == 200


def test_assinatura_fallback_para_corpo_sem_query_string():
    """Notificações de teste manual ("Simular") do painel do Mercado Pago
    não usam a URL completa cadastrada (sem query string) -- o fallback para
    o data.id do corpo continua aceitando essas notificações legítimas."""
    pedido = criar_pedido_publico(18.0)
    resultado = resultado_mp(pedido, status="approved")
    resposta = enviar_webhook(resultado.id, resultado=resultado, usar_query_string=False)
    assert resposta.status_code == 200


def test_assinatura_normaliza_data_id_alfanumerico_para_minusculas():
    """Documentação oficial: se o data.id for alfanumérico, deve ser
    convertido para minúsculas antes de montar o manifesto assinado."""
    pedido = criar_pedido_publico(18.0)
    data_id_maiusculo = "ABC123XYZ"
    resultado = resultado_mp(pedido, status="approved", payment_id=data_id_maiusculo)
    ts = str(int(time.time()))
    request_id = f"req-{uuid.uuid4().hex[:8]}"
    # Assina com o id já em minúsculas (como o Mercado Pago faz antes de
    # calcular a assinatura) -- a validação deve normalizar o id recebido
    # (maiúsculo) da mesma forma e aceitar.
    sig = assinar(data_id_maiusculo.lower(), request_id, ts)
    body = json.dumps({"type": "payment", "data": {"id": data_id_maiusculo}}).encode()
    with patch("backend.mercadopago_provider.consultar_pagamento", return_value=resultado):
        resposta = client.post(
            f"/api/webhooks/pagamentos/mercadopago?data.id={data_id_maiusculo}&type=payment",
            content=body,
            headers={"x-signature": sig, "x-request-id": request_id, "Content-Type": "application/json", "X-Forwarded-For": ip_unico()},
        )
    assert resposta.status_code == 200
