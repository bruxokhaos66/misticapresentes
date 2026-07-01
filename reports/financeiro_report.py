import calendar
from datetime import datetime

from database import query_db
from reports.vendas_report import _custo_vendas


def contas_pagas_periodo(mes, ano):
    return query_db(
        "SELECT valor, categoria FROM contas_a_pagar WHERE status='Pago' AND data_vencimento LIKE ?",
        (f"%/{mes}/{ano}%",),
    )


def despesas_por_categoria(mes, ano):
    despesas = {"Aluguel": 0.0, "Internet": 0.0, "Energia": 0.0, "Compras": 0.0, "Marketing": 0.0, "Outros": 0.0}
    for valor, categoria in contas_pagas_periodo(mes, ano):
        if categoria in despesas:
            despesas[categoria] += float(valor or 0.0)
        else:
            despesas["Outros"] += float(valor or 0.0)
    return despesas


def dre_periodo(mes, ano):
    filtro = f"/{mes}/{ano}"
    vendas = query_db(
        """
        SELECT id, total_final
        FROM vendas
        WHERE COALESCE(status,'Concluído') != 'Cancelado'
          AND data_venda LIKE ?
        """,
        (f"%{filtro}%",),
    )
    receitas = sum(float(v[1] or 0.0) for v in vendas)
    custos = _custo_vendas([v[0] for v in vendas])
    lucro_bruto = receitas - custos
    despesas = despesas_por_categoria(mes, ano)
    total_despesas = sum(despesas.values())
    lucro_liquido = lucro_bruto - total_despesas

    dia_atual = datetime.now().day
    dias_no_mes = calendar.monthrange(int(ano), int(mes))[1]
    if str(mes) != datetime.now().strftime("%m") or str(ano) != datetime.now().strftime("%Y"):
        dia_atual = dias_no_mes
    faturamento_previsto = (receitas / dia_atual) * dias_no_mes if dia_atual > 0 else receitas
    media_diaria = receitas / dia_atual if dia_atual > 0 else 0.0

    return {
        "receitas": receitas,
        "custos": custos,
        "lucro_bruto": lucro_bruto,
        "despesas": despesas,
        "total_despesas": total_despesas,
        "lucro_liquido": lucro_liquido,
        "dias_no_mes": dias_no_mes,
        "dias_avaliados": dia_atual,
        "faturamento_previsto": faturamento_previsto,
        "media_diaria": media_diaria,
    }


def contas_pendentes_resumo():
    res = query_db("SELECT COUNT(*), COALESCE(SUM(valor),0) FROM contas_a_pagar WHERE status='Pendente'")
    return res[0] if res else (0, 0.0)


def contas_para_alerta():
    return query_db(
        """
        SELECT descricao, valor, data_vencimento
        FROM contas_a_pagar
        WHERE COALESCE(status,'Pendente') NOT IN ('Pago','Excluido')
        ORDER BY id DESC
        LIMIT 50
        """
    )
