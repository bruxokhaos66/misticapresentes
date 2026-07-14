import importlib
import os
import uuid

from fastapi.testclient import TestClient

from backend.database import conectar
from backend.order_status_routes import expirar_pedidos_pendentes


TEST_API_KEY = "test-api-key"
os.environ.setdefault("MISTICA_SITE_API_KEY", TEST_API_KEY)
os.environ.setdefault("MISTICA_SYNC_KEY", TEST_API_KEY)
os.environ["MISTICA_PIX_KEY"] = os.environ.get("MISTICA_PIX_KEY") or "order-lifecycle@example.com"

main = importlib.import_module("backend.main")
client = TestClient(main.app)
client.__enter__()
HEADERS = {"X-Mistica-Api-Key": TEST_API_KEY}


def codigo_unico(prefixo: str) -> str:
    return f"{prefixo}-{uuid.uuid4().hex[:10]}".upper()


def criar_produto(*, quantidade: int, sob_encomenda: bool = False, limite: int = 10) -> dict:
    payload = {
        "codigo_p": codigo_unico("CICLO"),
        "nome": "Produto de ciclo de estoque",
        "preco": 29.9,
        "custo": 10.0,
        "quantidade": quantidade,
        "categoria": "Testes",
        "sob_encomenda": sob_encomenda,
        "limite_encomenda": limite,
    }
    response = client.post("/api/produtos", json=payload, headers=HEADERS)
    assert response.status_code == 200, response.text
    return {**payload, "id": response.json()["id"]}


def criar_pedido(produto: dict, *, quantidade: int = 1, ciente: bool = False) -> dict:
    response = client.post(
        "/api/checkout/pedidos",
        headers={"X-Forwarded-For": f"203.0.113.{int(uuid.uuid4().hex[:2], 16) or 1}"},
        json={
            "cliente": "Cliente ciclo",
            "ciente_sob_encomenda": ciente,
            "itens": [
                {
                    "produto_id": produto["id"],
                    "codigo_p": produto["codigo_p"],
                    "quantidade": quantidade,
                }
            ],
        },
    )
    assert response.status_code == 200, response.text
    return response.json()


def estoque(produto_id: int) -> int:
    with conectar() as conn:
        row = conn.execute("SELECT quantidade FROM produtos WHERE id=?", (produto_id,)).fetchone()
    return int(row["quantidade"])


def test_confirmacao_repetida_nao_baixa_estoque_duas_vezes():
    produto = criar_produto(quantidade=2)
    pedido = criar_pedido(produto)

    assert estoque(produto["id"]) == 1
    assert pedido["estoque_baixado"] is True

    # A confirmação de pagamento só pode ser produzida por POST /api/pagamentos
    # (conciliação de valor contra pedidos.total_final) — ver
    # backend/order_status_routes.py::bloquear_avanco_financeiro_sem_conciliacao,
    # que bloqueia "Pagamento confirmado" na rota genérica de status.
    primeira = client.post(
        "/api/pagamentos",
        headers=HEADERS,
        json={"venda_id": pedido["id"], "valor": pedido["total_final"], "status": "Confirmado", "usuario": "Teste"},
    )
    segunda = client.post(
        "/api/pagamentos",
        headers=HEADERS,
        json={"venda_id": pedido["id"], "valor": pedido["total_final"], "status": "Confirmado", "usuario": "Teste"},
    )

    assert primeira.status_code == 200, primeira.text
    assert segunda.status_code == 200, segunda.text
    assert primeira.json()["estoque_baixado_agora"] is False
    assert segunda.json()["estoque_baixado_agora"] is False
    assert estoque(produto["id"]) == 1


def test_rota_generica_de_status_nao_confirma_pagamento_sem_conciliacao():
    """Regressão da falha encontrada na revisão: POST /api/pedidos/{id}/status
    não pode mais ser um caminho paralelo para produzir 'Pagamento confirmado'
    sem passar pela conciliação de valor em POST /api/pagamentos."""
    produto = criar_produto(quantidade=2)
    pedido = criar_pedido(produto)

    resposta = client.post(
        f"/api/pedidos/{pedido['id']}/status",
        headers=HEADERS,
        json={"status": "Pagamento confirmado", "usuario": "Teste"},
    )
    assert resposta.status_code == 409, resposta.text

    pedido_apos = client.get(f"/api/pedidos/{pedido['id']}", headers=HEADERS).json()
    assert pedido_apos["status"] == "Aguardando pagamento"

    resposta_separando = client.post(
        f"/api/pedidos/{pedido['id']}/status",
        headers=HEADERS,
        json={"status": "Separando pedido", "usuario": "Teste"},
    )
    assert resposta_separando.status_code == 409, resposta_separando.text

    # Depois de confirmar corretamente via /api/pagamentos, a progressão
    # logística continua funcionando normalmente pela rota genérica.
    confirmacao = client.post(
        "/api/pagamentos",
        headers=HEADERS,
        json={"venda_id": pedido["id"], "valor": pedido["total_final"], "status": "Confirmado", "usuario": "Teste"},
    )
    assert confirmacao.status_code == 200, confirmacao.text

    resposta_separando_apos = client.post(
        f"/api/pedidos/{pedido['id']}/status",
        headers=HEADERS,
        json={"status": "Separando pedido", "usuario": "Teste"},
    )
    assert resposta_separando_apos.status_code == 200, resposta_separando_apos.text
    assert client.get(f"/api/pedidos/{pedido['id']}", headers=HEADERS).json()["status"] == "Separando pedido"


def test_expiracao_repetida_repoe_reserva_uma_unica_vez():
    produto = criar_produto(quantidade=2)
    pedido = criar_pedido(produto)
    assert estoque(produto["id"]) == 1

    with conectar() as conn:
        conn.execute("UPDATE pedidos SET expira_em='2000-01-01T00:00:00' WHERE id=?", (pedido["id"],))
        conn.commit()
        primeira = expirar_pedidos_pendentes(conn, agora="2001-01-01T00:00:00")
        segunda = expirar_pedidos_pendentes(conn, agora="2001-01-01T00:00:01")

    assert primeira == 1
    assert segunda == 0
    assert estoque(produto["id"]) == 2

    with conectar() as conn:
        row = conn.execute(
            "SELECT status, estoque_reposto_cancelamento FROM pedidos WHERE id=?",
            (pedido["id"],),
        ).fetchone()
    assert row["status"] == "Cancelado"
    assert int(row["estoque_reposto_cancelamento"] or 0) == 1


def test_encomenda_expirada_nao_cria_estoque_fisico():
    produto = criar_produto(quantidade=0, sob_encomenda=True, limite=3)
    pedido = criar_pedido(produto, quantidade=2, ciente=True)

    assert pedido["estoque_baixado"] is False
    assert estoque(produto["id"]) == 0

    with conectar() as conn:
        conn.execute("UPDATE pedidos SET expira_em='2000-01-01T00:00:00' WHERE id=?", (pedido["id"],))
        conn.commit()
        expirados = expirar_pedidos_pendentes(conn, agora="2001-01-01T00:00:00")

    assert expirados == 1
    assert estoque(produto["id"]) == 0
