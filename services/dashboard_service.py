import json
import os
from datetime import datetime

from config import DOCS_PATH
from database import query_db
from reports.date_filters import intervalo_dia, intervalo_mes

DASHBOARD_STATE_PATH = os.path.join(DOCS_PATH, "mistica_dashboard_state.json")


def _filtro_data_iso_dia_sql(coluna="data_iso"):
    """Filtro tolerante para datas ISO salvas como YYYY-MM-DD ou YYYY-MM-DD HH:MM:SS."""
    return f"substr(COALESCE({coluna}, ''), 1, 10) >= ? AND substr(COALESCE({coluna}, ''), 1, 10) < ?"


def _filtro_data_iso_timestamp_sql(coluna="data_iso"):
    """Compara data_iso completa; datas sem hora viram 00:00:00."""
    return f"datetime(CASE WHEN length(COALESCE({coluna}, '')) = 10 THEN {coluna} || ' 00:00:00' ELSE {coluna} END) >= datetime(?) AND datetime(CASE WHEN length(COALESCE({coluna}, '')) = 10 THEN {coluna} || ' 00:00:00' ELSE {coluna} END) < datetime(?)"


def _ler_estado_dashboard():
    try:
        if os.path.exists(DASHBOARD_STATE_PATH):
            with open(DASHBOARD_STATE_PATH, "r", encoding="utf-8") as f:
                return json.load(f) or {}
    except Exception:
        pass
    return {}


def registrar_fechamento_diario_dashboard(usuario="Sistema"):
    """Marca o horário de fechamento do dia para o card VENDAS HOJE.

    Não apaga vendas. Apenas faz o Dashboard somar VENDAS HOJE a partir deste momento.
    O card VENDAS MÊS continua considerando o mês inteiro.
    """
    estado = _ler_estado_dashboard()
    agora = datetime.now()
    estado["fechamento_diario_iso"] = agora.strftime("%Y-%m-%d %H:%M:%S")
    estado["fechamento_diario_dia"] = agora.strftime("%Y-%m-%d")
    estado["fechamento_diario_usuario"] = str(usuario or "Sistema")
    os.makedirs(os.path.dirname(DASHBOARD_STATE_PATH), exist_ok=True)
    with open(DASHBOARD_STATE_PATH, "w", encoding="utf-8") as f:
        json.dump(estado, f, ensure_ascii=False, indent=2)
    return estado["fechamento_diario_iso"]


def _inicio_vendas_hoje():
    ini_hoje, fim_hoje = intervalo_dia(datetime.now())
    estado = _ler_estado_dashboard()
    fechamento = str(estado.get("fechamento_diario_iso") or "")
    dia_fechamento = str(estado.get("fechamento_diario_dia") or "")
    hoje = datetime.now().strftime("%Y-%m-%d")
    if fechamento and dia_fechamento == hoje:
        return fechamento, fim_hoje + " 23:59:59" if len(fim_hoje) == 10 else fim_hoje
    return ini_hoje + " 00:00:00" if len(ini_hoje) == 10 else ini_hoje, fim_hoje + " 00:00:00" if len(fim_hoje) == 10 else fim_hoje


def obter_kpis_dashboard():
    ini_mes, fim_mes = intervalo_mes()
    ini_mes_dia, fim_mes_dia = ini_mes[:10], fim_mes[:10]
    ini_hoje_ts, fim_hoje_ts = _inicio_vendas_hoje()

    tot_hoje = query_db(
        f"SELECT SUM(total_final) FROM vendas WHERE COALESCE(status,'Concluído') != 'Cancelado' AND {_filtro_data_iso_timestamp_sql()}",
        (ini_hoje_ts, fim_hoje_ts),
    )[0][0] or 0.0
    tot_mes = query_db(
        f"SELECT SUM(total_final) FROM vendas WHERE COALESCE(status,'Concluído') != 'Cancelado' AND {_filtro_data_iso_dia_sql()}",
        (ini_mes_dia, fim_mes_dia),
    )[0][0] or 0.0
    qtd_prod = query_db("SELECT COUNT(*) FROM produtos WHERE COALESCE(ativo,1)=1")[0][0] or 0
    qtd_cli = query_db("SELECT COUNT(*) FROM clientes WHERE COALESCE(ativo,1)=1")[0][0] or 0
    tot_estoque = query_db("SELECT SUM(quantidade) FROM produtos WHERE COALESCE(ativo,1)=1")[0][0] or 0
    return {
        "tot_hoje": tot_hoje,
        "tot_mes": tot_mes,
        "qtd_prod": qtd_prod,
        "qtd_cli": qtd_cli,
        "tot_estoque": tot_estoque,
    }
