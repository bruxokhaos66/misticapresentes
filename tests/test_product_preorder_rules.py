import importlib
import os
import uuid

from fastapi.testclient import TestClient


TEST_API_KEY = "test-api-key"
os.environ.setdefault("MISTICA_SITE_API_KEY", TEST_API_KEY)
os.environ.setdefault("MISTICA_SYNC_KEY", TEST_API_KEY)

main = importlib.import_module("backend.main")
client = TestClient(main.app)
client.__enter__()
HEADERS = {"X-Mistica-Api-Key": TEST_API_KEY}


def codigo_unico(prefixo: str) -> str:
    return f"{prefixo}-{uuid.uuid4().hex[:10]}"


def test_produto_sob_encomenda_e_limite_aparecem_no_catalogo_publico():
    codigo = codigo_unico("ENC")
    response = client.post(
        "/api/produtos",
        headers=HEADERS,
        json={
            "codigo_p": codigo,
            "nome": "Produto sob encomenda explícito",
            "preco": 89.9,
            "custo": 40.0,
            "quantidade": 0,
            "categoria": "Produtos especiais",
            "selo": "Exclusivo",
            "sob_encomenda": True,
            "limite_encomenda": 7,
        },
    )
    assert response.status_code == 200, response.text
    criado = response.json()
    assert criado["sob_encomenda"] is True
    assert criado["limite_encomenda"] == 7

    catalogo = client.get("/api/produtos", params={"busca": codigo, "limite": 10})
    assert catalogo.status_code == 200, catalogo.text
    produto = next(item for item in catalogo.json() if item["codigo_p"] == codigo)
    assert produto["sob_encomenda"] is True
    assert produto["limite_encomenda"] == 7
    assert produto["quantidade"] == 0


def test_produto_normal_tem_regra_explicita_desativada_por_padrao():
    codigo = codigo_unico("NORMAL")
    response = client.post(
        "/api/produtos",
        headers=HEADERS,
        json={
            "codigo_p": codigo,
            "nome": "Produto normal",
            "preco": 19.9,
            "quantidade": 2,
        },
    )
    assert response.status_code == 200, response.text
    assert response.json()["sob_encomenda"] is False

    catalogo = client.get("/api/produtos", params={"busca": codigo, "limite": 10})
    produto = next(item for item in catalogo.json() if item["codigo_p"] == codigo)
    assert produto["sob_encomenda"] is False
    assert produto["limite_encomenda"] == 10


def test_limite_de_encomenda_fora_da_faixa_e_rejeitado():
    base = {
        "codigo_p": codigo_unico("LIM"),
        "nome": "Produto com limite inválido",
        "preco": 10.0,
        "quantidade": 0,
        "sob_encomenda": True,
    }

    abaixo = client.post(
        "/api/produtos",
        headers=HEADERS,
        json={**base, "limite_encomenda": 0},
    )
    acima = client.post(
        "/api/produtos",
        headers=HEADERS,
        json={**base, "codigo_p": codigo_unico("LIM"), "limite_encomenda": 101},
    )

    assert abaixo.status_code == 422
    assert acima.status_code == 422
