from __future__ import annotations

import importlib
import os
import uuid
from datetime import datetime

from fastapi.testclient import TestClient

from backend.database import conectar


TEST_API_KEY = "test-api-key"  # pragma: allowlist secret
os.environ["MISTICA_SITE_API_KEY"] = TEST_API_KEY
os.environ["MISTICA_SYNC_KEY"] = TEST_API_KEY
os.environ.setdefault("MISTICA_PIX_KEY", "checkout-coupon@example.com")  # pragma: allowlist secret

main = importlib.import_module("backend.main")
client = TestClient(main.app)
client.__enter__()
HEADERS = {"X-Mistica-Api-Key": TEST_API_KEY}


def _codigo(prefixo: str) -> str:
    return f"{prefixo}-{uuid.uuid4().hex[:10]}"


def _criar_produto(*, preco: float = 50.0, quantidade: int = 3) -> dict:
    payload = {
        "codigo_p": _codigo("CUP-PROD"),
        "nome": "Produto teste de cupom HTTP",
        "preco": preco,
        "custo": 10.0,
        "quantidade": quantidade,
        "categoria": "Testes",
    }
    response = client.post("/api/produtos", json=payload, headers=HEADERS)
    assert response.status_code == 200, response.text
    return {**payload, "id": response.json()["id"]}


def _criar_campanha(*, tipo: str, valor: float) -> str:
    codigo = _codigo("CUPOM")
    agora = datetime.now().isoformat(timespec="seconds")
    with conectar() as conn:
        conn.execute(
            """
            INSERT INTO campanhas (
                titulo, descricao, tipo, valor, codigo_cupom, ativo,
                data_inicio, data_fim, criado_em, atualizado_em
            ) VALUES (?,?,?,?,?,?,?,?,?,?)
            """,
            (
                f"Campanha {codigo}",
                "Teste HTTP de cupom",
                tipo,
                valor,
                codigo,
                1,
                None,
                None,
                agora,
                agora,
            ),
        )
        conn.commit()
    return codigo


def _checkout(produto: dict, cupom: str):
    payload = {
        "cliente": "Cliente cupom HTTP",
        "itens": [
            {
                "produto_id": produto["id"],
                "codigo_p": produto["codigo_p"],
                "quantidade": 1,
                "valor_unitario": 0.01,
                "valor_total": 0.01,
            }
        ],
        "subtotal": 0.01,
        "desconto": 9999.0,
        "taxa": 9999.0,
        "total_final": 0.01,
        "cupom": cupom.lower(),
    }
    headers = {
        "X-Forwarded-For": f"198.51.100.{int(uuid.uuid4().hex[:2], 16) or 1}",
        "Idempotency-Key": str(uuid.uuid4()),
    }
    return client.post("/api/checkout/pedidos", json=payload, headers=headers)


def test_checkout_aplica_desconto_fixo_do_banco_e_ignora_valores_do_cliente():
    produto = _criar_produto(preco=50.0)
    cupom = _criar_campanha(tipo="desconto_fixo", valor=12.5)

    response = _checkout(produto, cupom)

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["subtotal"] == 50.0
    assert data["desconto"] == 12.5
    assert data["total_final"] == 37.5
    assert data["cupom"] == cupom
    assert data["frete_gratis"] is False


def test_checkout_frete_gratis_nao_reduz_valor_dos_produtos():
    produto = _criar_produto(preco=80.0)
    cupom = _criar_campanha(tipo="frete_gratis", valor=0)

    response = _checkout(produto, cupom)

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["subtotal"] == 80.0
    assert data["desconto"] == 0.0
    assert data["total_final"] == 80.0
    assert data["cupom"] == cupom
    assert data["frete_gratis"] is True
