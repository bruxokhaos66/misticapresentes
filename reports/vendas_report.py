from datetime import datetime

from database import query_db
from services.dia_operacional_service import intervalo_vendas_hoje


def _custo_vendas(vendas_ids):
    if not vendas_ids:
        return 0.0
    placeholder = ",".join("?" for _ in vendas_ids)
    res = query_db(
        f"SELECT SUM(quantidade * custo_unitario) FROM vendas_itens WHERE venda_id IN ({placeholder})",
        tuple(vendas_ids),
    )
    return float(res[0][0] or 0.0) if res else 0.0


def _filtro_data_sql(coluna='data_venda'):
    return f"(COALESCE({coluna}, '') LIKE ? OR COALESCE(data_iso, '') LIKE ?)"


def _filtro_intervalo_iso_sql():
    return "(datetime(data_iso) >= datetime(?) AND datetime(data_iso) < datetime(?))"


def vendas_por_filtro(filtro):
    vendas = query_db(
        f"""
        SELECT id, data_venda, cliente, total_final, vendedor
        FROM vendas
        WHERE COALESCE(status,'Concluído') != 'Cancelado'
          AND {_filtro_data_sql()}
        ORDER BY id DESC
        """,
        (f"%{filtro}%", f"%{filtro}%"),
    )
    total = sum(float(v[3] or 0) for v in vendas)
    ids = [v[0] for v in vendas]
    custo = _custo_vendas(ids)
    return {"vendas": vendas, "total": total, "custo": custo, "lucro": total - custo}


def lucro_liquido_periodo(mes, ano):
    filtro = f"/{mes}/{ano}"
    vendas = query_db(
        f"""
        SELECT id, total_final, COALESCE(taxa,0), COALESCE(desconto,0)
        FROM vendas
        WHERE COALESCE(status,'Concluído') != 'Cancelado'
          AND {_filtro_data_sql()}
        """,
        (f"%{filtro}%", f"%{filtro}%"),
    )
    receitas = sum(float(v[1] or 0) for v in vendas)
    taxas = sum(float(v[2] or 0) for v in vendas)
    descontos = sum(float(v[3] or 0) for v in vendas)
    custos = _custo_vendas([v[0] for v in vendas])
    despesas_res = query_db(
        "SELECT SUM(valor) FROM contas_a_pagar WHERE status='Pago' AND data_vencimento LIKE ?",
        (f"%/{mes}/{ano}%",),
    )
    despesas = float(despesas_res[0][0] or 0.0) if despesas_res else 0.0
    lucro = receitas - custos - despesas
    return {"receitas": receitas, "taxas": taxas, "descontos": descontos, "custos": custos, "despesas": despesas, "lucro": lucro}


def produtos_mais_vendidos(limite=15):
    return query_db(
        """
        SELECT vi.codigo_p, vi.nome_p, SUM(vi.quantidade), SUM(vi.valor_total)
        FROM vendas_itens vi
        JOIN vendas v ON vi.venda_id = v.id
        WHERE COALESCE(v.status,'Concluído') != 'Cancelado'
        GROUP BY vi.codigo_p, vi.nome_p
        ORDER BY SUM(vi.quantidade) DESC
        LIMIT ?
        """,
        (int(limite),),
    )


def ranking_clientes(limite=10):
    return query_db(
        """
        SELECT cliente, COUNT(*), SUM(total_final)
        FROM vendas
        WHERE COALESCE(status,'Concluído') != 'Cancelado'
          AND cliente != 'Consumidor Final'
        GROUP BY cliente
        ORDER BY SUM(total_final) DESC
        LIMIT ?
        """,
        (int(limite),),
    )


def resumo_vendas_hoje_operacional():
    inicio, fim, dia_operacional = intervalo_vendas_hoje()
    res = query_db(
        f"""
        SELECT COUNT(*), COALESCE(SUM(total_final),0)
        FROM vendas
        WHERE COALESCE(status,'Concluído') != 'Cancelado'
          AND (
              COALESCE(dia_operacional,'') = ?
              OR {_filtro_intervalo_iso_sql()}
          )
        """,
        (dia_operacional, inicio, fim),
    )
    return res[0] if res else (0, 0.0)


def resumo_vendas_periodo(filtro):
    hoje = datetime.now().strftime("%d/%m/%Y")
    if str(filtro or "") == hoje:
        return resumo_vendas_hoje_operacional()
    res = query_db(
        f"""
        SELECT COUNT(*), COALESCE(SUM(total_final),0)
        FROM vendas
        WHERE COALESCE(status,'Concluído') != 'Cancelado'
          AND {_filtro_data_sql()}
        """,
        (f"%{filtro}%", f"%{filtro}%"),
    )
    return res[0] if res else (0, 0.0)


def lucro_bruto_itens_periodo(filtro):
    res = query_db(
        f"""
        SELECT COALESCE(SUM(vi.quantidade * (vi.valor_unitario - vi.custo_unitario)),0),
               COALESCE(SUM(vi.valor_total),0),
               COALESCE(SUM(vi.quantidade * vi.custo_unitario),0)
        FROM vendas_itens vi
        JOIN vendas v ON vi.venda_id = v.id
        WHERE COALESCE(v.status,'Concluído') != 'Cancelado'
          AND {_filtro_data_sql('v.data_venda')}
        """,
        (f"%{filtro}%", f"%{filtro}%"),
    )
    return res[0] if res else (0.0, 0.0, 0.0)


def produto_campeao():
    res = query_db(
        """
        SELECT vi.nome_p, SUM(vi.quantidade), SUM(vi.valor_total)
        FROM vendas_itens vi
        JOIN vendas v ON vi.venda_id = v.id
        WHERE COALESCE(v.status,'Concluído') != 'Cancelado'
        GROUP BY vi.codigo_p, vi.nome_p
        ORDER BY SUM(vi.quantidade) DESC
        LIMIT 1
        """
    )
    return res[0] if res else None


def buscar_venda_resumo(venda_id):
    res = query_db(
        "SELECT id, data_venda, cliente, total_final, forma_pagamento, status FROM vendas WHERE id=?",
        (venda_id,),
    )
    return res[0] if res else None


def vendas_recentes(limite=5):
    return query_db("SELECT id, data_venda, cliente, total_final FROM vendas ORDER BY id DESC LIMIT ?", (int(limite),))


def buscar_venda_cupom(venda_id):
    res = query_db(
        """
        SELECT id, data_venda, cliente, subtotal, desconto, taxa, total_final, forma_pagamento, vendedor
        FROM vendas
        WHERE id=?
        """,
        (venda_id,),
    )
    return res[0] if res else None


def itens_venda(venda_id):
    return query_db("SELECT nome_p, quantidade, valor_total FROM vendas_itens WHERE venda_id=?", (venda_id,))


def total_vendido_produto(codigo_p):
    res = query_db(
        """
        SELECT COALESCE(SUM(vi.quantidade),0)
        FROM vendas_itens vi
        JOIN vendas v ON vi.venda_id = v.id
        WHERE vi.codigo_p = ?
          AND COALESCE(v.status,'Concluído') != 'Cancelado'
        """,
        (codigo_p,),
    )
    return int(res[0][0] or 0) if res else 0
