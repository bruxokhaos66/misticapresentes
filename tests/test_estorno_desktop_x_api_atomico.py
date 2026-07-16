"""Concorrência cruzada entre os dois caminhos de estorno de vendas de
PDV/caixa que compartilham o mesmo banco SQLite (Fase 2 — PR
fix/caixa-estorno-atomico):

- services/venda_service.py::cancelar_venda_service   (app desktop)
- backend/main.py::estornar_venda ("/api/vendas/{id}/estornar", API REST)

Os dois caminhos usam implementações diferentes (uma em cima de
database.connection.get_connection, outra em cima de backend.database.conectar)
mas operam sobre as mesmas tabelas (vendas, vendas_itens, produtos). Este
arquivo garante que a exclusão mútua da reivindicação por CAS
(`UPDATE ... WHERE ... NOT LIKE 'cancel%'`) vale também quando os dois
caminhos competem entre si, não só dentro do mesmo caminho.

Achado documentado (não uma condição de corrida, um gap de escopo
pré-existente e fora do escopo deste PR): a rota REST não grava saída em
fluxo_caixa (não tem associação com caixa_id) — só o caminho desktop grava.
Portanto, quando a API vence a corrida, a devolução de estoque acontece
corretamente e de forma exclusiva, mas nenhum lançamento financeiro de
estorno é criado. Isso é verificado explicitamente abaixo para não regredir
silenciosamente caso a API passe a gravar fluxo_caixa no futuro sem os
mesmos testes de exclusão mútua.

Nota sobre flake pré-existente (investigado na Fase A, PR #331): o CI
relatou um `threading.BrokenBarrierError` intermitente em
`test_api_x_api_no_banco_compartilhado`. Reprodução estatística mostrou que
o mesmo erro ocorre também em `origin/main` ANTES das mudanças da Fase A —
este arquivo não foi alterado pelo PR #331 e a Fase A não toca nada usado
aqui. A causa raiz não era só timeout apertado: os dois threads faziam
`with TestClient(main.app) as thread_client:` (o que dispara o
lifespan/startup do FastAPI, incluindo inicialização de banco e logging)
*dentro* do trecho cronometrado pela barreira — sob CI compartilhado, esse
startup concorrente pode variar bem mais que os poucos segundos que a
corrida em si leva, e um simples aumento de timeout (10s -> 30s) não foi
suficiente (voltou a falhar com o mesmo erro). A correção definitiva foi
tirar a criação do `TestClient` de dentro do bloco cronometrado,
pré-aquecendo os dois clients ANTES da barreira: assim `barreira.wait`
só precisa cobrir o skew de agendamento das threads até o POST em si, não
mais o startup do app. Nenhuma asserção nem a semântica do teste mudou —
a corrida real do POST concorrente continua sendo exercida.
"""

import os
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

import pytest

os.environ.setdefault("MISTICA_SITE_API_KEY", "test-api-key")
os.environ.setdefault("MISTICA_SYNC_KEY", "test-api-key")
os.environ.setdefault("MISTICA_PIX_WEBHOOK_SECRET", "test-estorno-cruzado-webhook-secret")
os.environ.setdefault("MISTICA_PIX_KEY", "49999999999")

import importlib

import config
import database.connection as db_conn
import backend.database as backend_db
from fastapi.testclient import TestClient

from services import venda_service
from services.caixa_service import abrir_caixa, fechar_caixa_simples

main = importlib.import_module("backend.main")
HEADERS = {"X-Mistica-Api-Key": os.environ["MISTICA_SITE_API_KEY"]}


@pytest.fixture()
def banco_compartilhado(tmp_path, monkeypatch):
    """Aponta os dois caminhos (desktop e API) para o mesmo arquivo SQLite,
    como acontece em produção (MISTICA_DB_PATH compartilhado)."""
    db_path = str(tmp_path / "estorno_desktop_x_api.db")
    monkeypatch.setattr(config, "DB_PATH", db_path)
    monkeypatch.setattr(db_conn, "DB_PATH", db_path)
    monkeypatch.setattr(backend_db, "DB_PATH", db_path)
    monkeypatch.setattr(venda_service, "_confirmar_venda_no_banco_central", lambda venda_id: (True, None))

    from database import init_db

    init_db()
    return db_path


def _produto(codigo, preco=60.0, quantidade=5):
    with backend_db.conectar() as conn:
        conn.execute(
            "INSERT INTO produtos (codigo_p, nome, preco, quantidade, categoria, custo) VALUES (?,?,?,?,?,?)",
            (codigo, f"Produto {codigo}", preco, quantidade, "Testes", 20.0),
        )
        conn.commit()


def _venda_direto(codigo, caixa_id, preco=60.0, quantidade=1):
    agora = datetime.now().strftime("%d/%m/%Y %H:%M")
    agora_iso = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    total = round(preco * quantidade, 2)
    with backend_db.conectar() as conn:
        cur = conn.execute(
            """
            INSERT INTO vendas (cliente, data_venda, data_iso, subtotal, desconto, taxa, total_final, forma_pagamento, vendedor, status)
            VALUES (?,?,?,?,?,?,?,?,?,?)
            """,
            ("Consumidor Final", agora, agora_iso, total, 0.0, 0.0, total, "Dinheiro", "Teste", "Concluído"),
        )
        venda_id = int(cur.lastrowid)
        conn.execute(
            "INSERT INTO vendas_itens (venda_id, codigo_p, nome_p, quantidade, custo_unitario, valor_unitario, valor_total) VALUES (?,?,?,?,?,?,?)",
            (venda_id, codigo, f"Produto {codigo}", quantidade, 20.0, preco, total),
        )
        conn.execute("UPDATE produtos SET quantidade = quantidade - ? WHERE codigo_p=?", (quantidade, codigo))
        conn.commit()
    return venda_id


def _estoque(codigo):
    with backend_db.conectar() as conn:
        row = conn.execute("SELECT quantidade FROM produtos WHERE codigo_p=?", (codigo,)).fetchone()
    return int(row["quantidade"])


def _status_venda(venda_id):
    with backend_db.conectar() as conn:
        row = conn.execute("SELECT status FROM vendas WHERE id=?", (venda_id,)).fetchone()
    return row["status"]


def _fluxo_saidas(caixa_id):
    with backend_db.conectar() as conn:
        return conn.execute(
            "SELECT valor, descricao FROM fluxo_caixa WHERE caixa_id=? AND tipo='Saida'", (caixa_id,)
        ).fetchall()


# desktop × desktop (regressão explícita nesta suíte cruzada, já coberta em
# test_estorno_caixa_atomico.py, repetida aqui como controle de sanidade do
# fixture compartilhado)


def test_desktop_x_desktop_no_banco_compartilhado(banco_compartilhado):
    codigo = uuid.uuid4().hex[:10]
    _produto(codigo, quantidade=5)
    caixa_id = abrir_caixa(0.0, "Teste")
    venda_id = _venda_direto(codigo, caixa_id)
    assert _estoque(codigo) == 4

    barreira = threading.Barrier(2)

    def estornar():
        barreira.wait(timeout=30)
        try:
            venda_service.cancelar_venda_service(venda_id, "Teste", caixa_id)
            return "ok"
        except ValueError as exc:
            return str(exc)

    with ThreadPoolExecutor(max_workers=2) as executor:
        resultados = [f.result(timeout=45) for f in [executor.submit(estornar) for _ in range(2)]]

    assert sorted(resultados) == ["Venda ja cancelada.", "ok"]
    assert _estoque(codigo) == 5


# API × API no mesmo banco compartilhado (controle de sanidade)


def test_api_x_api_no_banco_compartilhado(banco_compartilhado):
    codigo = uuid.uuid4().hex[:10]
    _produto(codigo, quantidade=5)
    caixa_id = abrir_caixa(0.0, "Teste")
    venda_id = _venda_direto(codigo, caixa_id)
    barreira = threading.Barrier(2)

    # O startup do TestClient (lifespan do FastAPI) é feito ANTES da
    # barreira, fora do trecho cronometrado: assim a janela do barrier só
    # precisa cobrir o skew de agendamento das threads até o POST, não a
    # inicialização do app (que sob CI compartilhado/GIL pode variar bem
    # mais que os poucos segundos que a corrida em si leva).
    def enviar(cliente):
        barreira.wait(timeout=30)
        return cliente.post(f"/api/vendas/{venda_id}/estornar", headers=HEADERS, json={"usuario": "Teste"})

    with TestClient(main.app) as cliente_a, TestClient(main.app) as cliente_b:
        with ThreadPoolExecutor(max_workers=2) as executor:
            respostas = [
                f.result(timeout=45)
                for f in [executor.submit(enviar, cliente_a), executor.submit(enviar, cliente_b)]
            ]

    for resposta in respostas:
        assert resposta.status_code == 200, resposta.text
    assert sum(1 for r in respostas if r.json()["ja_cancelada"] is False) == 1
    assert _estoque(codigo) == 5


# desktop × API — o cenário cruzado propriamente dito


def test_desktop_x_api_apenas_um_vence_e_nao_duplica_efeitos(banco_compartilhado):
    resultados_gerais = []
    for _ in range(8):
        codigo = uuid.uuid4().hex[:10]
        _produto(codigo, quantidade=5)
        caixa_id = abrir_caixa(0.0, "Teste")
        venda_id = _venda_direto(codigo, caixa_id)
        assert _estoque(codigo) == 4

        barreira = threading.Barrier(2)
        resultado = {}

        def estornar_desktop():
            barreira.wait(timeout=30)
            try:
                venda_service.cancelar_venda_service(venda_id, "Teste", caixa_id)
                resultado["desktop"] = "ok"
            except ValueError as exc:
                resultado["desktop"] = str(exc)

        def estornar_api(cliente):
            barreira.wait(timeout=30)
            resp = cliente.post(f"/api/vendas/{venda_id}/estornar", headers=HEADERS, json={"usuario": "Teste"})
            resultado["api_status"] = resp.status_code
            resultado["api_ja_cancelada"] = resp.json().get("ja_cancelada") if resp.status_code == 200 else None

        with TestClient(main.app) as cliente_api:
            with ThreadPoolExecutor(max_workers=2) as executor:
                f1 = executor.submit(estornar_desktop)
                f2 = executor.submit(estornar_api, cliente_api)
                f1.result(timeout=45)
                f2.result(timeout=45)

        # Exclusão mútua: exatamente um dos dois caminhos reivindicou a
        # transição (rowcount==1); o outro observa o estado JÁ cancelado.
        desktop_venceu = resultado["desktop"] == "ok"
        api_venceu = resultado["api_status"] == 200 and resultado["api_ja_cancelada"] is False
        assert desktop_venceu != api_venceu  # exatamente um dos dois, nunca os dois, nunca nenhum

        # Em qualquer dos dois casos, a venda termina cancelada e o estoque é
        # devolvido uma única vez — nunca duplicado, nunca esquecido.
        assert _status_venda(venda_id) == "Cancelado"
        assert _estoque(codigo) == 5

        if desktop_venceu:
            assert resultado["api_ja_cancelada"] is True
            # O caminho desktop grava a saída financeira; a API não tem essa
            # responsabilidade nesta rota (ver docstring do módulo).
            assert len(_fluxo_saidas(caixa_id)) == 1
        else:
            assert resultado["desktop"] == "Venda ja cancelada."
            # Achado documentado: quando a API vence, nenhuma saída
            # financeira é criada (a rota REST não grava fluxo_caixa nesta
            # versão) — nunca duplicada, mas também nunca criada por essa
            # rota. Ver "Riscos residuais" no relatório do PR.
            assert len(_fluxo_saidas(caixa_id)) == 0

        resultados_gerais.append("desktop" if desktop_venceu else "api")
        fechar_caixa_simples(caixa_id, 0.0)

    # O CAS garante exclusão mútua independentemente de qual lado vence — o
    # importante (verificado a cada repetição acima) é que sempre um e só
    # um vence, nunca os dois nem nenhum. Qual caminho normalmente vence
    # neste ambiente de teste reflete o custo relativo de inicializar um
    # TestClient HTTP por chamada (API) vs. abrir uma conexão sqlite direta
    # (desktop), não uma falha de exclusão mútua — por isso não travamos
    # aqui em "as duas ordens ocorreram", só na exclusão mútua em si.
    assert set(resultados_gerais) <= {"desktop", "api"} and resultados_gerais


# Prova determinística (sem depender de timing de scheduler) de que os dois
# sentidos da corrida funcionam corretamente quando um caminho realmente
# vence primeiro: cada um trata corretamente perder para o outro.


def test_api_primeiro_depois_desktop_ve_estado_ja_atual(banco_compartilhado):
    codigo = uuid.uuid4().hex[:10]
    _produto(codigo, quantidade=5)
    caixa_id = abrir_caixa(0.0, "Teste")
    venda_id = _venda_direto(codigo, caixa_id)

    resposta = TestClient(main.app).post(f"/api/vendas/{venda_id}/estornar", headers=HEADERS, json={"usuario": "Teste"})
    assert resposta.status_code == 200 and resposta.json()["ja_cancelada"] is False
    assert _estoque(codigo) == 5

    with pytest.raises(ValueError, match="ja cancelada"):
        venda_service.cancelar_venda_service(venda_id, "Teste", caixa_id)

    assert _estoque(codigo) == 5  # desktop nao repete a devolucao
    assert len(_fluxo_saidas(caixa_id)) == 0  # API nao grava fluxo_caixa nesta rota


def test_desktop_primeiro_depois_api_ve_ja_cancelada(banco_compartilhado):
    codigo = uuid.uuid4().hex[:10]
    _produto(codigo, quantidade=5)
    caixa_id = abrir_caixa(0.0, "Teste")
    venda_id = _venda_direto(codigo, caixa_id)

    venda_service.cancelar_venda_service(venda_id, "Teste", caixa_id)
    assert _estoque(codigo) == 5
    assert len(_fluxo_saidas(caixa_id)) == 1

    resposta = TestClient(main.app).post(f"/api/vendas/{venda_id}/estornar", headers=HEADERS, json={"usuario": "Teste"})
    assert resposta.status_code == 200 and resposta.json()["ja_cancelada"] is True
    assert _estoque(codigo) == 5  # API nao repete a devolucao
    assert len(_fluxo_saidas(caixa_id)) == 1  # nada duplicado
