from database import query_db


def produtos_mais_vendidos(limite=15):
    """Ranking de produtos considerando apenas vendas validas."""
    return query_db(
        """
        SELECT vi.codigo_p, vi.nome_p, SUM(vi.quantidade), SUM(vi.valor_total)
        FROM vendas_itens vi
        JOIN vendas v ON vi.venda_id = v.id
        WHERE COALESCE(v.status,'Concluido') != 'Cancelado'
        GROUP BY vi.codigo_p, vi.nome_p
        ORDER BY SUM(vi.quantidade) DESC
        LIMIT ?
        """,
        (int(limite),),
    )
