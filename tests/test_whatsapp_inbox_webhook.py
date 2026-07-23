"""Testes de recebimento de mensagens da Central de Atendimento WhatsApp
(backend/whatsapp_inbox_service.py + extensão do webhook em
backend/whatsapp_webhook_routes.py). Nunca chama a Graph API real."""
from __future__ import annotations

import hashlib
import hmac
import importlib
import json
import os
import uuid

os.environ.setdefault("MISTICA_SITE_API_KEY", "test-api-key")
os.environ.setdefault("MISTICA_SYNC_KEY", "test-api-key")
os.environ.setdefault("MISTICA_PIX_KEY", "49999999999")

APP_SECRET = os.environ.get("WHATSAPP_APP_SECRET") or "app-secret-teste-" + uuid.uuid4().hex[:8]
VERIFY_TOKEN = os.environ.get("WHATSAPP_VERIFY_TOKEN") or "verify-teste-" + uuid.uuid4().hex[:8]
os.environ["WHATSAPP_APP_SECRET"] = APP_SECRET
os.environ["WHATSAPP_VERIFY_TOKEN"] = VERIFY_TOKEN
os.environ.setdefault("WHATSAPP_PROVIDER", "meta_cloud")
os.environ.setdefault("WHATSAPP_PHONE_NUMBER_ID", "123456")
os.environ.setdefault("WHATSAPP_ACCESS_TOKEN", "token-de-teste")

from fastapi.testclient import TestClient

main = importlib.import_module("backend.main")
client = TestClient(main.app)
client.__enter__()

from backend.database import conectar
import backend.whatsapp_webhook_routes as webhook_routes


def _assinar(corpo: bytes) -> str:
    return "sha256=" + hmac.new(APP_SECRET.encode("utf-8"), corpo, hashlib.sha256).hexdigest()


def _payload_texto(wa_id: str, msg_id: str, texto: str, *, profile_name: str = "Cliente Teste") -> bytes:
    return json.dumps(
        {
            "entry": [
                {
                    "changes": [
                        {
                            "value": {
                                "contacts": [{"profile": {"name": profile_name}, "wa_id": wa_id}],
                                "messages": [
                                    {"from": wa_id, "id": msg_id, "type": "text", "timestamp": "1700000000", "text": {"body": texto}}
                                ],
                            }
                        }
                    ]
                }
            ]
        }
    ).encode()


def _payload_tipo(wa_id: str, msg_id: str, tipo: str, bloco: dict) -> bytes:
    return json.dumps(
        {
            "entry": [
                {
                    "changes": [
                        {
                            "value": {
                                "contacts": [{"profile": {"name": "Cliente"}, "wa_id": wa_id}],
                                "messages": [{"from": wa_id, "id": msg_id, "type": tipo, "timestamp": "1700000000", tipo: bloco}],
                            }
                        }
                    ]
                }
            ]
        }
    ).encode()


def _habilitar_inbox(monkeypatch):
    monkeypatch.setattr(webhook_routes, "whatsapp_cloud_inbox_habilitado", lambda: True)


def test_webhook_ignora_mensagens_com_flag_desligada(monkeypatch):
    monkeypatch.setattr(webhook_routes, "whatsapp_cloud_inbox_habilitado", lambda: False)
    wa_id = "5511" + str(uuid.uuid4().int)[:9]
    msg_id = f"wamid.{uuid.uuid4().hex}"
    corpo = _payload_texto(wa_id, msg_id, "Olá, quero comprar um produto")
    resp = client.post("/api/webhooks/whatsapp", content=corpo, headers={"X-Hub-Signature-256": _assinar(corpo)})
    assert resp.status_code == 200
    with conectar() as conn:
        linha = conn.execute("SELECT id FROM whatsapp_messages WHERE meta_message_id=?", (msg_id,)).fetchone()
    assert linha is None


def test_webhook_persiste_mensagem_de_texto(monkeypatch):
    _habilitar_inbox(monkeypatch)
    wa_id = "5511" + str(uuid.uuid4().int)[:9]
    msg_id = f"wamid.{uuid.uuid4().hex}"
    corpo = _payload_texto(wa_id, msg_id, "Olá, quero comprar um produto", profile_name="Maria Teste")
    resp = client.post("/api/webhooks/whatsapp", content=corpo, headers={"X-Hub-Signature-256": _assinar(corpo)})
    assert resp.status_code == 200
    assert resp.json()["mensagens"]["processadas"] == 1
    with conectar() as conn:
        mensagem = conn.execute("SELECT * FROM whatsapp_messages WHERE meta_message_id=?", (msg_id,)).fetchone()
        contato = conn.execute("SELECT * FROM whatsapp_contacts WHERE wa_id=?", (wa_id,)).fetchone()
        conversa = conn.execute("SELECT * FROM whatsapp_conversations WHERE id=?", (mensagem["conversation_id"],)).fetchone()
    assert mensagem["text_body"] == "Olá, quero comprar um produto"
    assert mensagem["direction"] == "inbound"
    assert contato["profile_name"] == "Maria Teste"
    assert conversa["unread_count"] == 1
    assert conversa["last_inbound_at"] is not None


def test_webhook_assinatura_invalida_nao_persiste(monkeypatch):
    _habilitar_inbox(monkeypatch)
    wa_id = "5511" + str(uuid.uuid4().int)[:9]
    msg_id = f"wamid.{uuid.uuid4().hex}"
    corpo = _payload_texto(wa_id, msg_id, "texto qualquer")
    resp = client.post("/api/webhooks/whatsapp", content=corpo, headers={"X-Hub-Signature-256": "sha256=00"})
    assert resp.status_code == 401
    with conectar() as conn:
        linha = conn.execute("SELECT id FROM whatsapp_messages WHERE meta_message_id=?", (msg_id,)).fetchone()
    assert linha is None


def test_webhook_mensagem_duplicada_nao_duplica(monkeypatch):
    _habilitar_inbox(monkeypatch)
    wa_id = "5511" + str(uuid.uuid4().int)[:9]
    msg_id = f"wamid.{uuid.uuid4().hex}"
    corpo = _payload_texto(wa_id, msg_id, "mensagem repetida")
    headers = {"X-Hub-Signature-256": _assinar(corpo)}
    resp1 = client.post("/api/webhooks/whatsapp", content=corpo, headers=headers)
    resp2 = client.post("/api/webhooks/whatsapp", content=corpo, headers=headers)
    assert resp1.json()["mensagens"]["processadas"] == 1
    assert resp2.json()["mensagens"]["duplicadas"] == 1
    with conectar() as conn:
        total = conn.execute("SELECT COUNT(*) AS n FROM whatsapp_messages WHERE meta_message_id=?", (msg_id,)).fetchone()
        conversa = conn.execute(
            "SELECT unread_count FROM whatsapp_conversations WHERE id=(SELECT conversation_id FROM whatsapp_messages WHERE meta_message_id=?)",
            (msg_id,),
        ).fetchone()
    assert total["n"] == 1
    assert conversa["unread_count"] == 1


def test_webhook_tipo_desconhecido_nao_quebra(monkeypatch):
    _habilitar_inbox(monkeypatch)
    wa_id = "5511" + str(uuid.uuid4().int)[:9]
    msg_id = f"wamid.{uuid.uuid4().hex}"
    corpo = json.dumps(
        {
            "entry": [
                {
                    "changes": [
                        {
                            "value": {
                                "messages": [{"from": wa_id, "id": msg_id, "type": "algum_tipo_novo_da_meta"}],
                            }
                        }
                    ]
                }
            ]
        }
    ).encode()
    resp = client.post("/api/webhooks/whatsapp", content=corpo, headers={"X-Hub-Signature-256": _assinar(corpo)})
    assert resp.status_code == 200
    assert resp.json()["mensagens"]["processadas"] == 1
    with conectar() as conn:
        mensagem = conn.execute("SELECT * FROM whatsapp_messages WHERE meta_message_id=?", (msg_id,)).fetchone()
    assert mensagem["message_type"] == "unknown"
    assert mensagem["text_body"] == "[Tipo de mensagem ainda não suportado]"


def test_webhook_mensagem_de_imagem_guarda_so_metadados(monkeypatch):
    _habilitar_inbox(monkeypatch)
    wa_id = "5511" + str(uuid.uuid4().int)[:9]
    msg_id = f"wamid.{uuid.uuid4().hex}"
    corpo = _payload_tipo(wa_id, msg_id, "image", {"id": "media-abc123", "mime_type": "image/jpeg", "caption": "Olha essa vela"})
    resp = client.post("/api/webhooks/whatsapp", content=corpo, headers={"X-Hub-Signature-256": _assinar(corpo)})
    assert resp.status_code == 200
    with conectar() as conn:
        mensagem = conn.execute("SELECT * FROM whatsapp_messages WHERE meta_message_id=?", (msg_id,)).fetchone()
    assert mensagem["message_type"] == "image"
    assert mensagem["media_id"] == "media-abc123"
    assert mensagem["media_mime_type"] == "image/jpeg"
    assert mensagem["text_body"] == "Olha essa vela"
    assert mensagem["media_path"] is None


def test_webhook_status_e_mensagens_no_mesmo_payload(monkeypatch):
    """O mesmo endpoint processa status de entrega (notificações
    administrativas) e mensagens recebidas (Central de Atendimento) sem
    misturar as duas idempotências."""
    _habilitar_inbox(monkeypatch)
    wa_id = "5511" + str(uuid.uuid4().int)[:9]
    msg_id = f"wamid.{uuid.uuid4().hex}"
    corpo = json.dumps(
        {
            "entry": [
                {
                    "changes": [
                        {
                            "value": {
                                "statuses": [{"id": f"wamid.{uuid.uuid4().hex}", "status": "delivered", "timestamp": "1700000321"}],
                                "messages": [{"from": wa_id, "id": msg_id, "type": "text", "text": {"body": "oi"}}],
                            }
                        }
                    ]
                }
            ]
        }
    ).encode()
    resp = client.post("/api/webhooks/whatsapp", content=corpo, headers={"X-Hub-Signature-256": _assinar(corpo)})
    assert resp.status_code == 200
    corpo_resposta = resp.json()
    assert corpo_resposta["mensagens"]["processadas"] == 1
