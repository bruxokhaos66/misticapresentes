"""Fase B — Auditoria do fluxo comercial: visibilidade de estorno pendente.

Cancelar um pedido que já teve pagamento confirmado (backend/
order_status_routes.py::cancelar_com_reposicao) nunca estorna o pagamento
automaticamente por desenho (decisão financeira fica com o operador) — mas
antes desta rota não havia nenhuma forma de listar quais pedidos cancelados
ainda têm dinheiro recebido sem devolução formal registrada, exigindo cruzar
manualmente GET /api/pedidos com GET /api/pagamentos. Este teste cobre a nova
rota GET /api/pagamentos/estornos-pendentes.
"""

import importlib
import os
import uuid

from fastapi.testclient import TestClient

os.environ.setdefault("MISTICA_SITE_API_KEY", "test-api-key")
os.environ.setdefault("MISTICA_SYNC_KEY", "test-api-key")
os.environ.setdefault("MISTICA_PIX_WEBHOOK_SECRET", "test-estorno-pendente-webhook-secret")
os.environ.setdefault("MISTICA_PIX_KEY", "49999999999")

main = importlib.import_module("backend.main")
client = TestClient(main.app)
client.__enter__()

TEST_API_KEY = os.environ["MISTICA_SITE_API_KEY"]
HEADERS = {"X-Mistica-Api-Key": TEST_API_KEY}


def ip_unico() -> str:
    return f"203.0.114.{uuid.uuid4().int % 256}"


def codigo_unico(prefixo: str) -> str:
    return f"{prefixo}-{uuid.uuid4().hex[:10]}"


def criar_produto(preco: float = 50.0, quantidade: int = 10) -> dict:
    resposta = client.post(
        "/api/produtos",
        json={
            "nome": "Produto estorno pendente",
            "codigo_p": codigo_unico("ESTPEND"),
            "preco": preco,
            "quantidade": quantidade,
            "categoria": "Testes",
        },
        headers=HEADERS,
    )
    assert resposta.status_code == 200, resposta.text
    return resposta.json()


def criar_pedido_pendente(preco: float = 50.0, quantidade: int = 1) -> dict:
    produto = criar_produto(preco, quantidade=quantidade + 10)
    resposta = client.post(
        "/api/vendas",
        json={
            "cliente": "Cliente estorno pendente",
            "status": "Aguardando pagamento",
            "baixa_estoque": True,
            "itens": [{"produto_id": produto["id"], "quantidade": quantidade}],
        },
        headers={**HEADERS, "X-Forwarded-For": ip_unico()},
    )
    assert resposta.status_code == 200, resposta.text
    return client.get(f"/api/pedidos/{resposta.json()['id']}", headers=HEADERS).json()


def confirmar_pagamento(pedido: dict) -> dict:
    resposta = client.post(
        "/api/pagamentos",
        json={"venda_id": pedido["id"], "valor": pedido["total_final"], "status": "Confirmado"},
        headers={**HEADERS, "X-Forwarded-For": ip_unico()},
    )
    assert resposta.status_code == 200, resposta.text
    corpo = resposta.json()
    assert corpo["confirmado"] is True
    return corpo


def cancelar_pedido(pedido_id: int) -> dict:
    resposta = client.delete(f"/api/pedidos/{pedido_id}", headers=HEADERS)
    assert resposta.status_code == 200, resposta.text
    return resposta.json()


def listar_estornos_pendentes() -> list[dict]:
    resposta = client.get("/api/pagamentos/estornos-pendentes", headers=HEADERS)
    assert resposta.status_code == 200, resposta.text
    return resposta.json()


def test_pedido_cancelado_apos_pagamento_confirmado_aparece_como_estorno_pendente():
    pedido = criar_pedido_pendente(preco=88.0)
    confirmar_pagamento(pedido)

    ids_antes = {item["venda_id"] for item in listar_estornos_pendentes()}
    assert pedido["id"] not in ids_antes

    cancelar_pedido(pedido["id"])

    ids_depois = {item["venda_id"] for item in listar_estornos_pendentes()}
    assert pedido["id"] in ids_depois


def test_marcar_pagamento_como_estornado_remove_o_pedido_da_lista():
    pedido = criar_pedido_pendente(preco=61.0)
    pagamento = confirmar_pagamento(pedido)
    cancelar_pedido(pedido["id"])

    assert pedido["id"] in {item["venda_id"] for item in listar_estornos_pendentes()}

    resposta = client.put(
        f"/api/pagamentos/{pagamento['id']}/status",
        json={"status": "Estornado", "usuario": "Admin"},
        headers={**HEADERS, "X-Forwarded-For": ip_unico()},
    )
    assert resposta.status_code == 200, resposta.text

    assert pedido["id"] not in {item["venda_id"] for item in listar_estornos_pendentes()}


def test_pedido_cancelado_sem_pagamento_confirmado_nao_aparece_na_lista():
    pedido = criar_pedido_pendente(preco=45.0)
    cancelar_pedido(pedido["id"])

    assert pedido["id"] not in {item["venda_id"] for item in listar_estornos_pendentes()}


def test_pedido_pago_nao_cancelado_nao_aparece_na_lista():
    pedido = criar_pedido_pendente(preco=72.0)
    confirmar_pagamento(pedido)

    assert pedido["id"] not in {item["venda_id"] for item in listar_estornos_pendentes()}
