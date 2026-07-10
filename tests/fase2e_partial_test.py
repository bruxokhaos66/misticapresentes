import sqlite3
from datetime import datetime

import database.connection as connection
import config
from database.migrations import init_db
from reports.vendas_report import vendas_por_filtro
from services.dashboard_service import obter_kpis_dashboard


def setup_temp_db(tmp_path, monkeypatch):
    db_path = tmp_path / "fase2e_test.db"
    monkeypatch.setattr(connection, "DB_PATH", str(db_path))
    monkeypatch.setattr(config, "DB_PATH", str(db_path))
    init_db()
    conn = sqlite3.connect(str(db_path))
    cur = conn.cursor()
    # Usa o timestamp completo de "agora" (não só a data) para que a venda
    # caia no período operacional atual mesmo perto da virada das 23h (ver
    # services/dia_operacional_service.py) — um data_iso truncado à meia-noite
    # podia cair no dia operacional anterior e deixar o teste instável
    # dependendo do horário em que rodasse.
    agora = datetime.now()
    hoje_iso = agora.strftime("%Y-%m-%d %H:%M:%S")
    today_br = agora.strftime("%d/%m/%Y")
    cur.execute(
        "INSERT INTO vendas (cliente, data_venda, data_iso, subtotal, desconto, taxa, total_final, forma_pagamento, vendedor, status) VALUES (?,?,?,?,?,?,?,?,?,?)",
        ("Cliente A", f"{today_br} 10:00", hoje_iso, 100.0, 0.0, 0.0, 100.0, "Dinheiro", "Vendedor", "Concluído"),
    )
    cur.execute(
        "INSERT INTO vendas (cliente, data_venda, data_iso, subtotal, desconto, taxa, total_final, forma_pagamento, vendedor, status) VALUES (?,?,?,?,?,?,?,?,?,?)",
        ("Cliente B", "01/01/2024 10:00", None, 50.0, 0.0, 0.0, 50.0, "Dinheiro", "Vendedor", "Cancelado"),
    )
    conn.commit()
    conn.close()
    return str(db_path)


def test_vendas_por_filtro_usa_data_iso_quando_existir_e_exclui_canceladas(tmp_path, monkeypatch):
    setup_temp_db(tmp_path, monkeypatch)
    filtro = datetime.now().strftime("/%m/%Y")
    resultado = vendas_por_filtro(filtro)
    assert resultado["total"] == 100.0
    assert len(resultado["vendas"]) == 1
    assert resultado["vendas"][0][2] == "Cliente A"


def test_dashboard_exclui_vendas_canceladas(tmp_path, monkeypatch):
    setup_temp_db(tmp_path, monkeypatch)
    kpis = obter_kpis_dashboard()
    assert kpis["tot_hoje"] == 100.0
    assert kpis["tot_mes"] == 100.0
