"""Feature flag MISTICA_REST_ESTORNO_ENABLED (issue #335 — mitigação temporária,
PR fix/restringe-estorno-rest-producao).

A rota REST de estorno (POST /api/vendas/{id}/estornar) devolve estoque mas
não reverte o lançamento financeiro em fluxo_caixa, porque a venda não é
associada ao caixa_id original (ver docstring de backend.main.estornar_venda
e tests/test_estorno_desktop_x_api_atomico.py). Até a correção estrutural,
a rota fica atrás de uma feature flag dedicada, independente de APP_ENV, de
hostname, de query string e da chave geral de sincronização -- ver
backend/api_security.py::estorno_rest_habilitado.

Este arquivo verifica exclusivamente o comportamento da própria flag (rota
bloqueada por padrão, sem efeitos colaterais, sem vazar motivo técnico, sem
contorno por query string/header). O comportamento da rota HABILITADA
(CAS atômico, idempotência, auditoria, concorrência com o caminho desktop)
já é coberto por tests/test_estorno_venda_pdv_api_atomico.py e
tests/test_estorno_desktop_x_api_atomico.py, que agora ligam a flag
explicitamente."""

import importlib
import os
import uuid
from datetime import datetime

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("MISTICA_SITE_API_KEY", "test-api-key")
os.environ.setdefault("MISTICA_SYNC_KEY", "test-api-key")
os.environ.setdefault("MISTICA_PIX_WEBHOOK_SECRET", "test-estorno-flag-webhook-secret")
os.environ.setdefault("MISTICA_PIX_KEY", "49999999999")

import config
import database.connection as db_conn
import backend.database as backend_db
from backend import api_security

main = importlib.import_module("backend.main")

TEST_API_KEY = os.environ["MISTICA_SITE_API_KEY"]
HEADERS = {"X-Mistica-Api-Key": TEST_API_KEY}


@pytest.fixture()
def banco_isolado(tmp_path, monkeypatch):
    db_path = str(tmp_path / "estorno_flag.db")
    monkeypatch.setattr(config, "DB_PATH", db_path)
    monkeypatch.setattr(db_conn, "DB_PATH", db_path)
    monkeypatch.setattr(backend_db, "DB_PATH", db_path)

    from database import init_db

    init_db()
    return db_path


@pytest.fixture()
def flag_desligada(monkeypatch):
    monkeypatch.delenv("MISTICA_REST_ESTORNO_ENABLED", raising=False)


def _produto(codigo, preco=60.0, quantidade=5):
    with backend_db.conectar() as conn:
        conn.execute(
            "INSERT INTO produtos (codigo_p, nome, preco, quantidade, categoria, custo) VALUES (?,?,?,?,?,?)",
            (codigo, f"Produto {codigo}", preco, quantidade, "Testes", 20.0),
        )
        conn.commit()


def _venda(codigo, preco=60.0, quantidade=1):
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


def _venda_criar_com_estoque(quantidade_inicial=5, quantidade_vendida=1):
    codigo = uuid.uuid4().hex[:10]
    _produto(codigo, quantidade=quantidade_inicial)
    venda_id = _venda(codigo, quantidade=quantidade_vendida)
    return codigo, venda_id


def _estoque(codigo):
    with backend_db.conectar() as conn:
        row = conn.execute("SELECT quantidade FROM produtos WHERE codigo_p=?", (codigo,)).fetchone()
    return int(row["quantidade"])


def _status_venda(venda_id):
    with backend_db.conectar() as conn:
        row = conn.execute("SELECT status FROM vendas WHERE id=?", (venda_id,)).fetchone()
    return row["status"]


def _auditoria_estorno(venda_id):
    with backend_db.conectar() as conn:
        return conn.execute(
            "SELECT id FROM audit_log WHERE entidade='venda' AND entidade_id=? AND acao='estornar'",
            (venda_id,),
        ).fetchall()


def _fluxo_saidas_todas():
    with backend_db.conectar() as conn:
        return conn.execute("SELECT id FROM fluxo_caixa WHERE tipo='Saida'").fetchall()


# 1. flag ausente -> bloqueada


def test_flag_ausente_bloqueia_rota(banco_isolado, flag_desligada, monkeypatch):
    assert api_security.estorno_rest_habilitado() is False
    codigo, venda_id = _venda_criar_com_estoque()

    with TestClient(main.app) as cliente:
        resposta = cliente.post(f"/api/vendas/{venda_id}/estornar", headers=HEADERS, json={"usuario": "Teste"})

    assert resposta.status_code == 404
    assert _status_venda(venda_id) == "Concluído"
    assert _estoque(codigo) == 4


# 2. flag "false" explícita -> bloqueada


@pytest.mark.parametrize("valor_flag", ["false", "0", "nao", "qualquercoisa", "  ", "FALSE"])
def test_flag_false_ou_invalida_bloqueia_rota(banco_isolado, monkeypatch, valor_flag):
    monkeypatch.setenv("MISTICA_REST_ESTORNO_ENABLED", valor_flag)
    assert api_security.estorno_rest_habilitado() is False
    codigo, venda_id = _venda_criar_com_estoque()

    with TestClient(main.app) as cliente:
        resposta = cliente.post(f"/api/vendas/{venda_id}/estornar", headers=HEADERS, json={"usuario": "Teste"})

    assert resposta.status_code == 404
    assert _status_venda(venda_id) == "Concluído"
    assert _estoque(codigo) == 4


# 3. flag "true" -> disponível


@pytest.mark.parametrize("valor_flag", ["true", "1", "yes", "on", "sim", "TRUE"])
def test_flag_true_libera_rota(banco_isolado, monkeypatch, valor_flag):
    monkeypatch.setenv("MISTICA_REST_ESTORNO_ENABLED", valor_flag)
    assert api_security.estorno_rest_habilitado() is True
    codigo, venda_id = _venda_criar_com_estoque()

    with TestClient(main.app) as cliente:
        resposta = cliente.post(f"/api/vendas/{venda_id}/estornar", headers=HEADERS, json={"usuario": "Teste"})

    assert resposta.status_code == 200, resposta.text
    assert resposta.json()["ja_cancelada"] is False
    assert _status_venda(venda_id) == "Cancelado"
    assert _estoque(codigo) == 5


# 4. produção não habilita automaticamente


def test_producao_nao_habilita_automaticamente(banco_isolado, flag_desligada, monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setattr(api_security, "APP_ENV", "production")
    monkeypatch.setattr(api_security, "IS_PRODUCTION", True)
    assert api_security.estorno_rest_habilitado() is False
    codigo, venda_id = _venda_criar_com_estoque()

    with TestClient(main.app) as cliente:
        resposta = cliente.post(f"/api/vendas/{venda_id}/estornar", headers=HEADERS, json={"usuario": "Teste"})

    assert resposta.status_code == 404
    assert _status_venda(venda_id) == "Concluído"


# 5. query string não contorna


def test_query_string_nao_contorna_flag_desligada(banco_isolado, flag_desligada):
    codigo, venda_id = _venda_criar_com_estoque()

    with TestClient(main.app) as cliente:
        resposta = cliente.post(
            f"/api/vendas/{venda_id}/estornar?enabled=true&habilitado=1&flag=on&MISTICA_REST_ESTORNO_ENABLED=true",
            headers=HEADERS,
            json={"usuario": "Teste"},
        )

    assert resposta.status_code == 404
    assert _status_venda(venda_id) == "Concluído"
    assert _estoque(codigo) == 4


# 6. header não contorna


def test_header_nao_contorna_flag_desligada(banco_isolado, flag_desligada):
    codigo, venda_id = _venda_criar_com_estoque()
    cabecalhos = dict(HEADERS)
    cabecalhos.update(
        {
            "X-Mistica-Rest-Estorno-Enabled": "true",
            "X-Feature-Flag": "MISTICA_REST_ESTORNO_ENABLED=true",
            "X-Debug-Enable-Estorno": "1",
        }
    )

    with TestClient(main.app) as cliente:
        resposta = cliente.post(f"/api/vendas/{venda_id}/estornar", headers=cabecalhos, json={"usuario": "Teste"})

    assert resposta.status_code == 404
    assert _status_venda(venda_id) == "Concluído"
    assert _estoque(codigo) == 4


# 7 + 8 + 9 + 10 combinados: rota bloqueada não consulta/altera venda, não
# movimenta estoque, não escreve fluxo_caixa, não grava auditoria de estorno.


def test_rota_bloqueada_nao_tem_efeito_colateral_algum(banco_isolado, flag_desligada):
    codigo, venda_id = _venda_criar_com_estoque(quantidade_inicial=5, quantidade_vendida=1)
    saidas_antes = len(_fluxo_saidas_todas())
    auditoria_antes = len(_auditoria_estorno(venda_id))

    with TestClient(main.app) as cliente:
        resposta = cliente.post(f"/api/vendas/{venda_id}/estornar", headers=HEADERS, json={"usuario": "Teste"})

    assert resposta.status_code == 404
    # não consultou nem alterou a venda
    assert _status_venda(venda_id) == "Concluído"
    # não repôs estoque
    assert _estoque(codigo) == 4
    # não escreveu fluxo_caixa
    assert len(_fluxo_saidas_todas()) == saidas_antes
    # não gravou auditoria de estorno
    assert len(_auditoria_estorno(venda_id)) == auditoria_antes


def test_rota_bloqueada_nao_expoe_motivo_tecnico(banco_isolado, flag_desligada):
    codigo, venda_id = _venda_criar_com_estoque()

    with TestClient(main.app) as cliente:
        resposta = cliente.post(f"/api/vendas/{venda_id}/estornar", headers=HEADERS, json={"usuario": "Teste"})

    assert resposta.status_code == 404
    corpo = resposta.json()
    texto = str(corpo).lower()
    for termo_proibido in ("fluxo_caixa", "caixa_id", "issue", "#335", "flag", "mistica_rest_estorno"):
        assert termo_proibido not in texto


def test_rota_bloqueada_mesmo_com_venda_inexistente(banco_isolado, flag_desligada):
    """A flag é checada antes de qualquer SELECT -- mesmo um venda_id que não
    existe retorna 404 genérico da flag, sem chegar a consultar o banco."""
    with TestClient(main.app) as cliente:
        resposta = cliente.post("/api/vendas/999999999/estornar", headers=HEADERS, json={"usuario": "Teste"})

    assert resposta.status_code == 404


def test_rota_bloqueada_mesmo_sem_chave_de_api(banco_isolado, flag_desligada):
    """Flag desligada responde 404 antes mesmo de validar a chave de API --
    quem não tem a flag ligada não descobre se a chave está certa ou errada."""
    codigo, venda_id = _venda_criar_com_estoque()

    with TestClient(main.app) as cliente:
        resposta = cliente.post(f"/api/vendas/{venda_id}/estornar", json={"usuario": "Teste"})

    assert resposta.status_code == 404
    assert _status_venda(venda_id) == "Concluído"
