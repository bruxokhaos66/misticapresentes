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
import tempfile
import uuid

from fastapi.testclient import TestClient

os.environ.setdefault("MISTICA_SITE_API_KEY", "test-api-key")
os.environ.setdefault("MISTICA_SYNC_KEY", "test-api-key")
os.environ.setdefault("MISTICA_PIX_KEY", "49999999999")

import database.connection as db_connection  # noqa: E402
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
    def __enter__(self):
        fd, self.path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        os.remove(self.path)
        self._original_db_path = db_connection.DB_PATH
        db_connection.DB_PATH = self.path
        db_migrations.init_db()
        return self

    def __exit__(self, *exc):
        db_connection.DB_PATH = self._original_db_path
        try:
            os.remove(self.path)
        except OSError:
            pass

    def conn(self):
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        return conn

    def criar_pedido_legado(self, *, tipo_item: str = TIPO_ITEM_LEGADO_AMBIGUO) -> int:
        """Simula um pedido criado antes da coluna tipo_item existir: um
        pedido com um item cujo tipo_item está no valor padrão ambíguo (o
        estado real de um item legado depois do ALTER TABLE, antes de
        qualquer backfill rodar)."""
        conn = self.conn()
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
        conn.close()
        return pedido_id

    def registrar_audit(self, pedido_id: int, acao: str, dados_depois: str | None = "irrelevante"):
        conn = self.conn()
        conn.execute(
            "INSERT INTO audit_log (entidade, entidade_id, acao, usuario, dados_depois, data_hora) VALUES (?,?,?,?,?,?)",
            ("pedido", str(pedido_id), acao, "Sistema", dados_depois, "2020-01-01T00:00:00"),
        )
        conn.commit()
        conn.close()

    def tipo_item_do_pedido(self, pedido_id: int) -> str:
        conn = self.conn()
        row = conn.execute("SELECT tipo_item FROM pedidos_itens WHERE pedido_id=?", (pedido_id,)).fetchone()
        conn.close()
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
    with BancoIsolado() as banco:
        pedido_id = banco.criar_pedido_legado()
        banco.registrar_audit(pedido_id, "criar")
        db_migrations._backfill_tipo_item_pedidos_itens()
        assert banco.tipo_item_do_pedido(pedido_id) == TIPO_ITEM_FISICO


def test_backfill_reclassifica_pedido_legado_com_evidencia_de_encomenda():
    with BancoIsolado() as banco:
        pedido_id = banco.criar_pedido_legado()
        banco.registrar_audit(pedido_id, "criar_sob_encomenda")
        db_migrations._backfill_tipo_item_pedidos_itens()
        assert banco.tipo_item_do_pedido(pedido_id) == TIPO_ITEM_SOB_ENCOMENDA


# 3. Banco legado sem audit_log (tabela ausente).


def test_backfill_sem_tabela_audit_log_nao_quebra_e_mantem_ambiguo():
    with BancoIsolado() as banco:
        pedido_id = banco.criar_pedido_legado()
        conn = banco.conn()
        conn.execute("DROP TABLE audit_log")
        conn.commit()
        conn.close()

        db_migrations._backfill_tipo_item_pedidos_itens()  # não deve lançar

        assert banco.tipo_item_do_pedido(pedido_id) == TIPO_ITEM_LEGADO_AMBIGUO


# 4. audit_log vazio.


def test_backfill_com_audit_log_vazio_mantem_ambiguo():
    with BancoIsolado() as banco:
        pedido_id = banco.criar_pedido_legado()
        db_migrations._backfill_tipo_item_pedidos_itens()
        assert banco.tipo_item_do_pedido(pedido_id) == TIPO_ITEM_LEGADO_AMBIGUO


# 5. JSON inválido em dados_depois não afeta a decisão (o backfill nunca
# interpreta esse campo — só entidade/entidade_id/acao).


def test_backfill_ignora_json_invalido_em_dados_depois():
    with BancoIsolado() as banco:
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
    with BancoIsolado() as banco:
        pedido_id = banco.criar_pedido_legado()
        banco.registrar_audit(pedido_id, "criar")
        banco.registrar_audit(pedido_id, "criar_sob_encomenda")
        db_migrations._backfill_tipo_item_pedidos_itens()
        assert banco.tipo_item_do_pedido(pedido_id) == TIPO_ITEM_LEGADO_AMBIGUO


# 7. Migração/backfill executados duas vezes: idempotente.


def test_backfill_executado_duas_vezes_e_idempotente():
    with BancoIsolado() as banco:
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

        db_migrations.init_db()  # roda a migração inteira de novo, não só o backfill
        db_migrations._backfill_tipo_item_pedidos_itens()
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
