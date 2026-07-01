from database import query_db

def diagnostico_tabelas(tabelas_obrigatorias):
    problemas = []
    existentes = {r[0] for r in query_db("SELECT name FROM sqlite_master WHERE type='table'")}
    for t in tabelas_obrigatorias:
        if t not in existentes:
            problemas.append(f"Tabela ausente: {t}")
    return problemas

def criar_indices_seguros():
    indices = [
        "CREATE INDEX IF NOT EXISTS idx_produtos_codigo ON produtos(codigo_p)",
        "CREATE INDEX IF NOT EXISTS idx_produtos_nome ON produtos(nome)",
        "CREATE INDEX IF NOT EXISTS idx_clientes_nome ON clientes(nome)",
        "CREATE INDEX IF NOT EXISTS idx_vendas_data_iso ON vendas(data_iso)",
        "CREATE INDEX IF NOT EXISTS idx_vendas_status ON vendas(status)",
        "CREATE INDEX IF NOT EXISTS idx_vendas_itens_codigo ON vendas_itens(codigo_p)",
        "CREATE INDEX IF NOT EXISTS idx_fluxo_data_iso ON fluxo_caixa(data_iso)",
        "CREATE INDEX IF NOT EXISTS idx_mov_estoque_codigo ON movimentacao_estoque(codigo_p)",
    ]
    for sql in indices:
        query_db(sql, commit=True)

def normalizar_nulos_basicos():
    comandos = [
        "UPDATE produtos SET quantidade=0 WHERE quantidade IS NULL",
        "UPDATE produtos SET preco=0 WHERE preco IS NULL",
        "UPDATE produtos SET ativo=1 WHERE ativo IS NULL",
        "UPDATE clientes SET ativo=1 WHERE ativo IS NULL",
        "UPDATE vendas SET status='Concluído' WHERE status IS NULL OR status=''",
    ]
    for sql in comandos:
        try:
            query_db(sql, commit=True)
        except Exception:
            pass

def localizar_venda(vid):
    res = query_db("SELECT id, data_venda, cliente, total_final, forma_pagamento, vendedor FROM vendas WHERE id=?", (vid,))
    return res[0] if res else None

def vendas_recentes(limite=10):
    return query_db("SELECT id, data_venda, cliente, total_final, forma_pagamento FROM vendas ORDER BY id DESC LIMIT ?", (limite,))

def cupom_venda(vid):
    venda = localizar_venda(vid)
    itens = query_db("SELECT nome_p, quantidade, valor_total FROM vendas_itens WHERE venda_id=?", (vid,))
    return venda, itens
