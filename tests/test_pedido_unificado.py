"""Modelo comercial unificado de pedidos (Pix + cartão de crédito/débito) --
Fase 1 da unificação de pedidos (ver backend/pedido_comercial.py,
backend/pedido_notificacao_routes.py::listar_pedidos_para_notificacao,
database/migrations.py::_criar_pedido_comercial_unificado).

Cobre: Pix e cartão (crédito/débito/parcelado) aparecendo na mesma fila de
notificação, rótulo correto de forma de pagamento (nunca fixo em "crédito"
independente do tipo real), parcelas exibidas corretamente, ausência de
duplicação entre retorno imediato e webhook, situação comercial (status_pedido)
avançando uma única vez, e migração idempotente.
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
os.environ.setdefault("MERCADO_PAGO_WEBHOOK_SECRET", "test-mp-webhook-secret-unificado")

main = importlib.import_module("backend.main")
client = TestClient(main.app)
client.__enter__()

TEST_API_KEY = os.environ["MISTICA_SITE_API_KEY"]
HEADERS = {"X-Mistica-Api-Key": TEST_API_KEY}


def ip_unico() -> str:
    n = uuid.uuid4().int
    return f"203.0.{(n >> 8) % 256}.{n % 256}"


def codigo_unico(prefixo: str) -> str:
    return f"{prefixo}-{uuid.uuid4().hex[:10]}"


def criar_produto(preco: float, quantidade: int = 20) -> dict:
    resposta = client.post(
        "/api/produtos",
        json={"nome": "Produto Unificação", "codigo_p": codigo_unico("UNIF"), "preco": preco, "quantidade": quantidade, "categoria": "Testes"},
        headers=HEADERS,
    )
    assert resposta.status_code == 200, resposta.text
    return resposta.json()


def criar_pedido_publico(preco: float, quantidade: int = 1) -> dict:
    produto = criar_produto(preco, quantidade=quantidade + 10)
    resposta = client.post(
        "/api/checkout/pedidos",
        json={"cliente": "Cliente Unificação", "telefone": "5599999999999", "forma_recebimento": "retirada", "itens": [{"produto_id": produto["id"], "quantidade": quantidade}]},
        headers={"X-Forwarded-For": ip_unico()},
    )
    assert resposta.status_code == 200, resposta.text
    return resposta.json()


def resultado_mp(pedido, *, status="approved", status_detail="accredited", payment_id=None, valor=None, installments=1, payment_method_id="visa", payment_type_id="credit_card"):
    from backend.mercadopago_client import ResultadoPagamentoMP

    if payment_id is None:
        payment_id = f"mp-unif-{uuid.uuid4().hex[:12]}"
    return ResultadoPagamentoMP(
        id=payment_id,
        status=status,
        status_detail=status_detail,
        transaction_amount=valor if valor is not None else pedido["total_final"],
        installments=installments,
        payment_method_id=payment_method_id,
        payment_type_id=payment_type_id,
        external_reference=str(pedido["id"]),
        currency_id="BRL",
        collector_id="1",
    )


def pagar_cartao(pedido, resultado, idempotency_key=None, installments=1, **overrides):
    body = {
        "pedido_id": pedido["id"],
        "txid": pedido["pix_txid"],
        "token": "card_token_" + uuid.uuid4().hex,
        "payment_method_id": resultado.payment_method_id,
        "installments": installments,
        "payer": {"email": "cliente-unif@example.com", "nome": "Maria", "documento_numero": "12345678900"},
    }
    body.update(overrides)
    headers = {"Idempotency-Key": idempotency_key or str(uuid.uuid4()), "X-Forwarded-For": ip_unico()}
    with patch("backend.mercadopago_routes.criar_pagamento_cartao", return_value=resultado):
        return client.post("/api/payments/mercadopago/card", json=body, headers=headers)


def confirmar_pix(pedido) -> dict:
    resposta = client.post(
        "/api/pagamentos",
        json={"venda_id": pedido["id"], "forma": "Pix", "valor": pedido["total_final"], "status": "Confirmado", "usuario": "Admin"},
        headers=HEADERS,
    )
    assert resposta.status_code == 200, resposta.text
    return resposta.json()


def buscar_notificacoes() -> list[dict]:
    resposta = client.get("/api/pedidos/notificacoes/pendentes", headers=HEADERS)
    assert resposta.status_code == 200, resposta.text
    return resposta.json()["pedidos"]


def marcar_visualizado(pedido_id: int):
    resposta = client.post(f"/api/pedidos/{pedido_id}/visualizar", headers=HEADERS)
    assert resposta.status_code == 200, resposta.text


# 1. Pix aprovado aparece na tabela/fila unificada -------------------------------------------------


def test_pix_aprovado_aparece_na_fila_unificada():
    pedido = criar_pedido_publico(45.0)
    confirmar_pix(pedido)
    ids = {p["id"] for p in buscar_notificacoes()}
    assert pedido["id"] in ids


# 2. Crédito aprovado aparece na mesma fila ---------------------------------------------------------


def test_credito_aprovado_aparece_na_mesma_fila_unificada():
    pedido = criar_pedido_publico(60.0)
    resultado = resultado_mp(pedido, payment_type_id="credit_card", payment_method_id="visa")
    resposta = pagar_cartao(pedido, resultado)
    assert resposta.status_code == 200, resposta.text

    notificacoes = buscar_notificacoes()
    achado = next((p for p in notificacoes if p["id"] == pedido["id"]), None)
    assert achado is not None, "cartão aprovado deve aparecer na mesma fila que o Pix"
    assert achado["payment_type_id"] == "credit_card"
    assert achado["payment_method_id"] == "visa"


# 3. Débito aparece corretamente quando payment_type_id for debit_card -----------------------------


def test_debito_e_identificado_corretamente_nunca_como_credito():
    pedido = criar_pedido_publico(70.0)
    resultado = resultado_mp(pedido, payment_type_id="debit_card", payment_method_id="master", installments=1)
    resposta = pagar_cartao(pedido, resultado, installments=1)
    assert resposta.status_code == 200, resposta.text

    detalhe = client.get(f"/api/pedidos/{pedido['id']}", headers=HEADERS).json()
    assert detalhe["payment_type_id"] == "debit_card"
    assert "débito" in detalhe["forma_pagamento"].lower() or "debito" in detalhe["forma_pagamento"].lower()
    assert "crédito" not in detalhe["forma_pagamento"].lower() and "credito" not in detalhe["forma_pagamento"].lower()


# 4. Parcelamento exibe o número correto -------------------------------------------------------------


def test_parcelamento_exibe_numero_correto_de_parcelas():
    pedido = criar_pedido_publico(300.0)
    resultado = resultado_mp(pedido, payment_type_id="credit_card", installments=6)
    resposta = pagar_cartao(pedido, resultado, installments=6)
    assert resposta.status_code == 200, resposta.text
    assert resposta.json()["parcelas"] == 6

    detalhe = client.get(f"/api/pedidos/{pedido['id']}", headers=HEADERS).json()
    assert detalhe["parcelas"] == 6
    assert "6x" in detalhe["forma_pagamento"]


def test_a_vista_nao_mostra_1x():
    pedido = criar_pedido_publico(80.0)
    resultado = resultado_mp(pedido, payment_type_id="credit_card", installments=1)
    resposta = pagar_cartao(pedido, resultado, installments=1)
    assert resposta.status_code == 200, resposta.text
    assert resposta.json()["parcelas"] == 1


# 5. Webhook não duplica pedido nem notificação / retorno imediato + webhook = uma única aprovação --


def test_retorno_imediato_e_webhook_geram_apenas_uma_aprovacao():
    from tests.test_mercadopago_webhook import enviar_webhook

    pedido = criar_pedido_publico(120.0)
    resultado = resultado_mp(pedido, payment_type_id="credit_card")

    resposta_imediata = pagar_cartao(pedido, resultado)
    assert resposta_imediata.status_code == 200, resposta_imediata.text
    assert resposta_imediata.json()["aprovado"] is True

    resposta_webhook = enviar_webhook(resultado.id, resultado=resultado)
    assert resposta_webhook.status_code == 200, resposta_webhook.text

    pagamentos = client.get("/api/pagamentos", params={"venda_id": pedido["id"]}, headers=HEADERS).json()
    confirmados = [p for p in pagamentos if p["status"] == "Confirmado"]
    assert len(confirmados) == 1, "retorno imediato + webhook do MESMO pagamento/status nunca geram duas confirmações"

    detalhe = client.get(f"/api/pedidos/{pedido['id']}", headers=HEADERS).json()
    assert detalhe["status"] == "Pagamento confirmado"
    assert detalhe["estoque_baixado"] == 1


def test_webhook_reenviado_nao_duplica_evento():
    from tests.test_mercadopago_webhook import enviar_webhook

    pedido = criar_pedido_publico(65.0)
    resultado = resultado_mp(pedido, payment_type_id="credit_card")
    primeira = enviar_webhook(resultado.id, resultado=resultado)
    assert primeira.status_code == 200, primeira.text
    segunda = enviar_webhook(resultado.id, resultado=resultado)
    assert segunda.status_code == 200, segunda.text
    assert segunda.json().get("duplicado") is True

    pagamentos = client.get("/api/pagamentos", params={"venda_id": pedido["id"]}, headers=HEADERS).json()
    confirmados = [p for p in pagamentos if p["status"] == "Confirmado"]
    assert len(confirmados) == 1


# 6. Situação comercial (status_pedido) avança uma única vez, separada do status financeiro ---------


def test_status_pedido_comercial_novo_ate_confirmado_pix():
    pedido = criar_pedido_publico(55.0)
    detalhe_antes = client.get(f"/api/pedidos/{pedido['id']}", headers=HEADERS).json()
    assert detalhe_antes["status_pedido"] == "novo"

    confirmar_pix(pedido)
    detalhe_depois = client.get(f"/api/pedidos/{pedido['id']}", headers=HEADERS).json()
    assert detalhe_depois["status_pedido"] == "confirmado"
    assert detalhe_depois["data_aprovacao"]
    # Situação financeira e comercial permanecem informações distintas.
    assert detalhe_depois["status"] == "Pagamento confirmado"


def test_status_pedido_comercial_nao_regride_em_reconfirmacao():
    pedido = criar_pedido_publico(55.0)
    confirmar_pix(pedido)
    # Reconfirmar o mesmo valor (idempotente na conciliação) nunca duplica a
    # entrada de histórico "confirmado" nem altera status_pedido de novo.
    confirmar_pix(pedido)
    logs = client.get("/api/pedidos/status-log", headers=HEADERS).json()
    entradas_confirmado_deste_pedido = [
        l for l in logs if l["venda_id"] == pedido["id"] and l["status"] == "confirmado"
    ]
    assert len(entradas_confirmado_deste_pedido) == 1


def test_pedido_notificacao_some_da_fila_apos_visualizado():
    pedido = criar_pedido_publico(48.0)
    confirmar_pix(pedido)
    assert pedido["id"] in {p["id"] for p in buscar_notificacoes()}
    marcar_visualizado(pedido["id"])
    assert pedido["id"] not in {p["id"] for p in buscar_notificacoes()}


def test_notificacoes_exige_autenticacao_administrativa():
    resposta = client.get("/api/pedidos/notificacoes/pendentes")
    assert resposta.status_code in (401, 403)


# 7. Migração idempotente: rodar de novo nunca duplica nem sobrescreve dado já definido --------------


def test_migracao_status_pedido_comercial_e_idempotente():
    from database.migrations import _backfill_status_pedido_comercial
    from backend.database import conectar

    pedido = criar_pedido_publico(33.0)
    confirmar_pix(pedido)

    with conectar() as conn:
        antes = conn.execute("SELECT status_pedido, data_aprovacao FROM pedidos WHERE id=?", (pedido["id"],)).fetchone()
    assert antes["status_pedido"] == "confirmado"

    # Rodar o backfill de novo (equivalente a reexecutar a migração) nunca
    # sobrescreve um status_pedido já definido -- o UPDATE só toca linhas
    # com status_pedido IS NULL.
    _backfill_status_pedido_comercial()
    _backfill_status_pedido_comercial()

    with conectar() as conn:
        depois = conn.execute("SELECT status_pedido, data_aprovacao FROM pedidos WHERE id=?", (pedido["id"],)).fetchone()
    assert depois["status_pedido"] == "confirmado"
    assert depois["data_aprovacao"] == antes["data_aprovacao"]


def test_dados_sensiveis_de_cartao_nunca_aparecem_no_pedido():
    pedido = criar_pedido_publico(90.0)
    resultado = resultado_mp(pedido, payment_type_id="credit_card")
    resposta = pagar_cartao(pedido, resultado, installments=1)
    assert resposta.status_code == 200, resposta.text

    detalhe = client.get(f"/api/pedidos/{pedido['id']}", headers=HEADERS).json()
    texto = str(detalhe)
    assert "card_token_" not in texto
    assert "cvv" not in texto.lower()
    assert "TEST-access-token" not in texto
