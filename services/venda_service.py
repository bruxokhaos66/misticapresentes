from datetime import datetime
import threading

from database import get_connection
from repositories import estoque as estoque_repo
from repositories import vendas as vendas_repo
from services.dia_operacional_service import etiqueta_dia_operacional
from services.estoque_service import validar_estoque_carrinho



def calcular_total_venda(carrinho, desconto_percentual=0, forma_pagamento="Dinheiro"):
    subtotal = sum(float(item.get("t", 0) or 0) for item in carrinho)
    try:
        desconto_percentual = float(str(desconto_percentual or "0").replace(",", "."))
    except Exception:
        desconto_percentual = 0.0
    desconto_percentual = max(0.0, min(12.0, desconto_percentual))
    desconto = subtotal * (desconto_percentual / 100)
    base = max(0.0, subtotal - desconto)
    forma = forma_pagamento or "Dinheiro"
    taxa = 0.0
    if forma == "Debito" and base > 0:
        taxa = 1.5  # Taxa fixa definida pela loja.
    elif "Credito 1x" in forma:
        taxa = base * 0.015
    elif "Credito 2x" in forma:
        taxa = base * 0.02
    elif "Credito 3x" in forma:
        taxa = base * 0.025
    return {"s": subtotal, "d": desconto, "tx": taxa, "tot": base + taxa}



def _tentar_sincronizar_venda_sem_bloquear(venda_id):
    """Registra pendência e tenta enviar em segundo plano.

    A tela de venda nunca deve esperar internet/API, porque isso trava o caixa.
    """
    try:
        from services.sync_service import enfileirar_venda_para_sync
        enfileirar_venda_para_sync(venda_id)
    except Exception as exc:
        print(f"[Sync] Nao consegui enfileirar venda {venda_id}: {exc}")
        return None

    def executar():
        try:
            from services.sync_service import sincronizar_pendencias
            sincronizar_pendencias(limite=3)
        except Exception as exc:
            print(f"[Sync] Venda {venda_id} ficou pendente: {exc}")

    try:
        threading.Thread(target=executar, daemon=True).start()
    except Exception as exc:
        print(f"[Sync] Venda {venda_id} ficou pendente: {exc}")
    return None



def registrar_venda_service(carrinho, cliente, data_venda, data_iso, calculo, forma_pagamento, vendedor, caixa_id):
    if not caixa_id:
        raise ValueError("Abra o caixa antes de registrar uma venda.")
    validar_estoque_carrinho(carrinho)
    try:
        momento_venda = datetime.strptime(str(data_iso), "%Y-%m-%d %H:%M:%S")
    except Exception:
        momento_venda = datetime.now()
    dia_operacional = etiqueta_dia_operacional(momento_venda)

    conn = get_connection()
    cur = conn.cursor()
    try:
        venda_id = vendas_repo.inserir_venda_cursor(
            cur,
            cliente,
            data_venda,
            data_iso,
            calculo["s"],
            calculo["d"],
            calculo["tx"],
            calculo["tot"],
            forma_pagamento,
            vendedor,
            "Concluído",
            dia_operacional,
        )

        for item in carrinho:
            produto = estoque_repo.buscar_produto_movimento_cursor(cur, item["id"])
            if not produto:
                raise ValueError(f"Produto {item['id']} nao localizado.")
            nome_produto = produto[0]
            custo_unitario = float(produto[1] or 0)
            estoque_anterior = int(produto[2] or 0)
            quantidade = int(item["q"])
            if quantidade > estoque_anterior:
                raise ValueError(f"Estoque insuficiente para {nome_produto}. Disponivel: {estoque_anterior}.")

            vendas_repo.inserir_item_cursor(cur, venda_id, item["id"], item["n"], quantidade, custo_unitario, item["p"], item["t"])
            if estoque_repo.baixar_estoque_cursor(cur, item["id"], quantidade) != 1:
                raise ValueError(f"Nao consegui baixar estoque de {nome_produto}; atualize a venda.")

            estoque_posterior = estoque_anterior - quantidade
            estoque_repo.registrar_movimentacao_cursor(
                cur,
                item["id"],
                nome_produto,
                -quantidade,
                "Venda",
                f"Venda no {venda_id}",
                vendedor,
                datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
                estoque_anterior,
                estoque_posterior,
                venda_id,
            )

        vendas_repo.inserir_fluxo_cursor(
            cur,
            "Entrada",
            f"Venda no {venda_id} ({forma_pagamento}) - Dia operacional {dia_operacional}",
            calculo["tot"],
            data_venda,
            data_iso,
            caixa_id,
            forma_pagamento,
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    _tentar_sincronizar_venda_sem_bloquear(venda_id)
    return venda_id



def obter_resumo_venda(venda_id):
    return vendas_repo.obter_status_total(venda_id)



def consultar_venda_salva(venda_id):
    return vendas_repo.buscar_venda(venda_id)



def cancelar_venda_service(venda_id, usuario, caixa_id=None):
    if not caixa_id:
        raise ValueError("Abra o caixa antes de cancelar/estornar uma venda.")

    status_total = vendas_repo.obter_status_total_forma(venda_id)
    if not status_total:
        raise ValueError("Venda nao localizada.")
    status, valor_estorno, forma_original = status_total
    if str(status or "").lower() in ("cancelado", "cancelada"):
        raise ValueError("Venda ja cancelada.")

    forma_estorno = forma_original or "Estorno"
    valor_estorno = float(valor_estorno or 0)
    conn = get_connection()
    cur = conn.cursor()
    try:
        itens = vendas_repo.listar_itens_cursor(cur, venda_id)
        for codigo_p, nome_p, quantidade in itens:
            quantidade = int(quantidade or 0)
            produto = estoque_repo.buscar_produto_movimento_cursor(cur, codigo_p)
            estoque_anterior = int(produto[2] if produto else 0)
            estoque_posterior = estoque_anterior + quantidade
            if estoque_repo.somar_estoque_cursor(cur, codigo_p, quantidade) != 1:
                raise ValueError(f"Nao consegui devolver estoque do produto {codigo_p}.")
            estoque_repo.registrar_movimentacao_cursor(
                cur,
                codigo_p,
                nome_p,
                quantidade,
                "Cancelamento",
                f"Cancelamento venda no {venda_id}",
                usuario,
                datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
                estoque_anterior,
                estoque_posterior,
                venda_id,
            )

        vendas_repo.marcar_cancelada_cursor(cur, venda_id)
        agora_data = datetime.now().strftime("%d/%m/%Y %H:%M")
        agora_iso = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        vendas_repo.inserir_fluxo_cursor(
            cur,
            "Saida",
            f"Estorno venda no {venda_id} ({forma_estorno})",
            valor_estorno,
            agora_data,
            agora_iso,
            caixa_id,
            forma_estorno,
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    _tentar_sincronizar_venda_sem_bloquear(venda_id)
    return valor_estorno
