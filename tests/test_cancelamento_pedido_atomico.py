"""Testes do cancelamento atômico de pedidos (Fase 2 — PR
fix/cancelamento-pedido-atomico).

Antes desta correção, backend/order_status_routes.py::cancelar_com_reposicao
e repor_estoque_cancelamento liam o estado do pedido (status,
estoque_baixado, estoque_reposto_cancelamento) num SELECT separado e só
depois decidiam e escreviam — sem nenhuma garantia de que o estado lido
ainda era o mesmo no momento da escrita. Duas requisições concorrentes (dois
cancelamentos, cancelamento x confirmação de pagamento, cancelamento x
expiração) podiam observar o mesmo estado "antigo" e executar ações
incompatíveis (reposição em dobro, pedido pago reaberto por cancelamento
tardio, etc.).

A correção substitui cada leitura-decisão-escrita por um único UPDATE com
guarda no próprio WHERE (compare-and-swap): a checagem do estado atual e a
escrita da transição acontecem atomicamente. Só uma reivindica (rowcount>0);
a(s) outra(s) reagem ao estado JÁ ATUAL, nunca ao que leram antes.
"""

import importlib
import os
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta

from fastapi.testclient import TestClient

os.environ.setdefault("MISTICA_SITE_API_KEY", "test-api-key")
os.environ.setdefault("MISTICA_SYNC_KEY", "test-api-key")
os.environ.setdefault("MISTICA_PIX_WEBHOOK_SECRET", "test-cancelamento-atomico-webhook-secret")
os.environ.setdefault("MISTICA_PIX_KEY", "49999999999")

from backend.database import conectar  # noqa: E402
from backend.order_status_routes import TIPO_ITEM_FISICO, TIPO_ITEM_SOB_ENCOMENDA  # noqa: E402

main = importlib.import_module("backend.main")
client = TestClient(main.app)
client.__enter__()

TEST_API_KEY = os.environ["MISTICA_SITE_API_KEY"]
WEBHOOK_SECRET = os.environ["MISTICA_PIX_WEBHOOK_SECRET"]
HEADERS = {"X-Mistica-Api-Key": TEST_API_KEY}
WEBHOOK_HEADERS = {"X-Mistica-Webhook-Secret": WEBHOOK_SECRET}


def ip_unico() -> str:
    return f"203.0.113.{uuid.uuid4().int % 256}"


def codigo_unico(prefixo: str) -> str:
    return f"{prefixo}-{uuid.uuid4().hex[:10]}"


def criar_produto(*, sob_encomenda: bool = False, quantidade: int = 10, limite: int = 10, preco: float = 45.0) -> dict:
    payload = {
        "codigo_p": codigo_unico("CANCATOM"),
        "nome": f"Produto cancelamento atomico {uuid.uuid4().hex[:8]}",
        "preco": preco,
        "custo": 15.0,
        "quantidade": quantidade,
        "categoria": "Testes",
        "sob_encomenda": sob_encomenda,
        "limite_encomenda": limite,
    }
    resposta = client.post("/api/produtos", json=payload, headers=HEADERS)
    assert resposta.status_code == 200, resposta.text
    return {**payload, "id": resposta.json()["id"], "codigo_p": payload["codigo_p"].upper()}


def criar_pedido_pendente(produto: dict, *, quantidade: int = 1) -> dict:
    resposta = client.post(
        "/api/vendas",
        headers={**HEADERS, "X-Forwarded-For": ip_unico()},
        json={"cliente": "Cliente cancelamento", "status": "Aguardando pagamento", "baixa_estoque": True, "itens": [{"produto_id": produto["id"], "quantidade": quantidade}]},
    )
    assert resposta.status_code == 200, resposta.text
    criado = resposta.json()
    return client.get(f"/api/pedidos/{criado['id']}", headers=HEADERS).json()


def criar_pedido_encomenda(produto: dict, *, quantidade: int = 1) -> dict:
    resposta = client.post(
        "/api/checkout/pedidos",
        headers={"X-Forwarded-For": ip_unico()},
        json={"cliente": "Cliente cancelamento encomenda", "ciente_sob_encomenda": True, "itens": [{"produto_id": produto["id"], "codigo_p": produto["codigo_p"], "quantidade": quantidade}]},
    )
    assert resposta.status_code == 200, resposta.text
    return resposta.json()


def _inserir_pedido_itens_direto(itens: list[tuple], *, status: str = "Aguardando pagamento", estoque_baixado: int = 0) -> dict:
    agora = datetime.now().isoformat(timespec="seconds")
    total = round(sum(item[5] for item in itens), 2)
    with conectar() as conn:
        cur = conn.execute(
            """
            INSERT INTO pedidos (
                cliente, telefone, data_venda, subtotal, desconto, taxa, total_final,
                forma_pagamento, vendedor, status, data_iso, dia_operacional,
                origem, expira_em, estoque_baixado, estoque_reservado
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                "Cliente misto cancelamento", None, agora, total, 0.0, 0.0, total,
                "Pix site/celular", "Site/Celular", status, agora, agora[:10],
                "site", None, estoque_baixado, 0,
            ),
        )
        pedido_id = int(cur.lastrowid)
        for codigo_p, nome_p, quantidade, custo_unitario, valor_unitario, valor_total, tipo_item in itens:
            conn.execute(
                """
                INSERT INTO pedidos_itens
                (pedido_id, codigo_p, nome_p, quantidade, custo_unitario, valor_unitario, valor_total, tipo_item)
                VALUES (?,?,?,?,?,?,?,?)
                """,
                (pedido_id, codigo_p, nome_p, quantidade, custo_unitario, valor_unitario, valor_total, tipo_item),
            )
        conn.commit()
    return client.get(f"/api/pedidos/{pedido_id}", headers=HEADERS).json()


def montar_pedido_misto(produto_fisico: dict, produto_encomenda: dict, *, qtd_fisico: int = 1, qtd_encomenda: int = 1, estoque_baixado: int = 0) -> dict:
    total_fisico = round(produto_fisico["preco"] * qtd_fisico, 2)
    total_encomenda = round(produto_encomenda["preco"] * qtd_encomenda, 2)
    return _inserir_pedido_itens_direto(
        [
            (produto_fisico["codigo_p"], produto_fisico["nome"], qtd_fisico, produto_fisico["custo"], produto_fisico["preco"], total_fisico, TIPO_ITEM_FISICO),
            (produto_encomenda["codigo_p"], produto_encomenda["nome"], qtd_encomenda, produto_encomenda["custo"], produto_encomenda["preco"], total_encomenda, TIPO_ITEM_SOB_ENCOMENDA),
        ],
        estoque_baixado=estoque_baixado,
    )


def estoque(produto_id: int) -> int:
    with conectar() as conn:
        row = conn.execute("SELECT quantidade FROM produtos WHERE id=?", (produto_id,)).fetchone()
    return int(row["quantidade"])


def cancelar(pedido_id: int):
    return client.delete(f"/api/pedidos/{pedido_id}", headers={**HEADERS, "X-Forwarded-For": ip_unico()})


def confirmar(pedido_id: int, valor: float):
    return client.post(
        "/api/pagamentos",
        headers={**HEADERS, "X-Forwarded-For": ip_unico()},
        json={"venda_id": pedido_id, "valor": valor, "status": "Confirmado", "usuario": "Teste"},
    )


def confirmar_webhook(txid: str, valor: float):
    return client.post(
        "/api/pagamentos/webhook",
        headers={**WEBHOOK_HEADERS, "X-Forwarded-For": ip_unico()},
        json={"txid": txid, "valor": valor, "status": "Confirmado"},
    )


def obter_pedido(pedido_id: int) -> dict:
    return client.get(f"/api/pedidos/{pedido_id}", headers=HEADERS).json()


def historico(pedido_id: int) -> list[dict]:
    return obter_pedido(pedido_id)["historico_status"]


# 1/2 — cancelamento simples e repetição idempotente


def test_cancelamento_simples_de_pedido_pendente():
    produto = criar_produto(quantidade=5)
    pedido = criar_pedido_pendente(produto)
    assert estoque(produto["id"]) == 4

    resposta = cancelar(pedido["id"])
    assert resposta.status_code == 200, resposta.text
    corpo = resposta.json()
    assert corpo["status"] == "Cancelado"
    assert corpo["estoque_reposto_agora"] is True
    assert corpo["ja_cancelado"] is False
    assert estoque(produto["id"]) == 5
    assert obter_pedido(pedido["id"])["status"] == "Cancelado"


def test_cancelamento_repetido_e_idempotente():
    produto = criar_produto(quantidade=5)
    pedido = criar_pedido_pendente(produto)

    primeira = cancelar(pedido["id"])
    segunda = cancelar(pedido["id"])
    terceira = cancelar(pedido["id"])

    assert primeira.status_code == 200
    assert primeira.json()["estoque_reposto_agora"] is True
    for resposta in (segunda, terceira):
        assert resposta.status_code == 200, resposta.text
        assert resposta.json()["ja_cancelado"] is True
        assert resposta.json()["estoque_reposto_agora"] is False

    assert estoque(produto["id"]) == 5  # nunca duplica a reposição


# 3 — dois cancelamentos simultâneos


def test_dois_cancelamentos_simultaneos_nao_duplicam_reposicao():
    produto = criar_produto(quantidade=5)
    pedido = criar_pedido_pendente(produto)
    barreira = threading.Barrier(2)

    def enviar():
        with TestClient(main.app) as thread_client:
            barreira.wait(timeout=10)
            return thread_client.delete(f"/api/pedidos/{pedido['id']}", headers={**HEADERS, "X-Forwarded-For": ip_unico()})

    with ThreadPoolExecutor(max_workers=2) as executor:
        futuros = [executor.submit(enviar) for _ in range(2)]
        respostas = [f.result(timeout=20) for f in futuros]

    for resposta in respostas:
        assert resposta.status_code == 200, resposta.text
    assert sum(1 for r in respostas if r.json()["estoque_reposto_agora"] is True) == 1
    assert sum(1 for r in respostas if r.json()["ja_cancelado"] is True) == 1
    assert estoque(produto["id"]) == 5


# 4 — cancelamento concorrente com webhook exato


def test_cancelamento_concorrente_com_webhook_exato_resultado_deterministico():
    produto = criar_produto(quantidade=5)
    pedido = criar_pedido_pendente(produto)
    txid = pedido["pix_txid"]
    assert txid
    barreira = threading.Barrier(2)

    def enviar_cancelamento():
        with TestClient(main.app) as thread_client:
            barreira.wait(timeout=10)
            return thread_client.delete(f"/api/pedidos/{pedido['id']}", headers={**HEADERS, "X-Forwarded-For": ip_unico()})

    def enviar_webhook():
        with TestClient(main.app) as thread_client:
            barreira.wait(timeout=10)
            return thread_client.post(
                "/api/pagamentos/webhook",
                json={"txid": txid, "valor": pedido["total_final"], "status": "Confirmado"},
                headers={**WEBHOOK_HEADERS, "X-Forwarded-For": ip_unico()},
            )

    with ThreadPoolExecutor(max_workers=2) as executor:
        futuro_cancel = executor.submit(enviar_cancelamento)
        futuro_pag = executor.submit(enviar_webhook)
        resposta_cancel = futuro_cancel.result(timeout=20)
        resposta_pag = futuro_pag.result(timeout=20)

    assert resposta_cancel.status_code == 200, resposta_cancel.text
    assert resposta_pag.status_code == 200, resposta_pag.text

    pedido_final = obter_pedido(pedido["id"])
    # Determinístico e nunca "meio-termo": o cancelamento explícito sempre
    # vence uma corrida contra um pagamento simultâneo por design (ver
    # docstring de cancelar_com_reposicao) — mas o que este teste garante
    # de fato é a ausência de estados inconsistentes/duplicados.
    assert pedido_final["status"] == "Cancelado"
    assert estoque(produto["id"]) == 5  # nunca duplicado, nunca negativo
    # Nenhuma movimentação duplicada: só uma entrada "Cancelado" no histórico.
    assert sum(1 for h in pedido_final["historico_status"] if h["status"] == "Cancelado") == 1


# 5 — cancelamento concorrente com confirmação manual


def test_cancelamento_concorrente_com_confirmacao_manual_resultado_deterministico():
    produto = criar_produto(quantidade=5)
    pedido = criar_pedido_pendente(produto)
    barreira = threading.Barrier(2)

    def enviar_cancelamento():
        with TestClient(main.app) as thread_client:
            barreira.wait(timeout=10)
            return thread_client.delete(f"/api/pedidos/{pedido['id']}", headers={**HEADERS, "X-Forwarded-For": ip_unico()})

    def enviar_confirmacao():
        with TestClient(main.app) as thread_client:
            barreira.wait(timeout=10)
            return thread_client.post(
                "/api/pagamentos",
                json={"venda_id": pedido["id"], "valor": pedido["total_final"], "status": "Confirmado", "usuario": "Teste"},
                headers={**HEADERS, "X-Forwarded-For": ip_unico()},
            )

    with ThreadPoolExecutor(max_workers=2) as executor:
        futuro_cancel = executor.submit(enviar_cancelamento)
        futuro_pag = executor.submit(enviar_confirmacao)
        resposta_cancel = futuro_cancel.result(timeout=20)
        resposta_pag = futuro_pag.result(timeout=20)

    assert resposta_cancel.status_code == 200, resposta_cancel.text
    assert resposta_pag.status_code == 200, resposta_pag.text
    assert obter_pedido(pedido["id"])["status"] == "Cancelado"
    assert estoque(produto["id"]) == 5


# 6 — cancelamento concorrente com expiração


def test_cancelamento_concorrente_com_expiracao_nao_duplica_reposicao():
    produto = criar_produto(quantidade=5)
    pedido = criar_pedido_pendente(produto)
    with conectar() as conn:
        conn.execute("UPDATE pedidos SET expira_em='2000-01-01T00:00:00' WHERE id=?", (pedido["id"],))
        conn.commit()
    barreira = threading.Barrier(2)

    def enviar_cancelamento():
        with TestClient(main.app) as thread_client:
            barreira.wait(timeout=10)
            return thread_client.delete(f"/api/pedidos/{pedido['id']}", headers={**HEADERS, "X-Forwarded-For": ip_unico()})

    def rodar_expiracao():
        from backend.order_status_routes import expirar_pedidos_pendentes

        barreira.wait(timeout=10)
        with conectar() as conn:
            expirar_pedidos_pendentes(conn, agora="2099-01-01T00:00:00")

    with ThreadPoolExecutor(max_workers=2) as executor:
        futuro_cancel = executor.submit(enviar_cancelamento)
        futuro_exp = executor.submit(rodar_expiracao)
        resposta_cancel = futuro_cancel.result(timeout=20)
        futuro_exp.result(timeout=20)

    assert resposta_cancel.status_code == 200, resposta_cancel.text
    assert obter_pedido(pedido["id"])["status"] == "Cancelado"
    assert estoque(produto["id"]) == 5  # reposto uma única vez, não importa quem venceu


# 7/8/9 — reposição por tipo de item


def test_pedido_fisico_repoe_uma_vez():
    produto = criar_produto(quantidade=5)
    pedido = criar_pedido_pendente(produto, quantidade=2)
    assert estoque(produto["id"]) == 3

    resposta = cancelar(pedido["id"])
    assert resposta.status_code == 200
    assert resposta.json()["estoque_reposto_agora"] is True
    assert estoque(produto["id"]) == 5

    assert cancelar(pedido["id"]).json()["estoque_reposto_agora"] is False
    assert estoque(produto["id"]) == 5


def test_pedido_sob_encomenda_nao_repoe():
    produto = criar_produto(sob_encomenda=True, quantidade=0, limite=5)
    pedido = criar_pedido_encomenda(produto, quantidade=2)
    assert estoque(produto["id"]) == 0

    resposta = cancelar(pedido["id"])
    assert resposta.status_code == 200, resposta.text
    assert resposta.json()["estoque_reposto_agora"] is False
    assert estoque(produto["id"]) == 0


def test_carrinho_misto_repoe_so_a_parte_fisica():
    fisico = criar_produto(quantidade=5)
    encomenda = criar_produto(sob_encomenda=True, quantidade=0, limite=5)
    pedido = montar_pedido_misto(fisico, encomenda, qtd_fisico=2, qtd_encomenda=1)
    confirmacao = confirmar(pedido["id"], pedido["total_final"])
    assert confirmacao.status_code == 200, confirmacao.text
    assert estoque(fisico["id"]) == 3
    assert estoque(encomenda["id"]) == 0

    resposta = cancelar(pedido["id"])
    assert resposta.status_code == 200, resposta.text
    assert resposta.json()["estoque_reposto_agora"] is True
    assert estoque(fisico["id"]) == 5
    assert estoque(encomenda["id"]) == 0  # nunca ganha saldo fictício


# 10 — legado_ambiguo não é reposto incorretamente (não deveria coexistir com
# estoque_baixado=1 no fluxo normal pós-#313; simulado defensivamente).


def test_legado_ambiguo_nao_e_reposto_mas_cancelamento_nao_quebra():
    fisico = criar_produto(quantidade=5)
    ambiguo = criar_produto(quantidade=0)
    pedido = montar_pedido_misto(fisico, ambiguo, qtd_fisico=2, qtd_encomenda=1, estoque_baixado=1)
    with conectar() as conn:
        conn.execute(
            "UPDATE pedidos_itens SET tipo_item='legado_ambiguo' WHERE pedido_id=? AND codigo_p=?",
            (pedido["id"], ambiguo["codigo_p"]),
        )
        # Simula que a baixa física do item 'fisico' já havia ocorrido (é
        # isso que estoque_baixado=1 significa) antes deste cancelamento.
        conn.execute("UPDATE produtos SET quantidade = quantidade - 2 WHERE id=?", (fisico["id"],))
        conn.commit()
    assert estoque(fisico["id"]) == 3

    resposta = cancelar(pedido["id"])
    assert resposta.status_code == 200, resposta.text
    assert resposta.json()["estoque_reposto_agora"] is True  # o item físico foi reposto
    assert estoque(fisico["id"]) == 5
    assert estoque(ambiguo["id"]) == 0  # item ambíguo nunca ganha estoque fictício


# 11/12 — estados bloqueados


def test_pedido_concluido_nao_cancela_silenciosamente():
    produto = criar_produto(quantidade=5)
    pedido = criar_pedido_pendente(produto)
    with conectar() as conn:
        conn.execute("UPDATE pedidos SET status='Concluído' WHERE id=?", (pedido["id"],))
        conn.commit()

    resposta = cancelar(pedido["id"])
    assert resposta.status_code == 409, resposta.text
    assert obter_pedido(pedido["id"])["status"] == "Concluído"
    assert estoque(produto["id"]) == 4  # nada mudou


def test_pedido_entregue_nao_cancela_automaticamente():
    produto = criar_produto(quantidade=5)
    pedido = criar_pedido_pendente(produto)
    with conectar() as conn:
        conn.execute("UPDATE pedidos SET status='Entregue' WHERE id=?", (pedido["id"],))
        conn.commit()

    resposta = cancelar(pedido["id"])
    assert resposta.status_code == 409, resposta.text
    assert obter_pedido(pedido["id"])["status"] == "Entregue"


# 13 — pedido já pago cancela com reposição (rastreabilidade financeira preservada)


def test_pedido_pago_cancela_e_preserva_rastreabilidade_financeira():
    produto = criar_produto(quantidade=5)
    pedido = criar_pedido_pendente(produto)
    confirmacao = confirmar(pedido["id"], pedido["total_final"])
    assert confirmacao.status_code == 200, confirmacao.text
    assert obter_pedido(pedido["id"])["status"] == "Pagamento confirmado"

    resposta = cancelar(pedido["id"])
    assert resposta.status_code == 200, resposta.text
    assert resposta.json()["estoque_reposto_agora"] is True
    assert obter_pedido(pedido["id"])["status"] == "Cancelado"
    assert estoque(produto["id"]) == 5

    # O registro de pagamento continua existindo e correto (não apagado).
    pagamentos = client.get("/api/pagamentos", params={"venda_id": pedido["id"]}, headers=HEADERS).json()
    assert len(pagamentos) == 1
    assert pagamentos[0]["status"] == "Confirmado"


# 14 — pagamento após cancelamento vira tardio


def test_pagamento_apos_cancelamento_vira_tardio():
    produto = criar_produto(quantidade=5)
    pedido = criar_pedido_pendente(produto)
    cancelamento = cancelar(pedido["id"])
    assert cancelamento.status_code == 200

    resposta = confirmar(pedido["id"], pedido["total_final"])
    assert resposta.status_code == 200, resposta.text
    assert resposta.json()["confirmado"] is False
    assert resposta.json()["status_conciliacao"] == "pagamento_tardio"
    assert obter_pedido(pedido["id"])["status"] == "Cancelado"
    assert estoque(produto["id"]) == 5  # não baixa de novo


# 15 — rollback em falha intermediária (produto excluído entre a criação e o cancelamento)


def test_rollback_completo_quando_reposicao_falha_no_meio():
    fisico_ok = criar_produto(quantidade=5)
    fisico_removido = criar_produto(quantidade=5)
    pedido = montar_pedido_misto(fisico_ok, fisico_removido, qtd_fisico=1, qtd_encomenda=1, estoque_baixado=1)
    with conectar() as conn:
        conn.execute("UPDATE pedidos_itens SET tipo_item='fisico' WHERE pedido_id=?", (pedido["id"],))
        conn.commit()
        # Remove o segundo produto do catálogo para forçar a falha de
        # "produto não encontrado" no meio do loop de reposição.
        conn.execute("DELETE FROM produtos WHERE id=?", (fisico_removido["id"],))
        conn.commit()

    resposta = cancelar(pedido["id"])
    assert resposta.status_code == 404, resposta.text

    # Nada foi aplicado: nem a baixa do primeiro item que teria sido
    # reposta com sucesso, nem o status do pedido.
    assert estoque(fisico_ok["id"]) == 5
    pedido_apos = obter_pedido(pedido["id"])
    assert pedido_apos["status"] == "Aguardando pagamento"


# 16 — nenhuma movimentação duplicada (via reconfirmação + cancelamentos concorrentes já cobertos acima)


def test_nenhuma_movimentacao_duplicada_apos_varios_cancelamentos():
    produto = criar_produto(quantidade=5)
    pedido = criar_pedido_pendente(produto)
    for _ in range(5):
        resposta = cancelar(pedido["id"])
        assert resposta.status_code == 200
    assert estoque(produto["id"]) == 5


# 17 — histórico registrado uma única vez


def test_historico_de_cancelamento_registrado_uma_unica_vez():
    produto = criar_produto(quantidade=5)
    pedido = criar_pedido_pendente(produto)
    cancelar(pedido["id"])
    cancelar(pedido["id"])
    cancelar(pedido["id"])

    hist = historico(pedido["id"])
    entradas_cancelado = [h for h in hist if h["status"] == "Cancelado"]
    assert len(entradas_cancelado) == 1


# 18 — auditoria sanitizada


def test_auditoria_de_cancelamento_e_sanitizada():
    produto = criar_produto(quantidade=5)
    pedido = criar_pedido_pendente(produto)
    resposta = client.delete(
        f"/api/pedidos/{pedido['id']}",
        headers={**HEADERS, "X-Forwarded-For": ip_unico()},
    )
    assert resposta.status_code == 200

    with conectar() as conn:
        linhas = conn.execute(
            "SELECT dados_antes, dados_depois FROM audit_log WHERE entidade='pedido' AND entidade_id=? AND acao='cancelar'",
            (str(pedido["id"]),),
        ).fetchall()
    assert linhas
    for linha in linhas:
        texto = f"{linha['dados_antes'] or ''} {linha['dados_depois'] or ''}".lower()
        for termo_proibido in ("fornecedor", "custo", "margem", "http://", "https://"):
            assert termo_proibido not in texto


def test_motivo_de_cancelamento_e_sanitizado_e_truncado():
    from backend.order_status_routes import cancelar_com_reposicao

    produto = criar_produto(quantidade=5)
    pedido = criar_pedido_pendente(produto)
    motivo_bruto = "a" * 5000 + "\x00\x07 controle"

    with conectar() as conn:
        retorno = cancelar_com_reposicao(conn, pedido["id"], "Teste", motivo_bruto, "2026-01-01T00:00:00")
        conn.commit()
    assert retorno["status"] == "Cancelado"

    hist = historico(pedido["id"])
    entrada = next(h for h in hist if h["status"] == "Cancelado")
    assert len(entrada["observacao"]) <= 280
    assert "\x00" not in entrada["observacao"]
    assert "\x07" not in entrada["observacao"]


# 19 — aliases de rota usam a mesma função


def test_aliases_de_rota_usam_a_mesma_funcao_autoritativa():
    produto_a = criar_produto(quantidade=5)
    pedido_a = criar_pedido_pendente(produto_a)
    resposta_a = client.delete(f"/api/pedidos/{pedido_a['id']}", headers={**HEADERS, "X-Forwarded-For": ip_unico()})
    assert resposta_a.status_code == 200
    assert estoque(produto_a["id"]) == 5

    produto_b = criar_produto(quantidade=5)
    pedido_b = criar_pedido_pendente(produto_b)
    resposta_b = client.post(f"/api/pedidos/{pedido_b['id']}/cancelar", headers={**HEADERS, "X-Forwarded-For": ip_unico()})
    assert resposta_b.status_code == 200
    assert estoque(produto_b["id"]) == 5

    produto_c = criar_produto(quantidade=5)
    pedido_c = criar_pedido_pendente(produto_c)
    resposta_c = client.post(f"/api/vendas/{pedido_c['id']}/cancelar", headers={**HEADERS, "X-Forwarded-For": ip_unico()})
    assert resposta_c.status_code == 200
    assert estoque(produto_c["id"]) == 5

    produto_d = criar_produto(quantidade=5)
    pedido_d = criar_pedido_pendente(produto_d)
    resposta_d = client.post(
        f"/api/pedidos/{pedido_d['id']}/status",
        headers={**HEADERS, "X-Forwarded-For": ip_unico()},
        json={"status": "Cancelado", "usuario": "Teste"},
    )
    assert resposta_d.status_code == 200
    assert estoque(produto_d["id"]) == 5

    # Todas as rotas respeitam o mesmo bloqueio de estado: pedido Concluído.
    produto_e = criar_produto(quantidade=5)
    pedido_e = criar_pedido_pendente(produto_e)
    with conectar() as conn:
        conn.execute("UPDATE pedidos SET status='Concluído' WHERE id=?", (pedido_e["id"],))
        conn.commit()
    for rota in (
        lambda: client.delete(f"/api/pedidos/{pedido_e['id']}", headers={**HEADERS, "X-Forwarded-For": ip_unico()}),
        lambda: client.post(f"/api/pedidos/{pedido_e['id']}/cancelar", headers={**HEADERS, "X-Forwarded-For": ip_unico()}),
        lambda: client.post(f"/api/vendas/{pedido_e['id']}/cancelar", headers={**HEADERS, "X-Forwarded-For": ip_unico()}),
    ):
        assert rota().status_code == 409


# 20 — retry da mesma requisição (idempotência natural do DELETE)


def test_retry_da_mesma_requisicao_de_cancelamento_e_seguro():
    produto = criar_produto(quantidade=5)
    pedido = criar_pedido_pendente(produto)

    respostas = [cancelar(pedido["id"]) for _ in range(3)]
    for resposta in respostas:
        assert resposta.status_code == 200
    assert estoque(produto["id"]) == 5


# 21 — banco legado continua funcionando (pedido sem tipo_item explícito, migrado)


def test_banco_legado_continua_cancelando_e_repondo_corretamente():
    produto = criar_produto(quantidade=5)
    pedido = _inserir_pedido_itens_direto(
        [(produto["codigo_p"], produto["nome"], 2, produto["custo"], produto["preco"], produto["preco"] * 2, TIPO_ITEM_FISICO)],
        status="Aguardando pagamento",
        estoque_baixado=1,
    )
    with conectar() as conn:
        conn.execute("UPDATE produtos SET quantidade = quantidade - 2 WHERE id=?", (produto["id"],))
        conn.commit()
    assert estoque(produto["id"]) == 3

    resposta = cancelar(pedido["id"])
    assert resposta.status_code == 200, resposta.text
    assert resposta.json()["estoque_reposto_agora"] is True
    assert estoque(produto["id"]) == 5
