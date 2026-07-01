from datetime import datetime

from database import query_db


def obter_kpis_dashboard():
    hoje = datetime.now().strftime("%d/%m/%Y")
    mes = datetime.now().strftime("/%m/%Y")
    tot_hoje = query_db(
        "SELECT SUM(total_final) FROM vendas WHERE COALESCE(status,'Concluído') != 'Cancelado' AND data_venda LIKE ?",
        (f"%{hoje}%",),
    )[0][0] or 0.0
    tot_mes = query_db(
        "SELECT SUM(total_final) FROM vendas WHERE COALESCE(status,'Concluído') != 'Cancelado' AND data_venda LIKE ?",
        (f"%{mes}%",),
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
