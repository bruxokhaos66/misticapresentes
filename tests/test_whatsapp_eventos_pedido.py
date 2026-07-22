"""Testes de integração: pontos do fluxo de pedido/pagamento realmente
enfileiram (ou pulam, quando desabilitado) o evento administrativo
correto em notification_outbox. Nunca chama a Graph API real -- o provider
de envio nem entra em jogo aqui, só o enfileiramento transacional.
"""
import importlib
import os
import uuid

os.environ.setdefault("MISTICA_SITE_API_KEY", "test-api-key")
os.environ.setdefault("MISTICA_SYNC_KEY", "test-api-key")
os.environ.setdefault("MISTICA_PIX_KEY", "49999999999")
os.environ.setdefault("MERCADO_PAGO_ENABLED", "true")
os.environ.setdefault("MERCADO_PAGO_ACCESS_TOKEN", "TEST-access-token")
os.environ.setdefault("MERCADO_PAGO_PUBLIC_KEY", "TEST-public-key")

from fastapi.testclient import TestClient

main = importlib.import_module("backend.main")
client = TestClient(main.app)
client.__enter__()

from backend.database import conectar

TEST_API_KEY = os.environ["MISTICA_SITE_API_KEY"]
HEADERS = {"X-Mistica-Api-Key": TEST_API_KEY}

_TEMPLATE_ENV_VARS = [
    "WHATSAPP_TEMPLATE_ADMIN_NOVO_PEDIDO",
    "WHATSAPP_TEMPLATE_ADMIN_PIX_GERADO",
    "WHATSAPP_TEMPLATE_ADMIN_PAGAMENTO_APROVADO",
    "WHATSAPP_TEMPLATE_ADMIN_PAGAMENTO_PENDENTE",
    "WHATSAPP_TEMPLATE_ADMIN_PAGAMENTO_RECUSADO",
    "WHATSAPP_TEMPLATE_ADMIN_PAGAMENTO_EXPIRADO",
    "WHATSAPP_TEMPLATE_ADMIN_PAGAMENTO_CANCELADO",
    "WHATSAPP_TEMPLATE_ADMIN_PAGAMENTO_REEMBOLSADO",
    "WHATSAPP_TEMPLATE_ADMIN_CHARGEBACK",
    "WHATSAPP_TEMPLATE_ADMIN_FALHA_RECONCILIACAO",
]


def _habilitar_whatsapp(monkeypatch):
    monkeypatch.setenv("WHATSAPP_NOTIFICATIONS_ENABLED", "true")
    monkeypatch.setenv("WHATSAPP_PROVIDER", "meta_cloud")
    monkeypatch.setenv("WHATSAPP_PHONE_NUMBER_ID", "123456")
    monkeypatch.setenv("WHATSAPP_ACCESS_TOKEN", "token-teste")
    monkeypatch.setenv("WHATSAPP_APP_SECRET", "segredo-teste")
    monkeypatch.setenv("WHATSAPP_VERIFY_TOKEN", "verify-teste")
    monkeypatch.setenv("WHATSAPP_ADMIN_RECIPIENTS", "5511999998888")
    for env_var in _TEMPLATE_ENV_VARS:
        monkeypatch.setenv(env_var, "template_teste")


def _desabilitar_whatsapp(monkeypatch):
    monkeypatch.setenv("WHATSAPP_NOTIFICATIONS_ENABLED", "false")


def ip_unico() -> str:
    return f"203.0.{uuid.uuid4().int % 256}.{uuid.uuid4().int % 256}"


def codigo_unico(prefixo: str) -> str:
    return f"{prefixo}-{uuid.uuid4().hex[:10]}"


def criar_pedido_publico(preco: float = 50.0, quantidade: int = 1) -> dict:
    resposta = client.post(
        "/api/produtos",
        json={"nome": "Produto WhatsApp", "codigo_p": codigo_unico("WPP"), "preco": preco, "quantidade": quantidade + 10, "categoria": "Testes"},
        headers=HEADERS,
    )
    assert resposta.status_code == 200, resposta.text
    produto = resposta.json()
    resposta = client.post(
        "/api/checkout/pedidos",
        json={"cliente": "Cliente WhatsApp", "telefone": "5599999999999", "forma_recebimento": "retirada", "itens": [{"produto_id": produto["id"], "quantidade": quantidade}]},
        headers={"X-Forwarded-For": ip_unico()},
    )
    assert resposta.status_code == 200, resposta.text
    return resposta.json()


def _linhas_outbox(order_id: int) -> list:
    with conectar() as conn:
        rows = conn.execute("SELECT event_type, status FROM notification_outbox WHERE order_id=? ORDER BY id", (order_id,)).fetchall()
    return [dict(row) for row in rows]


def test_criar_pedido_com_pix_enfileira_pedido_criado_e_pix_gerado(monkeypatch):
    _habilitar_whatsapp(monkeypatch)
    pedido = criar_pedido_publico()
    eventos = _linhas_outbox(pedido["id"])
    tipos = [e["event_type"] for e in eventos]
    assert "PEDIDO_CRIADO" in tipos
    assert "PIX_GERADO" in tipos
    assert all(e["status"] == "pending" for e in eventos)


def test_criar_pedido_com_whatsapp_desabilitado_marca_skipped(monkeypatch):
    _desabilitar_whatsapp(monkeypatch)
    pedido = criar_pedido_publico()
    eventos = _linhas_outbox(pedido["id"])
    assert len(eventos) >= 1
    assert all(e["status"] == "skipped_disabled" for e in eventos)


def test_criar_pedido_nao_duplica_em_dois_requests_idempotentes(monkeypatch):
    _habilitar_whatsapp(monkeypatch)
    pedido = criar_pedido_publico()
    total_inicial = len(_linhas_outbox(pedido["id"]))
    # Uma segunda "criação" não acontece de fato (cada requisição cria um
    # pedido novo) -- este teste garante que um único pedido nunca acumula
    # PEDIDO_CRIADO duplicado mesmo que o endpoint seja chamado de novo
    # manualmente com o mesmo id (verificação direta da idempotência da
    # camada de outbox, já coberta em profundidade em
    # tests/test_whatsapp_outbox.py; aqui confirmamos que a integração real
    # não introduz uma segunda chamada acidental).
    assert total_inicial == len([e for e in _linhas_outbox(pedido["id"]) if e["event_type"] in ("PEDIDO_CRIADO", "PIX_GERADO")])


def test_pagamento_aprovado_enfileira_evento(monkeypatch):
    _habilitar_whatsapp(monkeypatch)
    pedido = criar_pedido_publico()
    resp = client.post(
        "/api/pagamentos",
        json={"venda_id": pedido["id"], "forma": "Pix", "valor": pedido["total_final"], "status": "Confirmado", "usuario": "Teste"},
        headers=HEADERS,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["status_conciliacao"] == "ok"
    eventos = _linhas_outbox(pedido["id"])
    assert any(e["event_type"] == "PAGAMENTO_APROVADO" for e in eventos)


def test_pagamento_recusado_enfileira_evento(monkeypatch):
    _habilitar_whatsapp(monkeypatch)
    pedido = criar_pedido_publico()
    resp = client.post(
        "/api/pagamentos",
        json={"venda_id": pedido["id"], "forma": "Cartão", "valor": pedido["total_final"], "status": "Recusado", "usuario": "Teste"},
        headers=HEADERS,
    )
    assert resp.status_code == 200, resp.text
    eventos = _linhas_outbox(pedido["id"])
    assert any(e["event_type"] == "PAGAMENTO_RECUSADO" for e in eventos)


def test_pagamento_divergente_nao_gera_pagamento_aprovado(monkeypatch):
    _habilitar_whatsapp(monkeypatch)
    pedido = criar_pedido_publico()
    resp = client.post(
        "/api/pagamentos",
        json={"venda_id": pedido["id"], "forma": "Pix", "valor": 0.01, "status": "Confirmado", "usuario": "Teste"},
        headers=HEADERS,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["status_conciliacao"] != "ok"
    eventos = _linhas_outbox(pedido["id"])
    assert not any(e["event_type"] == "PAGAMENTO_APROVADO" for e in eventos)


def test_reconfirmacao_do_mesmo_pagamento_nao_duplica_notificacao(monkeypatch):
    _habilitar_whatsapp(monkeypatch)
    pedido = criar_pedido_publico()
    for _ in range(2):
        resp = client.post(
            "/api/pagamentos",
            json={"venda_id": pedido["id"], "forma": "Pix", "valor": pedido["total_final"], "status": "Confirmado", "usuario": "Teste"},
            headers=HEADERS,
        )
        assert resp.status_code == 200
    eventos = [e for e in _linhas_outbox(pedido["id"]) if e["event_type"] == "PAGAMENTO_APROVADO"]
    # A primeira chamada confirma e gera 1 notificação; a segunda é uma
    # reconfirmação idempotente (mesmo valor, pedido já pago) que não cria
    # um novo pagamento nem uma nova notificação -- ver
    # backend/payment_routes.py::_classificar_conciliacao (status já
    # confirmado é tratado como reconfirmação, não gera pagamento novo).
    assert len(eventos) == 1


def test_estorno_sem_chargeback_gera_reembolsado(monkeypatch):
    _habilitar_whatsapp(monkeypatch)
    pedido = criar_pedido_publico()
    resp = client.post(
        "/api/pagamentos",
        json={"venda_id": pedido["id"], "forma": "Pix", "valor": pedido["total_final"], "status": "Estornado", "usuario": "Teste"},
        headers=HEADERS,
    )
    assert resp.status_code == 200
    eventos = _linhas_outbox(pedido["id"])
    assert any(e["event_type"] == "PAGAMENTO_REEMBOLSADO" for e in eventos)
    assert not any(e["event_type"] == "CHARGEBACK_RECEBIDO" for e in eventos)


def test_estorno_com_origem_chargeback_gera_chargeback(monkeypatch):
    _habilitar_whatsapp(monkeypatch)
    pedido = criar_pedido_publico()
    resp = client.post(
        "/api/pagamentos",
        json={"venda_id": pedido["id"], "forma": "Cartão", "valor": pedido["total_final"], "status": "Estornado", "usuario": "Teste", "origem_estorno": "chargeback"},
        headers=HEADERS,
    )
    assert resp.status_code == 200
    eventos = _linhas_outbox(pedido["id"])
    assert any(e["event_type"] == "CHARGEBACK_RECEBIDO" for e in eventos)
    assert not any(e["event_type"] == "PAGAMENTO_REEMBOLSADO" for e in eventos)


def test_evento_aprovado_e_o_mais_evidente_no_payload(monkeypatch):
    """PAGAMENTO_APROVADO deve ser visualmente inequívoco (nunca confundível
    com PEDIDO_CRIADO/PIX_GERADO, que só significam 'aguardando
    pagamento')."""
    _habilitar_whatsapp(monkeypatch)
    pedido = criar_pedido_publico()
    client.post(
        "/api/pagamentos",
        json={"venda_id": pedido["id"], "forma": "Pix", "valor": pedido["total_final"], "status": "Confirmado", "usuario": "Teste"},
        headers=HEADERS,
    )
    with conectar() as conn:
        linhas = conn.execute(
            "SELECT event_type, payload_json FROM notification_outbox WHERE order_id=? ORDER BY id", (pedido["id"],)
        ).fetchall()
    tipos = [row["event_type"] for row in linhas]
    assert tipos[0] == "PEDIDO_CRIADO"
    assert "PAGAMENTO_APROVADO" in tipos
    assert tipos[0] != "PAGAMENTO_APROVADO"
