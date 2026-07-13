import importlib
import os
import uuid

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

os.environ.setdefault("MISTICA_SITE_API_KEY", "test-api-key")
os.environ.setdefault("MISTICA_SYNC_KEY", "test-api-key")

main = importlib.import_module("backend.main")
product_routes = importlib.import_module("backend.product_routes")
client = TestClient(main.app)
client.__enter__()
HEADERS = {"X-Mistica-Api-Key": "test-api-key"}


def codigo(prefixo="INT"):
    return f"{prefixo}-{uuid.uuid4().hex[:8]}"


def payload_base(**overrides):
    payload = {
        "codigo_p": codigo(),
        "nome": "  Produto   de   teste  ",
        "preco": 19.90,
        "custo": 7.45,
        "quantidade": 5,
        "estoque_minimo": 1,
        "imagem_url": "https://example.com/produto.webp",
        "imagens": ["https://example.com/produto.webp"],
        "link_externo": "https://example.com/item",
    }
    payload.update(overrides)
    return payload


def test_codigo_e_nome_sao_normalizados_e_lucro_recalculado():
    codigo_original = f"  abc-{uuid.uuid4().hex[:8]}  "
    response = client.post(
        "/api/produtos",
        json=payload_base(codigo_p=codigo_original, nome="  Incenso   Natural ", lucro=999999),
        headers=HEADERS,
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["lucro"] == 12.45

    produtos = client.get("/api/produtos/admin", params={"busca": codigo_original.strip()}, headers=HEADERS).json()
    salvo = next(item for item in produtos if item["id"] == data["id"])
    assert salvo["codigo_p"] == codigo_original.strip().upper()
    assert salvo["nome"] == "Incenso Natural"
    assert salvo["lucro"] == 12.45


def test_codigo_duplicado_ignora_caixa_e_espacos():
    base = codigo("DUP")
    primeiro = client.post("/api/produtos", json=payload_base(codigo_p=base), headers=HEADERS)
    assert primeiro.status_code == 200, primeiro.text

    duplicado = client.post("/api/produtos", json=payload_base(codigo_p=f"  {base.lower()}  "), headers=HEADERS)
    assert duplicado.status_code == 409
    assert "Já existe" in duplicado.json()["detail"]


def test_edicao_tambem_impede_codigo_duplicado():
    a = client.post("/api/produtos", json=payload_base(codigo_p=codigo("EDA")), headers=HEADERS).json()
    codigo_b = codigo("EDB")
    b = client.post("/api/produtos", json=payload_base(codigo_p=codigo_b), headers=HEADERS).json()

    response = client.put(
        f"/api/produtos/{a['id']}",
        json=payload_base(codigo_p=f" {codigo_b.lower()} "),
        headers=HEADERS,
    )
    assert response.status_code == 409
    assert b["id"] != a["id"]


@pytest.mark.parametrize("campo,valor", [("preco", -1), ("preco", 1_000_000.01), ("custo", 4.999)])
def test_valores_monetarios_invalidos_sao_rejeitados(campo, valor):
    response = client.post("/api/produtos", json=payload_base(**{campo: valor}), headers=HEADERS)
    assert response.status_code == 422


def test_nan_e_infinito_sao_rejeitados_no_modelo():
    for valor in (float("nan"), float("inf"), float("-inf")):
        with pytest.raises(ValidationError):
            product_routes.ProdutoCompletoIn(**payload_base(preco=valor))


def test_urls_perigosas_e_relativas_sao_rejeitadas():
    for campo, valor in (
        ("imagem_url", "javascript:alert(1)"),
        ("imagem_url", "/imagem.webp"),
        ("link_externo", "http://example.com/item"),
        ("link_externo", "https://usuario:senha@example.com/item"),
    ):
        response = client.post("/api/produtos", json=payload_base(**{campo: valor}), headers=HEADERS)
        assert response.status_code == 422, (campo, valor, response.text)


def test_limites_de_texto_e_estoque_sao_aplicados():
    assert client.post("/api/produtos", json=payload_base(nome="x" * 161), headers=HEADERS).status_code == 422
    assert client.post("/api/produtos", json=payload_base(quantidade=1_000_001), headers=HEADERS).status_code == 422
    assert client.post("/api/produtos", json=payload_base(imagens=[f"https://example.com/{i}.webp" for i in range(13)]), headers=HEADERS).status_code == 422
