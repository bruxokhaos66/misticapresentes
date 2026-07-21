"""Testes de backend/whatsapp_provider.py -- assinatura de webhook, envio de
template (HTTP mockado, nunca chama a rede real), classificação de erros
transitório/permanente e parsing de callbacks de status."""
import hashlib
import hmac
import importlib
import os

import httpx
import pytest


def _reload_flags_and_provider(monkeypatch, **env):
    for chave in list(os.environ):
        if chave.startswith("WHATSAPP_"):
            monkeypatch.delenv(chave, raising=False)
    for chave, valor in env.items():
        monkeypatch.setenv(chave, valor)
    import backend.whatsapp_flags as flags_mod
    importlib.reload(flags_mod)
    import backend.whatsapp_provider as provider_mod
    importlib.reload(provider_mod)
    return provider_mod


def test_disabled_provider_nunca_chama_rede(monkeypatch):
    provider_mod = _reload_flags_and_provider(monkeypatch)
    provider = provider_mod.DisabledWhatsAppProvider()
    resultado = provider.send_template(to="5511999998888", template_name="x", language="pt_BR")
    assert resultado.ok is False
    assert resultado.status == "skipped_disabled"
    assert provider.validate_webhook_signature(b"{}", {}) is False
    assert provider.parse_delivery_webhook({}) == []


def test_construir_provider_fabrica(monkeypatch):
    provider_mod = _reload_flags_and_provider(monkeypatch, WHATSAPP_PROVIDER="meta_cloud")
    assert isinstance(provider_mod.construir_provider("meta_cloud"), provider_mod.MetaWhatsAppCloudProvider)
    assert isinstance(provider_mod.construir_provider("disabled"), provider_mod.DisabledWhatsAppProvider)
    assert isinstance(provider_mod.construir_provider("desconhecido"), provider_mod.DisabledWhatsAppProvider)


def test_validar_assinatura_correta(monkeypatch):
    provider_mod = _reload_flags_and_provider(monkeypatch, WHATSAPP_APP_SECRET="segredo-teste")
    provider = provider_mod.MetaWhatsAppCloudProvider()
    corpo = b'{"entry": []}'
    assinatura = hmac.new(b"segredo-teste", corpo, hashlib.sha256).hexdigest()
    headers = {"X-Hub-Signature-256": f"sha256={assinatura}"}
    assert provider.validate_webhook_signature(corpo, headers) is True


def test_validar_assinatura_incorreta(monkeypatch):
    provider_mod = _reload_flags_and_provider(monkeypatch, WHATSAPP_APP_SECRET="segredo-teste")
    provider = provider_mod.MetaWhatsAppCloudProvider()
    corpo = b'{"entry": []}'
    headers = {"X-Hub-Signature-256": "sha256=00000000"}
    assert provider.validate_webhook_signature(corpo, headers) is False


def test_validar_assinatura_sem_segredo_configurado(monkeypatch):
    provider_mod = _reload_flags_and_provider(monkeypatch)
    provider = provider_mod.MetaWhatsAppCloudProvider()
    assert provider.validate_webhook_signature(b"{}", {"X-Hub-Signature-256": "sha256=abc"}) is False


def test_validar_assinatura_header_ausente(monkeypatch):
    provider_mod = _reload_flags_and_provider(monkeypatch, WHATSAPP_APP_SECRET="segredo-teste")
    provider = provider_mod.MetaWhatsAppCloudProvider()
    assert provider.validate_webhook_signature(b"{}", {}) is False


def test_parse_delivery_webhook_extrai_status(monkeypatch):
    provider_mod = _reload_flags_and_provider(monkeypatch)
    provider = provider_mod.MetaWhatsAppCloudProvider()
    payload = {
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "statuses": [
                                {"id": "wamid.123", "status": "delivered", "timestamp": "1700000000"},
                                {"id": "wamid.124", "status": "read", "timestamp": "1700000010"},
                                {"id": "wamid.125", "status": "ignorado_desconhecido"},
                            ]
                        }
                    }
                ]
            }
        ]
    }
    resultados = provider.parse_delivery_webhook(payload)
    assert len(resultados) == 2
    assert resultados[0].provider_message_id == "wamid.123"
    assert resultados[0].status == "delivered"
    assert resultados[1].status == "read"


def test_parse_delivery_webhook_payload_malformado_nao_levanta(monkeypatch):
    provider_mod = _reload_flags_and_provider(monkeypatch)
    provider = provider_mod.MetaWhatsAppCloudProvider()
    assert provider.parse_delivery_webhook({"entry": "nao-e-uma-lista"}) == []
    assert provider.parse_delivery_webhook({}) == []


def test_send_template_sucesso(monkeypatch):
    provider_mod = _reload_flags_and_provider(
        monkeypatch,
        WHATSAPP_PHONE_NUMBER_ID="123",
        WHATSAPP_ACCESS_TOKEN="token-teste",
    )
    provider = provider_mod.MetaWhatsAppCloudProvider()

    def _fake_post(self, url, json=None):
        return httpx.Response(200, json={"messages": [{"id": "wamid.abc"}]})

    monkeypatch.setattr(httpx.Client, "post", _fake_post)
    resultado = provider.send_template(to="5511999998888", template_name="admin_novo_pedido", language="pt_BR", components=[provider_mod.ComponenteTemplate(texto="123")])
    assert resultado.ok is True
    assert resultado.provider_message_id == "wamid.abc"


def test_send_template_erro_permanente_token_invalido(monkeypatch):
    provider_mod = _reload_flags_and_provider(
        monkeypatch,
        WHATSAPP_PHONE_NUMBER_ID="123",
        WHATSAPP_ACCESS_TOKEN="token-teste",
    )
    provider = provider_mod.MetaWhatsAppCloudProvider()

    def _fake_post(self, url, json=None):
        return httpx.Response(401, json={"error": {"code": 190, "message": "token invalido com detalhe sensivel"}})

    monkeypatch.setattr(httpx.Client, "post", _fake_post)
    with pytest.raises(provider_mod.WhatsAppEnvioPermanente) as exc_info:
        provider.send_template(to="5511999998888", template_name="x", language="pt_BR")
    assert "token invalido com detalhe sensivel" not in str(exc_info.value)


def test_send_template_erro_transitorio_rate_limit(monkeypatch):
    provider_mod = _reload_flags_and_provider(
        monkeypatch,
        WHATSAPP_PHONE_NUMBER_ID="123",
        WHATSAPP_ACCESS_TOKEN="token-teste",
    )
    provider = provider_mod.MetaWhatsAppCloudProvider()

    def _fake_post(self, url, json=None):
        return httpx.Response(429, headers={"Retry-After": "30"}, json={"error": {"code": 4}})

    monkeypatch.setattr(httpx.Client, "post", _fake_post)
    with pytest.raises(provider_mod.WhatsAppEnvioTransitorio) as exc_info:
        provider.send_template(to="5511999998888", template_name="x", language="pt_BR")
    assert exc_info.value.retry_after_seconds == 30.0


def test_send_template_erro_transitorio_5xx(monkeypatch):
    provider_mod = _reload_flags_and_provider(
        monkeypatch,
        WHATSAPP_PHONE_NUMBER_ID="123",
        WHATSAPP_ACCESS_TOKEN="token-teste",
    )
    provider = provider_mod.MetaWhatsAppCloudProvider()

    def _fake_post(self, url, json=None):
        return httpx.Response(503, json={})

    monkeypatch.setattr(httpx.Client, "post", _fake_post)
    with pytest.raises(provider_mod.WhatsAppEnvioTransitorio):
        provider.send_template(to="5511999998888", template_name="x", language="pt_BR")


def test_send_template_timeout_e_transitorio(monkeypatch):
    provider_mod = _reload_flags_and_provider(
        monkeypatch,
        WHATSAPP_PHONE_NUMBER_ID="123",
        WHATSAPP_ACCESS_TOKEN="token-teste",
    )
    provider = provider_mod.MetaWhatsAppCloudProvider()

    def _fake_post(self, url, json=None):
        raise httpx.TimeoutException("timeout")

    monkeypatch.setattr(httpx.Client, "post", _fake_post)
    with pytest.raises(provider_mod.WhatsAppEnvioTransitorio):
        provider.send_template(to="5511999998888", template_name="x", language="pt_BR")


def test_send_template_sem_credenciais_e_permanente(monkeypatch):
    provider_mod = _reload_flags_and_provider(monkeypatch)
    provider = provider_mod.MetaWhatsAppCloudProvider()
    with pytest.raises(provider_mod.WhatsAppEnvioPermanente):
        provider.send_template(to="5511999998888", template_name="x", language="pt_BR")


def test_send_text_nao_suportado(monkeypatch):
    provider_mod = _reload_flags_and_provider(monkeypatch)
    provider = provider_mod.MetaWhatsAppCloudProvider()
    with pytest.raises(provider_mod.WhatsAppEnvioPermanente):
        provider.send_text(to="5511999998888", texto="oi")
