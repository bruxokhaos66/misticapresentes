from database import query_db


def valoracao_estoque():
    linhas = query_db("SELECT nome, quantidade, custo, preco FROM produtos WHERE COALESCE(ativo,1)=1")
    itens = []
    custo_total = 0.0
    venda_total = 0.0
    for nome, quantidade, custo, preco in linhas:
        qtd = int(quantidade or 0)
        custo_item = qtd * float(custo or 0.0)
        venda_item = qtd * float(preco or 0.0)
        custo_total += custo_item
        venda_total += venda_item
        itens.append((nome, qtd, custo_item, venda_item))
    return {"itens": itens, "custo_total": custo_total, "venda_total": venda_total, "lucro_estimado": venda_total - custo_total}


def estoque_baixo(limite=6):
    return query_db(
        """
        SELECT nome, quantidade, estoque_minimo
        FROM produtos
        WHERE COALESCE(ativo,1)=1
          AND COALESCE(quantidade,0) <= COALESCE(estoque_minimo,0)
        ORDER BY quantidade ASC
        LIMIT ?
        """,
        (int(limite),),
    )


def contar_estoque_baixo():
    res = query_db("SELECT COUNT(*) FROM produtos WHERE COALESCE(ativo,1)=1 AND COALESCE(quantidade,0) <= COALESCE(estoque_minimo,0)")
    return int(res[0][0] or 0) if res else 0


def produtos_sem_giro(limite=15, somente_com_estoque=False):
    filtro_estoque = "AND COALESCE(p.quantidade,0) > 0" if somente_com_estoque else ""
    return query_db(
        f"""
        SELECT p.nome, p.quantidade, p.categoria
        FROM produtos p
        WHERE COALESCE(p.ativo,1)=1
          AND p.codigo_p NOT IN (
            SELECT DISTINCT codigo_p FROM vendas_itens WHERE codigo_p IS NOT NULL AND codigo_p != ''
        )
        {filtro_estoque}
        ORDER BY p.quantidade DESC, p.nome ASC
        LIMIT ?
        """,
        (int(limite),),
    )


def produtos_para_giro():
    return query_db("SELECT codigo_p, nome, quantidade, estoque_minimo, categoria FROM produtos WHERE COALESCE(ativo,1)=1")


def produtos_cadastro_incompleto():
    res = query_db("SELECT COUNT(*) FROM produtos WHERE COALESCE(ativo,1)=1 AND (codigo_p IS NULL OR codigo_p='' OR nome IS NULL OR nome='')")
    return int(res[0][0] or 0) if res else 0
