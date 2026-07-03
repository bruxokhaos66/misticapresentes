from datetime import datetime, time, timedelta

from database import query_db
from services.dia_operacional_service import intervalo_vendas_hoje

META_VENDEDOR_PERIODO = 1500.00
BONUS_META_VENDEDOR = 100.00


def periodo_meta_atual(agora=None):
    """Período de meta: segunda-feira 00:00 até sábado 12:00."""
    agora = agora or datetime.now()
    segunda = agora.date() - timedelta(days=agora.weekday())
    inicio = datetime.combine(segunda, time.min)
    fim = datetime.combine(segunda + timedelta(days=5), time(12, 0, 0))
    status = "em_andamento" if inicio <= agora < fim else "encerrado"
    return inicio, fim, status


def vendas_dia_operacional_detalhadas(limite=200):
    inicio, fim, dia = intervalo_vendas_hoje()
    return query_db(
        """
        SELECT
            v.id,
            COALESCE(v.data_venda,''),
            COALESCE(v.data_iso,''),
            COALESCE(v.vendedor,'Sem vendedor'),
            COALESCE(vi.nome_p,'Produto não identificado'),
            COALESCE(vi.quantidade,0),
            COALESCE(vi.valor_total,0),
            COALESCE(v.total_final,0),
            COALESCE(v.forma_pagamento,''),
            COALESCE(v.dia_operacional,'')
        FROM vendas v
        JOIN vendas_itens vi ON vi.venda_id = v.id
        WHERE COALESCE(v.status,'Concluído') != 'Cancelado'
          AND (
                COALESCE(v.dia_operacional,'') = ?
                OR (datetime(v.data_iso) >= datetime(?) AND datetime(v.data_iso) < datetime(?))
          )
        ORDER BY v.id DESC, vi.id DESC
        LIMIT ?
        """,
        (dia, inicio, fim, int(limite)),
    )


def resumo_meta_vendedores():
    inicio, fim, status = periodo_meta_atual()
    linhas = query_db(
        """
        SELECT
            COALESCE(vendedor,'Sem vendedor') AS vendedor,
            COUNT(*) AS qtd_vendas,
            COALESCE(SUM(total_final),0) AS total
        FROM vendas
        WHERE COALESCE(status,'Concluído') != 'Cancelado'
          AND datetime(data_iso) >= datetime(?)
          AND datetime(data_iso) < datetime(?)
        GROUP BY COALESCE(vendedor,'Sem vendedor')
        ORDER BY total DESC
        """,
        (inicio.strftime("%Y-%m-%d %H:%M:%S"), fim.strftime("%Y-%m-%d %H:%M:%S")),
    )
    resumo = []
    for vendedor, qtd, total in linhas:
        total = float(total or 0.0)
        falta = max(0.0, META_VENDEDOR_PERIODO - total)
        bateu = total >= META_VENDEDOR_PERIODO
        resumo.append({
            "vendedor": vendedor,
            "qtd_vendas": int(qtd or 0),
            "total": total,
            "meta": META_VENDEDOR_PERIODO,
            "falta": falta,
            "bateu_meta": bateu,
            "bonus": BONUS_META_VENDEDOR if bateu else 0.0,
            "status_periodo": status,
            "inicio": inicio.strftime("%d/%m/%Y %H:%M"),
            "fim": fim.strftime("%d/%m/%Y %H:%M"),
        })
    return resumo


def total_mes_vendedor(vendedor):
    mes = datetime.now().strftime("/%m/%Y")
    res = query_db(
        """
        SELECT COUNT(*), COALESCE(SUM(total_final),0)
        FROM vendas
        WHERE COALESCE(status,'Concluído') != 'Cancelado'
          AND COALESCE(vendedor,'') = ?
          AND (COALESCE(data_venda,'') LIKE ? OR COALESCE(data_iso,'') LIKE ?)
        """,
        (str(vendedor or ""), f"%{mes}%", f"%{mes}%"),
    )
    return res[0] if res else (0, 0.0)


def resumo_vendedor_atual(vendedor):
    metas = resumo_meta_vendedores()
    atual = next((m for m in metas if m["vendedor"] == vendedor), None)
    qtd_mes, total_mes = total_mes_vendedor(vendedor)
    if not atual:
        inicio, fim, status = periodo_meta_atual()
        atual = {
            "vendedor": vendedor,
            "qtd_vendas": 0,
            "total": 0.0,
            "meta": META_VENDEDOR_PERIODO,
            "falta": META_VENDEDOR_PERIODO,
            "bateu_meta": False,
            "bonus": 0.0,
            "status_periodo": status,
            "inicio": inicio.strftime("%d/%m/%Y %H:%M"),
            "fim": fim.strftime("%d/%m/%Y %H:%M"),
        }
    atual["qtd_mes"] = int(qtd_mes or 0)
    atual["total_mes"] = float(total_mes or 0.0)
    return atual
