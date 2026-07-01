from datetime import datetime

from database import get_connection
from repositories import estoque as estoque_repo


def consultar_estoque_produto(codigo_p):
    info = estoque_repo.obter_info(codigo_p)
    if not info:
        return None
    return {
        "nome": info[0],
        "quantidade": int(info[1] or 0),
        "estoque_minimo": int(info[2] or 0),
    }


def validar_estoque_carrinho(carrinho):
    if not carrinho:
        raise ValueError("Carrinho vazio.")
    qtd_por_codigo = {}
    for item in carrinho:
        codigo = item["id"]
        qtd_por_codigo[codigo] = qtd_por_codigo.get(codigo, 0) + int(item["q"])

    avisos = []
    for codigo, qtd_total in qtd_por_codigo.items():
        info = consultar_estoque_produto(codigo)
        if not info:
            raise ValueError(f"Produto {codigo} nao localizado. Atualize a venda.")
        estoque_atual = info["quantidade"]
        if qtd_total > estoque_atual:
            raise ValueError(
                f"Estoque insuficiente para '{info['nome']}'.\n"
                f"Disponivel: {estoque_atual}\nNo carrinho: {qtd_total}"
            )
        restante = estoque_atual - qtd_total
        minimo = info["estoque_minimo"]
        if restante <= minimo:
            avisos.append(f"{info['nome']}: ficara com {restante} un. (minimo {minimo})")
    return avisos


def registrar_movimentacao_estoque_service(codigo_p, produto, quantidade, tipo, motivo, usuario, estoque_anterior, estoque_posterior, venda_id=None):
    estoque_repo.registrar_movimentacao(
        codigo_p,
        produto,
        quantidade,
        tipo,
        motivo,
        usuario,
        datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
        estoque_anterior,
        estoque_posterior,
        venda_id,
    )


def registrar_inventario_service(codigo_p, produto, quantidade_sistema, quantidade_contada, usuario, observacao=""):
    quantidade_sistema = int(quantidade_sistema or 0)
    quantidade_contada = int(quantidade_contada or 0)
    diferenca = quantidade_contada - quantidade_sistema
    agora = datetime.now().strftime("%d/%m/%Y %H:%M:%S")

    conn = get_connection()
    cur = conn.cursor()
    try:
        estoque_repo.inserir_inventario_cursor(
            cur,
            codigo_p,
            produto,
            quantidade_sistema,
            quantidade_contada,
            diferenca,
            usuario,
            agora,
            observacao,
        )
        estoque_repo.definir_estoque_cursor(cur, codigo_p, quantidade_contada)
        estoque_repo.registrar_movimentacao_cursor(
            cur,
            codigo_p,
            produto,
            diferenca,
            "Inventario",
            observacao or "Ajuste por inventario",
            usuario,
            agora,
            quantidade_sistema,
            quantidade_contada,
            None,
        )
        conn.commit()
        return diferenca
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
