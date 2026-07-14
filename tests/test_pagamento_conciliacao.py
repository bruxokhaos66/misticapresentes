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


def ip_unico() -> str:
    # /api/vendas é limitado por IP (20 req/60s); a suíte cria muitos pedidos,
    # então cada chamada usa um IP forjado diferente (mesmo padrão de
    # tests/test_checkout_concurrency.py) para não esbarrar no rate limit.
    return f"203.0.{uuid.uuid4().int % 256}.{uuid.uuid4().int % 256}"


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
        headers={**HEADERS, "X-Forwarded-For": ip_unico()},
    )
    assert resposta.status_code == 200, resposta.text
    criado = resposta.json()
    pedido = client.get(f"/api/pedidos/{criado['id']}", headers=HEADERS).json()
    return {"pedido": pedido, "produto": produto}


def post_pagamento(json_body: dict, headers: dict | None = None):
    hdrs = {**HEADERS, **(headers or {}), "X-Forwarded-For": ip_unico()}
    return client.post("/api/pagamentos", json=json_body, headers=hdrs)


def post_webhook(json_body: dict, headers: dict | None = None):
    hdrs = {**WEBHOOK_HEADERS, **(headers or {}), "X-Forwarded-For": ip_unico()}
    return client.post("/api/pagamentos/webhook", json=json_body, headers=hdrs)


def put_status_pagamento(pagamento_id: int, json_body: dict, headers: dict | None = None):
    hdrs = {**HEADERS, **(headers or {}), "X-Forwarded-For": ip_unico()}
    return client.put(f"/api/pagamentos/{pagamento_id}/status", json=json_body, headers=hdrs)


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

    resposta = post_pagamento({"venda_id": pedido["id"], "valor": total_final, "status": "Confirmado"})
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

    primeira = post_pagamento({"venda_id": pedido["id"], "valor": pedido["total_final"], "status": "Confirmado"})
    assert primeira.status_code == 200
    # O estoque já foi reservado na criação do pedido pendente (ver
    # criar_pedido_pendente); a confirmação de pagamento não baixa de novo.
    assert primeira.json()["estoque_baixado_agora"] is False
    assert primeira.json()["confirmado"] is True

    quantidade_apos_primeira = obter_produto(contexto["produto"]["id"])["quantidade"]

    segunda = post_pagamento({"venda_id": pedido["id"], "valor": pedido["total_final"], "status": "Confirmado"})
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

    resposta = post_pagamento({"venda_id": pedido["id"], "valor": 50.0, "status": "Confirmado"})
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

    resposta = post_pagamento({"venda_id": pedido["id"], "valor": 999.0, "status": "Confirmado"})
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

    resposta = post_pagamento({"venda_id": pedido["id"], "status": "Confirmado"})
    assert resposta.status_code == 422

    assert obter_pedido(pedido["id"])["status"] == "Aguardando pagamento"


# ---------------------------------------------------------------------------
# 5. Valor inválido é rejeitado
# ---------------------------------------------------------------------------


def test_valor_negativo_e_rejeitado():
    contexto = criar_pedido_pendente(preco=15.0, quantidade=1)
    pedido = contexto["pedido"]

    resposta = post_pagamento({"venda_id": pedido["id"], "valor": -10.0, "status": "Confirmado"})
    assert resposta.status_code == 422
    assert obter_pedido(pedido["id"])["status"] == "Aguardando pagamento"


def test_valor_nao_numerico_e_rejeitado():
    contexto = criar_pedido_pendente(preco=15.0, quantidade=1)
    pedido = contexto["pedido"]

    resposta = post_pagamento({"venda_id": pedido["id"], "valor": "nao-e-numero", "status": "Confirmado"})
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

    resposta = post_pagamento({"venda_id": pedido["id"], "valor": valor_impreciso, "status": "Confirmado"})
    assert resposta.status_code == 200
    corpo = resposta.json()
    assert corpo["confirmado"] is True
    assert corpo["status_conciliacao"] == "ok"


def test_valor_um_centavo_a_menos_e_tratado_como_divergencia_real():
    # Garante que a tolerância de arredondamento não vira uma brecha: um
    # centavo de diferença real ainda deve ser detectado como divergência.
    contexto = criar_pedido_pendente(preco=10.00, quantidade=1)
    pedido = contexto["pedido"]

    resposta = post_pagamento({"venda_id": pedido["id"], "valor": 9.99, "status": "Confirmado"})
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

    primeira = post_pagamento({"venda_id": pedido_a["id"], "valor": pedido_a["total_final"], "status": "Confirmado"}, {**HEADERS, "Idempotency-Key": chave})
    assert primeira.status_code == 200
    assert primeira.json()["venda_id"] == pedido_a["id"]

    segunda = post_pagamento({"venda_id": pedido_b["id"], "valor": pedido_b["total_final"], "status": "Confirmado"}, {**HEADERS, "Idempotency-Key": chave})
    assert segunda.status_code == 409

    # O pedido B nunca deveria ter sido tocado pela chave que pertencia ao pedido A.
    assert obter_pedido(pedido_b["id"])["status"] == "Aguardando pagamento"


# ---------------------------------------------------------------------------
# 15. Auditoria registra divergência sem segredo
# ---------------------------------------------------------------------------


def test_auditoria_de_divergencia_nao_expoe_segredo_de_webhook():
    contexto = criar_pedido_pendente(preco=25.0, quantidade=1)
    pedido = contexto["pedido"]

    resposta = post_pagamento({"venda_id": pedido["id"], "valor": 1.0, "status": "Confirmado"})
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


# ---------------------------------------------------------------------------
# Revisão adicional — item 2: atualizar_status_pagamento (PUT
# /api/pagamentos/{id}/status) usa a MESMA conciliação, nunca aceita valor
# novo do corpo da requisição, e nenhuma rota paralela de status de pedido
# consegue confirmar/baixar estoque sem ela.
# ---------------------------------------------------------------------------


def registrar_pagamento_pendente(pedido_id: int, valor: float) -> dict:
    """Registra um pagamento em status 'Aguardando' (sem tentar confirmar),
    para depois exercitar PUT /api/pagamentos/{id}/status isoladamente."""
    resposta = post_pagamento({"venda_id": pedido_id, "valor": valor, "status": "Aguardando"})
    assert resposta.status_code == 200, resposta.text
    return resposta.json()


def test_atualizacao_manual_sem_valor_registrado_e_rejeitada():
    # Simula um registro legado/corrompido (fora da API, que sempre exige
    # valor) com pagamentos.valor NULL, para provar que a conciliação nunca
    # assume um valor no lugar do ausente.
    import backend.database as backend_database

    contexto = criar_pedido_pendente(preco=18.0, quantidade=1)
    pedido = contexto["pedido"]
    with backend_database.conectar() as conn:
        cur = conn.execute(
            "INSERT INTO pagamentos (venda_id, forma, valor, status) VALUES (?,?,?,?)",
            (pedido["id"], "Pix", None, "Aguardando"),
        )
        pagamento_id = int(cur.lastrowid)
        conn.commit()

    resposta = put_status_pagamento(pagamento_id, {"status": "Confirmado", "usuario": "Teste"})
    assert resposta.status_code == 400, resposta.text
    assert obter_pedido(pedido["id"])["status"] == "Aguardando pagamento"


def test_atualizacao_manual_com_valor_menor_nao_confirma():
    contexto = criar_pedido_pendente(preco=70.0, quantidade=1)
    pedido = contexto["pedido"]
    pagamento = registrar_pagamento_pendente(pedido["id"], valor=50.0)

    resposta = put_status_pagamento(pagamento['id'], {"status": "Confirmado", "usuario": "Teste"})
    assert resposta.status_code == 200, resposta.text
    corpo = resposta.json()
    assert corpo["status_conciliacao"] == "divergente_menor"
    assert corpo["estoque_baixado_agora"] is False
    assert obter_pedido(pedido["id"])["status"] == "Pagamento divergente"


def test_atualizacao_manual_com_valor_maior_nao_confirma():
    contexto = criar_pedido_pendente(preco=30.0, quantidade=1)
    pedido = contexto["pedido"]
    pagamento = registrar_pagamento_pendente(pedido["id"], valor=999.0)

    resposta = put_status_pagamento(pagamento['id'], {"status": "Confirmado", "usuario": "Teste"})
    assert resposta.status_code == 200, resposta.text
    corpo = resposta.json()
    assert corpo["status_conciliacao"] == "divergente_maior"
    assert corpo["estoque_baixado_agora"] is False
    assert obter_pedido(pedido["id"])["status"] == "Pagamento divergente"


def test_atualizacao_manual_com_valor_exato_confirma():
    contexto = criar_pedido_pendente(preco=44.0, quantidade=1)
    pedido = contexto["pedido"]
    pagamento = registrar_pagamento_pendente(pedido["id"], valor=pedido["total_final"])

    resposta = put_status_pagamento(pagamento['id'], {"status": "Confirmado", "usuario": "Teste"})
    assert resposta.status_code == 200, resposta.text
    corpo = resposta.json()
    assert corpo["status_conciliacao"] == "ok"
    assert obter_pedido(pedido["id"])["status"] == "Pagamento confirmado"


def test_atualizacao_manual_repetida_e_idempotente():
    contexto = criar_pedido_pendente(preco=22.0, quantidade=1)
    pedido = contexto["pedido"]
    quantidade_apos_reserva = obter_produto(contexto["produto"]["id"])["quantidade"]
    pagamento = registrar_pagamento_pendente(pedido["id"], valor=pedido["total_final"])

    primeira = put_status_pagamento(pagamento['id'], {"status": "Confirmado", "usuario": "Teste"})
    segunda = put_status_pagamento(pagamento['id'], {"status": "Confirmado", "usuario": "Teste"})
    assert primeira.status_code == 200
    assert segunda.status_code == 200
    assert primeira.json()["estoque_baixado_agora"] is False  # já reservado na criação
    assert segunda.json()["estoque_baixado_agora"] is False
    assert obter_pedido(pedido["id"])["status"] == "Pagamento confirmado"
    assert obter_produto(contexto["produto"]["id"])["quantidade"] == quantidade_apos_reserva


def test_rota_vendas_status_duplicada_tambem_bloqueia_confirmacao_sem_conciliacao():
    """A rota espelhada em order_api_guard_inner_routes.py (/api/vendas/{id}/status)
    precisa da MESMA proteção que /api/pedidos/{id}/status."""
    contexto = criar_pedido_pendente(preco=12.0, quantidade=1)
    pedido = contexto["pedido"]

    resposta = client.post(
        f"/api/vendas/{pedido['id']}/status",
        json={"status": "Pagamento confirmado", "usuario": "Teste"},
        headers=HEADERS,
    )
    assert resposta.status_code == 409, resposta.text
    assert obter_pedido(pedido["id"])["status"] == "Aguardando pagamento"


def test_baixa_manual_de_estoque_nao_confirma_pagamento():
    """POST /api/pedidos/{id}/baixar-estoque é um recurso documentado e
    deliberadamente separado (baixa estoque de um pedido AINDA pendente, sem
    exigir pagamento — ver docs/admin/BAIXA_MANUAL_ESTOQUE.md). Ele nunca
    altera pedidos.status, então não é um caminho para produzir o estado
    'pago/confirmado' — só decrementa estoque, o que já era o comportamento
    documentado antes deste PR e permanece inalterado."""
    contexto = criar_pedido_pendente(preco=15.0, quantidade=1)
    pedido = contexto["pedido"]

    resposta = client.post(f"/api/pedidos/{pedido['id']}/baixar-estoque", headers=HEADERS)
    assert resposta.status_code == 200, resposta.text
    # Estoque já havia sido baixado/reservado na criação; este endpoint não
    # baixa de novo (guard de estoque_baixado) e não mexe no status financeiro.
    assert resposta.json()["estoque_baixado_agora"] is False
    assert obter_pedido(pedido["id"])["status"] == "Aguardando pagamento"


# ---------------------------------------------------------------------------
# Revisão adicional — item 3: múltiplos eventos de pagamento (txids
# diferentes) para o mesmo pedido.
# ---------------------------------------------------------------------------


def test_segundo_pagamento_exato_com_txid_diferente_nao_baixa_estoque_de_novo():
    contexto = criar_pedido_pendente(preco=38.0, quantidade=1)
    pedido = contexto["pedido"]
    quantidade_apos_reserva = obter_produto(contexto["produto"]["id"])["quantidade"]

    primeiro = post_webhook({"txid": pedido["pix_txid"], "valor": pedido["total_final"], "status": "Confirmado"})
    assert primeiro.status_code == 200
    assert primeiro.json()["confirmado"] is True

    # Segundo evento com um identificador de transação diferente (ex.: o PSP
    # reprocessou e gerou um novo ID de notificação para o mesmo pedido).
    # Não corresponde a nenhum pix_txid salvo, então o backend usa o
    # venda_id explícito como fallback (ver confirmar_pagamento_webhook).
    segundo = post_webhook({"txid": f"EVENTO-DIFERENTE-{uuid.uuid4().hex[:8]}", "venda_id": pedido["id"], "valor": pedido["total_final"], "status": "Confirmado"})
    assert segundo.status_code == 200
    assert segundo.json()["confirmado"] is True
    assert segundo.json()["estoque_baixado_agora"] is False

    assert obter_produto(contexto["produto"]["id"])["quantidade"] == quantidade_apos_reserva
    # Dois eventos legítimos e distintos: dois registros de pagamento, sem
    # nenhuma perda de rastreabilidade.
    pagamentos = client.get("/api/pagamentos", params={"venda_id": pedido["id"]}, headers=HEADERS).json()
    assert len(pagamentos) == 2


def test_pagamentos_parciais_nao_sao_somados_silenciosamente():
    """Este PR não implementa conciliação acumulativa: cada pagamento é
    conciliado isoladamente contra o total do pedido. Dois pagamentos
    parciais que juntos fechariam o total NÃO confirmam o pedido — cada um
    fica marcado como divergente_menor, exigindo tratamento administrativo
    explícito (ex.: registrar manualmente um pagamento pelo valor
    remanescente, ou ajustar via painel)."""
    contexto = criar_pedido_pendente(preco=100.0, quantidade=1)
    pedido = contexto["pedido"]

    primeiro = post_pagamento({"venda_id": pedido["id"], "valor": 60.0, "status": "Confirmado"})
    segundo = post_pagamento({"venda_id": pedido["id"], "valor": 40.0, "status": "Confirmado"})
    assert primeiro.status_code == 200
    assert segundo.status_code == 200
    assert primeiro.json()["status_conciliacao"] == "divergente_menor"
    assert segundo.json()["status_conciliacao"] == "divergente_menor"
    assert primeiro.json()["confirmado"] is False
    assert segundo.json()["confirmado"] is False
    # 60 + 40 = 100 (o total), mas isso nunca é somado automaticamente.
    assert obter_pedido(pedido["id"])["status"] == "Pagamento divergente"
    assert bool(obter_pedido(pedido["id"])["estoque_baixado"]) is True  # só a reserva original


def test_pagamento_divergente_seguido_de_pagamento_exato_confirma():
    contexto = criar_pedido_pendente(preco=90.0, quantidade=1)
    pedido = contexto["pedido"]

    divergente = post_pagamento({"venda_id": pedido["id"], "valor": 10.0, "status": "Confirmado"})
    assert divergente.status_code == 200
    assert divergente.json()["status_conciliacao"] == "divergente_menor"
    assert obter_pedido(pedido["id"])["status"] == "Pagamento divergente"

    exato = post_pagamento({"venda_id": pedido["id"], "valor": pedido["total_final"], "status": "Confirmado"})
    assert exato.status_code == 200
    assert exato.json()["status_conciliacao"] == "ok"
    assert exato.json()["confirmado"] is True
    assert obter_pedido(pedido["id"])["status"] == "Pagamento confirmado"


def test_pagamento_exato_seguido_de_pagamento_divergente_nao_regride_pedido():
    contexto = criar_pedido_pendente(preco=65.0, quantidade=1)
    pedido = contexto["pedido"]

    exato = post_pagamento({"venda_id": pedido["id"], "valor": pedido["total_final"], "status": "Confirmado"})
    assert exato.status_code == 200
    assert obter_pedido(pedido["id"])["status"] == "Pagamento confirmado"

    # Um segundo evento divergente (ex.: registro duplicado por engano, ou
    # estorno parcial mal registrado) nunca pode regredir um pedido já pago.
    divergente = post_pagamento({"venda_id": pedido["id"], "valor": 1.0, "status": "Confirmado"})
    assert divergente.status_code == 200
    corpo = divergente.json()
    assert corpo["status_conciliacao"] == "divergente_menor"
    assert corpo["confirmado"] is False
    # O pedido continua confirmado; a divergência fica só no histórico/auditoria.
    assert obter_pedido(pedido["id"])["status"] == "Pagamento confirmado"


def test_txid_ja_vinculado_a_pedido_ignora_venda_id_conflitante():
    """Um txid sempre resolve para o pedido que legitimamente o gerou; um
    venda_id divergente no mesmo payload nunca sequestra o pedido certo."""
    contexto_a = criar_pedido_pendente(preco=20.0, quantidade=1)
    contexto_b = criar_pedido_pendente(preco=20.0, quantidade=1)
    pedido_a = contexto_a["pedido"]
    pedido_b = contexto_b["pedido"]
    assert pedido_a["pix_txid"] != pedido_b["pix_txid"]

    resposta = post_webhook({
            "txid": pedido_a["pix_txid"],  # pertence ao pedido A
            "venda_id": pedido_b["id"],  # tentativa de apontar para B
            "valor": pedido_a["total_final"],
            "status": "Confirmado",
        })
    assert resposta.status_code == 200
    assert resposta.json()["venda_id"] == pedido_a["id"]
    assert obter_pedido(pedido_a["id"])["status"] == "Pagamento confirmado"
    assert obter_pedido(pedido_b["id"])["status"] == "Aguardando pagamento"


def test_dois_eventos_simultaneos_com_txids_diferentes_confirmam_uma_unica_vez():
    contexto = criar_pedido_pendente(preco=48.0, quantidade=1)
    pedido = contexto["pedido"]
    quantidade_apos_reserva = obter_produto(contexto["produto"]["id"])["quantidade"]
    barreira = threading.Barrier(2)

    def enviar_webhook(txid: str):
        with TestClient(main.app) as thread_client:
            barreira.wait(timeout=10)
            return thread_client.post(
                "/api/pagamentos/webhook",
                json={"txid": txid, "venda_id": pedido["id"], "valor": pedido["total_final"], "status": "Confirmado"},
                headers={**WEBHOOK_HEADERS, "X-Forwarded-For": ip_unico()},
            )

    txid_1 = f"EVENTO-A-{uuid.uuid4().hex[:8]}"
    txid_2 = f"EVENTO-B-{uuid.uuid4().hex[:8]}"
    with ThreadPoolExecutor(max_workers=2) as executor:
        futuros = [executor.submit(enviar_webhook, txid_1), executor.submit(enviar_webhook, txid_2)]
        respostas = [futuro.result(timeout=20) for futuro in futuros]

    for resposta in respostas:
        assert resposta.status_code == 200, resposta.text
        assert resposta.json()["confirmado"] is True

    # Chaves de idempotência diferentes (txids diferentes) não impedem as duas
    # requisições de processar — a proteção contra baixa dupla vem do guard de
    # estoque em backend/order_status_routes.py::baixar_estoque_do_pedido.
    assert obter_produto(contexto["produto"]["id"])["quantidade"] == quantidade_apos_reserva
    assert obter_pedido(pedido["id"])["status"] == "Pagamento confirmado"
    pagamentos = client.get("/api/pagamentos", params={"venda_id": pedido["id"]}, headers=HEADERS).json()
    assert len(pagamentos) == 2


# ---------------------------------------------------------------------------
# Revisão adicional — item 4: status "Pagamento divergente" — reserva de
# estoque, expiração e acompanhamento público.
# ---------------------------------------------------------------------------


def test_divergencia_preserva_a_reserva_de_estoque_ate_expirar():
    """Regra atual documentada aqui: um pedido divergente NÃO devolve a
    reserva de estoque automaticamente — ela é preservada (o item continua
    fora do estoque disponível para outros clientes) até o pedido ser
    corrigido com um pagamento exato ou expirar no mesmo prazo de um pedido
    nunca pago. Isso evita vender o item a outra pessoa enquanto a
    divergência ainda pode ser corrigida administrativamente."""
    contexto = criar_pedido_pendente(preco=33.0, quantidade=1)
    pedido = contexto["pedido"]
    quantidade_apos_reserva = obter_produto(contexto["produto"]["id"])["quantidade"]

    resposta = post_pagamento({"venda_id": pedido["id"], "valor": 1.0, "status": "Confirmado"})
    assert resposta.status_code == 200
    assert obter_pedido(pedido["id"])["status"] == "Pagamento divergente"
    assert bool(obter_pedido(pedido["id"])["estoque_baixado"]) is True
    assert obter_produto(contexto["produto"]["id"])["quantidade"] == quantidade_apos_reserva


def test_expiracao_de_pedido_divergente_libera_reserva_uma_unica_vez_e_nao_repete():
    import backend.database as backend_database
    from backend.order_status_routes import expirar_pedidos_pendentes

    contexto = criar_pedido_pendente(preco=27.0, quantidade=1)
    pedido = contexto["pedido"]
    quantidade_apos_reserva = obter_produto(contexto["produto"]["id"])["quantidade"]

    divergente = post_pagamento({"venda_id": pedido["id"], "valor": 1.0, "status": "Confirmado"})
    assert divergente.status_code == 200
    assert obter_pedido(pedido["id"])["status"] == "Pagamento divergente"

    with backend_database.conectar() as conn:
        conn.execute("UPDATE pedidos SET expira_em='2000-01-01T00:00:00' WHERE id=?", (pedido["id"],))
        conn.commit()
        primeira = expirar_pedidos_pendentes(conn, agora="2001-01-01T00:00:00")
        segunda = expirar_pedidos_pendentes(conn, agora="2001-01-01T00:00:01")

    assert primeira == 1
    assert segunda == 0
    assert obter_pedido(pedido["id"])["status"] == "Cancelado"
    # A reserva original (1 unidade) volta ao estoque uma única vez.
    assert obter_produto(contexto["produto"]["id"])["quantidade"] == quantidade_apos_reserva + 1


def test_pagamento_exato_antes_da_expiracao_evita_cancelamento_de_pedido_divergente():
    import backend.database as backend_database
    from backend.order_status_routes import expirar_pedidos_pendentes

    contexto = criar_pedido_pendente(preco=52.0, quantidade=1)
    pedido = contexto["pedido"]

    divergente = post_pagamento({"venda_id": pedido["id"], "valor": 1.0, "status": "Confirmado"})
    assert divergente.status_code == 200
    assert obter_pedido(pedido["id"])["status"] == "Pagamento divergente"

    # O prazo de expiração ainda não passou: um pagamento correto chega a
    # tempo e confirma o pedido normalmente.
    exato = post_pagamento({"venda_id": pedido["id"], "valor": pedido["total_final"], "status": "Confirmado"})
    assert exato.status_code == 200
    assert obter_pedido(pedido["id"])["status"] == "Pagamento confirmado"

    # Mesmo que o prazo original já tivesse passado, o pedido não está mais
    # em nenhum dos dois status expiráveis, então não é cancelado.
    with backend_database.conectar() as conn:
        conn.execute("UPDATE pedidos SET expira_em='2000-01-01T00:00:00' WHERE id=?", (pedido["id"],))
        conn.commit()
        expirados = expirar_pedidos_pendentes(conn, agora="2001-01-01T00:00:00")
    assert expirados == 0
    assert obter_pedido(pedido["id"])["status"] == "Pagamento confirmado"


def test_acompanhamento_publico_reflete_pagamento_divergente_sem_mensagem_enganosa():
    contexto = criar_pedido_pendente(preco=19.0, quantidade=1)
    pedido = contexto["pedido"]

    resposta_pagamento = post_pagamento({"venda_id": pedido["id"], "valor": 5.0, "status": "Confirmado"})
    assert resposta_pagamento.status_code == 200

    status_publico = client.get(
        f"/api/pedidos/{pedido['id']}/status", params={"txid": pedido["pix_txid"]}
    )
    assert status_publico.status_code == 200
    corpo = status_publico.json()
    assert corpo["status_atual"] == "Pagamento divergente"
    # Não pode aparentar cancelado nem pago/confirmado.
    assert corpo["status_atual"] not in {"Cancelado", "Pagamento confirmado"}
    assert bool(corpo["estoque_baixado"]) is True
    # Nenhum dado sensível (chave de API, segredo de webhook, motivo interno
    # bruto de conciliação) vaza no acompanhamento público.
    assert WEBHOOK_SECRET not in str(corpo)
    assert TEST_API_KEY not in str(corpo)
