"""Testes do endpoint de callback de status do WhatsApp Cloud API
(backend/whatsapp_webhook_routes.py). Nunca chama a Graph API real."""
import hashlib
import hmac
import importlib
import json
import os
import uuid

os.environ.setdefault("MISTICA_SITE_API_KEY", "test-api-key")
os.environ.setdefault("MISTICA_SYNC_KEY", "test-api-key")
os.environ.setdefault("MISTICA_PIX_KEY", "49999999999")
APP_SECRET = "app-secret-teste-" + uuid.uuid4().hex[:8]
VERIFY_TOKEN = "verify-teste-" + uuid.uuid4().hex[:8]
os.environ["WHATSAPP_APP_SECRET"] = APP_SECRET
os.environ["WHATSAPP_VERIFY_TOKEN"] = VERIFY_TOKEN
os.environ.setdefault("WHATSAPP_PROVIDER", "meta_cloud")

from fastapi.testclient import TestClient

main = importlib.import_module("backend.main")
client = TestClient(main.app)
client.__enter__()

from backend.database import conectar


def _assinar(corpo: bytes, segredo: str = APP_SECRET) -> str:
    return "sha256=" + hmac.new(segredo.encode("utf-8"), corpo, hashlib.sha256).hexdigest()


def test_verificacao_webhook_sucesso():
    resp = client.get("/api/webhooks/whatsapp", params={"hub.mode": "subscribe", "hub.verify_token": VERIFY_TOKEN, "hub.challenge": "desafio-123"})
    assert resp.status_code == 200
    assert resp.text == "desafio-123"


def test_verificacao_webhook_token_incorreto():
    resp = client.get("/api/webhooks/whatsapp", params={"hub.mode": "subscribe", "hub.verify_token": "errado", "hub.challenge": "x"})
    assert resp.status_code == 403


def test_verificacao_webhook_modo_incorreto():
    resp = client.get("/api/webhooks/whatsapp", params={"hub.mode": "unsubscribe", "hub.verify_token": VERIFY_TOKEN, "hub.challenge": "x"})
    assert resp.status_code == 403


def _payload_status(message_id: str, status: str, timestamp: str = "1700000000") -> bytes:
    return json.dumps(
        {
            "entry": [
                {
                    "changes": [
                        {"value": {"statuses": [{"id": message_id, "status": status, "timestamp": timestamp}]}}
                    ]
                }
            ]
        }
    ).encode()


def _criar_linha_outbox(order_id: int, provider_message_id: str, status: str = "sent"):
    with conectar() as conn:
        conn.execute(
            """
            INSERT INTO notification_outbox
                (event_type, aggregate_type, aggregate_id, order_id, channel, provider,
                 recipient_reference, template_name, template_language, payload_json,
                 idempotency_key, status, attempts, provider_message_id, created_at, updated_at, sent_at)
            VALUES ('PAGAMENTO_APROVADO', 'pedido', ?, ?, 'whatsapp', 'meta_cloud',
                    'admin:teste', 'admin_pagamento_aprovado', 'pt_BR', '{}',
                    ?, ?, 1, ?, '2026-01-01T00:00:00', '2026-01-01T00:00:00', '2026-01-01T00:00:00')
            """,
            (order_id, order_id, f"idem:{uuid.uuid4().hex}", status, provider_message_id),
        )
        conn.commit()


def test_webhook_assinatura_invalida_rejeitada():
    corpo = _payload_status("wamid.x", "delivered")
    resp = client.post("/api/webhooks/whatsapp", content=corpo, headers={"X-Hub-Signature-256": "sha256=00"})
    assert resp.status_code == 401


def test_webhook_sem_assinatura_rejeitado():
    corpo = _payload_status("wamid.x", "delivered")
    resp = client.post("/api/webhooks/whatsapp", content=corpo)
    assert resp.status_code == 401


def test_webhook_atualiza_status_delivered():
    msg_id = f"wamid.{uuid.uuid4().hex}"
    order_id = abs(hash(uuid.uuid4())) % 1_000_000 + 1
    _criar_linha_outbox(order_id, msg_id, status="sent")
    corpo = _payload_status(msg_id, "delivered")
    resp = client.post("/api/webhooks/whatsapp", content=corpo, headers={"X-Hub-Signature-256": _assinar(corpo)})
    assert resp.status_code == 200
    with conectar() as conn:
        linha = conn.execute("SELECT status, delivered_at FROM notification_outbox WHERE provider_message_id=?", (msg_id,)).fetchone()
    assert linha["status"] == "delivered"
    assert linha["delivered_at"] is not None


def test_webhook_nao_regride_de_read_para_delivered():
    msg_id = f"wamid.{uuid.uuid4().hex}"
    order_id = abs(hash(uuid.uuid4())) % 1_000_000 + 1
    _criar_linha_outbox(order_id, msg_id, status="read")
    corpo = _payload_status(msg_id, "delivered", timestamp="1700000099")
    resp = client.post("/api/webhooks/whatsapp", content=corpo, headers={"X-Hub-Signature-256": _assinar(corpo)})
    assert resp.status_code == 200
    with conectar() as conn:
        linha = conn.execute("SELECT status FROM notification_outbox WHERE provider_message_id=?", (msg_id,)).fetchone()
    assert linha["status"] == "read"


def test_webhook_failed_marca_permanently_failed():
    msg_id = f"wamid.{uuid.uuid4().hex}"
    order_id = abs(hash(uuid.uuid4())) % 1_000_000 + 1
    _criar_linha_outbox(order_id, msg_id, status="sent")
    corpo = json.dumps(
        {"entry": [{"changes": [{"value": {"statuses": [{"id": msg_id, "status": "failed", "errors": [{"code": 131026, "title": "numero nao encontrado"}]}]}}]}]}
    ).encode()
    resp = client.post("/api/webhooks/whatsapp", content=corpo, headers={"X-Hub-Signature-256": _assinar(corpo)})
    assert resp.status_code == 200
    with conectar() as conn:
        linha = conn.execute("SELECT status, last_error_code FROM notification_outbox WHERE provider_message_id=?", (msg_id,)).fetchone()
    assert linha["status"] == "permanently_failed"
    assert linha["last_error_code"] == "131026"


def test_webhook_evento_duplicado_nao_reprocessa_duas_vezes():
    msg_id = f"wamid.{uuid.uuid4().hex}"
    order_id = abs(hash(uuid.uuid4())) % 1_000_000 + 1
    _criar_linha_outbox(order_id, msg_id, status="sent")
    corpo = _payload_status(msg_id, "delivered", timestamp="1700000555")
    headers = {"X-Hub-Signature-256": _assinar(corpo)}
    resp1 = client.post("/api/webhooks/whatsapp", content=corpo, headers=headers)
    resp2 = client.post("/api/webhooks/whatsapp", content=corpo, headers=headers)
    assert resp1.status_code == 200
    assert resp2.status_code == 200
    assert resp2.json()["processados"] == 0
    with conectar() as conn:
        total = conn.execute("SELECT COUNT(*) AS n FROM whatsapp_status_eventos WHERE provider_message_id=?", (msg_id,)).fetchone()
    assert total["n"] == 1


def test_webhook_provider_message_id_desconhecido_nao_falha():
    corpo = _payload_status(f"wamid.{uuid.uuid4().hex}", "delivered")
    resp = client.post("/api/webhooks/whatsapp", content=corpo, headers={"X-Hub-Signature-256": _assinar(corpo)})
    assert resp.status_code == 200


def test_webhook_payload_json_invalido():
    corpo = b"{invalido"
    resp = client.post("/api/webhooks/whatsapp", content=corpo, headers={"X-Hub-Signature-256": _assinar(corpo)})
    assert resp.status_code == 400


def test_webhook_status_desconhecido_ignorado():
    corpo = _payload_status("wamid.x", "algum_status_novo_da_meta")
    resp = client.post("/api/webhooks/whatsapp", content=corpo, headers={"X-Hub-Signature-256": _assinar(corpo)})
    assert resp.status_code == 200
    assert resp.json().get("ignorado") is True
