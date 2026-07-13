import importlib
import os
import uuid

from fastapi.testclient import TestClient


TEST_API_KEY = "test-api-key"
os.environ.setdefault("MISTICA_SITE_API_KEY", TEST_API_KEY)
os.environ.setdefault("MISTICA_SYNC_KEY", TEST_API_KEY)
os.environ["MISTICA_PIX_KEY"] = os.environ.get("MISTICA_PIX_KEY") or "checkout-integrity@example.com"

main = importlib.import_module("backend.main")
client = TestClient(main.app)
client.__enter__()
HEADERS = {"X-Mistica-Api-Key": TEST_API_KEY}


def codigo_unico(prefixo: str) -> str:
    return f"{prefixo}-{uuid.uuid4().hex[:10]}"


def criar_produto(*, preco: float = 37.9, quantidade: int = 3) -> dict:
    payload = {
        "codigo_p": codigo_unico("CHK"),
        "nome": "Produto de integridade do checkout",
        "preco": preco,
        "custo": 10.0,
        "quantidade": quantidade,
        "categoria": "Testes",
    }
    response = client.post("/api/produtos", json=payload, headers=HEADERS)
    assert response.status_code == 200, response.text
    return {**payload, "id": response.json()["id"]}


def pedido(produto: dict, *, quantidade: int = 1, extras: dict | None = None):
    payload = {
        "cliente": "Cliente teste",
        "itens": [
            {
                "produto_id": produto["id"],
                "codigo_p": produto["codigo_p"],
                "quantidade": quantidade,
                "valor_unitario": 0.01,
                "valor_total": 0.01,
                "custo_unitario": 999999.0,
            }
        ],
        "subtotal": 0.01,
        "desconto": 999999.0,
        "taxa": 999999.0,
        "total_final": 0.01,
    }
    if extras:
        payload.update(extras)
    # Cada cenário usa um IP próprio para não compartilhar a janela do rate limiter
    # com outros testes da suíte que também exercitam o checkout público.
    headers = {"X-Forwarded-For": f"198.51.100.{int(uuid.uuid4().hex[:2], 16) or 1}"}
    return client.post("/api/checkout/pedidos", json=payload, headers=headers)


def test_checkout_ignora_preco_subtotal_desconto_taxa_e_total_do_navegador():
    produto = criar_produto(preco=37.9, quantidade=3)

    response = pedido(produto, quantidade=2)

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["subtotal"] == 75.8
    assert data["desconto"] == 0.0
    assert data["total_final"] == 75.8
    assert data["estoque_reservado"] is True
    assert data["pix_copia_cola"]


def test_checkout_bloqueia_produto_inativo_mesmo_com_id_e_codigo_validos():
    produto = criar_produto(preco=25.0, quantidade=2)
    exclusao = client.delete(f"/api/produtos/{produto['id']}", headers=HEADERS)
    assert exclusao.status_code == 200, exclusao.text

    response = pedido(produto)

    assert response.status_code == 404
    assert "inativo" in response.json()["detail"].lower()


def test_checkout_bloqueia_quantidade_acima_do_estoque():
    produto = criar_produto(preco=12.5, quantidade=1)

    response = pedido(produto, quantidade=2)

    assert response.status_code == 409
    assert "estoque insuficiente" in response.json()["detail"].lower()


def test_checkout_rejeita_cupom_inexistente_sem_aplicar_desconto_enviado():
    produto = criar_produto(preco=50.0, quantidade=2)

    response = pedido(produto, extras={"cupom": "CUPOM-QUE-NAO-EXISTE"})

    assert response.status_code == 400
    assert "cupom inválido ou expirado" in response.json()["detail"].lower()
