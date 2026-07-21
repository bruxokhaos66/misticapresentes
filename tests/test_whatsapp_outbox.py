"""Testes de backend/whatsapp_outbox.py -- enfileiramento transacional,
idempotência e comportamento com o recurso desabilitado. Usa o banco de
teste isolado (ver tests/conftest.py), nunca chama rede."""
import importlib
import os
import uuid

os.environ.setdefault("MISTICA_SITE_API_KEY", "test-api-key")

from database.migrations import init_db

init_db()

from backend.database import conectar


def _reload_com_config(monkeypatch, habilitado: bool, destinatarios="5511999998888,5511977776666"):
    for chave in list(os.environ):
        if chave.startswith("WHATSAPP_"):
            monkeypatch.delenv(chave, raising=False)
    if habilitado:
        monkeypatch.setenv("WHATSAPP_NOTIFICATIONS_ENABLED", "true")
        monkeypatch.setenv("WHATSAPP_PROVIDER", "meta_cloud")
        monkeypatch.setenv("WHATSAPP_PHONE_NUMBER_ID", "123456")
        monkeypatch.setenv("WHATSAPP_ACCESS_TOKEN", "token-teste")
        monkeypatch.setenv("WHATSAPP_APP_SECRET", "segredo-teste")
        monkeypatch.setenv("WHATSAPP_VERIFY_TOKEN", "verify-teste")
        monkeypatch.setenv("WHATSAPP_ADMIN_RECIPIENTS", destinatarios)
        for evento, env_var in {
            "PEDIDO_CRIADO": "WHATSAPP_TEMPLATE_ADMIN_NOVO_PEDIDO",
            "PIX_GERADO": "WHATSAPP_TEMPLATE_ADMIN_PIX_GERADO",
            "PAGAMENTO_APROVADO": "WHATSAPP_TEMPLATE_ADMIN_PAGAMENTO_APROVADO",
            "PAGAMENTO_PENDENTE": "WHATSAPP_TEMPLATE_ADMIN_PAGAMENTO_PENDENTE",
            "PAGAMENTO_RECUSADO": "WHATSAPP_TEMPLATE_ADMIN_PAGAMENTO_RECUSADO",
            "PAGAMENTO_EXPIRADO": "WHATSAPP_TEMPLATE_ADMIN_PAGAMENTO_EXPIRADO",
            "PAGAMENTO_CANCELADO": "WHATSAPP_TEMPLATE_ADMIN_PAGAMENTO_CANCELADO",
            "PAGAMENTO_REEMBOLSADO": "WHATSAPP_TEMPLATE_ADMIN_PAGAMENTO_REEMBOLSADO",
            "CHARGEBACK_RECEBIDO": "WHATSAPP_TEMPLATE_ADMIN_CHARGEBACK",
            "FALHA_DE_RECONCILIACAO": "WHATSAPP_TEMPLATE_ADMIN_FALHA_RECONCILIACAO",
        }.items():
            monkeypatch.setenv(env_var, f"template_{evento.lower()}")
    import backend.whatsapp_flags as flags_mod
    importlib.reload(flags_mod)
    import backend.whatsapp_events as events_mod
    importlib.reload(events_mod)
    import backend.whatsapp_outbox as outbox_mod
    importlib.reload(outbox_mod)
    return outbox_mod, events_mod


def _pedido_id() -> int:
    return abs(hash(uuid.uuid4())) % 1_000_000 + 1


def test_desabilitado_registra_uma_linha_skipped(monkeypatch):
    outbox_mod, events_mod = _reload_com_config(monkeypatch, habilitado=False)
    pedido_id = _pedido_id()
    with conectar() as conn:
        novas = outbox_mod.enfileirar_evento_whatsapp(
            conn, evento=events_mod.EVENTO_PEDIDO_CRIADO, pedido_id=pedido_id,
            sufixo_idempotencia="unico", contexto=events_mod.ContextoEventoPedido(pedido_id=pedido_id, valor=100.0),
        )
        conn.commit()
    assert novas == 1
    with conectar() as conn:
        linhas = conn.execute("SELECT status, recipient_reference FROM notification_outbox WHERE order_id=?", (pedido_id,)).fetchall()
    assert len(linhas) == 1
    assert linhas[0]["status"] == "skipped_disabled"
    assert linhas[0]["recipient_reference"] is None


def test_habilitado_cria_uma_linha_por_destinatario(monkeypatch):
    outbox_mod, events_mod = _reload_com_config(monkeypatch, habilitado=True)
    pedido_id = _pedido_id()
    with conectar() as conn:
        novas = outbox_mod.enfileirar_evento_whatsapp(
            conn, evento=events_mod.EVENTO_PEDIDO_CRIADO, pedido_id=pedido_id,
            sufixo_idempotencia="unico", contexto=events_mod.ContextoEventoPedido(pedido_id=pedido_id, valor=100.0, forma_pagamento="Pix", entrega="Retirada"),
        )
        conn.commit()
    assert novas == 2  # dois destinatários configurados
    with conectar() as conn:
        linhas = conn.execute("SELECT status, recipient_reference, template_name FROM notification_outbox WHERE order_id=?", (pedido_id,)).fetchall()
    assert len(linhas) == 2
    for linha in linhas:
        assert linha["status"] == "pending"
        assert linha["recipient_reference"] is not None
        assert linha["template_name"] == "template_pedido_criado"


def test_idempotencia_mesmo_sufixo_nao_duplica(monkeypatch):
    outbox_mod, events_mod = _reload_com_config(monkeypatch, habilitado=True, destinatarios="5511999998888")
    pedido_id = _pedido_id()
    contexto = events_mod.ContextoEventoPedido(pedido_id=pedido_id, valor=50.0)
    with conectar() as conn:
        primeira = outbox_mod.enfileirar_evento_whatsapp(conn, evento=events_mod.EVENTO_PAGAMENTO_APROVADO, pedido_id=pedido_id, sufixo_idempotencia="pagamento-1", contexto=contexto)
        conn.commit()
    with conectar() as conn:
        segunda = outbox_mod.enfileirar_evento_whatsapp(conn, evento=events_mod.EVENTO_PAGAMENTO_APROVADO, pedido_id=pedido_id, sufixo_idempotencia="pagamento-1", contexto=contexto)
        conn.commit()
    assert primeira == 1
    assert segunda == 0
    with conectar() as conn:
        total = conn.execute("SELECT COUNT(*) AS n FROM notification_outbox WHERE order_id=? AND event_type=?", (pedido_id, events_mod.EVENTO_PAGAMENTO_APROVADO)).fetchone()
    assert total["n"] == 1


def test_sufixo_diferente_gera_evento_novo(monkeypatch):
    outbox_mod, events_mod = _reload_com_config(monkeypatch, habilitado=True, destinatarios="5511999998888")
    pedido_id = _pedido_id()
    contexto = events_mod.ContextoEventoPedido(pedido_id=pedido_id, valor=50.0)
    with conectar() as conn:
        outbox_mod.enfileirar_evento_whatsapp(conn, evento=events_mod.EVENTO_PAGAMENTO_APROVADO, pedido_id=pedido_id, sufixo_idempotencia="tentativa-1", contexto=contexto)
        conn.commit()
    with conectar() as conn:
        segunda = outbox_mod.enfileirar_evento_whatsapp(conn, evento=events_mod.EVENTO_PAGAMENTO_APROVADO, pedido_id=pedido_id, sufixo_idempotencia="tentativa-2", contexto=contexto)
        conn.commit()
    assert segunda == 1


def test_payload_sanitizado_nao_contem_pii(monkeypatch):
    outbox_mod, events_mod = _reload_com_config(monkeypatch, habilitado=True, destinatarios="5511999998888")
    pedido_id = _pedido_id()
    contexto = events_mod.ContextoEventoPedido(pedido_id=pedido_id, valor=42.5, forma_pagamento="Pix", entrega="Entrega")
    with conectar() as conn:
        outbox_mod.enfileirar_evento_whatsapp(conn, evento=events_mod.EVENTO_PEDIDO_CRIADO, pedido_id=pedido_id, sufixo_idempotencia="unico", contexto=contexto)
        conn.commit()
    with conectar() as conn:
        linha = conn.execute("SELECT payload_json FROM notification_outbox WHERE order_id=?", (pedido_id,)).fetchone()
    payload = linha["payload_json"]
    for termo_proibido in ("cpf", "email", "telefone", "token", "senha", "cardholder", "@"):
        assert termo_proibido not in payload.lower()


def test_resolver_numero_por_referencia(monkeypatch):
    outbox_mod, events_mod = _reload_com_config(monkeypatch, habilitado=True, destinatarios="5511999998888")
    referencia = outbox_mod._referencia_destinatario("5511999998888")
    assert outbox_mod.resolver_numero_por_referencia(referencia) == "5511999998888"
    assert outbox_mod.resolver_numero_por_referencia("admin:naoexiste0000000") is None
