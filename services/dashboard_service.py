from datetime import datetime

from database import query_db
from reports.date_filters import intervalo_dia, intervalo_mes


def _filtro_data_iso_dia_sql(coluna="data_iso"):
    """Filtro tolerante para datas ISO salvas como YYYY-MM-DD ou YYYY-MM-DD HH:MM:SS."""
    return f"substr(COALESCE({coluna}, ''), 1, 10) >= ? AND substr(COALESCE({coluna}, ''), 1, 10) < ?"


def obter_kpis_dashboard():
    ini_hoje, fim_hoje = intervalo_dia(datetime.now())
    ini_mes, fim_mes = intervalo_mes()
    ini_hoje_dia, fim_hoje_dia = ini_hoje[:10], fim_hoje[:10]
    ini_mes_dia, fim_mes_dia = ini_mes[:10], fim_mes[:10]

    tot_hoje = query_db(
        f"SELECT SUM(total_final) FROM vendas WHERE COALESCE(status,'Concluído') != 'Cancelado' AND {_filtro_data_iso_dia_sql()}",
        (ini_hoje_dia, fim_hoje_dia),
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
