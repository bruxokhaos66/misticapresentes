from __future__ import annotations


def buscar_produto_persistido_para_estoque(conn, item):
    """Localiza o produto autoritativo de um item de pedido já persistido.

    A flag ``ativo`` controla a disponibilidade para novas vendas. Depois que
    um pedido foi criado, porém, a inativação do produto não pode apagar a
    referência necessária para confirmar, cancelar ou repor o estoque daquele
    pedido. Por isso, esta busca usa a identidade persistida no item e não
    filtra o estado atual do catálogo.

    Código e ID têm precedência. A busca por nome existe somente como fallback
    para pedidos legados que não conservaram uma identificação melhor.
    """
    codigo = str(item["codigo_p"] or "").strip()
    nome = str(item["nome_p"] or "").strip()

    if codigo:
        produto = conn.execute(
            "SELECT id, codigo_p, nome, quantidade FROM produtos WHERE codigo_p=?",
            (codigo,),
        ).fetchone()
        if produto:
            return produto

        if codigo.isdigit():
            produto = conn.execute(
                "SELECT id, codigo_p, nome, quantidade FROM produtos WHERE id=?",
                (int(codigo),),
            ).fetchone()
            if produto:
                return produto

    if nome:
        produto = conn.execute(
            "SELECT id, codigo_p, nome, quantidade FROM produtos WHERE lower(trim(nome))=lower(trim(?))",
            (nome,),
        ).fetchone()
        if produto:
            return produto

    return None


def instalar_busca_produto_persistido() -> None:
    """Instala a busca somente no fluxo operacional de pedidos existentes."""
    from backend import order_status_routes

    order_status_routes.buscar_produto_para_baixa = buscar_produto_persistido_para_estoque
