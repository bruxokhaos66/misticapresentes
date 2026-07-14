"""Testes da conciliação de valor no fluxo de pagamento (Fase 2 — PR fix/pix-validar-valor-pago).

Cobrem a regra autoritativa: um pagamento só confirma o pedido quando
valor_recebido == total_final_autoritativo do pedido (comparação em centavos
via Decimal, nunca `float ==`), tanto na confirmação manual (POST
/api/pagamentos, PUT /api/pagamentos/{id}/status) quanto no webhook Pix
(POST /api/pagamentos/webhook), incluindo idempotência e concorrência.
"""

import importlib
import os
import sqlite3
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor

from fastapi.testclient import TestClient

os.environ.setdefault("MISTICA_SITE_API_KEY", "test-api-key")
os.environ.setdefault("MISTICA_SYNC_KEY", "test-api-key")
os.environ.setdefault("MISTICA_PIX_WEBHOOK_SECRET", "test-pagamento-conciliacao-webhook-secret")
os.environ.setdefault("MISTICA_PIX_KEY", "49999999999")

main = importlib.import_module("backend.main")
client = TestClient(main.app)
client.__enter__()

# Lidos de volta do ambiente (em vez de literais fixos) porque outro módulo de
# teste, importado antes deste no mesmo processo pytest, pode já ter definido
# essas variáveis primeiro (setdefault não sobrescreve); usar sempre o valor
# efetivamente ativo evita testes que passam isolados mas falham na suíte
# completa por autenticação com uma chave que nunca foi a realmente aplicada.
TEST_API_KEY = os.environ["MISTICA_SITE_API_KEY"]
WEBHOOK_SECRET = os.environ["MISTICA_PIX_WEBHOOK_SECRET"]
HEADERS = {"X-Mistica-Api-Key": TEST_API_KEY}
WEBHOOK_HEADERS = {"X-Mistica-Webhook-Secret": WEBHOOK_SECRET}


def codigo_unico(prefixo: str) -> str:
    return f"{prefixo}-{uuid.uuid4().hex[:10]}"


def criar_produto(preco: float, quantidade: int = 20) -> dict:
    resposta = client.post(
        "/api/produtos",
        json={
            "nome": "Produto Conciliação Pagamento",
            "codigo_p": codigo_unico("CONC"),
            "preco": preco,
            "quantidade": quantidade,
            "categoria": "Testes",
        },
        headers=HEADERS,
    )
    assert resposta.status_code == 200, resposta.text
    return resposta.json()


def criar_pedido_pendente(preco: float, quantidade: int = 1) -> dict:
    """Cria um pedido 'Aguardando pagamento' com estoque reservado e total_final
    autoritativo = preco * quantidade (recalculado pelo servidor)."""
    produto = criar_produto(preco, quantidade=quantidade + 10)
    resposta = client.post(
        "/api/vendas",
        json={
            "cliente": "Cliente Conciliação",
            "status": "Aguardando pagamento",
            "baixa_estoque": True,
            "itens": [{"produto_id": produto["id"], "quantidade": quantidade}],
        },
        headers=HEADERS,
    )
    assert resposta.status_code == 200, resposta.text
    criado = resposta.json()
    pedido = client.get(f"/api/pedidos/{criado['id']}", headers=HEADERS).json()
    return {"pedido": pedido, "produto": produto}


def obter_pedido(pedido_id: int) -> dict:
    return client.get(f"/api/pedidos/{pedido_id}", headers=HEADERS).json()


def obter_produto(produto_id: int) -> dict:
    return client.get(f"/api/produtos/{produto_id}").json()


# ---------------------------------------------------------------------------
# 1. Valor exato confirma
# ---------------------------------------------------------------------------


def test_valor_exato_confirma_pedido_e_baixa_estoque_uma_unica_vez():
    contexto = criar_pedido_pendente(preco=37.50, quantidade=2)
    pedido = contexto["pedido"]
    total_final = pedido["total_final"]
    assert total_final == 75.0

    quantidade_apos_reserva = obter_produto(contexto["produto"]["id"])["quantidade"]

    resposta = client.post(
        "/api/pagamentos",
        json={"venda_id": pedido["id"], "valor": total_final, "status": "Confirmado"},
        headers=HEADERS,
    )
    assert resposta.status_code == 200, resposta.text
    corpo = resposta.json()
    assert corpo["confirmado"] is True
    assert corpo["status_conciliacao"] == "ok"
    assert corpo["status"] == "Confirmado"

    pedido_apos = obter_pedido(pedido["id"])
    assert pedido_apos["status"] == "Pagamento confirmado"
    assert bool(pedido_apos["estoque_baixado"]) is True

    # Estoque já tinha sido reservado na criação do pedido pendente; a
    # confirmação não decrementa de novo.
    assert obter_produto(contexto["produto"]["id"])["quantidade"] == quantidade_apos_reserva


def test_pedido_ja_confirmado_permanece_idempotente_em_nova_confirmacao_exata():
    contexto = criar_pedido_pendente(preco=20.0, quantidade=1)
    pedido = contexto["pedido"]

    primeira = client.post(
        "/api/pagamentos",
        json={"venda_id": pedido["id"], "valor": pedido["total_final"], "status": "Confirmado"},
        headers=HEADERS,
    )
    assert primeira.status_code == 200
    # O estoque já foi reservado na criação do pedido pendente (ver
    # criar_pedido_pendente); a confirmação de pagamento não baixa de novo.
    assert primeira.json()["estoque_baixado_agora"] is False
    assert primeira.json()["confirmado"] is True

    quantidade_apos_primeira = obter_produto(contexto["produto"]["id"])["quantidade"]

    segunda = client.post(
        "/api/pagamentos",
        json={"venda_id": pedido["id"], "valor": pedido["total_final"], "status": "Confirmado"},
        headers=HEADERS,
    )
    assert segunda.status_code == 200
    corpo = segunda.json()
    assert corpo["confirmado"] is True
    assert corpo["estoque_baixado_agora"] is False

    assert obter_produto(contexto["produto"]["id"])["quantidade"] == quantidade_apos_primeira
    assert obter_pedido(pedido["id"])["status"] == "Pagamento confirmado"


# ---------------------------------------------------------------------------
# 2. Valor menor não confirma
# ---------------------------------------------------------------------------


def test_valor_menor_nao_confirma_nem_baixa_estoque():
    contexto = criar_pedido_pendente(preco=60.0, quantidade=1)
    pedido = contexto["pedido"]
    quantidade_apos_reserva = obter_produto(contexto["produto"]["id"])["quantidade"]

    resposta = client.post(
        "/api/pagamentos",
        json={"venda_id": pedido["id"], "valor": 50.0, "status": "Confirmado"},
        headers=HEADERS,
    )
    assert resposta.status_code == 200, resposta.text
    corpo = resposta.json()
    assert corpo["confirmado"] is False
    assert corpo["status_conciliacao"] == "divergente_menor"
    assert corpo["status"] == "Aguardando"
    assert "motivo_divergencia" in corpo

    pedido_apos = obter_pedido(pedido["id"])
    assert pedido_apos["status"] == "Pagamento divergente"
    # Estoque continua apenas com a reserva original (não houve baixa nem reposição).
    assert obter_produto(contexto["produto"]["id"])["quantidade"] == quantidade_apos_reserva


# ---------------------------------------------------------------------------
# 3. Valor maior não confirma automaticamente
# ---------------------------------------------------------------------------


def test_valor_maior_nao_confirma_automaticamente():
    contexto = criar_pedido_pendente(preco=40.0, quantidade=1)
    pedido = contexto["pedido"]

    resposta = client.post(
        "/api/pagamentos",
        json={"venda_id": pedido["id"], "valor": 999.0, "status": "Confirmado"},
        headers=HEADERS,
    )
    assert resposta.status_code == 200, resposta.text
    corpo = resposta.json()
    assert corpo["confirmado"] is False
    assert corpo["status_conciliacao"] == "divergente_maior"
    assert corpo["status"] == "Aguardando"

    pedido_apos = obter_pedido(pedido["id"])
    assert pedido_apos["status"] == "Pagamento divergente"
    assert bool(pedido_apos["estoque_baixado"]) is True  # só a reserva original


# ---------------------------------------------------------------------------
# 4. Valor ausente não confirma
# ---------------------------------------------------------------------------


def test_valor_ausente_nao_confirma():
    contexto = criar_pedido_pendente(preco=15.0, quantidade=1)
    pedido = contexto["pedido"]

    resposta = client.post(
        "/api/pagamentos",
        json={"venda_id": pedido["id"], "status": "Confirmado"},
        headers=HEADERS,
    )
    assert resposta.status_code == 422

    assert obter_pedido(pedido["id"])["status"] == "Aguardando pagamento"


# ---------------------------------------------------------------------------
# 5. Valor inválido é rejeitado
# ---------------------------------------------------------------------------


def test_valor_negativo_e_rejeitado():
    contexto = criar_pedido_pendente(preco=15.0, quantidade=1)
    pedido = contexto["pedido"]

    resposta = client.post(
        "/api/pagamentos",
        json={"venda_id": pedido["id"], "valor": -10.0, "status": "Confirmado"},
        headers=HEADERS,
    )
    assert resposta.status_code == 422
    assert obter_pedido(pedido["id"])["status"] == "Aguardando pagamento"


def test_valor_nao_numerico_e_rejeitado():
    contexto = criar_pedido_pendente(preco=15.0, quantidade=1)
    pedido = contexto["pedido"]

    resposta = client.post(
        "/api/pagamentos",
        json={"venda_id": pedido["id"], "valor": "nao-e-numero", "status": "Confirmado"},
        headers=HEADERS,
    )
    assert resposta.status_code == 422
    assert obter_pedido(pedido["id"])["status"] == "Aguardando pagamento"


# ---------------------------------------------------------------------------
# 6/7. Arredondamento de centavos e float impreciso
# ---------------------------------------------------------------------------


def test_arredondamento_de_centavos_nao_gera_falso_positivo_nem_negativo():
    # 0.10 * 3 tende a acumular erro de ponto flutuante em soma ingênua
    # (0.1 + 0.1 + 0.1 != 0.3 em binário); o backend já recalcula o total via
    # Decimal na criação do pedido, e a conciliação também precisa comparar em
    # centavos para não confundir 0.30000000000000004 com um valor diferente.
    contexto = criar_pedido_pendente(preco=0.10, quantidade=3)
    pedido = contexto["pedido"]
    assert pedido["total_final"] == 0.3

    valor_impreciso = 0.1 + 0.1 + 0.1  # 0.30000000000000004 em Python
    assert valor_impreciso != 0.3

    resposta = client.post(
        "/api/pagamentos",
        json={"venda_id": pedido["id"], "valor": valor_impreciso, "status": "Confirmado"},
        headers=HEADERS,
    )
    assert resposta.status_code == 200
    corpo = resposta.json()
    assert corpo["confirmado"] is True
    assert corpo["status_conciliacao"] == "ok"


def test_valor_um_centavo_a_menos_e_tratado_como_divergencia_real():
    # Garante que a tolerância de arredondamento não vira uma brecha: um
    # centavo de diferença real ainda deve ser detectado como divergência.
    contexto = criar_pedido_pendente(preco=10.00, quantidade=1)
    pedido = contexto["pedido"]

    resposta = client.post(
        "/api/pagamentos",
        json={"venda_id": pedido["id"], "valor": 9.99, "status": "Confirmado"},
        headers=HEADERS,
    )
    assert resposta.status_code == 200
    corpo = resposta.json()
    assert corpo["confirmado"] is False
    assert corpo["status_conciliacao"] == "divergente_menor"


# ---------------------------------------------------------------------------
# 8/9. Callback duplicado e concorrente do webhook Pix
# ---------------------------------------------------------------------------


def test_webhook_com_valor_exato_confirma_e_e_idempotente_em_chamada_duplicada_sequencial():
    contexto = criar_pedido_pendente(preco=45.0, quantidade=1)
    pedido = contexto["pedido"]
    assert pedido["pix_txid"], "pedido deveria ter txid Pix gerado (MISTICA_PIX_KEY configurada nos testes)"

    payload = {"txid": pedido["pix_txid"], "valor": pedido["total_final"], "status": "Confirmado"}

    primeira = client.post("/api/pagamentos/webhook", json=payload, headers=WEBHOOK_HEADERS)
    assert primeira.status_code == 200
    assert primeira.json()["confirmado"] is True

    segunda = client.post("/api/pagamentos/webhook", json=payload, headers=WEBHOOK_HEADERS)
    assert segunda.status_code == 200
    assert segunda.json()["id"] == primeira.json()["id"]  # mesma resposta salva, não reprocessou

    pagamentos = client.get("/api/pagamentos", params={"venda_id": pedido["id"]}, headers=HEADERS).json()
    assert len(pagamentos) == 1  # um único registro de pagamento para os dois callbacks


def test_webhook_concorrente_com_mesmo_txid_confirma_uma_unica_vez():
    contexto = criar_pedido_pendente(preco=55.0, quantidade=1)
    pedido = contexto["pedido"]
    assert pedido["pix_txid"]

    payload = {"txid": pedido["pix_txid"], "valor": pedido["total_final"], "status": "Confirmado"}
    barreira = threading.Barrier(2)

    def enviar_webhook():
        with TestClient(main.app) as thread_client:
            barreira.wait(timeout=10)
            return thread_client.post("/api/pagamentos/webhook", json=payload, headers=WEBHOOK_HEADERS)

    with ThreadPoolExecutor(max_workers=2) as executor:
        futuros = [executor.submit(enviar_webhook) for _ in range(2)]
        respostas = [futuro.result(timeout=20) for futuro in futuros]

    for resposta in respostas:
        assert resposta.status_code == 200, resposta.text
        assert resposta.json()["confirmado"] is True

    pagamentos = client.get("/api/pagamentos", params={"venda_id": pedido["id"]}, headers=HEADERS).json()
    assert len(pagamentos) == 1

    pedido_apos = obter_pedido(pedido["id"])
    assert pedido_apos["status"] == "Pagamento confirmado"


# ---------------------------------------------------------------------------
# 10. Mesma chave de idempotência não confirma dois pedidos diferentes
# ---------------------------------------------------------------------------


def test_mesma_idempotency_key_em_pedidos_diferentes_e_rejeitada():
    pedido_a = criar_pedido_pendente(preco=30.0, quantidade=1)["pedido"]
    pedido_b = criar_pedido_pendente(preco=30.0, quantidade=1)["pedido"]
    chave = f"pagamento-{uuid.uuid4().hex}"

    primeira = client.post(
        "/api/pagamentos",
        json={"venda_id": pedido_a["id"], "valor": pedido_a["total_final"], "status": "Confirmado"},
        headers={**HEADERS, "Idempotency-Key": chave},
    )
    assert primeira.status_code == 200
    assert primeira.json()["venda_id"] == pedido_a["id"]

    segunda = client.post(
        "/api/pagamentos",
        json={"venda_id": pedido_b["id"], "valor": pedido_b["total_final"], "status": "Confirmado"},
        headers={**HEADERS, "Idempotency-Key": chave},
    )
    assert segunda.status_code == 409

    # O pedido B nunca deveria ter sido tocado pela chave que pertencia ao pedido A.
    assert obter_pedido(pedido_b["id"])["status"] == "Aguardando pagamento"


# ---------------------------------------------------------------------------
# 15. Auditoria registra divergência sem segredo
# ---------------------------------------------------------------------------


def test_auditoria_de_divergencia_nao_expoe_segredo_de_webhook():
    contexto = criar_pedido_pendente(preco=25.0, quantidade=1)
    pedido = contexto["pedido"]

    resposta = client.post(
        "/api/pagamentos",
        json={"venda_id": pedido["id"], "valor": 1.0, "status": "Confirmado"},
        headers=HEADERS,
    )
    assert resposta.status_code == 200
    corpo = resposta.json()
    assert WEBHOOK_SECRET not in str(corpo)
    assert TEST_API_KEY not in str(corpo)


# ---------------------------------------------------------------------------
# 16. Migração idempotente em banco já existente, preservando dados
# ---------------------------------------------------------------------------


def test_migracao_pagamentos_adiciona_colunas_de_conciliacao_sem_apagar_dados(tmp_path, monkeypatch):
    import backend.database as backend_database
    import config
    import database.connection as connection
    from database.migrations import init_db

    db_path = tmp_path / "legado_pagamentos.db"
    monkeypatch.setattr(config, "DB_PATH", str(db_path))
    monkeypatch.setattr(connection, "DB_PATH", str(db_path))
    monkeypatch.setattr(backend_database, "DB_PATH", str(db_path))

    # Simula um banco de produção criado antes desta migração: tabela
    # `pagamentos` no schema antigo, sem as colunas novas, com um pagamento
    # real já gravado.
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        """
        CREATE TABLE pagamentos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            venda_id INTEGER NOT NULL,
            forma TEXT DEFAULT 'Pix',
            valor REAL DEFAULT 0,
            status TEXT DEFAULT 'Aguardando',
            comprovante TEXT DEFAULT '',
            observacao TEXT DEFAULT '',
            usuario TEXT DEFAULT 'Admin',
            data_hora TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    conn.execute("INSERT INTO pagamentos (venda_id, forma, valor, status) VALUES (1, 'Pix', 42.5, 'Confirmado')")
    conn.commit()
    conn.close()

    init_db()

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    linha = conn.execute("SELECT * FROM pagamentos WHERE venda_id=1").fetchone()
    colunas = {info[1] for info in conn.execute("PRAGMA table_info(pagamentos)").fetchall()}
    conn.close()

    assert {"valor_esperado", "status_conciliacao", "motivo_divergencia"} <= colunas
    # Dado pré-existente preservado.
    assert linha["valor"] == 42.5
    assert linha["status"] == "Confirmado"
    # Coluna nova aplicada com default seguro, sem exigir reprocessamento manual.
    assert linha["status_conciliacao"] == "nao_avaliado"
    assert linha["valor_esperado"] is None
    assert linha["motivo_divergencia"] is None

    # Rodar a migração de novo (idempotente) não falha nem duplica colunas.
    init_db()
