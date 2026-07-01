from database import query_db


def pesquisar_para_venda(termo="", limite=80):
    termo_like = f"%{termo or ''}%"
    return query_db(
        """
        SELECT codigo_p, nome, preco, quantidade, categoria
        FROM produtos
        WHERE COALESCE(ativo,1)=1
          AND (nome LIKE ? OR categoria LIKE ? OR codigo_p LIKE ?)
        ORDER BY nome
        LIMIT ?
        """,
        (termo_like, termo_like, termo_like, int(limite)),
    )


def listar_estoque(termo="", limite=300):
    if termo:
        termo_like = f"%{termo}%"
        return query_db(
            """
            SELECT codigo_p, nome, custo, lucro, preco, quantidade, estoque_minimo, categoria
            FROM produtos
            WHERE COALESCE(ativo,1)=1
              AND (nome LIKE ? OR categoria LIKE ? OR codigo_p LIKE ?)
            ORDER BY categoria, nome
            LIMIT ?
            """,
            (termo_like, termo_like, termo_like, int(limite)),
        )
    return query_db(
        """
        SELECT codigo_p, nome, custo, lucro, preco, quantidade, estoque_minimo, categoria
        FROM produtos
        WHERE COALESCE(ativo,1)=1
        ORDER BY categoria, nome
        LIMIT ?
        """,
        (int(limite),),
    )


def buscar_edicao(codigo_p):
    res = query_db(
        """
        SELECT nome, custo, lucro, preco, quantidade, estoque_minimo, categoria
        FROM produtos
        WHERE codigo_p=?
        """,
        (codigo_p,),
    )
    return res[0] if res else None


def buscar_resumo_estoque(codigo_p):
    res = query_db(
        """
        SELECT nome, COALESCE(quantidade,0), COALESCE(estoque_minimo,0), COALESCE(preco,0), COALESCE(custo,0)
        FROM produtos
        WHERE codigo_p=? AND COALESCE(ativo,1)=1
        """,
        (codigo_p,),
    )
    return res[0] if res else None


def buscar_preco_estoque(codigo_p):
    res = query_db(
        """
        SELECT COALESCE(quantidade,0), nome, COALESCE(preco,0), COALESCE(custo,0)
        FROM produtos
        WHERE codigo_p=?
        """,
        (codigo_p,),
    )
    return res[0] if res else None


def contar_por_categoria(categoria):
    res = query_db("SELECT COUNT(*) FROM produtos WHERE categoria=?", (categoria,))
    return int(res[0][0] or 0) if res else 0


def codigo_existe(codigo_p):
    return bool(query_db("SELECT 1 FROM produtos WHERE codigo_p=? LIMIT 1", (codigo_p,)))


def inserir_produto(codigo_p, nome, custo, lucro, preco, quantidade, estoque_minimo, categoria):
    query_db(
        """
        INSERT INTO produtos (codigo_p, nome, custo, lucro, preco, quantidade, estoque_minimo, categoria)
        VALUES (?,?,?,?,?,?,?,?)
        """,
        (codigo_p, nome, custo, lucro, preco, quantidade, estoque_minimo, categoria),
        commit=True,
    )


def atualizar_produto(codigo_p, nome, custo, lucro, preco, quantidade, estoque_minimo):
    query_db(
        """
        UPDATE produtos
        SET nome=?, custo=?, lucro=?, preco=?, quantidade=?, estoque_minimo=?
        WHERE codigo_p=?
        """,
        (nome, custo, lucro, preco, quantidade, estoque_minimo, codigo_p),
        commit=True,
    )


def inativar_produto(codigo_p):
    query_db("UPDATE produtos SET ativo=0 WHERE codigo_p=?", (codigo_p,), commit=True)


def listar_categorias():
    return [r[0] for r in query_db("SELECT nome FROM categorias WHERE COALESCE(ativo,1)=1 ORDER BY nome")]


def adicionar_categoria(nome):
    existente = query_db(
        "SELECT rowid, COALESCE(ativo,1) FROM categorias WHERE LOWER(nome)=LOWER(?) ORDER BY rowid DESC LIMIT 1",
        (nome,),
    )
    if existente:
        rowid, ativo = existente[0]
        if int(ativo or 0) == 1:
            raise ValueError("Esta categoria ja existe.")
        query_db("UPDATE categorias SET ativo=1, excluido_em=NULL WHERE rowid=?", (rowid,), commit=True)
        return
    query_db("INSERT INTO categorias (nome) VALUES (?)", (nome,), commit=True)


def contar_produtos_ativos_categoria(categoria):
    res = query_db(
        "SELECT COUNT(*) FROM produtos WHERE categoria=? AND COALESCE(ativo,1)=1",
        (categoria,),
    )
    return int(res[0][0] or 0) if res else 0


def inativar_categoria(nome, data_hora):
    query_db(
        "UPDATE categorias SET ativo=0, excluido_em=? WHERE nome=?",
        (data_hora, nome),
        commit=True,
    )


def registrar_historico_preco(codigo_p, produto, preco_antigo, preco_novo, custo_antigo, custo_novo, usuario, data_hora, motivo):
    query_db(
        """
        INSERT INTO historico_precos
        (codigo_p, produto, preco_antigo, preco_novo, custo_antigo, custo_novo, usuario, data_hora, motivo)
        VALUES (?,?,?,?,?,?,?,?,?)
        """,
        (codigo_p, produto, preco_antigo, preco_novo, custo_antigo, custo_novo, usuario, data_hora, motivo),
        commit=True,
    )
