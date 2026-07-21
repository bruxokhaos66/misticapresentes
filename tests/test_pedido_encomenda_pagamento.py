"""Testes da confirmação de pagamento para pedidos sob encomenda (Fase 2 — PR
fix/encomenda-confirmacao-pagamento).

Antes desta correção, produtos sob encomenda têm estoque físico zero por
definição (ver tests/test_preorder_checkout.py) e, ao confirmar o pagamento,
backend/order_status_routes.py::baixar_estoque_do_pedido tentava aplicar a
mesma baixa de estoque usada para produtos normais — a baixa falhava
(HTTPException 409 "Estoque insuficiente") e o pedido nunca saía de
"Aguardando pagamento", mesmo com o Pix pago corretamente.

Estes testes cobrem: pedido só físico, só sob encomenda, misto (defensivo —
a criação via checkout público bloqueia carrinho misto, mas a baixa de
estoque por item precisa se comportar corretamente se um pedido misto existir
por qualquer outro caminho), reconfirmação/concorrência, cancelamento e
expiração, pedidos legados ambíguos, e que PR #311/#312 permanecem intactos.
"""

import importlib
import os
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

from fastapi.testclient import TestClient

os.environ.setdefault("MISTICA_SITE_API_KEY", "test-api-key")
os.environ.setdefault("MISTICA_SYNC_KEY", "test-api-key")
os.environ.setdefault("MISTICA_PIX_WEBHOOK_SECRET", "test-encomenda-pagamento-webhook-secret")
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


def criar_produto(*, sob_encomenda: bool, quantidade: int, limite: int = 10, preco: float = 39.9) -> dict:
    payload = {
        "codigo_p": codigo_unico("ENCPAG"),
        "nome": f"Produto {'encomenda' if sob_encomenda else 'físico'} pagamento {uuid.uuid4().hex[:8]}",
        "preco": preco,
        "custo": 12.0,
        "quantidade": quantidade,
        "categoria": "Testes",
        "sob_encomenda": sob_encomenda,
        "limite_encomenda": limite,
    }
    resposta = client.post("/api/produtos", json=payload, headers=HEADERS)
    assert resposta.status_code == 200, resposta.text
    # codigo_p é normalizado para maiúsculas pelo servidor (ver
    # backend/product_routes.py); usar sempre o valor devolvido evita que
    # buscar_produto_para_baixa caia no fallback por nome ao montar itens de
    # pedido diretamente no banco (ver _inserir_pedido_itens_direto).
    return {**payload, "id": resposta.json()["id"], "codigo_p": payload["codigo_p"].upper()}


def criar_pedido_encomenda(produto: dict, *, quantidade: int = 1) -> dict:
    resposta = client.post(
        "/api/checkout/pedidos",
        headers={"X-Forwarded-For": ip_unico()},
        json={
            "cliente": "Cliente encomenda pagamento",
            "telefone": "11999999999",
            "ciente_sob_encomenda": True,
            "forma_recebimento": "retirada",
            "itens": [{"produto_id": produto["id"], "codigo_p": produto["codigo_p"], "quantidade": quantidade}],
        },
    )
    assert resposta.status_code == 200, resposta.text
    return resposta.json()


def criar_pedido_fisico(produto: dict, *, quantidade: int = 1) -> dict:
    resposta = client.post(
        "/api/vendas",
        headers={**HEADERS, "X-Forwarded-For": ip_unico()},
        json={
            "cliente": "Cliente físico pagamento",
            "status": "Aguardando pagamento",
            "baixa_estoque": True,
            "itens": [{"produto_id": produto["id"], "quantidade": quantidade}],
        },
    )
    assert resposta.status_code == 200, resposta.text
    criado = resposta.json()
    return client.get(f"/api/pedidos/{criado['id']}", headers=HEADERS).json()


def _inserir_pedido_itens_direto(itens: list[tuple]) -> dict:
    """Monta um pedido diretamente no banco (sem passar por nenhuma rota de
    criação), gravando pedidos_itens.tipo_item exatamente como o resto do
    sistema faria. Usado só para testar o comportamento de
    baixar_estoque_do_pedido/repor_estoque_cancelamento por item — nenhuma
    rota de criação real produz hoje um pedido que combine itens 'fisico' e
    'sob_encomenda' no mesmo pedido (POST /api/checkout/pedidos bloqueia isso
    de propósito, ver tests/test_preorder_checkout.py; POST /api/vendas
    sempre reserva/baixa o físico já na criação). Isso é intencional e
    continua assim — o teste verifica que a *aplicação de estoque por item*,
    usada por qualquer rota futura, nunca mistura as duas regras."""
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
                "Cliente misto pagamento", None, agora, total, 0.0, 0.0, total,
                "Pix site/celular", "Site/Celular", "Aguardando pagamento", agora, agora[:10],
                "site", None, 0, 0,
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


def montar_pedido_misto(produto_fisico: dict, produto_encomenda: dict, *, qtd_fisico: int = 1, qtd_encomenda: int = 1) -> dict:
    total_fisico = round(produto_fisico["preco"] * qtd_fisico, 2)
    total_encomenda = round(produto_encomenda["preco"] * qtd_encomenda, 2)
    return _inserir_pedido_itens_direto([
        (produto_fisico["codigo_p"], produto_fisico["nome"], qtd_fisico, produto_fisico["custo"], produto_fisico["preco"], total_fisico, TIPO_ITEM_FISICO),
        (produto_encomenda["codigo_p"], produto_encomenda["nome"], qtd_encomenda, produto_encomenda["custo"], produto_encomenda["preco"], total_encomenda, TIPO_ITEM_SOB_ENCOMENDA),
    ])


def estoque(produto_id: int) -> int:
    with conectar() as conn:
        row = conn.execute("SELECT quantidade FROM produtos WHERE id=?", (produto_id,)).fetchone()
    return int(row["quantidade"])


def confirmar(pedido_id: int, valor: float, *, headers: dict | None = None):
    return client.post(
        "/api/pagamentos",
        headers={**HEADERS, **(headers or {}), "X-Forwarded-For": ip_unico()},
        json={"venda_id": pedido_id, "valor": valor, "status": "Confirmado", "usuario": "Teste"},
    )


def confirmar_webhook(txid: str, valor: float):
    return client.post(
        "/api/pagamentos/webhook",
        headers={**WEBHOOK_HEADERS, "X-Forwarded-For": ip_unico()},
        json={"txid": txid, "valor": valor, "status": "Confirmado"},
    )


# 1/2/3/4/5/6 — comportamento básico: físico, encomenda, misto.


def test_pedido_so_fisico_confirma_e_baixa_estoque():
    produto = criar_produto(sob_encomenda=False, quantidade=5)
    pedido = criar_pedido_fisico(produto, quantidade=2)
    assert estoque(produto["id"]) == 3  # reservado na criação

    resposta = confirmar(pedido["id"], pedido["total_final"])
    assert resposta.status_code == 200, resposta.text
    assert resposta.json()["estoque_baixado_agora"] is False  # já baixado (reserva) na criação
    assert estoque(produto["id"]) == 3

    pedido_apos = client.get(f"/api/pedidos/{pedido['id']}", headers=HEADERS).json()
    assert pedido_apos["status"] == "Pagamento confirmado"


def test_pedido_so_encomenda_confirma_sem_baixar_estoque():
    produto = criar_produto(sob_encomenda=True, quantidade=0, limite=5)
    pedido = criar_pedido_encomenda(produto, quantidade=2)
    assert pedido["estoque_baixado"] is False
    assert estoque(produto["id"]) == 0

    resposta = confirmar(pedido["id"], pedido["total_final"])
    assert resposta.status_code == 200, resposta.text
    corpo = resposta.json()
    assert corpo["confirmado"] is True
    assert corpo["estoque_baixado_agora"] is False  # nenhum item físico foi decrementado

    assert estoque(produto["id"]) == 0  # nunca sai de zero: nenhum saldo negativo, nenhuma baixa

    pedido_apos = client.get(f"/api/pedidos/{pedido['id']}", headers=HEADERS).json()
    assert pedido_apos["status"] == "Aguardando encomenda"

    with conectar() as conn:
        mov = conn.execute(
            "SELECT COUNT(*) AS total FROM movimentacao_estoque WHERE codigo_p=?",
            (produto["codigo_p"],),
        ).fetchone()
    assert mov["total"] == 0  # nenhuma movimentação fictícia de saída


def test_carrinho_misto_confirma_e_baixa_so_a_parte_fisica():
    fisico = criar_produto(sob_encomenda=False, quantidade=5)
    encomenda = criar_produto(sob_encomenda=True, quantidade=0, limite=5)
    pedido = montar_pedido_misto(fisico, encomenda, qtd_fisico=2, qtd_encomenda=3)
    assert estoque(fisico["id"]) == 5  # baixa_estoque=False na criação: nada reservado ainda
    assert estoque(encomenda["id"]) == 0

    resposta = confirmar(pedido["id"], pedido["total_final"])
    assert resposta.status_code == 200, resposta.text
    assert resposta.json()["estoque_baixado_agora"] is True  # a parte física baixou

    assert estoque(fisico["id"]) == 3  # 5 - 2
    assert estoque(encomenda["id"]) == 0  # inalterado

    pedido_apos = client.get(f"/api/pedidos/{pedido['id']}", headers=HEADERS).json()
    assert pedido_apos["status"] == "Aguardando encomenda"  # tem item sob encomenda: não vira "Pagamento confirmado" puro


def test_estoque_zero_da_encomenda_nao_bloqueia_confirmacao():
    produto = criar_produto(sob_encomenda=True, quantidade=0, limite=5)
    pedido = criar_pedido_encomenda(produto, quantidade=1)
    resposta = confirmar(pedido["id"], pedido["total_final"])
    assert resposta.status_code == 200, resposta.text  # nunca 409 "Estoque insuficiente"


def test_estoque_zero_do_item_fisico_bloqueia_confirmacao():
    produto = criar_produto(sob_encomenda=False, quantidade=1)
    pedido = criar_pedido_fisico(produto, quantidade=1)
    assert estoque(produto["id"]) == 0  # reservado na criação

    # Um segundo pedido para o mesmo produto (sem reserva bem-sucedida) não é
    # possível criar aqui porque a criação já exige estoque; simula-se a
    # corrida "produto ficou sem estoque entre criação e confirmação"
    # zerando manualmente o estoque físico do produto antes da confirmação,
    # depois de desfazer a reserva já feita na criação (para isolar o
    # comportamento da baixa na *confirmação*, não da reserva).
    with conectar() as conn:
        conn.execute("UPDATE pedidos SET estoque_baixado=0 WHERE id=?", (pedido["id"],))
        conn.commit()

    resposta = confirmar(pedido["id"], pedido["total_final"])
    assert resposta.status_code == 409, resposta.text
    assert "estoque insuficiente" in resposta.json()["detail"].lower()

    pedido_apos = client.get(f"/api/pedidos/{pedido['id']}", headers=HEADERS).json()
    assert pedido_apos["status"] == "Aguardando pagamento"  # não confirma parcialmente


# 7/8 — reconfirmação e concorrência


def test_reconfirmacao_de_encomenda_nao_duplica():
    produto = criar_produto(sob_encomenda=True, quantidade=0, limite=5)
    pedido = criar_pedido_encomenda(produto, quantidade=2)

    primeira = confirmar(pedido["id"], pedido["total_final"])
    segunda = confirmar(pedido["id"], pedido["total_final"])
    assert primeira.status_code == 200, primeira.text
    assert segunda.status_code == 200, segunda.text
    assert primeira.json()["estoque_baixado_agora"] is False
    assert segunda.json()["estoque_baixado_agora"] is False
    assert estoque(produto["id"]) == 0

    with conectar() as conn:
        total_logs = conn.execute(
            "SELECT COUNT(*) AS total FROM pedido_status_log WHERE venda_id=? AND status='Pedido aguarda encomenda'",
            (pedido["id"],),
        ).fetchone()["total"]
    assert total_logs == 1  # não duplica o registro de "processado" nas reconfirmações


def test_dois_webhooks_concorrentes_para_pedido_so_encomenda_nao_duplicam():
    produto = criar_produto(sob_encomenda=True, quantidade=0, limite=5)
    pedido = criar_pedido_encomenda(produto, quantidade=1)
    txid = pedido["pix_txid"]
    assert txid

    with ThreadPoolExecutor(max_workers=2) as executor:
        futuros = [executor.submit(confirmar_webhook, txid, pedido["total_final"]) for _ in range(2)]
        respostas = [f.result() for f in futuros]

    for resposta in respostas:
        assert resposta.status_code == 200, resposta.text
    assert estoque(produto["id"]) == 0

    pedido_apos = client.get(f"/api/pedidos/{pedido['id']}", headers=HEADERS).json()
    assert pedido_apos["status"] == "Aguardando encomenda"


def test_dois_webhooks_concorrentes_para_carrinho_misto_nao_duplicam():
    fisico = criar_produto(sob_encomenda=False, quantidade=5)
    encomenda = criar_produto(sob_encomenda=True, quantidade=0, limite=5)
    pedido = montar_pedido_misto(fisico, encomenda, qtd_fisico=2, qtd_encomenda=1)
    with conectar() as conn:
        conn.execute("UPDATE pedidos SET pix_txid=? WHERE id=?", (f"txid-{uuid.uuid4().hex}", pedido["id"]))
        conn.commit()
        txid = conn.execute("SELECT pix_txid FROM pedidos WHERE id=?", (pedido["id"],)).fetchone()["pix_txid"]

    with ThreadPoolExecutor(max_workers=2) as executor:
        futuros = [executor.submit(confirmar_webhook, txid, pedido["total_final"]) for _ in range(2)]
        respostas = [f.result() for f in futuros]

    for resposta in respostas:
        assert resposta.status_code == 200, resposta.text
    assert estoque(fisico["id"]) == 3  # baixou uma única vez (5 - 2), nunca 1 (5 - 2 - 2)
    assert estoque(encomenda["id"]) == 0


# 9/11 — cancelamento e expiração de encomenda pura


def test_cancelamento_de_encomenda_nao_repoe_estoque():
    produto = criar_produto(sob_encomenda=True, quantidade=0, limite=5)
    pedido = criar_pedido_encomenda(produto, quantidade=2)
    confirmar(pedido["id"], pedido["total_final"])
    assert estoque(produto["id"]) == 0

    cancelamento = client.delete(f"/api/pedidos/{pedido['id']}", headers=HEADERS)
    assert cancelamento.status_code == 200, cancelamento.text
    assert cancelamento.json()["estoque_reposto_agora"] is False
    assert estoque(produto["id"]) == 0  # nunca cria saldo positivo fictício


def test_expiracao_de_encomenda_nao_repoe_estoque():
    produto = criar_produto(sob_encomenda=True, quantidade=0, limite=5)
    pedido = criar_pedido_encomenda(produto, quantidade=2)

    with conectar() as conn:
        conn.execute("UPDATE pedidos SET expira_em='2000-01-01T00:00:00' WHERE id=?", (pedido["id"],))
        conn.commit()
        from backend.order_status_routes import expirar_pedidos_pendentes

        expirados = expirar_pedidos_pendentes(conn, agora="2001-01-01T00:00:00")
    assert expirados == 1
    assert estoque(produto["id"]) == 0


# 10/12 — cancelamento e expiração de carrinho misto


def test_cancelamento_misto_repoe_so_o_item_fisico():
    fisico = criar_produto(sob_encomenda=False, quantidade=5)
    encomenda = criar_produto(sob_encomenda=True, quantidade=0, limite=5)
    pedido = montar_pedido_misto(fisico, encomenda, qtd_fisico=2, qtd_encomenda=1)
    confirmar(pedido["id"], pedido["total_final"])
    assert estoque(fisico["id"]) == 3
    assert estoque(encomenda["id"]) == 0

    cancelamento = client.delete(f"/api/pedidos/{pedido['id']}", headers=HEADERS)
    assert cancelamento.status_code == 200, cancelamento.text
    assert cancelamento.json()["estoque_reposto_agora"] is True
    assert estoque(fisico["id"]) == 5  # reposto
    assert estoque(encomenda["id"]) == 0  # nunca ganha saldo fictício


def test_expiracao_mista_repoe_so_o_item_fisico():
    fisico = criar_produto(sob_encomenda=False, quantidade=5)
    encomenda = criar_produto(sob_encomenda=True, quantidade=0, limite=5)
    pedido = montar_pedido_misto(fisico, encomenda, qtd_fisico=2, qtd_encomenda=1)

    # Confirma o pagamento primeiro (baixa a parte física de fato), depois
    # simula o pedido expirando (ex.: cancelado por outro motivo depois de já
    # confirmado, ou o worker de expiração rodando sobre um estado
    # inconsistente) — expirar_pedidos_pendentes só repõe pedidos que ainda
    # estão pendentes, então força o status de volta para testar a reposição.
    confirmacao = confirmar(pedido["id"], pedido["total_final"])
    assert confirmacao.status_code == 200, confirmacao.text
    assert estoque(fisico["id"]) == 3

    with conectar() as conn:
        conn.execute(
            "UPDATE pedidos SET status='Aguardando pagamento', expira_em='2000-01-01T00:00:00' WHERE id=?",
            (pedido["id"],),
        )
        conn.commit()
        from backend.order_status_routes import expirar_pedidos_pendentes

        expirados = expirar_pedidos_pendentes(conn, agora="2001-01-01T00:00:00")
    assert expirados == 1
    assert estoque(fisico["id"]) == 5
    assert estoque(encomenda["id"]) == 0


# 13 — produto alterado depois da criação não muda a classificação do item


def test_produto_alterado_apos_criacao_nao_muda_classificacao_do_item():
    produto = criar_produto(sob_encomenda=True, quantidade=0, limite=5)
    pedido = criar_pedido_encomenda(produto, quantidade=1)

    # Catálogo muda depois da criação do pedido: produto deixa de ser sob
    # encomenda e ganha estoque físico.
    atualizacao = client.put(
        f"/api/produtos/{produto['id']}",
        headers=HEADERS,
        json={
            "codigo_p": produto["codigo_p"],
            "nome": produto["nome"],
            "preco": produto["preco"],
            "custo": produto["custo"],
            "quantidade": 10,
            "categoria": "Testes",
            "sob_encomenda": False,
            "limite_encomenda": produto["limite_encomenda"],
        },
    )
    assert atualizacao.status_code == 200, atualizacao.text

    resposta = confirmar(pedido["id"], pedido["total_final"])
    assert resposta.status_code == 200, resposta.text
    assert resposta.json()["estoque_baixado_agora"] is False  # continua sendo tratado como sob encomenda

    # O item persistido continua sob encomenda; o estoque físico (agora
    # existente no catálogo) não é tocado por este pedido.
    assert estoque(produto["id"]) == 10
    with conectar() as conn:
        tipo = conn.execute("SELECT tipo_item FROM pedidos_itens WHERE pedido_id=?", (pedido["id"],)).fetchone()["tipo_item"]
    assert tipo == TIPO_ITEM_SOB_ENCOMENDA


# 14 — pedido legado ambíguo não confirma silenciosamente


def test_pedido_legado_ambiguo_nao_confirma_silenciosamente():
    """Monta o pedido diretamente no banco (não via /api/vendas), para que
    não exista audit_log('pedido','criar') associado — do contrário,
    init_db() (que roda a cada conectar()) reclassificaria o item de volta
    para 'fisico' a partir dessa evidência antes mesmo da confirmação
    (comportamento correto do backfill, coberto em
    tests/test_tipo_item_classificacao_legado.py). Aqui o objetivo é o caso
    sem nenhuma evidência: o valor 'legado_ambiguo' gravado pelo próprio
    ALTER TABLE (ver database/migrations.py) para um item legado real."""
    produto = criar_produto(sob_encomenda=False, quantidade=5)
    with conectar() as conn:
        cur = conn.execute(
            "INSERT INTO pedidos (cliente, status, total_final, estoque_baixado) VALUES (?,?,?,0)",
            ("Cliente legado ambíguo", "Aguardando pagamento", produto["preco"]),
        )
        pedido_id = int(cur.lastrowid)
        conn.execute(
            "INSERT INTO pedidos_itens (pedido_id, codigo_p, nome_p, quantidade, valor_unitario, valor_total) VALUES (?,?,?,?,?,?)",
            (pedido_id, produto["codigo_p"], produto["nome"], 1, produto["preco"], produto["preco"]),
        )
        conn.commit()

    pedido = client.get(f"/api/pedidos/{pedido_id}", headers=HEADERS).json()
    with conectar() as conn:
        tipo = conn.execute("SELECT tipo_item FROM pedidos_itens WHERE pedido_id=?", (pedido_id,)).fetchone()["tipo_item"]
    assert tipo == "legado_ambiguo"  # o DEFAULT do ALTER TABLE, sem nenhuma evidência para resolver

    resposta = confirmar(pedido_id, pedido["total_final"])
    assert resposta.status_code == 409, resposta.text
    assert "conciliação administrativa" in resposta.json()["detail"].lower()

    pedido_apos = client.get(f"/api/pedidos/{pedido_id}", headers=HEADERS).json()
    assert pedido_apos["status"] == "Aguardando pagamento"  # não confirma silenciosamente
    assert estoque(produto["id"]) == 5  # nem baixa nem repõe: nunca foi tocado


# 15 — rollback em falha intermediária (carrinho misto: item físico sem estoque no meio do loop)


def test_rollback_completo_quando_baixa_fisica_falha_no_meio_do_carrinho_misto():
    fisico_ok = criar_produto(sob_encomenda=False, quantidade=5)
    fisico_sem_estoque = criar_produto(sob_encomenda=False, quantidade=1)
    encomenda = criar_produto(sob_encomenda=True, quantidade=0, limite=5)

    pedido = _inserir_pedido_itens_direto([
        (fisico_ok["codigo_p"], fisico_ok["nome"], 1, fisico_ok["custo"], fisico_ok["preco"], fisico_ok["preco"] * 1, TIPO_ITEM_FISICO),
        (fisico_sem_estoque["codigo_p"], fisico_sem_estoque["nome"], 5, fisico_sem_estoque["custo"], fisico_sem_estoque["preco"], fisico_sem_estoque["preco"] * 5, TIPO_ITEM_FISICO),
        (encomenda["codigo_p"], encomenda["nome"], 1, encomenda["custo"], encomenda["preco"], encomenda["preco"] * 1, TIPO_ITEM_SOB_ENCOMENDA),
    ])

    resposta_pagamento = confirmar(pedido["id"], pedido["total_final"])
    assert resposta_pagamento.status_code == 409, resposta_pagamento.text

    # Nada foi aplicado: nem o item que teria baixado com sucesso, nem o
    # status do pedido, nem o pagamento em si.
    assert estoque(fisico_ok["id"]) == 5
    assert estoque(fisico_sem_estoque["id"]) == 1
    assert estoque(encomenda["id"]) == 0
    pedido_apos = client.get(f"/api/pedidos/{pedido['id']}", headers=HEADERS).json()
    assert pedido_apos["status"] == "Aguardando pagamento"
    with conectar() as conn:
        total_pagamentos = conn.execute("SELECT COUNT(*) AS total FROM pagamentos WHERE venda_id=?", (pedido["id"],)).fetchone()["total"]
    assert total_pagamentos == 0


# 16/17 — PR #311/#312 continuam intactos para pedidos de encomenda


def test_valor_divergente_de_encomenda_nao_confirma():
    produto = criar_produto(sob_encomenda=True, quantidade=0, limite=5)
    pedido = criar_pedido_encomenda(produto, quantidade=2)

    resposta = confirmar(pedido["id"], pedido["total_final"] - 1)
    assert resposta.status_code == 200, resposta.text
    assert resposta.json()["confirmado"] is False
    assert resposta.json()["status_conciliacao"] == "divergente_menor"

    pedido_apos = client.get(f"/api/pedidos/{pedido['id']}", headers=HEADERS).json()
    assert pedido_apos["status"] == "Pagamento divergente"
    assert estoque(produto["id"]) == 0


def test_pagamento_tardio_de_encomenda_cancelada_nao_confirma():
    produto = criar_produto(sob_encomenda=True, quantidade=0, limite=5)
    pedido = criar_pedido_encomenda(produto, quantidade=1)

    cancelamento = client.delete(f"/api/pedidos/{pedido['id']}", headers=HEADERS)
    assert cancelamento.status_code == 200, cancelamento.text

    resposta = confirmar(pedido["id"], pedido["total_final"])
    assert resposta.status_code == 200, resposta.text
    assert resposta.json()["status_conciliacao"] == "pagamento_tardio"

    pedido_apos = client.get(f"/api/pedidos/{pedido['id']}", headers=HEADERS).json()
    assert pedido_apos["status"] == "Cancelado"  # nunca reabre
    assert estoque(produto["id"]) == 0


# 18 — acompanhamento público retorna status coerente


def test_acompanhamento_publico_retorna_status_coerente_para_encomenda():
    produto = criar_produto(sob_encomenda=True, quantidade=0, limite=5)
    pedido = criar_pedido_encomenda(produto, quantidade=1)
    confirmar(pedido["id"], pedido["total_final"])

    status_publico = client.get(f"/api/pedidos/{pedido['id']}/status", params={"txid": pedido["pix_txid"]})
    assert status_publico.status_code == 200, status_publico.text
    corpo = status_publico.json()
    assert corpo["status_atual"] == "Aguardando encomenda"


# 19 — painel administrativo não expõe fornecedor/custo


def test_painel_admin_nao_expoe_url_de_fornecedor_ou_margem_para_encomenda():
    produto = criar_produto(sob_encomenda=True, quantidade=0, limite=5)
    pedido = criar_pedido_encomenda(produto, quantidade=1)
    confirmar(pedido["id"], pedido["total_final"])

    pedido_admin = client.get(f"/api/pedidos/{pedido['id']}", headers=HEADERS).json()
    assert "fornecedor" not in pedido_admin
    assert "margem" not in pedido_admin
    for item in pedido_admin["itens"]:
        assert "fornecedor" not in item
    texto_serializado = str(pedido_admin).lower()
    assert "http://" not in texto_serializado
    assert "https://" not in texto_serializado


# 20/21 — migração idempotente e banco legado preserva dados


def test_migracao_de_tipo_item_e_idempotente_e_preserva_pedidos_antigos():
    from database.migrations import init_db

    produto_fisico = criar_produto(sob_encomenda=False, quantidade=5)
    pedido_fisico = criar_pedido_fisico(produto_fisico, quantidade=1)

    produto_encomenda = criar_produto(sob_encomenda=True, quantidade=0, limite=5)
    pedido_encomenda = criar_pedido_encomenda(produto_encomenda, quantidade=1)

    # Simula reinicialização do app rodando a migração de novo (idempotente).
    init_db()
    init_db()

    with conectar() as conn:
        tipo_fisico = conn.execute("SELECT tipo_item FROM pedidos_itens WHERE pedido_id=?", (pedido_fisico["id"],)).fetchone()["tipo_item"]
        tipo_encomenda = conn.execute("SELECT tipo_item FROM pedidos_itens WHERE pedido_id=?", (pedido_encomenda["id"],)).fetchone()["tipo_item"]

    assert tipo_fisico == TIPO_ITEM_FISICO
    assert tipo_encomenda == TIPO_ITEM_SOB_ENCOMENDA

    # Confirma que os pedidos continuam confirmáveis normalmente depois da
    # migração rodar de novo (nenhum dado foi perdido/corrompido).
    assert confirmar(pedido_fisico["id"], pedido_fisico["total_final"]).status_code == 200
    assert confirmar(pedido_encomenda["id"], pedido_encomenda["total_final"]).status_code == 200


# 22 — auditoria sanitizada


def test_auditoria_da_baixa_de_estoque_e_sanitizada():
    produto = criar_produto(sob_encomenda=True, quantidade=0, limite=5)
    pedido = criar_pedido_encomenda(produto, quantidade=1)
    confirmar(pedido["id"], pedido["total_final"])

    with conectar() as conn:
        linhas = conn.execute(
            "SELECT dados_antes, dados_depois FROM audit_log WHERE entidade='estoque' AND entidade_id=?",
            (str(pedido["id"]),),
        ).fetchall()
    assert linhas
    for linha in linhas:
        texto = f"{linha['dados_antes'] or ''} {linha['dados_depois'] or ''}".lower()
        for termo_proibido in ("fornecedor", "custo", "margem", "http://", "https://"):
            assert termo_proibido not in texto
