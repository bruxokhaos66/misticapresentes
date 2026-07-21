"""Testes de integração: o webhook do Mercado Pago (backend/
payment_webhook_routes.py) enfileira PAGAMENTO_PENDENTE e distingue
CHARGEBACK_RECEBIDO de PAGAMENTO_REEMBOLSADO -- e a expiração automática de
pedidos (backend/order_status_routes.py) enfileira PAGAMENTO_EXPIRADO.
Nunca chama o Mercado Pago real: consultar_pagamento é sempre mockado."""
import hashlib
import hmac
import importlib
import json
import os
import time
import uuid
from unittest.mock import patch

os.environ.setdefault("MISTICA_SITE_API_KEY", "test-api-key")
os.environ.setdefault("MISTICA_SYNC_KEY", "test-api-key")
os.environ.setdefault("MISTICA_PIX_KEY", "49999999999")
os.environ.setdefault("MERCADO_PAGO_ENABLED", "true")
os.environ.setdefault("MERCADO_PAGO_ACCESS_TOKEN", "TEST-access-token")
os.environ.setdefault("MERCADO_PAGO_PUBLIC_KEY", "TEST-public-key")
# Nunca sobrescreve MERCADO_PAGO_WEBHOOK_SECRET globalmente aqui: outro
# módulo de teste (tests/test_mercadopago_webhook.py) também assina
# requisições com o SEU PRÓPRIO segredo capturado em uma constante de
# módulo -- uma atribuição global e incondicional em dois arquivos para a
# mesma variável de ambiente causaria uma corrida de importação (o último
# módulo importado por vencer, quebrando a verificação de assinatura do
# outro). Cada teste que precisa do webhook do Mercado Pago habilitado usa
# monkeypatch.setenv (revertido automaticamente ao final do teste).
WEBHOOK_SECRET = "webhook-secret-teste-" + uuid.uuid4().hex[:8]

from fastapi.testclient import TestClient

main = importlib.import_module("backend.main")
client = TestClient(main.app)
client.__enter__()

from backend.database import conectar

TEST_API_KEY = os.environ["MISTICA_SITE_API_KEY"]
HEADERS = {"X-Mistica-Api-Key": TEST_API_KEY}

_TEMPLATE_ENV_VARS = [
    "WHATSAPP_TEMPLATE_ADMIN_NOVO_PEDIDO", "WHATSAPP_TEMPLATE_ADMIN_PIX_GERADO",
    "WHATSAPP_TEMPLATE_ADMIN_PAGAMENTO_APROVADO", "WHATSAPP_TEMPLATE_ADMIN_PAGAMENTO_PENDENTE",
    "WHATSAPP_TEMPLATE_ADMIN_PAGAMENTO_RECUSADO", "WHATSAPP_TEMPLATE_ADMIN_PAGAMENTO_EXPIRADO",
    "WHATSAPP_TEMPLATE_ADMIN_PAGAMENTO_CANCELADO", "WHATSAPP_TEMPLATE_ADMIN_PAGAMENTO_REEMBOLSADO",
    "WHATSAPP_TEMPLATE_ADMIN_CHARGEBACK", "WHATSAPP_TEMPLATE_ADMIN_FALHA_RECONCILIACAO",
]


def _habilitar_whatsapp(monkeypatch):
    monkeypatch.setenv("MERCADO_PAGO_WEBHOOK_SECRET", WEBHOOK_SECRET)
    monkeypatch.setenv("WHATSAPP_NOTIFICATIONS_ENABLED", "true")
    monkeypatch.setenv("WHATSAPP_PROVIDER", "meta_cloud")
    monkeypatch.setenv("WHATSAPP_PHONE_NUMBER_ID", "123456")
    monkeypatch.setenv("WHATSAPP_ACCESS_TOKEN", "token-teste")
    monkeypatch.setenv("WHATSAPP_APP_SECRET", "segredo-teste")
    monkeypatch.setenv("WHATSAPP_VERIFY_TOKEN", "verify-teste")
    monkeypatch.setenv("WHATSAPP_ADMIN_RECIPIENTS", "5511999998888")
    for env_var in _TEMPLATE_ENV_VARS:
        monkeypatch.setenv(env_var, "template_teste")


def ip_unico() -> str:
    return f"203.0.{uuid.uuid4().int % 256}.{uuid.uuid4().int % 256}"


def codigo_unico(prefixo: str) -> str:
    return f"{prefixo}-{uuid.uuid4().hex[:10]}"


def criar_pedido_publico(preco: float = 80.0, quantidade: int = 1) -> dict:
    resposta = client.post(
        "/api/produtos",
        json={"nome": "Produto WhatsApp MP", "codigo_p": codigo_unico("WMP"), "preco": preco, "quantidade": quantidade + 10, "categoria": "Testes"},
        headers=HEADERS,
    )
    produto = resposta.json()
    resposta = client.post(
        "/api/checkout/pedidos",
        json={"cliente": "Cliente WhatsApp MP", "telefone": "5599999999999", "forma_recebimento": "retirada", "itens": [{"produto_id": produto["id"], "quantidade": quantidade}]},
        headers={"X-Forwarded-For": ip_unico()},
    )
    assert resposta.status_code == 200, resposta.text
    return resposta.json()


def resultado_mp(pedido, *, status="approved", payment_id=None, valor=None):
    from backend.mercadopago_client import ResultadoPagamentoMP

    if payment_id is None:
        payment_id = f"mp-wh-{uuid.uuid4().hex[:12]}"
    return ResultadoPagamentoMP(
        id=payment_id, status=status, status_detail="detalhe_teste",
        transaction_amount=valor if valor is not None else pedido["total_final"],
        installments=1, payment_method_id="visa", payment_type_id="credit_card",
        external_reference=str(pedido["id"]), currency_id="BRL", collector_id="1",
    )


def assinar(data_id: str, request_id: str, ts: str) -> str:
    manifest = f"id:{data_id};request-id:{request_id};ts:{ts};"
    v1 = hmac.new(WEBHOOK_SECRET.encode("utf-8"), manifest.encode("utf-8"), hashlib.sha256).hexdigest()
    return f"ts={ts},v1={v1}"


def enviar_webhook(payment_id: str, resultado):
    body = json.dumps({"type": "payment", "data": {"id": payment_id}}).encode()
    ts = str(int(time.time()))
    request_id = f"req-{uuid.uuid4().hex[:8]}"
    headers = {"x-signature": assinar(payment_id, request_id, ts), "x-request-id": request_id, "Content-Type": "application/json"}
    with patch("backend.mercadopago_provider.consultar_pagamento", return_value=resultado):
        return client.post(f"/api/webhooks/pagamentos/mercadopago?data.id={payment_id}", content=body, headers=headers)


def _linhas_outbox(order_id: int) -> list:
    with conectar() as conn:
        rows = conn.execute("SELECT event_type, status FROM notification_outbox WHERE order_id=? ORDER BY id", (order_id,)).fetchall()
    return [dict(row) for row in rows]


def test_webhook_pendente_enfileira_pagamento_pendente(monkeypatch):
    _habilitar_whatsapp(monkeypatch)
    pedido = criar_pedido_publico()
    resultado = resultado_mp(pedido, status="in_process")
    resp = enviar_webhook(resultado.id, resultado)
    assert resp.status_code == 200, resp.text
    eventos = _linhas_outbox(pedido["id"])
    assert any(e["event_type"] == "PAGAMENTO_PENDENTE" for e in eventos)


def test_webhook_aprovado_enfileira_pagamento_aprovado(monkeypatch):
    _habilitar_whatsapp(monkeypatch)
    pedido = criar_pedido_publico()
    resultado = resultado_mp(pedido, status="approved")
    resp = enviar_webhook(resultado.id, resultado)
    assert resp.status_code == 200, resp.text
    eventos = _linhas_outbox(pedido["id"])
    assert any(e["event_type"] == "PAGAMENTO_APROVADO" for e in eventos)


def test_webhook_chargeback_gera_evento_distinto_de_reembolso(monkeypatch):
    _habilitar_whatsapp(monkeypatch)
    pedido = criar_pedido_publico()
    # Aprova primeiro (chargeback só faz sentido sobre um pagamento aprovado).
    aprovado = resultado_mp(pedido, status="approved")
    enviar_webhook(aprovado.id, aprovado)
    chargeback = resultado_mp(pedido, status="charged_back", payment_id=aprovado.id)
    resp = enviar_webhook(chargeback.id, chargeback)
    assert resp.status_code == 200, resp.text
    eventos = _linhas_outbox(pedido["id"])
    assert any(e["event_type"] == "CHARGEBACK_RECEBIDO" for e in eventos)
    assert not any(e["event_type"] == "PAGAMENTO_REEMBOLSADO" for e in eventos)


def test_webhook_duplicado_nao_duplica_notificacao_pendente(monkeypatch):
    _habilitar_whatsapp(monkeypatch)
    pedido = criar_pedido_publico()
    resultado = resultado_mp(pedido, status="in_process")
    enviar_webhook(resultado.id, resultado)
    enviar_webhook(resultado.id, resultado)  # replay do mesmo evento
    eventos = [e for e in _linhas_outbox(pedido["id"]) if e["event_type"] == "PAGAMENTO_PENDENTE"]
    assert len(eventos) == 1


def test_pedido_expirado_enfileira_pagamento_expirado(monkeypatch):
    _habilitar_whatsapp(monkeypatch)
    pedido = criar_pedido_publico()
    passado = "2000-01-01T00:00:00"
    with conectar() as conn:
        conn.execute("UPDATE pedidos SET expira_em=? WHERE id=?", (passado, pedido["id"]))
        conn.commit()

    from backend.order_status_routes import expirar_pedidos_pendentes

    with conectar() as conn:
        total = expirar_pedidos_pendentes(conn)
        conn.commit()
    assert total >= 1
    eventos = _linhas_outbox(pedido["id"])
    assert any(e["event_type"] == "PAGAMENTO_EXPIRADO" for e in eventos)


def test_pedido_expirado_desabilitado_nao_gera_erro(monkeypatch):
    monkeypatch.setenv("WHATSAPP_NOTIFICATIONS_ENABLED", "false")
    pedido = criar_pedido_publico()
    passado = "2000-01-01T00:00:00"
    with conectar() as conn:
        conn.execute("UPDATE pedidos SET expira_em=? WHERE id=?", (passado, pedido["id"]))
        conn.commit()

    from backend.order_status_routes import expirar_pedidos_pendentes

    with conectar() as conn:
        total = expirar_pedidos_pendentes(conn)
        conn.commit()
    assert total >= 1
    with conectar() as conn:
        status_final = conn.execute("SELECT status FROM pedidos WHERE id=?", (pedido["id"],)).fetchone()
    assert status_final["status"] == "Cancelado"
