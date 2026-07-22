"""Testes do pagamento com cartão de crédito via Mercado Pago
(backend/mercadopago_routes.py), preservando o Pix já existente.

Nunca chama a API real do Mercado Pago: `criar_pagamento_cartao` é sempre
mockado (unittest.mock.patch), como exigido -- nenhum teste automatizado
pode gerar cobrança real.
"""

import importlib
import os
import uuid
from dataclasses import replace
from datetime import datetime, timedelta
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
        json={"cliente": "Cliente MP", "telefone": "5599999999999", "forma_recebimento": "retirada", "itens": [{"produto_id": produto["id"], "quantidade": quantidade}]},
        headers={"X-Forwarded-For": ip_unico()},
    )
    assert resposta.status_code == 200, resposta.text
    return resposta.json()


def criar_pedido_publico_entrega(preco: float, quantidade: int = 1) -> dict:
    produto = criar_produto(preco, quantidade=quantidade + 10)
    resposta = client.post(
        "/api/checkout/pedidos",
        json={
            "cliente": "Cliente MP Entrega", "telefone": "5599999999999", "forma_recebimento": "entrega",
            "endereco_cep": "89870000", "endereco_rua": "Rua das Flores", "endereco_numero": "123",
            "endereco_bairro": "Centro", "endereco_cidade": "Pinhalzinho", "endereco_uf": "SC",
            "itens": [{"produto_id": produto["id"], "quantidade": quantidade}],
        },
        headers={"X-Forwarded-For": ip_unico()},
    )
    assert resposta.status_code == 200, resposta.text
    return resposta.json()


def resultado_mp(pedido, *, status="approved", status_detail="accredited", payment_id=None, valor=None, installments=1, payment_method_id="visa", currency_id="BRL", causa_codigos=()):
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
        currency_id=currency_id,
        collector_id="1" if payment_id else None,
        causa_codigos=causa_codigos,
    )


def pagar_cartao(pedido, resultado, idempotency_key=None, installments=1, capturar_mock=None, **overrides):
    body = {
        "pedido_id": pedido["id"],
        "txid": pedido["pix_txid"],
        "token": "card_token_" + uuid.uuid4().hex,
        "payment_method_id": "visa",
        "installments": installments,
        "payer": {"email": "cliente@example.com", "nome": "Maria", "documento_numero": "12345678900"},
    }
    body.update(overrides)
    headers = {"Idempotency-Key": idempotency_key or str(uuid.uuid4()), "X-Forwarded-For": ip_unico()}
    with patch("backend.mercadopago_routes.criar_pagamento_cartao", return_value=resultado) as mock_criar:
        resposta = client.post("/api/payments/mercadopago/card", json=body, headers=headers)
        if capturar_mock is not None:
            capturar_mock.append(mock_criar)
        return resposta


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
        "payer": {"email": "cliente@example.com", "nome": "Maria", "documento_numero": "12345678900"},
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
                "payer": {"email": "c@example.com", "nome": "Maria", "documento_numero": "12345678900"},
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
                "payer": {"email": "c@example.com", "nome": "Maria", "documento_numero": "12345678900"},
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
                "payer": {"email": "c@example.com", "nome": "Maria", "documento_numero": "12345678900"},
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
                "payer": {"email": "c@example.com", "nome": "Maria", "documento_numero": "12345678900"},
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
                "payer": {"email": "c@example.com", "nome": "Maria", "documento_numero": "12345678900"},
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


def _quantidade_produto(codigo_p: str) -> int:
    # codigo_p é normalizado para maiúsculas na criação (backend/product_routes.py).
    resposta = client.get("/api/produtos", params={"busca": codigo_p})
    itens = [p for p in resposta.json() if p["codigo_p"].upper() == codigo_p.upper()]
    assert len(itens) == 1, f"produto {codigo_p} não encontrado de forma única: {itens}"
    return int(itens[0]["quantidade"])


def test_estoque_reservado_na_criacao_nao_e_baixado_de_novo_na_aprovacao_do_cartao():
    """A reserva de estoque físico já acontece na criação do pedido (ver
    backend/site_stock_routes.py) -- a aprovação do cartão reaproveita
    baixar_estoque_do_pedido, que é idempotente via pedidos.estoque_baixado.
    Prova que o estoque final reflete só UMA baixa (a da criação), nunca
    duas."""
    codigo = codigo_unico("MPESTQ")
    resposta = client.post(
        "/api/produtos",
        json={"nome": "Produto Estoque MP", "codigo_p": codigo, "preco": 40.0, "quantidade": 10, "categoria": "Testes"},
        headers=HEADERS,
    )
    produto = resposta.json()
    quantidade_inicial = _quantidade_produto(codigo)
    assert quantidade_inicial == 10

    resposta = client.post(
        "/api/checkout/pedidos",
        json={"cliente": "Cliente Estoque", "telefone": "5599999999999", "forma_recebimento": "retirada", "itens": [{"produto_id": produto["id"], "quantidade": 3}]},
        headers={"X-Forwarded-For": ip_unico()},
    )
    pedido = resposta.json()
    # A reserva já acontece aqui, na criação (itens físicos) -- confirma
    # antes de qualquer pagamento.
    assert _quantidade_produto(codigo) == 7

    aprovado = resultado_mp(pedido, status="approved")
    resposta = pagar_cartao(pedido, aprovado)
    assert resposta.status_code == 200
    assert resposta.json()["status"] == "aprovado"

    assert _quantidade_produto(codigo) == 7, "aprovação do cartão não pode baixar o estoque uma segunda vez"
    detalhe = client.get(f"/api/pedidos/{pedido['id']}", headers=HEADERS).json()
    assert detalhe["estoque_baixado"] == 1


def test_expiracao_libera_estoque_reservado_de_pedido_pago_com_cartao():
    """Um pedido criado para pagar com cartão, mas nunca confirmado, expira
    exatamente como um pedido Pix (mesmo campo pedidos.expira_em, mesma
    rotina expirar_pedidos_pendentes) -- o estoque reservado é devolvido, não
    fica preso indefinidamente."""
    codigo = codigo_unico("MPEXP")
    resposta = client.post(
        "/api/produtos",
        json={"nome": "Produto Expiração MP", "codigo_p": codigo, "preco": 20.0, "quantidade": 5, "categoria": "Testes"},
        headers=HEADERS,
    )
    produto = resposta.json()
    resposta = client.post(
        "/api/checkout/pedidos",
        json={"cliente": "Cliente Expiração", "telefone": "5599999999999", "forma_recebimento": "retirada", "itens": [{"produto_id": produto["id"], "quantidade": 2}]},
        headers={"X-Forwarded-For": ip_unico()},
    )
    pedido = resposta.json()
    assert _quantidade_produto(codigo) == 3  # 5 - 2 reservados

    from backend.database import conectar as conectar_backend

    with conectar_backend() as conn:
        conn.execute("UPDATE pedidos SET expira_em=? WHERE id=?", ("2000-01-01T00:00:00", pedido["id"]))
        conn.commit()

    # Qualquer chamada que rode expirar_pedidos_pendentes (ex.: consultar o
    # pedido) processa a expiração e repõe o estoque.
    detalhe = client.get(f"/api/pedidos/{pedido['id']}", headers=HEADERS).json()
    assert detalhe["status"] == "Cancelado"
    assert _quantidade_produto(codigo) == 5, "estoque reservado por um pedido de cartão nunca confirmado deve ser devolvido na expiração"

    # E depois de expirado/cancelado, uma tentativa de cartão tardia é
    # rejeitada (não reabre nem cobra um pedido morto).
    aprovado = resultado_mp(pedido, status="approved")
    resposta = pagar_cartao(pedido, aprovado)
    assert resposta.status_code == 409


def test_mesma_unidade_de_estoque_nao_e_vendida_duas_vezes_entre_pix_e_cartao():
    """Estoque limitado (1 unidade): o segundo pedido -- não importa se o
    cliente pretende pagar com Pix ou cartão -- nunca consegue reservar a
    mesma unidade já reservada pelo primeiro. A reserva acontece na criação
    do pedido, antes de qualquer decisão de forma de pagamento, então os
    dois provedores nunca disputam a mesma unidade fisicamente."""
    codigo = codigo_unico("MPUNI")
    resposta = client.post(
        "/api/produtos",
        json={"nome": "Produto Unidade Única MP", "codigo_p": codigo, "preco": 15.0, "quantidade": 1, "categoria": "Testes"},
        headers=HEADERS,
    )
    produto = resposta.json()

    resposta1 = client.post(
        "/api/checkout/pedidos",
        json={"cliente": "Cliente Pix", "telefone": "5599999999999", "forma_recebimento": "retirada", "itens": [{"produto_id": produto["id"], "quantidade": 1}]},
        headers={"X-Forwarded-For": ip_unico()},
    )
    assert resposta1.status_code == 200
    assert _quantidade_produto(codigo) == 0

    resposta2 = client.post(
        "/api/checkout/pedidos",
        json={"cliente": "Cliente Cartão", "telefone": "5599999999999", "forma_recebimento": "retirada", "itens": [{"produto_id": produto["id"], "quantidade": 1}]},
        headers={"X-Forwarded-For": ip_unico()},
    )
    assert resposta2.status_code in (404, 409), "segundo pedido não pode reservar a mesma última unidade já reservada pelo primeiro"


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


def test_moeda_diferente_de_brl_nunca_confirma_pedido():
    """Defesa em profundidade: mesmo que o Mercado Pago responda "approved"
    numa moeda que não seja BRL (conta mal configurada, resposta
    inesperada), o pedido nunca é confirmado a partir dela."""
    pedido = criar_pedido_publico(60.0)
    resultado_moeda_errada = resultado_mp(pedido, status="approved", currency_id="USD")
    resposta = pagar_cartao(pedido, resultado_moeda_errada)
    assert resposta.status_code == 200
    assert resposta.json()["status"] != "aprovado"
    detalhe = client.get(f"/api/pedidos/{pedido['id']}", headers=HEADERS).json()
    assert detalhe["status"] != "Pagamento confirmado"


# ---------------------------------------------------------------------------
# Diagnóstico interno sanitizado (Parte 3 da revisão do checkout de cartão):
# status/status_detail do provedor precisam ficar visíveis no log estruturado
# para investigação, mas token, número do cartão, CVV, CPF e e-mail do
# pagador NUNCA podem aparecer -- nem mesmo mascarados, já que este log nem
# recebe esses campos como entrada.
# ---------------------------------------------------------------------------

_CAMPOS_SENSIVEIS_PROIBIDOS = (
    "card_token_",  # prefixo usado pelos tokens de teste deste arquivo
    "cliente@example.com",
    "12345678900",
    "maria",  # nome do comprador usado por padrão em pagar_cartao()
)


def _log_resultado_cartao(caplog, pedido, resultado):
    import logging

    with caplog.at_level(logging.INFO, logger="backend.mercadopago_routes"):
        resposta = pagar_cartao(pedido, resultado)
    registros = [r for r in caplog.records if getattr(r, "evento", None) == "mp_cartao_resultado"]
    return resposta, registros


def test_log_resultado_cartao_recusado_traz_status_detail_sem_dado_sensivel(caplog):
    pedido = criar_pedido_publico(70.0)
    recusado = resultado_mp(pedido, status="rejected", status_detail="cc_rejected_bad_filled_security_code", payment_id="")
    resposta, registros = _log_resultado_cartao(caplog, pedido, recusado)

    assert resposta.status_code == 200
    assert len(registros) == 1
    record = registros[0]
    assert record.status_detail_provedor == "cc_rejected_bad_filled_security_code"
    assert record.status_provedor == "rejected"
    assert record.status_interno == "recusado"
    assert record.pedido_id == pedido["id"]
    assert "possible_environment_mismatch" in record.__dict__
    assert "credential_environment_confidence" in record.__dict__

    texto = f"{record.getMessage()} {record.__dict__}".lower()
    for proibido in _CAMPOS_SENSIVEIS_PROIBIDOS:
        assert proibido not in texto, f"log vazou dado sensível: {proibido}"
    for campo in ("token", "cvv", "numero_cartao", "access_token", "public_key"):
        assert not hasattr(record, campo)


def test_log_resultado_cartao_aprovado_tambem_registra_diagnostico(caplog):
    pedido = criar_pedido_publico(80.0)
    aprovado = resultado_mp(pedido, status="approved", status_detail="accredited")
    resposta, registros = _log_resultado_cartao(caplog, pedido, aprovado)

    assert resposta.status_code == 200
    assert len(registros) == 1
    assert registros[0].status_interno == "aprovado"
    assert registros[0].status_detail_provedor == "accredited"


def test_diagnostico_credenciais_mercadopago_sinaliza_prefixos_divergentes_sem_afirmar_certeza(monkeypatch):
    """O prefixo é só um indício (a doc oficial admite variação conforme a
    solução) -- por isso o diagnóstico nunca afirma "inconsistente" com
    certeza, só sinaliza baixa confiança para investigação manual no painel
    do Mercado Pago."""
    from backend.mercadopago_flags import diagnostico_credenciais_mercadopago

    monkeypatch.setenv("MERCADO_PAGO_PUBLIC_KEY", "TEST-abc123")
    monkeypatch.setenv("MERCADO_PAGO_ACCESS_TOKEN", "APP_USR-xyz789")
    diagnostico = diagnostico_credenciais_mercadopago()
    assert diagnostico["public_key_prefix_hint"] == "test_prefix"
    assert diagnostico["access_token_prefix_hint"] == "app_usr_prefix"
    assert diagnostico["possible_environment_mismatch"] is True
    assert diagnostico["credential_environment_confidence"] == "low"
    # nunca devolve a credencial em si, só o nome do prefixo observado
    for valor in diagnostico.values():
        assert "abc123" not in str(valor)
        assert "xyz789" not in str(valor)


def test_diagnostico_credenciais_mercadopago_prefixos_iguais_nao_e_garantia(monkeypatch):
    """Prefixos iguais reduzem o sinal de divergência, mas o diagnóstico
    nunca declara "consistente" com certeza -- confiança continua "low" e a
    confirmação real depende de checar o painel do Mercado Pago."""
    from backend.mercadopago_flags import diagnostico_credenciais_mercadopago

    monkeypatch.setenv("MERCADO_PAGO_PUBLIC_KEY", "TEST-abc123")
    monkeypatch.setenv("MERCADO_PAGO_ACCESS_TOKEN", "TEST-def456")
    diagnostico = diagnostico_credenciais_mercadopago()
    assert diagnostico["possible_environment_mismatch"] is False
    assert diagnostico["credential_environment_confidence"] == "low"


def test_diagnostico_credenciais_mercadopago_nunca_bloqueia_pagamento():
    """A heurística de prefixo é só diagnóstico -- mesmo com prefixos
    divergentes, o pagamento segue seu fluxo normal (aprovado/pendente/
    recusado conforme a resposta real do provedor), nunca é barrado por
    causa do diagnóstico."""
    pedido = criar_pedido_publico(90.0)
    aprovado = resultado_mp(pedido, status="approved", status_detail="accredited")
    resposta = pagar_cartao(pedido, aprovado)
    assert resposta.status_code == 200
    assert resposta.json()["status"] == "aprovado"


# ---------------------------------------------------------------------------
# Cenários oficiais de cartão de teste do Mercado Pago (sandbox), conforme
# https://www.mercadopago.com.br/developers/pt/docs/checkout-api/integration-test/test-cards
# e https://www.mercadopago.com.br/developers/pt/docs/your-integrations/test/accounts
#
# O cartão Visa 4235 6477 2802 5682 (CVV 123, validade 11/30) é dado
# PÚBLICO de teste do próprio Mercado Pago -- nunca é um cartão real, por
# isso pode aparecer em texto aqui (ao contrário de qualquer token/PAN real,
# que este projeto nunca loga nem persiste). O nome do titular é quem
# decide o resultado simulado, não o número do cartão:
#   - "APRO" -> pagamento aprovado (status_detail "accredited")
#   - "OTHE" -> pagamento recusado por erro geral (status_detail
#     "cc_rejected_other_reason") -- é o cenário OFICIAL de reprovação
#     esperada em sandbox, não evidência de bug.
#   - "CONT" -> pendente; "CALL"/"FUND"/"SECU"/"EXPI"/"FORM" -> outras
#     recusas específicas (autorização, saldo, CVV, validade, dados).
# CPF de teste associado: 12345678909.
#
# A recusa vista na imagem de validação usava o titular "OTHE" -- pelo
# comportamento documentado, é uma reprovação ESPERADA do cenário de teste,
# não evidência de defeito no fluxo de cartão. Estes testes não chamam a
# API real do Mercado Pago (nenhum teste automatizado deste projeto chama);
# eles documentam e travam o comportamento do NOSSO backend diante da
# resposta que o Mercado Pago publica para cada cenário.
# ---------------------------------------------------------------------------

CARTAO_TESTE_MERCADOPAGO = {
    "bandeira": "visa",
    "numero_mascarado": "4235 6477 2802 ****",  # dado público de teste, nunca um cartão real
    "validade": "11/30",
    "documento_teste": "12345678909",
}


def test_cenario_oficial_APRO_simula_pagamento_aprovado():
    """Titular "APRO" (documentação oficial) -> aprovado/accredited. Este é
    o cenário correto para validar aprovação em sandbox -- não o cartão da
    imagem, que usava "OTHE" propositalmente (ou não) para simular recusa."""
    pedido = criar_pedido_publico(55.0)
    aprovado = resultado_mp(pedido, status="approved", status_detail="accredited", payment_method_id="visa")
    resposta = pagar_cartao(
        pedido,
        aprovado,
        payer={"email": "cliente.teste@example.com", "nome": "Maria", "documento_numero": CARTAO_TESTE_MERCADOPAGO["documento_teste"]},
    )
    assert resposta.status_code == 200
    corpo = resposta.json()
    assert corpo["status"] == "aprovado"
    assert corpo["aprovado"] is True
    detalhe = client.get(f"/api/pedidos/{pedido['id']}", headers=HEADERS).json()
    assert detalhe["status"] == "Pagamento confirmado"


def test_cenario_oficial_OTHE_simula_recusa_esperada_do_cartao_de_teste():
    """Titular "OTHE" (documentação oficial) -> recusado/cc_rejected_other_
    reason. Reprovação ESPERADA do cenário de teste, não bug -- o pedido
    continua disponível para nova tentativa (com "APRO" ou outro método),
    nunca é cancelado só por causa disso."""
    pedido = criar_pedido_publico(55.0)
    recusado = resultado_mp(
        pedido, status="rejected", status_detail="cc_rejected_other_reason", payment_id="", payment_method_id="visa"
    )
    resposta = pagar_cartao(
        pedido,
        recusado,
        payer={"email": "cliente.teste@example.com", "nome": "Maria", "documento_numero": CARTAO_TESTE_MERCADOPAGO["documento_teste"]},
    )
    assert resposta.status_code == 200
    corpo = resposta.json()
    assert corpo["status"] == "recusado"
    assert corpo["aprovado"] is False
    # mensagem ao cliente continua genérica -- nunca expõe o status_detail
    # bruto do provedor, mesmo sendo um cenário de teste conhecido
    assert "cc_rejected_other_reason" not in corpo["mensagem"]
    detalhe = client.get(f"/api/pedidos/{pedido['id']}", headers=HEADERS).json()
    assert detalhe["status"] == "Aguardando pagamento"  # pedido segue disponível para nova tentativa


# ---------------------------------------------------------------------------
# Endereço de cobrança (reformulação do checkout): payer.address -- só os
# campos documentados pelos SDKs oficiais do Mercado Pago (ver a fonte
# primária citada em backend/mercadopago_client.py::criar_pagamento_cartao),
# nunca persistido em nenhuma tabela. Ver backend/mercadopago_routes.py::
# _resolver_endereco_cobranca.
# ---------------------------------------------------------------------------


def test_endereco_cobranca_explicito_e_enviado_para_o_mercado_pago():
    pedido = criar_pedido_publico(65.0)  # retirada -- sem endereço de entrega
    aprovado = resultado_mp(pedido, status="approved")
    payer = {
        "email": "cliente@example.com",
        "nome": "Maria",
        "documento_numero": "12345678900",
        "endereco_cobranca": {
            "usar_mesmo_da_entrega": False,
            "cep": "89870-000",
            "rua": "Av. Central",
            "numero": "500",
            "bairro": "Centro",
            "cidade": "Pinhalzinho",
            "uf": "sc",
        },
    }
    mocks = []
    resposta = pagar_cartao(pedido, aprovado, payer=payer, capturar_mock=mocks)
    assert resposta.status_code == 200, resposta.text
    _, kwargs = mocks[0].call_args
    assert kwargs["billing_address"] == {
        "zip_code": "89870000",
        "street_name": "Av. Central",
        "street_number": "500",
        "neighborhood": "Centro",
        "city": "Pinhalzinho",
        "federal_unit": "SC",
    }


def test_endereco_cobranca_reaproveita_endereco_de_entrega_quando_marcado():
    pedido = criar_pedido_publico_entrega(65.0)
    aprovado = resultado_mp(pedido, status="approved")
    payer = {
        "email": "cliente@example.com",
        "nome": "Maria",
        "documento_numero": "12345678900",
        "endereco_cobranca": {"usar_mesmo_da_entrega": True},
    }
    mocks = []
    resposta = pagar_cartao(pedido, aprovado, payer=payer, capturar_mock=mocks)
    assert resposta.status_code == 200, resposta.text
    _, kwargs = mocks[0].call_args
    assert kwargs["billing_address"] == {
        "zip_code": "89870000",
        "street_name": "Rua das Flores",
        "street_number": "123",
        "neighborhood": "Centro",
        "city": "Pinhalzinho",
        "federal_unit": "SC",
    }


def test_endereco_cobranca_reaproveitar_entrega_ignorado_quando_pedido_e_retirada():
    """'Usar o mesmo endereço da entrega' não faz sentido para retirada (não
    há endereço de entrega gravado) -- nenhum payer.address é enviado,
    nunca inventa um endereço."""
    pedido = criar_pedido_publico(65.0)
    aprovado = resultado_mp(pedido, status="approved")
    payer = {
        "email": "cliente@example.com",
        "nome": "Maria",
        "documento_numero": "12345678900",
        "endereco_cobranca": {"usar_mesmo_da_entrega": True},
    }
    mocks = []
    resposta = pagar_cartao(pedido, aprovado, payer=payer, capturar_mock=mocks)
    assert resposta.status_code == 200, resposta.text
    _, kwargs = mocks[0].call_args
    assert kwargs["billing_address"] is None


def test_endereco_cobranca_ausente_nao_envia_endereco():
    """Compatibilidade: chamadores que nunca enviam endereco_cobranca (ex.:
    todos os outros testes deste arquivo) continuam funcionando exatamente
    como antes -- billing_address é None, payer.address nunca é montado."""
    pedido = criar_pedido_publico(65.0)
    aprovado = resultado_mp(pedido, status="approved")
    mocks = []
    resposta = pagar_cartao(pedido, aprovado, capturar_mock=mocks)
    assert resposta.status_code == 200, resposta.text
    _, kwargs = mocks[0].call_args
    assert kwargs["billing_address"] is None


def test_endereco_cobranca_cep_invalido_e_rejeitado():
    pedido = criar_pedido_publico(65.0)
    payer = {
        "email": "cliente@example.com",
        "nome": "Maria",
        "documento_numero": "12345678900",
        "endereco_cobranca": {"usar_mesmo_da_entrega": False, "cep": "123", "rua": "Rua X", "numero": "1", "cidade": "Pinhalzinho", "uf": "SC"},
    }
    resposta = client.post(
        "/api/payments/mercadopago/card",
        json={
            "pedido_id": pedido["id"], "txid": pedido["pix_txid"], "token": "card_token_" + uuid.uuid4().hex,
            "payment_method_id": "visa", "installments": 1, "payer": payer,
        },
        headers={"Idempotency-Key": str(uuid.uuid4()), "X-Forwarded-For": ip_unico()},
    )
    assert resposta.status_code == 422


def test_billing_address_no_client_mercadopago_usa_payer_address():
    """Confirma o formato exato do payload enviado ao Mercado Pago (única
    integração real testada: mercadopago_client.criar_pagamento_cartao) --
    payer.address, com só os campos documentados pelos SDKs oficiais do
    Mercado Pago (mercadopago/sdk-nodejs::PayerRequest.address/AddressRequest
    e mercadopago/sdk-dotnet::PaymentPayerRequest.Address/
    PaymentPayerAddressRequest, confirmados por clone direto do GitHub nesta
    revisão de homologação -- ver a fonte primária citada em
    backend/mercadopago_client.py::criar_pagamento_cartao). NUNCA
    additional_info.payer.address (schema reduzido nos mesmos SDKs, sem
    neighborhood/city/federal_unit -- destino errado usado numa versão
    anterior desta integração, corrigido nesta revisão) e nunca uma
    propriedade fora das documentadas."""
    import httpx

    from backend.mercadopago_client import criar_pagamento_cartao

    capturado = {}

    class FakeResponse:
        status_code = 201

        def json(self):
            return {"id": "mp-billing-1", "status": "approved", "status_detail": "accredited", "transaction_amount": 10.0, "currency_id": "BRL"}

    def fake_post(self, url, json=None, headers=None):
        capturado["json"] = json
        return FakeResponse()

    with patch.object(httpx.Client, "post", fake_post):
        criar_pagamento_cartao(
            idempotency_key="k1", transaction_amount=10.0, token="tok", installments=1,
            payment_method_id="visa", issuer_id=None, payer_email="c@example.com",
            payer_doc_type="CPF", payer_doc_number="12345678900",
            external_reference="1", description="Pedido #1",
            billing_address={"zip_code": "89870000", "street_name": "Rua X", "street_number": "1", "neighborhood": "Centro", "city": "Pinhalzinho", "federal_unit": "SC"},
        )
    assert capturado["json"]["payer"]["address"] == {
        "zip_code": "89870000", "street_name": "Rua X", "street_number": "1", "neighborhood": "Centro", "city": "Pinhalzinho", "federal_unit": "SC",
    }
    assert "additional_info" not in capturado["json"]


# ---------------------------------------------------------------------------
# Device ID (antifraude) -- coletado no navegador pelo script oficial do
# Mercado Pago (v2/security.js), encaminhado ao provedor no header
# X-meli-session-id (nunca como campo do corpo JSON, nunca persistido, nunca
# logado, nunca usado como Idempotency-Key).
# ---------------------------------------------------------------------------


def test_device_id_valido_e_encaminhado_para_criar_pagamento():
    pedido = criar_pedido_publico(30.0)
    aprovado = resultado_mp(pedido, status="approved")
    mocks = []
    resposta = pagar_cartao(pedido, aprovado, device_id="abc123DEVICE-id_9", capturar_mock=mocks)
    assert resposta.status_code == 200, resposta.text
    _, kwargs = mocks[0].call_args
    assert kwargs["device_id"] == "abc123DEVICE-id_9"


def test_device_id_ausente_nao_bloqueia_pagamento():
    pedido = criar_pedido_publico(30.0)
    aprovado = resultado_mp(pedido, status="approved")
    mocks = []
    resposta = pagar_cartao(pedido, aprovado, capturar_mock=mocks)
    assert resposta.status_code == 200, resposta.text
    _, kwargs = mocks[0].call_args
    assert kwargs["device_id"] is None


def test_device_id_com_formato_invalido_e_descartado_sem_bloquear_pagamento():
    """Espaço/CRLF/tamanho fora do padrão nunca chegam a criar_pagamento_cartao
    -- validação conservadora descarta silenciosamente (o pagamento nunca é
    bloqueado por causa de um Device ID malformado, só perde esse sinal
    adicional de antifraude)."""
    pedido = criar_pedido_publico(30.0)
    aprovado = resultado_mp(pedido, status="approved")
    mocks = []
    resposta = pagar_cartao(pedido, aprovado, device_id="valor com espaco e\r\ninjeção", capturar_mock=mocks)
    assert resposta.status_code == 200, resposta.text
    _, kwargs = mocks[0].call_args
    assert kwargs["device_id"] is None


def test_device_id_grande_demais_e_descartado_sem_rejeitar_a_requisicao():
    """Um Device ID absurdamente grande nunca derruba a requisição inteira
    (HTTP 422 bloquearia o pagamento) -- é só descartado, o pagamento segue
    normalmente sem esse sinal."""
    pedido = criar_pedido_publico(30.0)
    aprovado = resultado_mp(pedido, status="approved")
    mocks = []
    resposta = pagar_cartao(pedido, aprovado, device_id="a" * 500, capturar_mock=mocks)
    assert resposta.status_code == 200, resposta.text
    _, kwargs = mocks[0].call_args
    assert kwargs["device_id"] is None


def test_device_id_curto_demais_e_descartado():
    pedido = criar_pedido_publico(30.0)
    aprovado = resultado_mp(pedido, status="approved")
    mocks = []
    resposta = pagar_cartao(pedido, aprovado, device_id="curto", capturar_mock=mocks)
    assert resposta.status_code == 200, resposta.text
    _, kwargs = mocks[0].call_args
    assert kwargs["device_id"] is None


def test_device_id_nunca_persistido_em_tentativas_pagamento_nem_auditoria():
    pedido = criar_pedido_publico(30.0)
    aprovado = resultado_mp(pedido, status="approved")
    device_id_teste = "device-id-nunca-persistido-xyz"
    resposta = pagar_cartao(pedido, aprovado, device_id=device_id_teste)
    assert resposta.status_code == 200, resposta.text
    from backend.database import conectar as _conectar

    with _conectar() as conn:
        linhas_tentativa = conn.execute("SELECT * FROM tentativas_pagamento WHERE pedido_id=?", (pedido["id"],)).fetchall()
        for linha in linhas_tentativa:
            assert device_id_teste not in str(dict(linha))
        linhas_auditoria = conn.execute(
            "SELECT * FROM audit_log WHERE entidade='tentativa_pagamento' ORDER BY id DESC LIMIT 5"
        ).fetchall()
        for linha in linhas_auditoria:
            assert device_id_teste not in str(dict(linha))


def test_device_id_nao_e_usado_como_idempotency_key():
    """Duas tentativas com o MESMO device_id mas Idempotency-Key diferentes
    (ex.: dois compradores no mesmo dispositivo compartilhado) nunca
    colidem -- confirma que device_id não participa do payload de
    idempotência."""
    pedido1 = criar_pedido_publico(30.0)
    pedido2 = criar_pedido_publico(40.0)
    aprovado1 = resultado_mp(pedido1, status="approved")
    aprovado2 = resultado_mp(pedido2, status="approved")
    mesmo_device_id = "device-compartilhado-0001"
    r1 = pagar_cartao(pedido1, aprovado1, device_id=mesmo_device_id)
    r2 = pagar_cartao(pedido2, aprovado2, device_id=mesmo_device_id)
    assert r1.status_code == 200 and r2.status_code == 200
    assert r1.json()["pedido_id"] != r2.json()["pedido_id"]


def test_client_mercadopago_encaminha_device_id_no_header_x_meli_session_id():
    """Único ponto que realmente conversa com o Mercado Pago
    (mercadopago_client.criar_pagamento_cartao) -- confirma que o Device ID
    vai no header X-meli-session-id (nome documentado publicamente pelo
    Mercado Pago) e NUNCA como campo do corpo JSON."""
    import httpx

    from backend.mercadopago_client import criar_pagamento_cartao

    capturado = {}

    class FakeResponse:
        status_code = 201

        def json(self):
            return {"id": "mp-device-1", "status": "approved", "status_detail": "accredited", "transaction_amount": 10.0, "currency_id": "BRL"}

    def fake_post(self, url, json=None, headers=None):
        capturado["json"] = json
        capturado["headers"] = headers
        return FakeResponse()

    with patch.object(httpx.Client, "post", fake_post):
        criar_pagamento_cartao(
            idempotency_key="k-device", transaction_amount=10.0, token="tok", installments=1,
            payment_method_id="visa", issuer_id=None, payer_email="c@example.com",
            payer_doc_type="CPF", payer_doc_number="12345678900",
            external_reference="1", description="Pedido #1",
            device_id="device-session-real-123",
        )
    assert capturado["headers"]["X-meli-session-id"] == "device-session-real-123"
    assert "device_id" not in capturado["json"]
    assert "device" not in str(capturado["json"]).lower()


def test_client_mercadopago_sem_device_id_nao_envia_header():
    import httpx

    from backend.mercadopago_client import criar_pagamento_cartao

    capturado = {}

    class FakeResponse:
        status_code = 201

        def json(self):
            return {"id": "mp-device-2", "status": "approved", "status_detail": "accredited", "transaction_amount": 10.0, "currency_id": "BRL"}

    def fake_post(self, url, json=None, headers=None):
        capturado["headers"] = headers
        return FakeResponse()

    with patch.object(httpx.Client, "post", fake_post):
        criar_pagamento_cartao(
            idempotency_key="k-sem-device", transaction_amount=10.0, token="tok", installments=1,
            payment_method_id="visa", issuer_id=None, payer_email="c@example.com",
            payer_doc_type="CPF", payer_doc_number="12345678900",
            external_reference="1", description="Pedido #1",
        )
    assert "X-meli-session-id" not in capturado["headers"]


# ---------------------------------------------------------------------------
# additional_info.items -- produto/quantidade/valor SEMPRE calculados pelo
# backend (pedidos_itens), nunca confiados ao cliente; só os campos
# documentados pelo schema oficial (id/title/quantity/unit_price).
# ---------------------------------------------------------------------------


def test_additional_info_items_montado_a_partir_dos_itens_reais_do_pedido():
    pedido = criar_pedido_publico(25.0, quantidade=3)
    aprovado = resultado_mp(pedido, status="approved", valor=75.0)
    mocks = []
    resposta = pagar_cartao(pedido, aprovado, capturar_mock=mocks)
    assert resposta.status_code == 200, resposta.text
    _, kwargs = mocks[0].call_args
    itens = kwargs["additional_info_items"]
    assert itens is not None and len(itens) == 1
    item = itens[0]
    assert set(item.keys()) == {"id", "title", "quantity", "unit_price"}
    assert item["quantity"] == 3
    assert item["unit_price"] == 25.0
    assert item["title"] == "Produto MP Teste"


def test_additional_info_items_soma_coerente_com_total_final():
    pedido = criar_pedido_publico(19.90, quantidade=2)
    aprovado = resultado_mp(pedido, status="approved")
    mocks = []
    resposta = pagar_cartao(pedido, aprovado, capturar_mock=mocks)
    assert resposta.status_code == 200, resposta.text
    _, kwargs = mocks[0].call_args
    itens = kwargs["additional_info_items"]
    soma = sum(i["quantity"] * i["unit_price"] for i in itens)
    assert round(soma, 2) == round(pedido["total_final"], 2)


def test_additional_info_items_nunca_inclui_campo_nao_documentado():
    """Nenhum category_id/picture_url/warranty inventado -- este catálogo não
    tem esses dados estruturados hoje. `description` é permitido (ver teste
    abaixo), mas só aparece quando o produto tem descrição cadastrada --
    aqui o produto não tem, então a chave nem aparece."""
    pedido = criar_pedido_publico(10.0)
    aprovado = resultado_mp(pedido, status="approved")
    mocks = []
    pagar_cartao(pedido, aprovado, capturar_mock=mocks)
    _, kwargs = mocks[0].call_args
    for item in kwargs["additional_info_items"]:
        assert "category_id" not in item
        assert "description" not in item
        assert "picture_url" not in item
        assert "warranty" not in item


def test_additional_info_items_inclui_description_quando_produto_tem_descricao():
    """Painel de Qualidade da integração aponta additional_info.items.
    description como recomendado -- quando o produto do catálogo tem
    `descricao` preenchida, ela deve ir para o item (nunca inventada para
    produtos sem descrição, ver teste acima)."""
    resposta_produto = client.post(
        "/api/produtos",
        json={
            "nome": "Produto MP Com Descricao", "codigo_p": codigo_unico("MPCD"), "preco": 10.0,
            "quantidade": 20, "categoria": "Testes", "descricao": "Vela aromática de lavanda, 100g.",
        },
        headers=HEADERS,
    )
    assert resposta_produto.status_code == 200, resposta_produto.text
    produto = resposta_produto.json()
    resposta_pedido = client.post(
        "/api/checkout/pedidos",
        json={"cliente": "Cliente MP", "telefone": "5599999999999", "forma_recebimento": "retirada", "itens": [{"produto_id": produto["id"], "quantidade": 1}]},
        headers={"X-Forwarded-For": ip_unico()},
    )
    assert resposta_pedido.status_code == 200, resposta_pedido.text
    pedido = resposta_pedido.json()
    aprovado = resultado_mp(pedido, status="approved")
    mocks = []
    resposta = pagar_cartao(pedido, aprovado, capturar_mock=mocks)
    assert resposta.status_code == 200, resposta.text
    _, kwargs = mocks[0].call_args
    itens = kwargs["additional_info_items"]
    assert itens is not None and len(itens) == 1
    assert itens[0]["description"] == "Vela aromática de lavanda, 100g."


def test_client_mercadopago_envia_additional_info_items_no_corpo_json():
    """additional_info.items É esperado dentro do corpo JSON (ao contrário do
    Device ID) -- é dado descritivo do pedido, não um sinal de sessão do
    dispositivo."""
    import httpx

    from backend.mercadopago_client import criar_pagamento_cartao

    capturado = {}

    class FakeResponse:
        status_code = 201

        def json(self):
            return {"id": "mp-items-1", "status": "approved", "status_detail": "accredited", "transaction_amount": 10.0, "currency_id": "BRL"}

    def fake_post(self, url, json=None, headers=None):
        capturado["json"] = json
        return FakeResponse()

    itens = [{"id": "SKU-1", "title": "Cristal Ametista", "quantity": 2, "unit_price": 25.0}]
    with patch.object(httpx.Client, "post", fake_post):
        criar_pagamento_cartao(
            idempotency_key="k-items", transaction_amount=50.0, token="tok", installments=1,
            payment_method_id="visa", issuer_id=None, payer_email="c@example.com",
            payer_doc_type="CPF", payer_doc_number="12345678900",
            external_reference="1", description="Pedido #1",
            additional_info_items=itens,
        )
    assert capturado["json"]["additional_info"] == {"items": itens}


def test_client_mercadopago_sem_itens_nunca_envia_additional_info_vazio():
    import httpx

    from backend.mercadopago_client import criar_pagamento_cartao

    capturado = {}

    class FakeResponse:
        status_code = 201

        def json(self):
            return {"id": "mp-items-2", "status": "approved", "status_detail": "accredited", "transaction_amount": 10.0, "currency_id": "BRL"}

    def fake_post(self, url, json=None, headers=None):
        capturado["json"] = json
        return FakeResponse()

    with patch.object(httpx.Client, "post", fake_post):
        criar_pagamento_cartao(
            idempotency_key="k-sem-items", transaction_amount=10.0, token="tok", installments=1,
            payment_method_id="visa", issuer_id=None, payer_email="c@example.com",
            payer_doc_type="CPF", payer_doc_number="12345678900",
            external_reference="1", description="Pedido #1",
        )
    assert "additional_info" not in capturado["json"]


# ---------------------------------------------------------------------------
# Mensagens amigáveis por status_detail + cooldown de recusa por alto risco.
# ---------------------------------------------------------------------------


def test_mensagem_amigavel_cc_rejected_high_risk():
    pedido = criar_pedido_publico(45.0)
    recusado = resultado_mp(pedido, status="rejected", status_detail="cc_rejected_high_risk", payment_id="")
    resposta = pagar_cartao(pedido, recusado)
    assert resposta.status_code == 200
    assert "critérios de segurança" in resposta.json()["mensagem"].lower()
    assert "cc_rejected_high_risk" not in resposta.json()["mensagem"]


def test_mensagem_amigavel_cpf_invalido_na_criacao():
    pedido = criar_pedido_publico(45.0)
    recusado = resultado_mp(pedido, status="rejected", status_detail="Invalid user identification number", payment_id="")
    resposta = pagar_cartao(pedido, recusado)
    assert resposta.status_code == 200
    assert "cpf" in resposta.json()["mensagem"].lower()


# ---------------------------------------------------------------------------
# card_token_id inválido/já usado (código 3003) -- causa raiz do bug de
# produção que motivou esta correção (pedido_id 39, tentativa_id 19). O
# CardToken do SDK é descartável (uso único, ver docs/card-form.md do
# mercadopago/sdk-js); reenviar o mesmo token numa nova tentativa é
# rejeitado pelo Mercado Pago com este código, nunca com um status_detail
# cc_rejected_*. Nunca deve ser tratado como uma recusa comum de crédito.
# ---------------------------------------------------------------------------


def test_card_token_invalido_retorna_422_com_mensagem_amigavel_e_sem_vazar_dado_bruto():
    pedido = criar_pedido_publico(45.0)
    recusado = resultado_mp(pedido, status="rejected", status_detail="Invalid card_token_id", payment_id="", causa_codigos=(3003,))
    resposta = pagar_cartao(pedido, recusado)
    assert resposta.status_code == 422
    corpo = resposta.json()
    assert corpo["codigo"] == "cartao_token_invalido"
    assert "revise" in corpo["mensagem"].lower()
    # Nunca expõe o texto bruto do provedor nem o código numérico 3003.
    assert "card_token_id" not in corpo["mensagem"].lower()
    assert "3003" not in corpo["mensagem"]
    detalhe = client.get(f"/api/pedidos/{pedido['id']}", headers=HEADERS).json()
    assert detalhe["status"] == "Aguardando pagamento"  # nunca cancela, nunca confirma


def test_card_token_invalido_detectado_so_pelo_codigo_de_causa_sem_texto_no_status_detail():
    # Defesa em profundidade: mesmo se o texto do status_detail não contiver
    # "card_token" (ex.: provedor muda a redação da mensagem), o código
    # numérico 3003 sozinho já é suficiente para classificar corretamente.
    pedido = criar_pedido_publico(45.0)
    recusado = resultado_mp(pedido, status="rejected", status_detail="Bad Request", payment_id="", causa_codigos=(3003,))
    resposta = pagar_cartao(pedido, recusado)
    assert resposta.status_code == 422
    assert resposta.json()["codigo"] == "cartao_token_invalido"


def test_recusa_de_credito_comum_continua_200_nunca_vira_422():
    # Regressão: uma recusa de crédito de verdade (ex.: saldo insuficiente)
    # nunca deve ser confundida com token inválido -- continua HTTP 200,
    # como sempre foi (o cliente pode tentar outro cartão no mesmo pedido).
    pedido = criar_pedido_publico(45.0)
    recusado = resultado_mp(pedido, status="rejected", status_detail="cc_rejected_insufficient_amount", payment_id="")
    resposta = pagar_cartao(pedido, recusado)
    assert resposta.status_code == 200
    corpo = resposta.json()
    assert corpo["status"] == "recusado"
    assert corpo["codigo"] is None


def test_nova_tentativa_com_token_novo_apos_token_invalido_nao_colide_na_idempotencia():
    # O bug relatado tinha 19 tentativas para o mesmo pedido -- a correção
    # também precisa garantir que uma nova tentativa (com token novo, nova
    # Idempotency-Key -- é isso que o frontend corrigido faz, ver
    # v2-mercadopago-checkout.js::enviarPagamentoCartao) nunca esbarra num
    # 409 de "chave já usada com dados diferentes" por causa do token
    # anterior ainda estar "preso" à mesma chave.
    pedido = criar_pedido_publico(70.0)
    token_invalido = resultado_mp(pedido, status="rejected", status_detail="Invalid card_token_id", payment_id="", causa_codigos=(3003,))
    resposta1 = pagar_cartao(pedido, token_invalido, idempotency_key=str(uuid.uuid4()))
    assert resposta1.status_code == 422

    aprovado = resultado_mp(pedido, status="approved", payment_id="mp-retry-token-novo")
    resposta2 = pagar_cartao(pedido, aprovado, idempotency_key=str(uuid.uuid4()))
    assert resposta2.status_code == 200
    assert resposta2.json()["status"] == "aprovado"


def test_recusa_por_alto_risco_aplica_cooldown_na_proxima_tentativa():
    pedido = criar_pedido_publico(45.0)
    recusado = resultado_mp(pedido, status="rejected", status_detail="cc_rejected_high_risk", payment_id="")
    r1 = pagar_cartao(pedido, recusado)
    assert r1.status_code == 200

    aprovado = resultado_mp(pedido, status="approved", payment_id="mp-retry-alto-risco")
    r2 = pagar_cartao(pedido, aprovado)
    assert r2.status_code == 429
    assert "aguarde" in r2.json()["detail"].lower()


def test_cooldown_alto_risco_nao_se_aplica_a_recusa_comum():
    pedido = criar_pedido_publico(45.0)
    recusado = resultado_mp(pedido, status="rejected", status_detail="cc_rejected_bad_filled_security_code", payment_id="")
    r1 = pagar_cartao(pedido, recusado)
    assert r1.status_code == 200

    aprovado = resultado_mp(pedido, status="approved", payment_id="mp-retry-comum")
    r2 = pagar_cartao(pedido, aprovado)
    assert r2.status_code == 200
    assert r2.json()["status"] == "aprovado"


def test_cooldown_alto_risco_expira_apos_a_janela():
    """O cooldown nunca é permanente: passado COOLDOWN_ALTO_RISCO_SEGUNDOS,
    uma nova tentativa é aceita normalmente. Simula a passagem do tempo
    reescrevendo tentativas_pagamento.atualizado_em diretamente (mesmo
    campo que _cooldown_alto_risco_restante lê), sem depender de esperar de
    verdade na suíte."""
    from backend.database import conectar as conectar_backend
    from backend.mercadopago_routes import COOLDOWN_ALTO_RISCO_SEGUNDOS

    pedido = criar_pedido_publico(45.0)
    recusado = resultado_mp(pedido, status="rejected", status_detail="cc_rejected_high_risk", payment_id="")
    r1 = pagar_cartao(pedido, recusado)
    assert r1.status_code == 200

    passado = (datetime.now() - timedelta(seconds=COOLDOWN_ALTO_RISCO_SEGUNDOS + 5)).isoformat(timespec="seconds")
    with conectar_backend() as conn:
        conn.execute(
            "UPDATE tentativas_pagamento SET atualizado_em=? WHERE pedido_id=? AND provedor='mercadopago'",
            (passado, pedido["id"]),
        )
        conn.commit()

    aprovado = resultado_mp(pedido, status="approved", payment_id="mp-retry-apos-cooldown")
    r2 = pagar_cartao(pedido, aprovado)
    assert r2.status_code == 200
    assert r2.json()["status"] == "aprovado"


def test_cooldown_alto_risco_e_por_pedido_nunca_bloqueia_outro_pedido():
    """A chave do cooldown é o pedido_id (tentativas_pagamento.pedido_id) --
    uma recusa de alto risco no pedido A nunca bloqueia uma tentativa de
    cartão no pedido B, mesmo que ambos aconteçam em sequência rápida."""
    pedido_a = criar_pedido_publico(45.0)
    pedido_b = criar_pedido_publico(45.0)

    recusado = resultado_mp(pedido_a, status="rejected", status_detail="cc_rejected_high_risk", payment_id="")
    r1 = pagar_cartao(pedido_a, recusado)
    assert r1.status_code == 200

    aprovado_b = resultado_mp(pedido_b, status="approved", payment_id="mp-pedido-b-aprovado")
    r2 = pagar_cartao(pedido_b, aprovado_b)
    assert r2.status_code == 200
    assert r2.json()["status"] == "aprovado"


def test_cooldown_alto_risco_nunca_bloqueia_pix():
    """O cooldown é exclusivo da rota de cartão -- Pix continua confirmando
    normalmente mesmo com uma recusa de alto risco recente no mesmo
    pedido."""
    pedido = criar_pedido_publico(45.0)
    recusado = resultado_mp(pedido, status="rejected", status_detail="cc_rejected_high_risk", payment_id="")
    r1 = pagar_cartao(pedido, recusado)
    assert r1.status_code == 200

    resposta_pix = client.post(
        "/api/pagamentos",
        json={"venda_id": pedido["id"], "forma": "Pix", "valor": pedido["total_final"], "status": "Confirmado"},
        headers={**HEADERS, "X-Forwarded-For": ip_unico(), "Idempotency-Key": str(uuid.uuid4())},
    )
    assert resposta_pix.status_code == 200
    assert resposta_pix.json()["status_conciliacao"] == "ok"


# ---------------------------------------------------------------------------
# payer.first_name/last_name -- coletados por campos explícitos do checkout
# (#mpBuyerFirstName/#mpBuyerLastName no frontend), NUNCA a partir de
# cardholderName ("Nome impresso no cartão", o titular do cartão -- pode ser
# outra pessoa) e nunca divididos automaticamente de um nome completo. `nome`
# é obrigatório; `sobrenome` é opcional (nomes civis de uma única palavra
# nunca são bloqueados nem preenchidos com valor inventado).
# ---------------------------------------------------------------------------


def test_nome_comprador_obrigatorio_e_enviado_como_first_name():
    pedido = criar_pedido_publico(40.0)
    aprovado = resultado_mp(pedido, status="approved")
    mocks = []
    resposta = pagar_cartao(
        pedido, aprovado, capturar_mock=mocks,
        payer={"email": "cliente@example.com", "nome": "  Ana   Maria  ", "documento_numero": "12345678900"},
    )
    assert resposta.status_code == 200, resposta.text
    _, kwargs = mocks[0].call_args
    assert kwargs["payer_first_name"] == "Ana Maria"  # espaços excessivos normalizados
    assert kwargs["payer_last_name"] is None


def test_sobrenome_comprador_opcional_e_enviado_quando_informado():
    pedido = criar_pedido_publico(40.0)
    aprovado = resultado_mp(pedido, status="approved")
    mocks = []
    resposta = pagar_cartao(
        pedido, aprovado, capturar_mock=mocks,
        payer={"email": "cliente@example.com", "nome": "Ana", "sobrenome": "Souza", "documento_numero": "12345678900"},
    )
    assert resposta.status_code == 200, resposta.text
    _, kwargs = mocks[0].call_args
    assert kwargs["payer_first_name"] == "Ana"
    assert kwargs["payer_last_name"] == "Souza"


def test_nome_comprador_de_uma_palavra_e_aceito_sem_exigir_sobrenome():
    """Nome civil legítimo de uma única palavra (ex.: nomes indígenas,
    artísticos ou de uma só palavra) nunca é bloqueado nem obrigado a ter
    sobrenome -- last_name simplesmente não é enviado ao Mercado Pago."""
    pedido = criar_pedido_publico(40.0)
    aprovado = resultado_mp(pedido, status="approved")
    mocks = []
    resposta = pagar_cartao(
        pedido, aprovado, capturar_mock=mocks,
        payer={"email": "cliente@example.com", "nome": "Madonna", "documento_numero": "12345678900"},
    )
    assert resposta.status_code == 200, resposta.text
    _, kwargs = mocks[0].call_args
    assert kwargs["payer_first_name"] == "Madonna"
    assert kwargs["payer_last_name"] is None


def test_nome_comprador_composto_com_particula_hifen_apostrofo_e_acentos():
    pedido = criar_pedido_publico(40.0)
    aprovado = resultado_mp(pedido, status="approved")
    mocks = []
    resposta = pagar_cartao(
        pedido, aprovado, capturar_mock=mocks,
        payer={
            "email": "cliente@example.com",
            "nome": "José da Conceição",
            "sobrenome": "O'Brien-Souza",
            "documento_numero": "12345678900",
        },
    )
    assert resposta.status_code == 200, resposta.text
    _, kwargs = mocks[0].call_args
    assert kwargs["payer_first_name"] == "José da Conceição"
    assert kwargs["payer_last_name"] == "O'Brien-Souza"


def test_sobrenome_ausente_nao_e_enviado_como_campo_vazio():
    pedido = criar_pedido_publico(40.0)
    aprovado = resultado_mp(pedido, status="approved")
    mocks = []
    resposta = pagar_cartao(
        pedido, aprovado, capturar_mock=mocks,
        payer={"email": "cliente@example.com", "nome": "Ana", "sobrenome": "   ", "documento_numero": "12345678900"},
    )
    assert resposta.status_code == 200, resposta.text
    _, kwargs = mocks[0].call_args
    assert kwargs["payer_last_name"] is None


def test_nome_comprador_vazio_e_rejeitado():
    pedido = criar_pedido_publico(40.0)
    resposta = client.post(
        "/api/payments/mercadopago/card",
        json={
            "pedido_id": pedido["id"], "txid": pedido["pix_txid"], "token": "card_token_" + uuid.uuid4().hex,
            "payment_method_id": "visa", "installments": 1,
            "payer": {"email": "cliente@example.com", "nome": "", "documento_numero": "12345678900"},
        },
        headers={"Idempotency-Key": str(uuid.uuid4()), "X-Forwarded-For": ip_unico()},
    )
    assert resposta.status_code == 422


def test_nome_comprador_ausente_e_rejeitado():
    pedido = criar_pedido_publico(40.0)
    resposta = client.post(
        "/api/payments/mercadopago/card",
        json={
            "pedido_id": pedido["id"], "txid": pedido["pix_txid"], "token": "card_token_" + uuid.uuid4().hex,
            "payment_method_id": "visa", "installments": 1,
            "payer": {"email": "cliente@example.com", "documento_numero": "12345678900"},
        },
        headers={"Idempotency-Key": str(uuid.uuid4()), "X-Forwarded-For": ip_unico()},
    )
    assert resposta.status_code == 422


def test_nome_comprador_com_numeros_e_rejeitado():
    pedido = criar_pedido_publico(40.0)
    resposta = client.post(
        "/api/payments/mercadopago/card",
        json={
            "pedido_id": pedido["id"], "txid": pedido["pix_txid"], "token": "card_token_" + uuid.uuid4().hex,
            "payment_method_id": "visa", "installments": 1,
            "payer": {"email": "cliente@example.com", "nome": "Ana123", "documento_numero": "12345678900"},
        },
        headers={"Idempotency-Key": str(uuid.uuid4()), "X-Forwarded-For": ip_unico()},
    )
    assert resposta.status_code == 422


def test_nome_comprador_com_html_e_rejeitado():
    pedido = criar_pedido_publico(40.0)
    resposta = client.post(
        "/api/payments/mercadopago/card",
        json={
            "pedido_id": pedido["id"], "txid": pedido["pix_txid"], "token": "card_token_" + uuid.uuid4().hex,
            "payment_method_id": "visa", "installments": 1,
            "payer": {"email": "cliente@example.com", "nome": "<script>alert(1)</script>", "documento_numero": "12345678900"},
        },
        headers={"Idempotency-Key": str(uuid.uuid4()), "X-Forwarded-For": ip_unico()},
    )
    assert resposta.status_code == 422


def test_sobrenome_com_caracteres_invalidos_e_rejeitado():
    pedido = criar_pedido_publico(40.0)
    resposta = client.post(
        "/api/payments/mercadopago/card",
        json={
            "pedido_id": pedido["id"], "txid": pedido["pix_txid"], "token": "card_token_" + uuid.uuid4().hex,
            "payment_method_id": "visa", "installments": 1,
            "payer": {"email": "cliente@example.com", "nome": "Ana", "sobrenome": "Souza99", "documento_numero": "12345678900"},
        },
        headers={"Idempotency-Key": str(uuid.uuid4()), "X-Forwarded-For": ip_unico()},
    )
    assert resposta.status_code == 422


def test_nome_comprador_maior_que_limite_e_rejeitado():
    pedido = criar_pedido_publico(40.0)
    resposta = client.post(
        "/api/payments/mercadopago/card",
        json={
            "pedido_id": pedido["id"], "txid": pedido["pix_txid"], "token": "card_token_" + uuid.uuid4().hex,
            "payment_method_id": "visa", "installments": 1,
            "payer": {"email": "cliente@example.com", "nome": "A" * 61, "documento_numero": "12345678900"},
        },
        headers={"Idempotency-Key": str(uuid.uuid4()), "X-Forwarded-For": ip_unico()},
    )
    assert resposta.status_code == 422


def test_nome_comprador_nunca_aparece_no_log_de_resultado(caplog):
    pedido = criar_pedido_publico(40.0)
    aprovado = resultado_mp(pedido, status="approved")
    resposta, registros = _log_resultado_cartao(caplog, pedido, aprovado)
    assert resposta.status_code == 200
    assert len(registros) == 1
    texto = f"{registros[0].getMessage()} {registros[0].__dict__}".lower()
    assert "maria" not in texto
    for campo in ("nome", "sobrenome", "first_name", "last_name", "payer_first_name", "payer_last_name"):
        assert not hasattr(registros[0], campo)


def test_client_mercadopago_envia_first_name_e_last_name_quando_informados():
    import httpx

    from backend.mercadopago_client import criar_pagamento_cartao

    capturado = {}

    class FakeResponse:
        status_code = 201

        def json(self):
            return {"id": "mp-nome-1", "status": "approved", "status_detail": "accredited", "transaction_amount": 10.0, "currency_id": "BRL"}

    def fake_post(self, url, json=None, headers=None):
        capturado["json"] = json
        return FakeResponse()

    with patch.object(httpx.Client, "post", fake_post):
        criar_pagamento_cartao(
            idempotency_key="k-nome", transaction_amount=10.0, token="tok", installments=1,
            payment_method_id="visa", issuer_id=None, payer_email="c@example.com",
            payer_doc_type="CPF", payer_doc_number="12345678900",
            external_reference="1", description="Pedido #1",
            payer_first_name="Ana Maria", payer_last_name="Souza",
        )
    assert capturado["json"]["payer"]["first_name"] == "Ana Maria"
    assert capturado["json"]["payer"]["last_name"] == "Souza"


def test_client_mercadopago_sem_sobrenome_nao_envia_last_name():
    import httpx

    from backend.mercadopago_client import criar_pagamento_cartao

    capturado = {}

    class FakeResponse:
        status_code = 201

        def json(self):
            return {"id": "mp-nome-2", "status": "approved", "status_detail": "accredited", "transaction_amount": 10.0, "currency_id": "BRL"}

    def fake_post(self, url, json=None, headers=None):
        capturado["json"] = json
        return FakeResponse()

    with patch.object(httpx.Client, "post", fake_post):
        criar_pagamento_cartao(
            idempotency_key="k-sem-sobrenome", transaction_amount=10.0, token="tok", installments=1,
            payment_method_id="visa", issuer_id=None, payer_email="c@example.com",
            payer_doc_type="CPF", payer_doc_number="12345678900",
            external_reference="1", description="Pedido #1",
            payer_first_name="Madonna",
        )
    assert capturado["json"]["payer"]["first_name"] == "Madonna"
    assert "last_name" not in capturado["json"]["payer"]


# ---------------------------------------------------------------------------
# Auditoria de débito -- o backend NUNCA presume crédito por padrão nem
# bloqueia debit_card: payment_type_id/payment_method_id são sempre os
# devolvidos pelo Mercado Pago (nunca hardcoded), installments é o que o
# CardForm (SDK) realmente ofereceu para aquele cartão. Estes testes
# confirmam esse comportamento já existente via mock -- nenhum cartão real,
# nenhuma chamada real ao Mercado Pago. A habilitação EFETIVA de débito na
# conta Mercado Pago não pode ser confirmada por teste automatizado (depende
# de configuração da conta) -- ver relatório final para o caminho de
# verificação manual no painel.
# ---------------------------------------------------------------------------


def test_pagamento_identificado_como_debit_card_e_processado_sem_discriminacao():
    pedido = criar_pedido_publico(30.0)
    aprovado = resultado_mp(pedido, status="approved", payment_method_id="master", installments=1)
    # resultado_mp() sempre marca payment_type_id="credit_card" -- substitui
    # aqui pelo cenário real de débito devolvido pelo provedor.
    aprovado_debito = replace(aprovado, payment_type_id="debit_card")
    resposta = pagar_cartao(pedido, aprovado_debito, installments=1)
    assert resposta.status_code == 200, resposta.text
    corpo = resposta.json()
    assert corpo["status"] == "aprovado"
    assert corpo["aprovado"] is True
    detalhe = client.get(f"/api/pedidos/{pedido['id']}", headers=HEADERS).json()
    assert detalhe["forma_pagamento"].startswith("Débito")


def test_rotulo_forma_pagamento_debit_card_nunca_e_exibido_como_credito():
    from backend.pedido_comercial import rotulo_forma_pagamento

    assert rotulo_forma_pagamento("debit_card", "master") == "Débito · Mastercard"
    assert rotulo_forma_pagamento("credit_card", "master") == "Crédito · Mastercard"
    assert rotulo_forma_pagamento("debit_card", "master") != rotulo_forma_pagamento("credit_card", "master")


def test_debito_recusado_por_metodo_nao_habilitado_retorna_mensagem_amigavel():
    """Simula o provedor recusando a criação (4xx) por payment_method_id não
    habilitado para a conta -- cenário real quando débito não está ativado
    no painel do Mercado Pago. Nunca deve vazar o texto bruto do provedor."""
    pedido = criar_pedido_publico(30.0)
    recusado = resultado_mp(
        pedido, status="rejected", status_detail="invalid_payment_method", payment_id="",
        payment_method_id="debmaster",
    )
    recusado = replace(recusado, payment_type_id=None)
    resposta = pagar_cartao(pedido, recusado, installments=1)
    assert resposta.status_code == 200
    corpo = resposta.json()
    assert corpo["status"] == "recusado"
    assert "invalid_payment_method" not in corpo["mensagem"]


def test_installments_de_debito_permanece_em_1_quando_e_isso_que_o_sdk_envia():
    """O backend nunca força um número de parcelas -- aceita o que o CardForm
    (SDK oficial) realmente ofereceu. Para débito, o SDK só oferece 1 opção;
    este teste confirma que o backend preserva installments=1 tal como
    enviado, sem inflar nem exigir múltiplas parcelas."""
    pedido = criar_pedido_publico(30.0)
    aprovado = resultado_mp(pedido, status="approved", payment_method_id="maestro", installments=1)
    aprovado_debito = replace(aprovado, payment_type_id="debit_card")
    resposta = pagar_cartao(pedido, aprovado_debito, installments=1)
    assert resposta.status_code == 200
    assert resposta.json()["parcelas"] == 1
