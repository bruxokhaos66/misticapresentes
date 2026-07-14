"""Testes da classificação persistida de pedidos_itens.tipo_item — revisão
pré-merge do PR #313 (fix/encomenda-confirmacao-pagamento).

Cobrem especificamente:
1. o novo default seguro 'legado_ambiguo' (em vez de 'fisico') para itens
   migrados antes da coluna existir;
2. o backfill via audit_log (evidência inequívoca de físico/encomenda,
   ausência de evidência, evidência conflitante, JSON inválido em
   dados_depois, idempotência ao rodar a migração de novo);
3. que tipo_item nunca é aceito de um campo enviado pelo cliente;
4. o CHECK constraint no banco e a normalização defensiva em Python.
"""

import importlib
import os
import sqlite3
import uuid

from fastapi.testclient import TestClient

os.environ.setdefault("MISTICA_SITE_API_KEY", "test-api-key")
os.environ.setdefault("MISTICA_SYNC_KEY", "test-api-key")
os.environ.setdefault("MISTICA_PIX_KEY", "49999999999")

import database.migrations as db_migrations  # noqa: E402
from backend.database import conectar  # noqa: E402
from backend.order_status_routes import (  # noqa: E402
    TIPO_ITEM_FISICO,
    TIPO_ITEM_LEGADO_AMBIGUO,
    TIPO_ITEM_SOB_ENCOMENDA,
    _tipo_item_normalizado,
)

main = importlib.import_module("backend.main")
client = TestClient(main.app)
client.__enter__()

HEADERS = {"X-Mistica-Api-Key": os.environ["MISTICA_SITE_API_KEY"]}


def codigo_unico(prefixo: str) -> str:
    return f"{prefixo}-{uuid.uuid4().hex[:10]}"


def ip_unico() -> str:
    return f"203.0.113.{uuid.uuid4().int % 256}"


def criar_produto(*, sob_encomenda: bool, quantidade: int, limite: int = 10) -> dict:
    payload = {
        "codigo_p": codigo_unico("TIPOITEM"),
        "nome": f"Produto tipo_item {uuid.uuid4().hex[:8]}",
        "preco": 29.9,
        "custo": 10.0,
        "quantidade": quantidade,
        "categoria": "Testes",
        "sob_encomenda": sob_encomenda,
        "limite_encomenda": limite,
    }
    resposta = client.post("/api/produtos", json=payload, headers=HEADERS)
    assert resposta.status_code == 200, resposta.text
    return {**payload, "id": resposta.json()["id"], "codigo_p": payload["codigo_p"].upper()}


# ---------------------------------------------------------------------------
# Banco isolado (arquivo sqlite próprio) para exercitar o backfill sem tocar
# no banco compartilhado usado pelo resto da suíte via TestClient.
# ---------------------------------------------------------------------------

class BancoIsolado:
    """Opera sobre o MESMO banco compartilhado usado pelo resto da suíte via
    conectar() — como qualquer outro teste deste repositório.

    Uma versão anterior desta fixture criava um arquivo sqlite à parte e
    trocava database.connection.DB_PATH para apontar para ele durante o
    teste. Isso causou uma falha real em CI: backend/main.py mantém uma
    tarefa periódica em background (spawnada pelo TestClient de QUALQUER
    módulo de teste ainda "vivo" no mesmo processo pytest) que chama
    backend.database.conectar(), e conectar() sempre roda
    database.migrations.init_db() de novo antes de abrir a conexão —
    init_db() usa database.connection.query_db() internamente, que lê
    database.connection.DB_PATH a cada chamada. Enquanto esse global ficava
    apontando para o arquivo temporário do teste, a tarefa periódica podia
    dar seu próprio init_db() nesse MESMO arquivo ao mesmo tempo que o
    teste, e as duas tentativas de bootstrap do usuário admin colidiam
    (UNIQUE constraint failed: usuarios.login). Por isso esta fixture nunca
    troca esse global: cada pedido/item usa um id novo (AUTOINCREMENT), e o
    backfill filtra sempre por pedido_id, então não há risco de um teste
    contaminar o outro operando no banco compartilhado."""

    def criar_pedido_legado(self, *, tipo_item: str = TIPO_ITEM_LEGADO_AMBIGUO) -> int:
        """Simula um pedido criado antes da coluna tipo_item existir: um
        pedido com um item cujo tipo_item está no valor padrão ambíguo (o
        estado real de um item legado depois do ALTER TABLE, antes de
        qualquer backfill rodar) — sem passar por /api/vendas ou
        /api/checkout/pedidos, então não existe nenhum evento audit_log
        'criar'/'criar_sob_encomenda' associado a menos que o teste registre
        um explicitamente."""
        with conectar() as conn:
            cur = conn.execute(
                "INSERT INTO pedidos (cliente, status, total_final) VALUES (?,?,?)",
                ("Cliente legado", "Aguardando pagamento", 29.9),
            )
            pedido_id = int(cur.lastrowid)
            conn.execute(
                "INSERT INTO pedidos_itens (pedido_id, codigo_p, nome_p, quantidade, tipo_item) VALUES (?,?,?,?,?)",
                (pedido_id, "COD-LEGADO", "Produto legado", 1, tipo_item),
            )
            conn.commit()
        return pedido_id

    def registrar_audit(self, pedido_id: int, acao: str, dados_depois: str | None = "irrelevante"):
        self.registrar_audits(pedido_id, [(acao, dados_depois)])

    def registrar_audits(self, pedido_id: int, eventos: list[tuple[str, str | None]]):
        """Grava um ou mais eventos audit_log('pedido', ...) para o mesmo
        pedido numa única transação. Importante para simular evidência
        conflitante (dois eventos para o mesmo pedido): o app tem uma tarefa
        periódica em background (backend/main.py) que chama conectar() a
        cada poucos segundos, e conectar() sempre roda init_db() de novo, que
        por sua vez roda _backfill_tipo_item_pedidos_itens() no final. Se os
        dois eventos fossem gravados em conexões/transações separadas,
        existiria uma janela em que só um deles está visível — a tarefa
        periódica poderia rodar o backfill nesse meio-tempo, resolver o item
        prematuramente com evidência incompleta, e o teste passaria a
        verificar um estado que não é mais o gravado pelo default do ALTER
        TABLE (não seria mais um teste de conflito de verdade)."""
        with conectar() as conn:
            for acao, dados_depois in eventos:
                conn.execute(
                    "INSERT INTO audit_log (entidade, entidade_id, acao, usuario, dados_depois, data_hora) VALUES (?,?,?,?,?,?)",
                    ("pedido", str(pedido_id), acao, "Sistema", dados_depois, "2020-01-01T00:00:00"),
                )
            conn.commit()

    def tipo_item_do_pedido(self, pedido_id: int) -> str:
        with conectar() as conn:
            row = conn.execute("SELECT tipo_item FROM pedidos_itens WHERE pedido_id=?", (pedido_id,)).fetchone()
        return row["tipo_item"]


# 1. Novos pedidos: comportamento inalterado (classificação explícita, nunca
# ambígua) — já coberto por tests/test_pedido_encomenda_pagamento.py, mas
# reforçado aqui isolando o valor gravado.


def test_novo_pedido_fisico_recebe_classificacao_explicita_nunca_ambigua():
    produto = criar_produto(sob_encomenda=False, quantidade=5)
    resposta = client.post(
        "/api/vendas",
        headers={**HEADERS, "X-Forwarded-For": ip_unico()},
        json={"cliente": "Cliente", "status": "Aguardando pagamento", "baixa_estoque": True, "itens": [{"produto_id": produto["id"], "quantidade": 1}]},
    )
    assert resposta.status_code == 200, resposta.text
    with conectar() as conn:
        tipo = conn.execute("SELECT tipo_item FROM pedidos_itens WHERE pedido_id=?", (resposta.json()["id"],)).fetchone()["tipo_item"]
    assert tipo == TIPO_ITEM_FISICO


def test_novo_pedido_encomenda_recebe_classificacao_explicita_nunca_ambigua():
    produto = criar_produto(sob_encomenda=True, quantidade=0, limite=5)
    resposta = client.post(
        "/api/checkout/pedidos",
        headers={"X-Forwarded-For": ip_unico()},
        json={"cliente": "Cliente", "ciente_sob_encomenda": True, "itens": [{"produto_id": produto["id"], "codigo_p": produto["codigo_p"], "quantidade": 1}]},
    )
    assert resposta.status_code == 200, resposta.text
    with conectar() as conn:
        tipo = conn.execute("SELECT tipo_item FROM pedidos_itens WHERE pedido_id=?", (resposta.json()["id"],)).fetchone()["tipo_item"]
    assert tipo == TIPO_ITEM_SOB_ENCOMENDA


# 2/3. Backfill — evidência inequívoca de item físico / de encomenda.


def test_backfill_reclassifica_pedido_legado_com_evidencia_fisica():
    banco = BancoIsolado()
    pedido_id = banco.criar_pedido_legado()
    banco.registrar_audit(pedido_id, "criar")
    db_migrations._backfill_tipo_item_pedidos_itens()
    assert banco.tipo_item_do_pedido(pedido_id) == TIPO_ITEM_FISICO


def test_backfill_reclassifica_pedido_legado_com_evidencia_de_encomenda():
    banco = BancoIsolado()
    pedido_id = banco.criar_pedido_legado()
    banco.registrar_audit(pedido_id, "criar_sob_encomenda")
    db_migrations._backfill_tipo_item_pedidos_itens()
    assert banco.tipo_item_do_pedido(pedido_id) == TIPO_ITEM_SOB_ENCOMENDA


# 3. Banco legado sem audit_log acessível (tabela ausente/corrompida —
# simulado fazendo query_db falhar para qualquer consulta, sem tocar no
# banco real compartilhado: ver docstring de BancoIsolado sobre por que não
# trocamos DB_PATH global).


def test_backfill_sem_audit_log_acessivel_nao_quebra_e_mantem_ambiguo(monkeypatch):
    banco = BancoIsolado()
    pedido_id = banco.criar_pedido_legado()

    def query_db_indisponivel(*_args, **_kwargs):
        raise sqlite3.OperationalError("no such table: audit_log")

    monkeypatch.setattr(db_migrations, "query_db", query_db_indisponivel)
    db_migrations._backfill_tipo_item_pedidos_itens()  # não deve lançar
    monkeypatch.undo()  # tipo_item_do_pedido() usa conectar(), que roda init_db() (e portanto query_db) de novo

    assert banco.tipo_item_do_pedido(pedido_id) == TIPO_ITEM_LEGADO_AMBIGUO


# 4. audit_log vazio (sem nenhum evento relacionado a este pedido).


def test_backfill_com_audit_log_vazio_mantem_ambiguo():
    banco = BancoIsolado()
    pedido_id = banco.criar_pedido_legado()
    db_migrations._backfill_tipo_item_pedidos_itens()
    assert banco.tipo_item_do_pedido(pedido_id) == TIPO_ITEM_LEGADO_AMBIGUO


# 5. JSON inválido em dados_depois não afeta a decisão (o backfill nunca
# interpreta esse campo — só entidade/entidade_id/acao).


def test_backfill_ignora_json_invalido_em_dados_depois():
    banco = BancoIsolado()
    pedido_id = banco.criar_pedido_legado()
    banco.registrar_audit(pedido_id, "criar_sob_encomenda", dados_depois="{isso nao e json valido")
    db_migrations._backfill_tipo_item_pedidos_itens()
    assert banco.tipo_item_do_pedido(pedido_id) == TIPO_ITEM_SOB_ENCOMENDA

    pedido_id_2 = banco.criar_pedido_legado()
    banco.registrar_audit(pedido_id_2, "criar_sob_encomenda", dados_depois=None)
    db_migrations._backfill_tipo_item_pedidos_itens()
    assert banco.tipo_item_do_pedido(pedido_id_2) == TIPO_ITEM_SOB_ENCOMENDA


# 6. Informação conflitante: o mesmo pedido com evidência dos dois lados
# nunca é resolvido automaticamente — permanece ambíguo.


def test_backfill_com_evidencia_conflitante_permanece_ambiguo():
    banco = BancoIsolado()
    pedido_id = banco.criar_pedido_legado()
    banco.registrar_audits(pedido_id, [("criar", "irrelevante"), ("criar_sob_encomenda", "irrelevante")])
    db_migrations._backfill_tipo_item_pedidos_itens()
    assert banco.tipo_item_do_pedido(pedido_id) == TIPO_ITEM_LEGADO_AMBIGUO


# 7. Backfill executado duas vezes seguidas: idempotente.


def test_backfill_executado_duas_vezes_e_idempotente():
    banco = BancoIsolado()
    pedido_fisico = banco.criar_pedido_legado()
    banco.registrar_audit(pedido_fisico, "criar")
    pedido_encomenda = banco.criar_pedido_legado()
    banco.registrar_audit(pedido_encomenda, "criar_sob_encomenda")
    pedido_ambiguo = banco.criar_pedido_legado()

    db_migrations._backfill_tipo_item_pedidos_itens()
    primeira = {
        pedido_fisico: banco.tipo_item_do_pedido(pedido_fisico),
        pedido_encomenda: banco.tipo_item_do_pedido(pedido_encomenda),
        pedido_ambiguo: banco.tipo_item_do_pedido(pedido_ambiguo),
    }

    db_migrations._backfill_tipo_item_pedidos_itens()  # rodar de novo não deve mudar nada
    segunda = {
        pedido_fisico: banco.tipo_item_do_pedido(pedido_fisico),
        pedido_encomenda: banco.tipo_item_do_pedido(pedido_encomenda),
        pedido_ambiguo: banco.tipo_item_do_pedido(pedido_ambiguo),
    }

    assert primeira == segunda
    assert primeira[pedido_fisico] == TIPO_ITEM_FISICO
    assert primeira[pedido_encomenda] == TIPO_ITEM_SOB_ENCOMENDA
    assert primeira[pedido_ambiguo] == TIPO_ITEM_LEGADO_AMBIGUO  # nunca "promovido" a físico


# 8. Nenhum item ambíguo é convertido silenciosamente em físico — e um
# pedido nessas condições bloqueia (não confirma) a confirmação de
# pagamento, no banco real usado pela API.


def test_pedido_com_tipo_item_legado_ambiguo_bloqueia_confirmacao_no_banco_real():
    """Monta o pedido diretamente no banco (sem passar por /api/vendas ou
    /api/checkout/pedidos), para que não exista nenhum evento audit_log
    'criar'/'criar_sob_encomenda' associado — a mesma condição de um pedido
    legado sem evidência. Isso importa: init_db() roda a cada conectar() e
    reclassifica automaticamente qualquer item 'legado_ambiguo' para o qual
    exista evidência (comportamento correto e testado acima em
    test_backfill_reclassifica_pedido_legado_com_evidencia_fisica); um pedido
    criado pela API normal teria essa evidência e seria "curado" de volta
    para 'fisico' na próxima conexão, o que não serve para testar o caso
    real de ausência de evidência."""
    with conectar() as conn:
        cur = conn.execute(
            "INSERT INTO pedidos (cliente, status, total_final, estoque_baixado) VALUES (?,?,?,0)",
            ("Cliente legado ambíguo", "Aguardando pagamento", 10.0),
        )
        pedido_id = int(cur.lastrowid)
        conn.execute(
            "INSERT INTO pedidos_itens (pedido_id, codigo_p, nome_p, quantidade, tipo_item) VALUES (?,?,?,?,?)",
            (pedido_id, "COD-LEGADO-REAL", "Produto legado real", 1, TIPO_ITEM_LEGADO_AMBIGUO),
        )
        conn.commit()

    pedido = client.get(f"/api/pedidos/{pedido_id}", headers=HEADERS).json()
    confirmacao = client.post(
        "/api/pagamentos",
        headers={**HEADERS, "X-Forwarded-For": ip_unico()},
        json={"venda_id": pedido_id, "valor": pedido["total_final"], "status": "Confirmado", "usuario": "Teste"},
    )
    assert confirmacao.status_code == 409, confirmacao.text
    assert "conciliação administrativa" in confirmacao.json()["detail"].lower()

    pedido_apos = client.get(f"/api/pedidos/{pedido_id}", headers=HEADERS).json()
    assert pedido_apos["status"] == "Aguardando pagamento"  # nunca confirmado como físico nem como encomenda


# ---------------------------------------------------------------------------
# 3. tipo_item é sempre calculado pelo servidor — nunca aceito de um campo
# enviado pelo cliente.
# ---------------------------------------------------------------------------


def test_checkout_publico_ignora_tipo_item_enviado_pelo_cliente_para_produto_fisico():
    produto = criar_produto(sob_encomenda=False, quantidade=5)
    resposta = client.post(
        "/api/vendas",
        headers={**HEADERS, "X-Forwarded-For": ip_unico()},
        json={
            "cliente": "Cliente",
            "status": "Aguardando pagamento",
            "baixa_estoque": True,
            "itens": [{"produto_id": produto["id"], "quantidade": 1, "tipo_item": "sob_encomenda"}],
        },
    )
    assert resposta.status_code == 200, resposta.text
    with conectar() as conn:
        tipo = conn.execute("SELECT tipo_item FROM pedidos_itens WHERE pedido_id=?", (resposta.json()["id"],)).fetchone()["tipo_item"]
    assert tipo == TIPO_ITEM_FISICO  # o payload malicioso foi ignorado (Pydantic descarta campo desconhecido)


def test_checkout_publico_ignora_tipo_item_enviado_pelo_cliente_para_produto_encomenda():
    produto = criar_produto(sob_encomenda=True, quantidade=0, limite=5)
    resposta = client.post(
        "/api/checkout/pedidos",
        headers={"X-Forwarded-For": ip_unico()},
        json={
            "cliente": "Cliente",
            "ciente_sob_encomenda": True,
            "itens": [{"produto_id": produto["id"], "codigo_p": produto["codigo_p"], "quantidade": 1, "tipo_item": "fisico"}],
        },
    )
    assert resposta.status_code == 200, resposta.text
    with conectar() as conn:
        tipo = conn.execute("SELECT tipo_item FROM pedidos_itens WHERE pedido_id=?", (resposta.json()["id"],)).fetchone()["tipo_item"]
    assert tipo == TIPO_ITEM_SOB_ENCOMENDA  # o payload malicioso foi ignorado


# ---------------------------------------------------------------------------
# 4. Valores permitidos: CHECK no banco + normalização defensiva em Python.
# ---------------------------------------------------------------------------


def test_check_constraint_rejeita_valor_invalido_no_banco():
    with conectar() as conn:
        try:
            conn.execute(
                "INSERT INTO pedidos_itens (pedido_id, codigo_p, nome_p, quantidade, tipo_item) VALUES (?,?,?,?,?)",
                (999999, "X", "X", 1, "valor_invalido"),
            )
            levantou = False
        except sqlite3.IntegrityError:
            levantou = True
    assert levantou, "CHECK constraint deveria rejeitar um tipo_item fora de fisico/sob_encomenda/legado_ambiguo"


def test_normalizacao_de_tipo_item_ignora_maiusculas_e_espacos():
    assert _tipo_item_normalizado({"tipo_item": "  SOB_ENCOMENDA  "}) == TIPO_ITEM_SOB_ENCOMENDA
    assert _tipo_item_normalizado({"tipo_item": "Fisico"}) == TIPO_ITEM_FISICO
    assert _tipo_item_normalizado({"tipo_item": None}) == ""
    assert _tipo_item_normalizado({"tipo_item": ""}) == ""
