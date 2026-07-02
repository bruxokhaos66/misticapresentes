import sqlite3
from datetime import datetime

import pytest

import database
from database import query_db
from services.caixa_service import abrir_caixa, marcar_conta_paga, salvar_conta
from services.critical_action_service import confirmar_acao, solicitar_confirmacao
from services.demo_service import criar_modo_demonstracao, remover_modo_demonstracao
from services.login_audit_service import bloqueio_ativo, registrar_falha_login, registrar_sucesso_login
from services.maintenance_service import PermissaoNegada, diagnosticar_caixa, diagnosticar_estoque, diagnosticar_financeiro, reiniciar_area_segura, reiniciar_dashboard
from services.password_policy import validar_forca_senha
from services.produto_service import cadastrar_produto_service
from services.system_diagnostics_service import backup_manual, diagnosticar_banco
from services.venda_service import calcular_total_venda, cancelar_venda_service, registrar_venda_service


@pytest.fixture()
def banco_limpo(tmp_path, monkeypatch):
    db_path = tmp_path / "mistica_teste.db"
    backup_dir = tmp_path / "backups"
    monkeypatch.setattr(database, "DB_PATH", str(db_path))
    monkeypatch.setattr(database, "BACKUP_DIR", str(backup_dir))

    import services.system_diagnostics_service as diag_service
    monkeypatch.setattr(diag_service, "DB_PATH", str(db_path))
    monkeypatch.setattr(diag_service, "BACKUP_DIR", str(backup_dir), raising=False)

    import services.maintenance_service as manut_service
    monkeypatch.setattr(manut_service, "DASHBOARD_MSG_PATH", str(tmp_path / "dashboard_msg.txt"))

    database.init_db()
    return db_path


def usuario_adm():
    return {"nome": "Administrador Teste", "perfil": "adm", "login": "admin"}


def usuario_vendedor():
    return {"nome": "Vendedor Teste", "perfil": "vendedor", "login": "vend"}


def test_init_db_cria_tabelas_obrigatorias(banco_limpo):
    conn = sqlite3.connect(banco_limpo)
    try:
        tabelas = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
    finally:
        conn.close()

    obrigatorias = {
        "usuarios",
        "login_tentativas",
        "logs",
        "categorias",
        "produtos",
        "clientes",
        "fornecedores",
        "vendas",
        "vendas_itens",
        "movimentacao_estoque",
        "inventario_estoque",
        "caixa_diario",
        "fluxo_caixa",
        "contas_a_pagar",
        "historico_precos",
        "isis_logs",
    }
    assert obrigatorias.issubset(tabelas)


def test_venda_baixa_estoque_e_cancelamento_devolve_estoque(banco_limpo):
    codigo = cadastrar_produto_service(
        nome="Incenso Teste",
        custo=2.0,
        lucro=100.0,
        preco=4.0,
        quantidade=10,
        estoque_minimo=2,
        categoria="Incensos",
        usuario="Teste",
    )
    caixa_id = abrir_caixa(100.0, "Teste")
    carrinho = [{"id": codigo, "n": "Incenso Teste", "q": 3, "p": 4.0, "t": 12.0}]
    calculo = calcular_total_venda(carrinho, 0, "Dinheiro")
    venda_id = registrar_venda_service(
        carrinho,
        "Consumidor Final",
        datetime.now().strftime("%d/%m/%Y %H:%M"),
        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        calculo,
        "Dinheiro",
        "Teste",
        caixa_id,
    )

    estoque_pos_venda = query_db("SELECT quantidade FROM produtos WHERE codigo_p=?", (codigo,))[0][0]
    assert estoque_pos_venda == 7

    cancelar_venda_service(venda_id, "Teste", caixa_id)
    estoque_pos_cancelamento = query_db("SELECT quantidade FROM produtos WHERE codigo_p=?", (codigo,))[0][0]
    status = query_db("SELECT status FROM vendas WHERE id=?", (venda_id,))[0][0]
    assert estoque_pos_cancelamento == 10
    assert status == "Cancelado"


def test_pagamento_de_conta_lanca_saida_no_fluxo(banco_limpo):
    caixa_id = abrir_caixa(200.0, "Teste")
    salvar_conta("Compra teste", 50.0, "10/07/2026", "Compras")
    conta_id = query_db("SELECT id FROM contas_a_pagar WHERE descricao=?", ("Compra teste",))[0][0]

    marcar_conta_paga(conta_id, caixa_id)

    status = query_db("SELECT status FROM contas_a_pagar WHERE id=?", (conta_id,))[0][0]
    fluxo = query_db("SELECT tipo, valor FROM fluxo_caixa WHERE caixa_id=? AND descricao LIKE ?", (caixa_id, "%Compra teste%"))
    assert status == "Pago"
    assert fluxo == [("Saida", 50.0)]


def test_debito_usa_taxa_percentual_de_1_5_porcento():
    carrinho = [{"t": 100.0}]
    calculo = calcular_total_venda(carrinho, 0, "Debito")
    assert calculo["tx"] == pytest.approx(1.5)
    assert calculo["tot"] == pytest.approx(101.5)


def test_politica_de_senha_recusa_fraca_e_aceita_forte():
    assert validar_forca_senha("1234")[0] is False
    assert validar_forca_senha("Mistica2026")[0] is True


def test_auditoria_login_bloqueia_apos_falhas(banco_limpo):
    login = "operador_teste"
    for _ in range(5):
        registrar_falha_login(login)
    assert bloqueio_ativo(login) is not None
    registrar_sucesso_login(login)
    total = query_db("SELECT COUNT(*) FROM login_tentativas WHERE login=?", (login,))[0][0]
    assert total == 6


def test_diagnostico_e_backup_manual(banco_limpo):
    diag = diagnosticar_banco()
    assert diag["ok"] is True
    caminho = backup_manual()
    assert caminho.endswith(".db")


def test_modo_demonstracao_cria_e_remove_dados(banco_limpo):
    criado = criar_modo_demonstracao()
    assert criado["produtos_demo"] == 3
    produtos = query_db("SELECT COUNT(*) FROM produtos WHERE codigo_p LIKE 'DEMO-%'")[0][0]
    assert produtos == 3
    removido = remover_modo_demonstracao()
    assert removido["produtos_removidos"] == 3
    produtos_final = query_db("SELECT COUNT(*) FROM produtos WHERE codigo_p LIKE 'DEMO-%'")[0][0]
    assert produtos_final == 0


def test_confirmacao_de_acao_critica():
    pendente = solicitar_confirmacao("cancelar_venda", "Venda 10", "Teste")
    assert pendente["confirmado"] is False
    ok, msg = confirmar_acao(pendente["token"], "cancelar_venda")
    assert ok is True
    assert "confirmada" in msg.lower()


def test_manutencao_dashboard_apenas_adm_e_com_log(banco_limpo):
    with pytest.raises(PermissaoNegada):
        reiniciar_dashboard(usuario_vendedor())

    resultado = reiniciar_dashboard(usuario_adm())
    assert resultado["ok"] is True
    logs = query_db("SELECT usuario, acao, detalhes FROM logs WHERE acao LIKE 'Manutenção%' ORDER BY id DESC LIMIT 1")
    assert logs[0][0] == "Administrador Teste"
    assert "Dashboard" in logs[0][1]


def test_diagnosticos_manutencao_por_area_apenas_adm(banco_limpo):
    with pytest.raises(PermissaoNegada):
        diagnosticar_caixa(usuario_vendedor())
    assert diagnosticar_caixa(usuario_adm())["area"] == "caixa"
    assert diagnosticar_estoque(usuario_adm())["area"] == "estoque"
    assert diagnosticar_financeiro(usuario_adm())["area"] == "financeiro"

    logs = query_db("SELECT COUNT(*) FROM logs WHERE acao LIKE 'Manutenção%'")[0][0]
    assert logs >= 3


def test_reiniciar_area_geral_cria_backup_e_log(banco_limpo):
    resultado = reiniciar_area_segura("geral", usuario_adm())
    assert resultado["area"] == "geral"
    assert resultado["backup"].endswith(".db")
    logs = query_db("SELECT COUNT(*) FROM logs WHERE acao LIKE 'Manutenção%'")[0][0]
    assert logs >= 4
