from datetime import datetime

import pytest

import database
from database import query_db
from services.audit_log_service import listar_acoes_logs, listar_logs_auditoria, listar_usuarios_logs, registrar_log_auditoria, resumo_logs_auditoria
from services.period_maintenance_service import listar_lancamentos_caixa_periodo, listar_vendas_periodo, zerar_vendas_e_caixa_periodo


@pytest.fixture()
def banco_limpo_periodo(tmp_path, monkeypatch):
    db_path = tmp_path / "periodo_teste.db"
    backup_dir = tmp_path / "backups"
    monkeypatch.setattr(database, "DB_PATH", str(db_path))
    monkeypatch.setattr(database, "BACKUP_DIR", str(backup_dir))
    database.init_db()
    return db_path


def usuario_adm():
    return {"nome": "Administrador Teste", "perfil": "adm", "login": "admin"}


def usuario_vendedor():
    return {"nome": "Vendedor Teste", "perfil": "vendedor", "login": "vend"}


def test_auditoria_lista_logs_de_usuarios_e_acoes(banco_limpo_periodo):
    registrar_log_auditoria("Vendedor Teste", "Venda", "Venda registrada")
    registrar_log_auditoria("Administrador Teste", "Manutenção", "Ajuste administrativo")

    usuarios = listar_usuarios_logs(usuario_adm())
    acoes = listar_acoes_logs(usuario_adm())
    logs = listar_logs_auditoria(usuario_adm(), termo="Venda")
    resumo = resumo_logs_auditoria(usuario_adm())

    assert "Vendedor Teste" in usuarios
    assert "Venda" in acoes
    assert len(logs) == 1
    assert resumo["total"] >= 2

    with pytest.raises(PermissionError):
        listar_logs_auditoria(usuario_vendedor())


def test_manutencao_periodo_lista_e_zera_vendas_e_caixa(banco_limpo_periodo):
    agora = datetime.now()
    data_venda = agora.strftime("%d/%m/%Y %H:%M")
    data_iso = agora.strftime("%Y-%m-%d %H:%M:%S")

    query_db(
        "INSERT INTO vendas (cliente, data_venda, data_iso, subtotal, desconto, taxa, total_final, forma_pagamento, vendedor, status) VALUES (?,?,?,?,?,?,?,?,?,?)",
        ("Cliente Teste", data_venda, data_iso, 100.0, 0.0, 0.0, 100.0, "Dinheiro", "Vendedor Teste", "Concluído"),
        commit=True,
    )
    query_db(
        "INSERT INTO fluxo_caixa (tipo, descricao, valor, data_hora, data_iso, caixa_id, forma_pagamento) VALUES (?,?,?,?,?,?,?)",
        ("Entrada", "Venda teste", 100.0, data_venda, data_iso, 1, "Dinheiro"),
        commit=True,
    )

    vendas = listar_vendas_periodo(usuario_adm(), "dia", agora.day, agora.month, agora.year)
    caixa = listar_lancamentos_caixa_periodo(usuario_adm(), "dia", agora.day, agora.month, agora.year)

    assert vendas["total_ativas"] == 100.0
    assert caixa["total"] == 100.0

    res = zerar_vendas_e_caixa_periodo(usuario_adm(), "dia", agora.day, agora.month, agora.year, "Teste automatizado")
    assert res["vendas_canceladas"] == 1
    assert res["lancamentos_removidos"] == 1

    status = query_db("SELECT status FROM vendas LIMIT 1")[0][0]
    qtd_fluxo = query_db("SELECT COUNT(*) FROM fluxo_caixa")[0][0]
    assert status == "Cancelado"
    assert qtd_fluxo == 0

    logs = query_db("SELECT COUNT(*) FROM logs WHERE acao LIKE 'Manutenção - Zerar%'")[0][0]
    assert logs == 1
