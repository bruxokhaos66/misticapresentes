from datetime import datetime

from database import query_db
from reports.date_filters import filtro_data_iso_sql, intervalo_dia, intervalo_mes


def obter_kpis_dashboard():
    ini_hoje, fim_hoje = intervalo_dia(datetime.now())
    ini_mes, fim_mes = intervalo_mes()
    tot_hoje = query_db(
        f"SELECT SUM(total_final) FROM vendas WHERE COALESCE(status,'Concluído') != 'Cancelado' AND {filtro_data_iso_sql()}",
        (ini_hoje, fim_hoje),
    )[0][0] or 0.0
    tot_mes = query_db(
        f"SELECT SUM(total_final) FROM vendas WHERE COALESCE(status,'Concluído') != 'Cancelado' AND {filtro_data_iso_sql()}",
        (ini_mes, fim_mes),
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
