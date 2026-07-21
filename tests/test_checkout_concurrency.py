import importlib
import os
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor

from fastapi.testclient import TestClient


TEST_API_KEY = "test-api-key"
os.environ.setdefault("MISTICA_SITE_API_KEY", TEST_API_KEY)
os.environ.setdefault("MISTICA_SYNC_KEY", TEST_API_KEY)
os.environ.setdefault("MISTICA_PIX_KEY", "49999999999")

main = importlib.import_module("backend.main")
HEADERS = {"X-Mistica-Api-Key": TEST_API_KEY}


def criar_produto_ultima_unidade() -> dict:
    codigo = f"CONC-{uuid.uuid4().hex[:10]}"
    with TestClient(main.app) as client:
        response = client.post(
            "/api/produtos",
            json={
                "codigo_p": codigo,
                "nome": "Produto concorrência última unidade",
                "preco": 29.9,
                "custo": 10.0,
                "quantidade": 1,
                "categoria": "Testes",
            },
            headers=HEADERS,
        )
    assert response.status_code == 200, response.text
    return {"id": response.json()["id"], "codigo_p": codigo}


def enviar_checkout(produto: dict, ip: str, barreira: threading.Barrier) -> tuple[int, dict]:
    payload = {
        "cliente": "Cliente concorrência",
        "forma_recebimento": "retirada",
        "itens": [
            {
                "produto_id": produto["id"],
                "codigo_p": produto["codigo_p"],
                "quantidade": 1,
            }
        ],
    }
    with TestClient(main.app) as client:
        barreira.wait(timeout=10)
        response = client.post(
            "/api/checkout/pedidos",
            json=payload,
            headers={"X-Forwarded-For": ip},
        )
    return response.status_code, response.json()


def test_dois_checkouts_nao_reservam_a_mesma_ultima_unidade():
    produto = criar_produto_ultima_unidade()
    barreira = threading.Barrier(2)

    with ThreadPoolExecutor(max_workers=2) as executor:
        futuros = [
            executor.submit(enviar_checkout, produto, "198.51.100.31", barreira),
            executor.submit(enviar_checkout, produto, "198.51.100.32", barreira),
        ]
        resultados = [futuro.result(timeout=20) for futuro in futuros]

    status = sorted(codigo for codigo, _corpo in resultados)
    assert status == [200, 409], resultados

    sucesso = next(corpo for codigo, corpo in resultados if codigo == 200)
    conflito = next(corpo for codigo, corpo in resultados if codigo == 409)
    assert sucesso["estoque_reservado"] is True
    assert "estoque insuficiente" in conflito["detail"].lower()

    with TestClient(main.app) as client:
        catalogo = client.get("/api/produtos", params={"busca": produto["codigo_p"]})
    assert catalogo.status_code == 200
    encontrado = next(item for item in catalogo.json() if item["id"] == produto["id"])
    assert encontrado["quantidade"] == 0
