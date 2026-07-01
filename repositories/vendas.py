from database import query_db


def inserir_venda_cursor(cur, cliente, data_venda, data_iso, subtotal, desconto, taxa, total_final, forma_pagamento, vendedor, status="Concluído"):
    cur.execute(
        """
        INSERT INTO vendas
        (cliente, data_venda, data_iso, subtotal, desconto, taxa, total_final, forma_pagamento, vendedor, status)
        VALUES (?,?,?,?,?,?,?,?,?,?)
        """,
        (cliente, data_venda, data_iso, subtotal, desconto, taxa, total_final, forma_pagamento, vendedor, status),
    )
    return cur.lastrowid


def inserir_item_cursor(cur, venda_id, codigo_p, nome_p, quantidade, custo_unitario, valor_unitario, valor_total):
    cur.execute(
        """
        INSERT INTO vendas_itens
        (venda_id, codigo_p, nome_p, quantidade, custo_unitario, valor_unitario, valor_total)
        VALUES (?,?,?,?,?,?,?)
        """,
        (venda_id, codigo_p, nome_p, int(quantidade), custo_unitario, valor_unitario, valor_total),
    )


def inserir_fluxo_cursor(cur, tipo, descricao, valor, data_hora, data_iso, caixa_id, forma_pagamento=None):
    cur.execute(
        """
        INSERT INTO fluxo_caixa (tipo, descricao, valor, data_hora, data_iso, caixa_id, forma_pagamento)
        VALUES (?,?,?,?,?,?,?)
        """,
        (tipo, descricao, valor, data_hora, data_iso, caixa_id, forma_pagamento),
    )


def obter_status_total(venda_id):
    res = query_db("SELECT status, total_final FROM vendas WHERE id=?", (venda_id,))
    return res[0] if res else None


def listar_itens_cursor(cur, venda_id):
    return cur.execute(
        "SELECT codigo_p, nome_p, quantidade FROM vendas_itens WHERE venda_id=?",
        (venda_id,),
    ).fetchall()


def marcar_cancelada_cursor(cur, venda_id):
    cur.execute("UPDATE vendas SET status='Cancelado' WHERE id=?", (venda_id,))
    return cur.rowcount


def buscar_venda(venda_id):
    res = query_db(
        """
        SELECT id, cliente, data_venda, subtotal, desconto, taxa, total_final, forma_pagamento, vendedor, status
        FROM vendas
        WHERE id=?
        """,
        (venda_id,),
    )
    return res[0] if res else None
