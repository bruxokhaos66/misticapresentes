"""Testes do estorno atômico de vendas de caixa/PDV via API
(POST /api/vendas/{venda_id}/estornar, Fase 2 — PR fix/caixa-estorno-atomico).

Antes desta correção, backend/main.py::estornar_venda lia o status da venda
num SELECT e só depois decidia (Python) se devolvia estoque e escrevia
'Cancelado' num UPDATE incondicional — nunca com guarda no WHERE. Duas
chamadas concorrentes desta rota para a mesma venda (dois cliques no painel
administrativo, um retry de rede, ou uma corrida com
services.venda_service.cancelar_venda_service chamado localmente pelo PDV
sobre o mesmo banco compartilhado) podiam ler o mesmo status "antigo" e as
duas devolverem estoque.

A correção usa o mesmo padrão de compare-and-swap já estabelecido em
backend/order_status_routes.py::cancelar_com_reposicao (PR #314): um único
UPDATE com guarda no próprio WHERE decide atomicamente quem reivindica a
transição; só quem reivindica devolve estoque."""

import importlib
import os
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

from fastapi.testclient import TestClient

os.environ.setdefault("MISTICA_SITE_API_KEY", "test-api-key")
os.environ.setdefault("MISTICA_SYNC_KEY", "test-api-key")
os.environ.setdefault("MISTICA_PIX_WEBHOOK_SECRET", "test-estorno-caixa-webhook-secret")
os.environ.setdefault("MISTICA_PIX_KEY", "49999999999")

from backend.database import conectar  # noqa: E402

main = importlib.import_module("backend.main")
client = TestClient(main.app)
client.__enter__()

TEST_API_KEY = os.environ["MISTICA_SITE_API_KEY"]
HEADERS = {"X-Mistica-Api-Key": TEST_API_KEY}


def codigo_unico(prefixo: str) -> str:
    return f"{prefixo}-{uuid.uuid4().hex[:10]}"


def criar_produto(*, quantidade: int = 10, preco: float = 45.0) -> dict:
    payload = {
        "codigo_p": codigo_unico("ESTPDV"),
        "nome": f"Produto estorno pdv {uuid.uuid4().hex[:8]}",
        "preco": preco,
        "custo": 15.0,
        "quantidade": quantidade,
        "categoria": "Testes",
    }
    resposta = client.post("/api/produtos", json=payload, headers=HEADERS)
    assert resposta.status_code == 200, resposta.text
    return {**payload, "id": resposta.json()["id"], "codigo_p": payload["codigo_p"].upper()}


def estoque(codigo_p: str) -> int:
    with conectar() as conn:
        row = conn.execute("SELECT quantidade FROM produtos WHERE codigo_p=?", (codigo_p,)).fetchone()
    return int(row["quantidade"])


def criar_venda_direto(produto: dict, *, quantidade: int = 1) -> int:
    """Insere uma venda concluída de caixa/PDV diretamente nas tabelas vendas/
    vendas_itens, do mesmo jeito que services/venda_service.registrar_venda_service
    faria — sem passar pela rota HTTP, já que a criação de vendas de PDV não é
    exposta como endpoint público (é feita localmente pelo app desktop)."""
    agora = datetime.now().strftime("%d/%m/%Y %H:%M")
    agora_iso = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    total = round(produto["preco"] * quantidade, 2)
    with conectar() as conn:
        cur = conn.execute(
            """
            INSERT INTO vendas (cliente, data_venda, data_iso, subtotal, desconto, taxa, total_final, forma_pagamento, vendedor, status)
            VALUES (?,?,?,?,?,?,?,?,?,?)
            """,
            ("Consumidor Final", agora, agora_iso, total, 0.0, 0.0, total, "Dinheiro", "Teste", "Concluído"),
        )
        venda_id = int(cur.lastrowid)
        conn.execute(
            """
            INSERT INTO vendas_itens (venda_id, codigo_p, nome_p, quantidade, custo_unitario, valor_unitario, valor_total)
            VALUES (?,?,?,?,?,?,?)
            """,
            (venda_id, produto["codigo_p"], produto["nome"], quantidade, produto["custo"], produto["preco"], total),
        )
        conn.execute("UPDATE produtos SET quantidade = quantidade - ? WHERE codigo_p=?", (quantidade, produto["codigo_p"]))
        conn.commit()
    return venda_id


def estornar(venda_id: int):
    return client.post(f"/api/vendas/{venda_id}/estornar", headers=HEADERS, json={"usuario": "Teste"})


# 1 — estorno simples devolve estoque


def test_estorno_simples_devolve_estoque():
    produto = criar_produto(quantidade=5)
    venda_id = criar_venda_direto(produto, quantidade=2)
    assert estoque(produto["codigo_p"]) == 3

    resposta = estornar(venda_id)
    assert resposta.status_code == 200, resposta.text
    corpo = resposta.json()
    assert corpo["status"] == "Cancelado"
    assert corpo["ja_cancelada"] is False
    assert estoque(produto["codigo_p"]) == 5


# 2 — estorno repetido é idempotente


def test_estorno_repetido_e_idempotente():
    produto = criar_produto(quantidade=5)
    venda_id = criar_venda_direto(produto, quantidade=1)

    primeira = estornar(venda_id)
    segunda = estornar(venda_id)
    terceira = estornar(venda_id)

    assert primeira.status_code == 200 and primeira.json()["ja_cancelada"] is False
    for resposta in (segunda, terceira):
        assert resposta.status_code == 200, resposta.text
        assert resposta.json()["ja_cancelada"] is True

    assert estoque(produto["codigo_p"]) == 5  # nunca duplica a devolução


# 3 — dois estornos simultâneos não duplicam devolução de estoque


def test_dois_estornos_simultaneos_nao_duplicam_devolucao():
    produto = criar_produto(quantidade=5)
    venda_id = criar_venda_direto(produto, quantidade=2)
    assert estoque(produto["codigo_p"]) == 3
    barreira = threading.Barrier(2)

    def enviar():
        with TestClient(main.app) as thread_client:
            barreira.wait(timeout=10)
            return thread_client.post(f"/api/vendas/{venda_id}/estornar", headers=HEADERS, json={"usuario": "Teste"})

    with ThreadPoolExecutor(max_workers=2) as executor:
        futuros = [executor.submit(enviar) for _ in range(2)]
        respostas = [f.result(timeout=20) for f in futuros]

    for resposta in respostas:
        assert resposta.status_code == 200, resposta.text
    assert sum(1 for r in respostas if r.json()["ja_cancelada"] is False) == 1
    assert sum(1 for r in respostas if r.json()["ja_cancelada"] is True) == 1
    assert estoque(produto["codigo_p"]) == 5


# 4 — venda inexistente


def test_estorno_de_venda_inexistente_retorna_404():
    resposta = estornar(999_999_999)
    assert resposta.status_code == 404


# 5 — auditoria registrada uma única vez, mesmo sob concorrência


def test_auditoria_de_estorno_registrada_uma_unica_vez_sob_concorrencia():
    import json as _json

    produto = criar_produto(quantidade=5)
    venda_id = criar_venda_direto(produto, quantidade=1)
    barreira = threading.Barrier(2)

    def enviar():
        with TestClient(main.app) as thread_client:
            barreira.wait(timeout=10)
            return thread_client.post(f"/api/vendas/{venda_id}/estornar", headers=HEADERS, json={"usuario": "Teste"})

    with ThreadPoolExecutor(max_workers=2) as executor:
        futuros = [executor.submit(enviar) for _ in range(2)]
        [f.result(timeout=20) for f in futuros]

    with conectar() as conn:
        linhas = conn.execute(
            "SELECT dados_antes, dados_depois FROM audit_log WHERE entidade='venda' AND entidade_id=? AND acao='estornar'",
            (str(venda_id),),
        ).fetchall()
    assert len(linhas) == 1
    assert _json.loads(linhas[0]["dados_depois"])["status"] == "Cancelado"
