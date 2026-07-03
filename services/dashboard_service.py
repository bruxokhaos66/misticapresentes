from datetime import datetime

from database import query_db
from services.dia_operacional_service import intervalo_vendas_hoje


def _filtro_data_sql(coluna='data_venda'):
    return f"(COALESCE({coluna}, '') LIKE ? OR COALESCE(data_iso, '') LIKE ?)"


def _filtro_intervalo_iso_sql():
    return "(datetime(data_iso) >= datetime(?) AND datetime(data_iso) < datetime(?))"


def obter_kpis_dashboard():
    inicio_hoje, fim_hoje, dia_operacional = intervalo_vendas_hoje()
    mes = datetime.now().strftime("/%m/%Y")
    tot_hoje = query_db(
        f"""
        SELECT SUM(total_final)
        FROM vendas
        WHERE COALESCE(status,'Concluído') != 'Cancelado'
          AND (
              COALESCE(dia_operacional,'') = ?
              OR {_filtro_intervalo_iso_sql()}
          )
        """,
        (dia_operacional, inicio_hoje, fim_hoje),
    )[0][0] or 0.0
    tot_mes = query_db(
        f"SELECT SUM(total_final) FROM vendas WHERE COALESCE(status,'Concluído') != 'Cancelado' AND {_filtro_data_sql()}",
        (f"%{mes}%", f"%{mes}%"),
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
        "dia_operacional": dia_operacional,
        "inicio_vendas_hoje": inicio_hoje,
        "fim_vendas_hoje": fim_hoje,
    }
