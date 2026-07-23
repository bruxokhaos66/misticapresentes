"""Testes da API administrativa da Central de Atendimento WhatsApp
(backend/whatsapp_inbox_routes.py). Nunca chama a Graph API real -- o envio é
sempre feito por um provider falso injetado via monkeypatch."""
from __future__ import annotations

import importlib
import os
import secrets as secrets_mod
import uuid
from datetime import datetime, timedelta

os.environ.setdefault("MISTICA_SITE_API_KEY", "test-api-key")
os.environ.setdefault("MISTICA_SYNC_KEY", "test-api-key")
os.environ.setdefault("MISTICA_PIX_KEY", "49999999999")
os.environ.setdefault("WHATSAPP_APP_SECRET", "app-secret-teste-" + uuid.uuid4().hex[:8])
os.environ.setdefault("WHATSAPP_VERIFY_TOKEN", "verify-teste-" + uuid.uuid4().hex[:8])
os.environ.setdefault("WHATSAPP_PROVIDER", "meta_cloud")
os.environ.setdefault("WHATSAPP_PHONE_NUMBER_ID", "123456")
os.environ.setdefault("WHATSAPP_ACCESS_TOKEN", "token-de-teste")

from fastapi.testclient import TestClient

main = importlib.import_module("backend.main")
client = TestClient(main.app)
client.__enter__()

from backend.database import conectar
import backend.whatsapp_inbox_routes as inbox_routes
from backend.whatsapp_inbox_repository import obter_ou_criar_conversa, upsert_contact
from backend.whatsapp_provider import ResultadoEnvioWhatsApp


def _sessao_admin(perfil: str = "adm") -> str:
    token = secrets_mod.token_urlsafe(24)
    agora = datetime.now()
    with conectar() as conn:
        conn.execute(
            """INSERT INTO painel_sessoes (token, usuario_id, login, nome, perfil, ip, user_agent, criada_em, expira_em, ultimo_acesso)
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (token, 1, "admin-teste", "Admin Teste", perfil, "127.0.0.1", "pytest", agora.isoformat(sep=" ", timespec="seconds"), (agora + timedelta(hours=1)).isoformat(sep=" ", timespec="seconds"), agora.isoformat(sep=" ", timespec="seconds")),
        )
        conn.commit()
    return token


def _criar_conversa_com_inbound(wa_id: str | None = None) -> int:
    wa_id = wa_id or ("5511" + str(uuid.uuid4().int)[:9])
    with conectar() as conn:
        contato = upsert_contact(conn, wa_id=wa_id, profile_name="Cliente Teste")
        conversa = obter_ou_criar_conversa(conn, contact_id=contato["id"])
        conn.execute(
            "UPDATE whatsapp_conversations SET last_inbound_at=? WHERE id=?",
            (datetime.now().isoformat(timespec="seconds"), conversa["id"]),
        )
        conn.commit()
    return conversa["id"]


ORIGEM_PERMITIDA = {"Origin": "http://localhost:8000"}


def _habilitar(monkeypatch):
    monkeypatch.setattr(inbox_routes, "whatsapp_cloud_inbox_habilitado", lambda: True)


def _diagnostico_ok(*a, **k):
    return {"enabled": True, "configuration_complete": True, "webhook_ready": True, "configuration_errors": []}


def test_status_exige_sessao_admin(monkeypatch):
    _habilitar(monkeypatch)
    resp = client.get("/api/admin/whatsapp/status")
    assert resp.status_code == 401


def test_status_com_sessao_nao_admin_e_negado(monkeypatch):
    _habilitar(monkeypatch)
    token = _sessao_admin(perfil="vendedor")
    client.cookies.set("mistica_painel_sessao", token)
    try:
        resp = client.get("/api/admin/whatsapp/status")
        assert resp.status_code == 403
    finally:
        client.cookies.delete("mistica_painel_sessao")


def test_status_com_sessao_admin(monkeypatch):
    _habilitar(monkeypatch)
    monkeypatch.setattr(inbox_routes, "diagnostico_configuracao_whatsapp_cloud_inbox", _diagnostico_ok)
    token = _sessao_admin()
    client.cookies.set("mistica_painel_sessao", token)
    try:
        resp = client.get("/api/admin/whatsapp/status")
        assert resp.status_code == 200
        corpo = resp.json()
        assert corpo["ok"] is True
        assert "WHATSAPP_ACCESS_TOKEN" not in str(corpo)
        assert "token-de-teste" not in str(corpo)
    finally:
        client.cookies.delete("mistica_painel_sessao")


def test_listar_e_obter_conversa(monkeypatch):
    _habilitar(monkeypatch)
    conversa_id = _criar_conversa_com_inbound()
    token = _sessao_admin()
    client.cookies.set("mistica_painel_sessao", token)
    try:
        resp = client.get("/api/admin/whatsapp/conversations", params={"page_size": 5})
        assert resp.status_code == 200
        assert any(c["id"] == conversa_id for c in resp.json()["conversations"])

        resp_detalhe = client.get(f"/api/admin/whatsapp/conversations/{conversa_id}")
        assert resp_detalhe.status_code == 200
        assert resp_detalhe.json()["conversation"]["id"] == conversa_id
        assert "phone_e164" not in resp_detalhe.json()["conversation"]
    finally:
        client.cookies.delete("mistica_painel_sessao")


def test_conversa_inexistente_404(monkeypatch):
    _habilitar(monkeypatch)
    token = _sessao_admin()
    client.cookies.set("mistica_painel_sessao", token)
    try:
        resp = client.get("/api/admin/whatsapp/conversations/999999999")
        assert resp.status_code == 404
    finally:
        client.cookies.delete("mistica_painel_sessao")


def test_marcar_lida_zera_contador(monkeypatch):
    _habilitar(monkeypatch)
    conversa_id = _criar_conversa_com_inbound()
    with conectar() as conn:
        conn.execute("UPDATE whatsapp_conversations SET unread_count=3 WHERE id=?", (conversa_id,))
        conn.commit()
    token = _sessao_admin()
    client.cookies.set("mistica_painel_sessao", token)
    try:
        resp = client.post(f"/api/admin/whatsapp/conversations/{conversa_id}/read", headers=ORIGEM_PERMITIDA)
        assert resp.status_code == 200
        with conectar() as conn:
            linha = conn.execute("SELECT unread_count FROM whatsapp_conversations WHERE id=?", (conversa_id,)).fetchone()
        assert linha["unread_count"] == 0
    finally:
        client.cookies.delete("mistica_painel_sessao")


def test_atualizar_status_conversa(monkeypatch):
    _habilitar(monkeypatch)
    conversa_id = _criar_conversa_com_inbound()
    token = _sessao_admin()
    client.cookies.set("mistica_painel_sessao", token)
    try:
        resp = client.patch(f"/api/admin/whatsapp/conversations/{conversa_id}", json={"status": "resolved"}, headers=ORIGEM_PERMITIDA)
        assert resp.status_code == 200
        resp_invalido = client.patch(f"/api/admin/whatsapp/conversations/{conversa_id}", json={"status": "status_invalido"}, headers=ORIGEM_PERMITIDA)
        assert resp_invalido.status_code == 422
    finally:
        client.cookies.delete("mistica_painel_sessao")


def test_vincular_cliente_inexistente_404(monkeypatch):
    _habilitar(monkeypatch)
    conversa_id = _criar_conversa_com_inbound()
    token = _sessao_admin()
    client.cookies.set("mistica_painel_sessao", token)
    try:
        resp = client.post(f"/api/admin/whatsapp/conversations/{conversa_id}/link-customer", json={"customer_id": 999999999}, headers=ORIGEM_PERMITIDA)
        assert resp.status_code == 404
    finally:
        client.cookies.delete("mistica_painel_sessao")


class _ProviderFalso:
    def send_inbox_text(self, *, to, texto, reply_to_meta_message_id=None):
        return ResultadoEnvioWhatsApp(ok=True, provider_message_id=f"wamid.fake.{uuid.uuid4().hex}", status="sent")

    def send_template(self, *, to, template_name, language, components=()):
        return ResultadoEnvioWhatsApp(ok=True, provider_message_id=f"wamid.fake.{uuid.uuid4().hex}", status="sent")


def test_enviar_texto_dentro_da_janela(monkeypatch):
    _habilitar(monkeypatch)
    monkeypatch.setattr(inbox_routes, "construir_provider", lambda nome: _ProviderFalso())
    conversa_id = _criar_conversa_com_inbound()
    token = _sessao_admin()
    client.cookies.set("mistica_painel_sessao", token)
    try:
        chave = f"idem-{uuid.uuid4().hex}"
        resp = client.post(
            f"/api/admin/whatsapp/conversations/{conversa_id}/messages",
            json={"text": "Olá! Já verifico seu pedido."},
            headers={"Idempotency-Key": chave, **ORIGEM_PERMITIDA},
        )
        assert resp.status_code == 200
        assert resp.json()["ok"] is True
        with conectar() as conn:
            mensagem = conn.execute(
                "SELECT * FROM whatsapp_messages WHERE conversation_id=? AND direction='outbound'", (conversa_id,)
            ).fetchone()
        assert mensagem["status"] == "sent"
        assert mensagem["sent_by_admin"] == "Admin Teste"

        # Reenvio com a MESMA Idempotency-Key nunca cria uma segunda mensagem.
        resp2 = client.post(
            f"/api/admin/whatsapp/conversations/{conversa_id}/messages",
            json={"text": "Olá! Já verifico seu pedido."},
            headers={"Idempotency-Key": chave, **ORIGEM_PERMITIDA},
        )
        assert resp2.status_code == 200
        with conectar() as conn:
            total = conn.execute(
                "SELECT COUNT(*) AS n FROM whatsapp_messages WHERE conversation_id=? AND direction='outbound'", (conversa_id,)
            ).fetchone()
        assert total["n"] == 1
    finally:
        client.cookies.delete("mistica_painel_sessao")


def test_enviar_texto_fora_da_janela_exige_template(monkeypatch):
    _habilitar(monkeypatch)
    monkeypatch.setattr(inbox_routes, "construir_provider", lambda nome: _ProviderFalso())
    wa_id = "5511" + str(uuid.uuid4().int)[:9]
    with conectar() as conn:
        contato = upsert_contact(conn, wa_id=wa_id, profile_name="Cliente Antigo")
        conversa = obter_ou_criar_conversa(conn, contact_id=contato["id"])
        antigo = (datetime.now() - timedelta(hours=48)).isoformat(timespec="seconds")
        conn.execute("UPDATE whatsapp_conversations SET last_inbound_at=? WHERE id=?", (antigo, conversa["id"]))
        conn.commit()
    conversa_id = conversa["id"]

    token = _sessao_admin()
    client.cookies.set("mistica_painel_sessao", token)
    try:
        resp = client.post(
            f"/api/admin/whatsapp/conversations/{conversa_id}/messages",
            json={"text": "Mensagem livre fora da janela"},
            headers={"Idempotency-Key": f"idem-{uuid.uuid4().hex}", **ORIGEM_PERMITIDA},
        )
        assert resp.status_code == 422
        assert "template" in resp.json()["detail"].lower()
    finally:
        client.cookies.delete("mistica_painel_sessao")


def test_enviar_sem_texto_nem_template_e_rejeitado(monkeypatch):
    _habilitar(monkeypatch)
    monkeypatch.setattr(inbox_routes, "construir_provider", lambda nome: _ProviderFalso())
    conversa_id = _criar_conversa_com_inbound()
    token = _sessao_admin()
    client.cookies.set("mistica_painel_sessao", token)
    try:
        resp = client.post(
            f"/api/admin/whatsapp/conversations/{conversa_id}/messages",
            json={},
            headers={"Idempotency-Key": f"idem-{uuid.uuid4().hex}", **ORIGEM_PERMITIDA},
        )
        assert resp.status_code == 422
    finally:
        client.cookies.delete("mistica_painel_sessao")
