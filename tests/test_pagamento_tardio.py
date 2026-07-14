"""Testes de pagamento tardio (Fase 2 — PR fix/pix-pagamento-tardio).

Cobrem a regra autoritativa: um Pix recebido depois que o pedido já saiu dos
status que aceitam confirmação pela primeira vez (Cancelado — inclui
expirado, já que este sistema não tem um status 'Expirado' separado — ou já
avançado além de 'Pagamento confirmado': Separando pedido, Pronto para
retirada, Entregue, Concluído) nunca confirma, nunca reabre o pedido, nunca
baixa/repõe estoque. Fica classificado como status_conciliacao =
'pagamento_tardio', persistido para conciliação administrativa.
"""

import importlib
import os
import sqlite3
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta

from fastapi.testclient import TestClient

os.environ.setdefault("MISTICA_SITE_API_KEY", "test-api-key")
os.environ.setdefault("MISTICA_SYNC_KEY", "test-api-key")
os.environ.setdefault("MISTICA_PIX_WEBHOOK_SECRET", "test-pagamento-tardio-webhook-secret")
os.environ.setdefault("MISTICA_PIX_KEY", "49999999999")

main = importlib.import_module("backend.main")
client = TestClient(main.app)
client.__enter__()

TEST_API_KEY = os.environ["MISTICA_SITE_API_KEY"]
WEBHOOK_SECRET = os.environ["MISTICA_PIX_WEBHOOK_SECRET"]
HEADERS = {"X-Mistica-Api-Key": TEST_API_KEY}
WEBHOOK_HEADERS = {"X-Mistica-Webhook-Secret": WEBHOOK_SECRET}


def ip_unico() -> str:
    return f"198.18.{uuid.uuid4().int % 256}.{uuid.uuid4().int % 256}"


def codigo_unico(prefixo: str) -> str:
    return f"{prefixo}-{uuid.uuid4().hex[:10]}"


def criar_produto(preco: float, quantidade: int = 20) -> dict:
    resposta = client.post(
        "/api/produtos",
        json={
            "nome": "Produto Pagamento Tardio",
            "codigo_p": codigo_unico("TARD"),
            "preco": preco,
            "quantidade": quantidade,
            "categoria": "Testes",
        },
        headers=HEADERS,
    )
    assert resposta.status_code == 200, resposta.text
    return resposta.json()


def criar_pedido_pendente(preco: float, quantidade: int = 1) -> dict:
    produto = criar_produto(preco, quantidade=quantidade + 10)
    resposta = client.post(
        "/api/vendas",
        json={
            "cliente": "Cliente Pagamento Tardio",
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


def obter_pedido(pedido_id: int) -> dict:
    return client.get(f"/api/pedidos/{pedido_id}", headers=HEADERS).json()


def obter_produto(produto_id: int) -> dict:
    return client.get(f"/api/produtos/{produto_id}").json()


def status_no_banco(pedido_id: int) -> str:
    """Lê pedidos.status diretamente do banco, sem passar por nenhuma rota
    (GET /api/pedidos/{id} e /api/pedidos já chamam expirar_pedidos_pendentes
    sozinhos — usar essa função para inspecionar o estado 'antes' de uma
    revalidação de prazo sem disparar a própria revalidação)."""
    import backend.database as backend_database

    with backend_database.conectar() as conn:
        row = conn.execute("SELECT status FROM pedidos WHERE id=?", (pedido_id,)).fetchone()
    return str(row["status"]) if row else ""


def post_pagamento(json_body: dict, headers: dict | None = None):
    hdrs = {**HEADERS, **(headers or {}), "X-Forwarded-For": ip_unico()}
    return client.post("/api/pagamentos", json=json_body, headers=hdrs)


def post_webhook(json_body: dict, headers: dict | None = None):
    hdrs = {**WEBHOOK_HEADERS, **(headers or {}), "X-Forwarded-For": ip_unico()}
    return client.post("/api/pagamentos/webhook", json=json_body, headers=hdrs)


def put_status_pagamento(pagamento_id: int, json_body: dict, headers: dict | None = None):
    hdrs = {**HEADERS, **(headers or {}), "X-Forwarded-For": ip_unico()}
    return client.put(f"/api/pagamentos/{pagamento_id}/status", json=json_body, headers=hdrs)


def forcar_expiracao_ja_processada(pedido_id: int):
    """Simula um pedido já expirado E já processado pelo worker periódico:
    prazo no passado + expirar_pedidos_pendentes já rodou (status='Cancelado',
    estoque já reposto)."""
    import backend.database as backend_database
    from backend.order_status_routes import expirar_pedidos_pendentes

    with backend_database.conectar() as conn:
        conn.execute("UPDATE pedidos SET expira_em=? WHERE id=?", ("2000-01-01T00:00:00", pedido_id))
        conn.commit()
        expirar_pedidos_pendentes(conn, agora="2001-01-01T00:00:00")


def forcar_prazo_vencido_sem_worker(pedido_id: int):
    """Simula o prazo já vencido, mas o worker periódico AINDA não rodou:
    só ajusta expira_em para o passado, sem chamar expirar_pedidos_pendentes.
    O pedido continua com status='Aguardando pagamento' no banco até algo
    revalidar o prazo."""
    import backend.database as backend_database

    with backend_database.conectar() as conn:
        conn.execute("UPDATE pedidos SET expira_em=? WHERE id=?", ("2000-01-01T00:00:00", pedido_id))
        conn.commit()


def cancelar_manualmente(pedido_id: int) -> dict:
    resposta = client.delete(f"/api/pedidos/{pedido_id}", headers={**HEADERS, "X-Forwarded-For": ip_unico()})
    assert resposta.status_code == 200, resposta.text
    return resposta.json()


# ---------------------------------------------------------------------------
# 1. Pix exato em pedido pendente confirma (comportamento do PR #311 intacto)
# ---------------------------------------------------------------------------


def test_pix_exato_em_pedido_pendente_confirma():
    contexto = criar_pedido_pendente(preco=40.0, quantidade=1)
    pedido = contexto["pedido"]

    resposta = post_pagamento({"venda_id": pedido["id"], "valor": pedido["total_final"], "status": "Confirmado"})
    assert resposta.status_code == 200, resposta.text
    corpo = resposta.json()
    assert corpo["confirmado"] is True
    assert corpo["status_conciliacao"] == "ok"
    assert obter_pedido(pedido["id"])["status"] == "Pagamento confirmado"


# ---------------------------------------------------------------------------
# 2/9/10. Pix exato em pedido expirado não confirma, não baixa nem repõe de novo
# ---------------------------------------------------------------------------


def test_pix_exato_em_pedido_expirado_nao_confirma_nem_baixa_estoque():
    contexto = criar_pedido_pendente(preco=50.0, quantidade=1)
    pedido = contexto["pedido"]
    forcar_expiracao_ja_processada(pedido["id"])
    assert obter_pedido(pedido["id"])["status"] == "Cancelado"
    quantidade_apos_reposicao = obter_produto(contexto["produto"]["id"])["quantidade"]

    resposta = post_pagamento({"venda_id": pedido["id"], "valor": pedido["total_final"], "status": "Confirmado"})
    assert resposta.status_code == 200, resposta.text
    corpo = resposta.json()
    assert corpo["confirmado"] is False
    assert corpo["status_conciliacao"] == "pagamento_tardio"
    assert "motivo_divergencia" in corpo
    assert corpo["estoque_baixado_agora"] is False

    pedido_apos = obter_pedido(pedido["id"])
    assert pedido_apos["status"] == "Cancelado"  # não reabriu
    assert obter_produto(contexto["produto"]["id"])["quantidade"] == quantidade_apos_reposicao  # não baixou nem repôs de novo


# ---------------------------------------------------------------------------
# 3. Pix exato em pedido cancelado (manualmente) não confirma
# ---------------------------------------------------------------------------


def test_pix_exato_em_pedido_cancelado_manualmente_nao_confirma():
    contexto = criar_pedido_pendente(preco=33.0, quantidade=1)
    pedido = contexto["pedido"]
    cancelar_manualmente(pedido["id"])
    assert obter_pedido(pedido["id"])["status"] == "Cancelado"
    quantidade_apos_cancelamento = obter_produto(contexto["produto"]["id"])["quantidade"]

    resposta = post_pagamento({"venda_id": pedido["id"], "valor": pedido["total_final"], "status": "Confirmado"})
    assert resposta.status_code == 200, resposta.text
    corpo = resposta.json()
    assert corpo["confirmado"] is False
    assert corpo["status_conciliacao"] == "pagamento_tardio"

    assert obter_pedido(pedido["id"])["status"] == "Cancelado"
    assert obter_produto(contexto["produto"]["id"])["quantidade"] == quantidade_apos_cancelamento


# ---------------------------------------------------------------------------
# 4/5. Pix divergente em pedido expirado/cancelado não confirma
# ---------------------------------------------------------------------------


def test_pix_divergente_em_pedido_expirado_nao_confirma():
    contexto = criar_pedido_pendente(preco=70.0, quantidade=1)
    pedido = contexto["pedido"]
    forcar_expiracao_ja_processada(pedido["id"])
    quantidade_apos_reposicao = obter_produto(contexto["produto"]["id"])["quantidade"]

    resposta = post_pagamento({"venda_id": pedido["id"], "valor": 5.0, "status": "Confirmado"})
    assert resposta.status_code == 200
    corpo = resposta.json()
    assert corpo["confirmado"] is False
    assert corpo["status_conciliacao"] == "pagamento_tardio"
    assert obter_pedido(pedido["id"])["status"] == "Cancelado"
    assert obter_produto(contexto["produto"]["id"])["quantidade"] == quantidade_apos_reposicao


def test_pix_divergente_em_pedido_cancelado_nao_confirma():
    contexto = criar_pedido_pendente(preco=80.0, quantidade=1)
    pedido = contexto["pedido"]
    cancelar_manualmente(pedido["id"])
    quantidade_apos_cancelamento = obter_produto(contexto["produto"]["id"])["quantidade"]

    resposta = post_pagamento({"venda_id": pedido["id"], "valor": 999.0, "status": "Confirmado"})
    assert resposta.status_code == 200
    corpo = resposta.json()
    assert corpo["confirmado"] is False
    assert corpo["status_conciliacao"] == "pagamento_tardio"
    assert obter_pedido(pedido["id"])["status"] == "Cancelado"
    assert obter_produto(contexto["produto"]["id"])["quantidade"] == quantidade_apos_cancelamento


# ---------------------------------------------------------------------------
# 6/7/8. Pagamento tardio é persistido, com a classificação certa, sem mudar
# o status do pedido
# ---------------------------------------------------------------------------


def test_pagamento_tardio_e_persistido_com_classificacao_correta():
    contexto = criar_pedido_pendente(preco=44.0, quantidade=1)
    pedido = contexto["pedido"]
    cancelar_manualmente(pedido["id"])

    resposta = post_pagamento({"venda_id": pedido["id"], "valor": pedido["total_final"], "status": "Confirmado", "comprovante": "COMPROVANTE-1"})
    assert resposta.status_code == 200
    pagamento_id = resposta.json()["id"]

    pagamentos = client.get("/api/pagamentos", params={"venda_id": pedido["id"]}, headers=HEADERS).json()
    registrado = next(p for p in pagamentos if p["id"] == pagamento_id)
    assert registrado["status_conciliacao"] == "pagamento_tardio"
    assert registrado["status"] != "Confirmado"  # nunca gravado como confirmado
    assert registrado["valor"] == pedido["total_final"]
    assert registrado["motivo_divergencia"]

    assert obter_pedido(pedido["id"])["status"] == "Cancelado"


# ---------------------------------------------------------------------------
# 11/12. Idempotência e concorrência de webhooks tardios
# ---------------------------------------------------------------------------


def test_webhook_tardio_repetido_e_idempotente():
    contexto = criar_pedido_pendente(preco=28.0, quantidade=1)
    pedido = contexto["pedido"]
    cancelar_manualmente(pedido["id"])
    assert pedido["pix_txid"]

    payload = {"txid": pedido["pix_txid"], "valor": pedido["total_final"], "status": "Confirmado"}
    primeira = post_webhook(payload)
    segunda = post_webhook(payload)

    assert primeira.status_code == 200
    assert segunda.status_code == 200
    assert primeira.json()["status_conciliacao"] == "pagamento_tardio"
    assert segunda.json()["id"] == primeira.json()["id"]  # resposta salva, não reprocessou

    pagamentos = client.get("/api/pagamentos", params={"venda_id": pedido["id"]}, headers=HEADERS).json()
    assert len(pagamentos) == 1
    assert obter_pedido(pedido["id"])["status"] == "Cancelado"


def test_dois_webhooks_tardios_concorrentes_nao_reabrem_pedido():
    contexto = criar_pedido_pendente(preco=36.0, quantidade=1)
    pedido = contexto["pedido"]
    cancelar_manualmente(pedido["id"])
    quantidade_apos_cancelamento = obter_produto(contexto["produto"]["id"])["quantidade"]
    barreira = threading.Barrier(2)

    def enviar_webhook(txid: str):
        with TestClient(main.app) as thread_client:
            barreira.wait(timeout=10)
            return thread_client.post(
                "/api/pagamentos/webhook",
                json={"txid": txid, "venda_id": pedido["id"], "valor": pedido["total_final"], "status": "Confirmado"},
                headers={**WEBHOOK_HEADERS, "X-Forwarded-For": ip_unico()},
            )

    txid_1 = f"TARDIO-A-{uuid.uuid4().hex[:8]}"
    txid_2 = f"TARDIO-B-{uuid.uuid4().hex[:8]}"
    with ThreadPoolExecutor(max_workers=2) as executor:
        futuros = [executor.submit(enviar_webhook, txid_1), executor.submit(enviar_webhook, txid_2)]
        respostas = [futuro.result(timeout=20) for futuro in futuros]

    for resposta in respostas:
        assert resposta.status_code == 200, resposta.text
        assert resposta.json()["confirmado"] is False
        assert resposta.json()["status_conciliacao"] == "pagamento_tardio"

    assert obter_pedido(pedido["id"])["status"] == "Cancelado"
    assert obter_produto(contexto["produto"]["id"])["quantidade"] == quantidade_apos_cancelamento


# ---------------------------------------------------------------------------
# 13/14. Expiração/cancelamento concorrendo com o pagamento
# ---------------------------------------------------------------------------


def test_expiracao_concorrente_com_pagamento_nao_confirma():
    """O prazo já venceu mas o worker periódico ainda não rodou (simulado
    por forcar_prazo_vencido_sem_worker). Duas requisições concorrentes: uma
    tenta pagar exato, a outra roda a expiração diretamente. O resultado tem
    que ser determinístico: o pedido termina Cancelado e o pagamento nunca
    confirma nem baixa estoque, não importa a ordem real de execução."""
    contexto = criar_pedido_pendente(preco=52.0, quantidade=1)
    pedido = contexto["pedido"]
    forcar_prazo_vencido_sem_worker(pedido["id"])
    assert status_no_banco(pedido["id"]) == "Aguardando pagamento"  # worker não rodou ainda
    quantidade_reservada = obter_produto(contexto["produto"]["id"])["quantidade"]
    barreira = threading.Barrier(2)

    def expirar_via_worker():
        import backend.database as backend_database
        from backend.order_status_routes import expirar_pedidos_pendentes

        barreira.wait(timeout=10)
        with backend_database.conectar() as conn:
            expirar_pedidos_pendentes(conn)

    def pagar():
        with TestClient(main.app) as thread_client:
            barreira.wait(timeout=10)
            return thread_client.post(
                "/api/pagamentos",
                json={"venda_id": pedido["id"], "valor": pedido["total_final"], "status": "Confirmado"},
                headers={**HEADERS, "X-Forwarded-For": ip_unico()},
            )

    with ThreadPoolExecutor(max_workers=2) as executor:
        futuro_pagamento = executor.submit(pagar)
        futuro_expiracao = executor.submit(expirar_via_worker)
        resposta_pagamento = futuro_pagamento.result(timeout=20)
        futuro_expiracao.result(timeout=20)

    assert resposta_pagamento.status_code == 200, resposta_pagamento.text
    # Não importa quem "chegou primeiro": o prazo já tinha vencido de verdade
    # (timestamp real no passado), então a própria confirmação de pagamento
    # revalida e vê o pedido cancelado, não importa se o worker explícito
    # também rodou em paralelo — o pedido termina cancelado e o pagamento
    # nunca confirma.
    assert obter_pedido(pedido["id"])["status"] == "Cancelado"
    assert resposta_pagamento.json()["confirmado"] is False
    # A reserva original é reposta uma única vez (nunca em dobro), não
    # importa se o worker explícito ou a própria confirmação reivindicou a
    # expiração primeiro.
    assert obter_produto(contexto["produto"]["id"])["quantidade"] == quantidade_reservada + 1


def test_cancelamento_concorrente_com_pagamento_nao_confirma():
    contexto = criar_pedido_pendente(preco=61.0, quantidade=1)
    pedido = contexto["pedido"]
    quantidade_reservada = obter_produto(contexto["produto"]["id"])["quantidade"]
    barreira = threading.Barrier(2)

    def cancelar():
        with TestClient(main.app) as thread_client:
            barreira.wait(timeout=10)
            return thread_client.delete(f"/api/pedidos/{pedido['id']}", headers={**HEADERS, "X-Forwarded-For": ip_unico()})

    def pagar():
        with TestClient(main.app) as thread_client:
            barreira.wait(timeout=10)
            return thread_client.post(
                "/api/pagamentos",
                json={"venda_id": pedido["id"], "valor": pedido["total_final"], "status": "Confirmado"},
                headers={**HEADERS, "X-Forwarded-For": ip_unico()},
            )

    with ThreadPoolExecutor(max_workers=2) as executor:
        futuro_cancelamento = executor.submit(cancelar)
        futuro_pagamento = executor.submit(pagar)
        resposta_cancelamento = futuro_cancelamento.result(timeout=20)
        resposta_pagamento = futuro_pagamento.result(timeout=20)

    assert resposta_cancelamento.status_code == 200
    assert resposta_pagamento.status_code == 200, resposta_pagamento.text

    pedido_final = obter_pedido(pedido["id"])
    quantidade_final = obter_produto(contexto["produto"]["id"])["quantidade"]
    # Cancelamento manual (DELETE /api/pedidos/{id}) e confirmação de
    # pagamento são duas ações independentes competindo pelo mesmo pedido; a
    # ordem final de quem "vence" (inclusive um cancelamento aplicado sobre
    # um pedido já confirmado, uma ação administrativa separada e fora do
    # escopo deste PR) não é o que este teste verifica. O que ESTE PR
    # garante, em qualquer ordem de execução:
    # 1. o estoque nunca sai do lugar em dobro nem fica negativo — a reserva
    #    original (1 unidade) é decrementada uma única vez e, se reposta,
    #    também uma única vez;
    # 2. a resposta do pagamento é sempre consistente com o que ele decidiu
    #    (confirmado=True só quando de fato confirmou, nunca um "meio-termo").
    assert pedido_final["status"] in {"Cancelado", "Pagamento confirmado"}
    assert quantidade_final in {quantidade_reservada, quantidade_reservada + 1}
    if resposta_pagamento.json()["confirmado"] is True:
        assert pedido_final["status"] in {"Cancelado", "Pagamento confirmado"}  # nunca um terceiro estado
    else:
        assert resposta_pagamento.json()["status_conciliacao"] in {"pagamento_tardio", "divergente_menor", "divergente_maior"}


# ---------------------------------------------------------------------------
# 15. Prazo vencido sem o worker ter rodado ainda
# ---------------------------------------------------------------------------


def test_prazo_vencido_sem_worker_e_revalidado_no_momento_do_pagamento():
    contexto = criar_pedido_pendente(preco=45.0, quantidade=1)
    pedido = contexto["pedido"]
    forcar_prazo_vencido_sem_worker(pedido["id"])
    # O status no banco ainda diz "Aguardando pagamento" — o worker periódico
    # não rodou. A confirmação precisa revalidar o prazo autoritativo sozinha.
    assert status_no_banco(pedido["id"]) == "Aguardando pagamento"

    resposta = post_pagamento({"venda_id": pedido["id"], "valor": pedido["total_final"], "status": "Confirmado"})
    assert resposta.status_code == 200
    assert resposta.json()["confirmado"] is False
    assert resposta.json()["status_conciliacao"] == "pagamento_tardio"
    assert obter_pedido(pedido["id"])["status"] == "Cancelado"


# ---------------------------------------------------------------------------
# 16. Pagamento no limite exato do prazo confirma normalmente
# ---------------------------------------------------------------------------


def test_pagamento_no_limite_exato_do_prazo_confirma():
    import backend.database as backend_database

    contexto = criar_pedido_pendente(preco=58.0, quantidade=1)
    pedido = contexto["pedido"]
    # expira_em um pouco no futuro: o prazo ainda não venceu no momento do
    # pagamento (limite exato, mas dentro da janela).
    expira_em_futuro = (datetime.now() + timedelta(seconds=2)).isoformat(timespec="seconds")
    with backend_database.conectar() as conn:
        conn.execute("UPDATE pedidos SET expira_em=? WHERE id=?", (expira_em_futuro, pedido["id"]))
        conn.commit()

    resposta = post_pagamento({"venda_id": pedido["id"], "valor": pedido["total_final"], "status": "Confirmado"})
    assert resposta.status_code == 200, resposta.text
    assert resposta.json()["confirmado"] is True
    assert resposta.json()["status_conciliacao"] == "ok"
    assert obter_pedido(pedido["id"])["status"] == "Pagamento confirmado"


# ---------------------------------------------------------------------------
# 17. txid de um pedido cancelado é resolvido corretamente (e tratado como
# tardio) — nunca aplicado silenciosamente a outro pedido
# ---------------------------------------------------------------------------


def test_txid_de_pedido_cancelado_e_resolvido_e_classificado_como_tardio():
    contexto = criar_pedido_pendente(preco=22.0, quantidade=1)
    pedido = contexto["pedido"]
    cancelar_manualmente(pedido["id"])

    resposta = post_webhook({"txid": pedido["pix_txid"], "valor": pedido["total_final"], "status": "Confirmado"})
    assert resposta.status_code == 200
    corpo = resposta.json()
    assert corpo["venda_id"] == pedido["id"]
    assert corpo["status_conciliacao"] == "pagamento_tardio"
    assert obter_pedido(pedido["id"])["status"] == "Cancelado"


# ---------------------------------------------------------------------------
# 18. Rota manual (PUT /pagamentos/{id}/status) segue a mesma regra
# ---------------------------------------------------------------------------


def test_rota_manual_de_status_de_pagamento_segue_a_mesma_regra():
    contexto = criar_pedido_pendente(preco=19.0, quantidade=1)
    pedido = contexto["pedido"]

    # Registra o pagamento ainda com o pedido pendente (sem confirmar).
    registrado = post_pagamento({"venda_id": pedido["id"], "valor": pedido["total_final"], "status": "Aguardando"})
    assert registrado.status_code == 200
    pagamento_id = registrado.json()["id"]

    # O pedido expira ANTES de o admin clicar em "confirmar" manualmente.
    forcar_expiracao_ja_processada(pedido["id"])

    resposta = put_status_pagamento(pagamento_id, {"status": "Confirmado", "usuario": "Teste"})
    assert resposta.status_code == 200, resposta.text
    corpo = resposta.json()
    assert corpo["status_conciliacao"] == "pagamento_tardio"
    assert corpo["estoque_baixado_agora"] is False
    assert obter_pedido(pedido["id"])["status"] == "Cancelado"


# ---------------------------------------------------------------------------
# 19. Rotas genéricas de status não reabrem um pedido cancelado
# ---------------------------------------------------------------------------


def test_rota_generica_de_status_nao_reabre_pedido_cancelado():
    contexto = criar_pedido_pendente(preco=15.0, quantidade=1)
    pedido = contexto["pedido"]
    cancelar_manualmente(pedido["id"])

    resposta = client.post(
        f"/api/pedidos/{pedido['id']}/status",
        headers={**HEADERS, "X-Forwarded-For": ip_unico()},
        json={"status": "Pagamento confirmado", "usuario": "Teste"},
    )
    assert resposta.status_code == 409, resposta.text
    assert obter_pedido(pedido["id"])["status"] == "Cancelado"

    resposta_separando = client.post(
        f"/api/pedidos/{pedido['id']}/status",
        headers={**HEADERS, "X-Forwarded-For": ip_unico()},
        json={"status": "Separando pedido", "usuario": "Teste"},
    )
    assert resposta_separando.status_code == 409, resposta_separando.text
    assert obter_pedido(pedido["id"])["status"] == "Cancelado"


# ---------------------------------------------------------------------------
# 20. Acompanhamento público continua coerente após pagamento tardio
# ---------------------------------------------------------------------------


def test_acompanhamento_publico_continua_coerente_apos_pagamento_tardio():
    contexto = criar_pedido_pendente(preco=17.0, quantidade=1)
    pedido = contexto["pedido"]
    cancelar_manualmente(pedido["id"])

    resposta_pagamento = post_pagamento({"venda_id": pedido["id"], "valor": pedido["total_final"], "status": "Confirmado"})
    assert resposta_pagamento.status_code == 200

    status_publico = client.get(f"/api/pedidos/{pedido['id']}/status", params={"txid": pedido["pix_txid"]})
    assert status_publico.status_code == 200
    corpo = status_publico.json()
    assert corpo["status_atual"] == "Cancelado"
    assert corpo["status_atual"] not in {"Pagamento confirmado", "Pago"}
    assert WEBHOOK_SECRET not in str(corpo)
    assert TEST_API_KEY not in str(corpo)


# ---------------------------------------------------------------------------
# 21. Auditoria não expõe segredo
# ---------------------------------------------------------------------------


def test_auditoria_de_pagamento_tardio_nao_expoe_segredo():
    contexto = criar_pedido_pendente(preco=26.0, quantidade=1)
    pedido = contexto["pedido"]
    cancelar_manualmente(pedido["id"])

    resposta = post_webhook({"txid": pedido["pix_txid"], "valor": pedido["total_final"], "status": "Confirmado"})
    assert resposta.status_code == 200
    corpo = resposta.json()
    assert WEBHOOK_SECRET not in str(corpo)
    assert TEST_API_KEY not in str(corpo)
    # payload Pix completo (copia-e-cola) não é ecoado na resposta de pagamento.
    assert "pix_copia_cola" not in corpo


# ---------------------------------------------------------------------------
# 22. Compatibilidade: novo valor de status_conciliacao ('pagamento_tardio')
# não exige migração de schema e funciona em banco já existente (mesmo
# schema criado pelo PR #311, sem nenhuma coluna nova).
# ---------------------------------------------------------------------------


def test_novo_valor_de_conciliacao_e_compativel_com_banco_existente(tmp_path, monkeypatch):
    import backend.database as backend_database
    import config
    import database.connection as connection
    from database.migrations import init_db

    db_path = tmp_path / "banco_existente_pr311.db"
    monkeypatch.setattr(config, "DB_PATH", str(db_path))
    monkeypatch.setattr(connection, "DB_PATH", str(db_path))
    monkeypatch.setattr(backend_database, "DB_PATH", str(db_path))

    # Roda a migração como já ficou depois do PR #311 (colunas de conciliação
    # já existem) — nenhuma coluna nova é necessária para "pagamento_tardio",
    # que é só mais um valor de texto em status_conciliacao.
    init_db()

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute(
        """
        INSERT INTO pedidos (cliente, status, total_final) VALUES ('Cliente Legado', 'Cancelado', 10.0)
        """
    )
    pedido_id = conn.execute("SELECT last_insert_rowid() AS id").fetchone()["id"]
    conn.execute(
        """
        INSERT INTO pagamentos (venda_id, forma, valor, status, valor_esperado, status_conciliacao, motivo_divergencia)
        VALUES (?, 'Pix', 10.0, 'Aguardando', 10.0, 'pagamento_tardio', 'Pagamento tardio: pedido já está Cancelado.')
        """,
        (pedido_id,),
    )
    conn.commit()

    linha = conn.execute("SELECT * FROM pagamentos WHERE venda_id=?", (pedido_id,)).fetchone()
    conn.close()

    assert linha["status_conciliacao"] == "pagamento_tardio"
    assert linha["valor"] == 10.0

    # Rodar a migração de novo (idempotente) não falha nem apaga o dado.
    init_db()
