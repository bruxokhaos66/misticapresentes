from database import query_db


def obter_info(codigo_p):
    res = query_db(
        """
        SELECT nome, COALESCE(quantidade,0), COALESCE(estoque_minimo,0)
        FROM produtos
        WHERE codigo_p=? AND COALESCE(ativo,1)=1
        """,
        (codigo_p,),
    )
    return res[0] if res else None


def atualizar_quantidade(codigo_p, quantidade):
    query_db("UPDATE produtos SET quantidade=? WHERE codigo_p=?", (int(quantidade), codigo_p), commit=True)


def registrar_movimentacao(codigo_p, produto, quantidade, tipo, motivo, usuario, data_hora, estoque_anterior, estoque_posterior, venda_id=None):
    query_db(
        """
        INSERT INTO movimentacao_estoque
        (codigo_p, produto, quantidade, tipo, motivo, usuario, data_hora, estoque_anterior, estoque_posterior, venda_id)
        VALUES (?,?,?,?,?,?,?,?,?,?)
        """,
        (codigo_p, produto, int(quantidade or 0), tipo, motivo, usuario, data_hora, int(estoque_anterior or 0), int(estoque_posterior or 0), venda_id),
        commit=True,
    )


def registrar_movimentacao_cursor(cur, codigo_p, produto, quantidade, tipo, motivo, usuario, data_hora, estoque_anterior, estoque_posterior, venda_id=None):
    cur.execute(
        """
        INSERT INTO movimentacao_estoque
        (codigo_p, produto, quantidade, tipo, motivo, usuario, data_hora, estoque_anterior, estoque_posterior, venda_id)
        VALUES (?,?,?,?,?,?,?,?,?,?)
        """,
        (codigo_p, produto, int(quantidade or 0), tipo, motivo, usuario, data_hora, int(estoque_anterior or 0), int(estoque_posterior or 0), venda_id),
    )


def inserir_inventario_cursor(cur, codigo_p, produto, quantidade_sistema, quantidade_contada, diferenca, usuario, data_hora, observacao):
    cur.execute(
        """
        INSERT INTO inventario_estoque
        (codigo_p, produto, quantidade_sistema, quantidade_contada, diferenca, usuario, data_hora, observacao)
        VALUES (?,?,?,?,?,?,?,?)
        """,
        (codigo_p, produto, quantidade_sistema, quantidade_contada, diferenca, usuario, data_hora, observacao),
    )


def buscar_produto_movimento_cursor(cur, codigo_p):
    return cur.execute(
        """
        SELECT nome, COALESCE(custo,0), COALESCE(quantidade,0)
        FROM produtos
        WHERE codigo_p=?
        """,
        (codigo_p,),
    ).fetchone()


def baixar_estoque_cursor(cur, codigo_p, quantidade):
    cur.execute(
        """
        UPDATE produtos
        SET quantidade = COALESCE(quantidade,0) - ?
        WHERE codigo_p=? AND COALESCE(quantidade,0) >= ?
        """,
        (int(quantidade), codigo_p, int(quantidade)),
    )
    return cur.rowcount


def somar_estoque_cursor(cur, codigo_p, quantidade):
    cur.execute(
        "UPDATE produtos SET quantidade = COALESCE(quantidade,0) + ? WHERE codigo_p=?",
        (int(quantidade), codigo_p),
    )
    return cur.rowcount


def definir_estoque_cursor(cur, codigo_p, quantidade):
    cur.execute("UPDATE produtos SET quantidade=? WHERE codigo_p=?", (int(quantidade), codigo_p))
    return cur.rowcount
