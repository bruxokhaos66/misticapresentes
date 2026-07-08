from datetime import datetime
import threading

from database import get_connection
from repositories import estoque as estoque_repo
from repositories import vendas as vendas_repo
from services.dia_operacional_service import etiqueta_dia_operacional
from services.estoque_service import validar_estoque_carrinho
from services.pagamento_misto_service import extrair_pagamentos_mistos


FORMAS_PAGAMENTO_PADRAO = ["Dinheiro", "Pix", "Debito", "Credito 1x", "Credito 2x", "Credito 3x"]
TAXAS_FIXAS_CARTAO = {
    "Debito": 1.50,
    "Credito 1x": 1.50,
    "Credito 2x": 2.00,
    "Credito 3x": 2.50,
}


def _taxa_por_forma(forma, valor_base):
    forma = str(forma or "Dinheiro")
    valor_base = float(valor_base or 0)
    if valor_base <= 0:
        return 0.0
    for nome_forma, taxa in TAXAS_FIXAS_CARTAO.items():
        if nome_forma in forma:
            return float(taxa or 0.0)
    return 0.0


def _subtotal_base(carrinho, desconto_percentual=0):
    subtotal = sum(float(item.get("t", 0) or 0) for item in carrinho)
    try:
        desconto_percentual = float(str(desconto_percentual or "0").replace(",", "."))
    except Exception:
        desconto_percentual = 0.0
    desconto_percentual = max(0.0, min(12.0, desconto_percentual))
    desconto = subtotal * (desconto_percentual / 100)
    base = max(0.0, subtotal - desconto)
    return subtotal, desconto, base


def _base_do_calculo(calculo):
    try:
        if "base" in calculo:
            return round(float(calculo.get("base") or 0), 2)
        return round(float(calculo.get("s", 0) or 0) - float(calculo.get("d", 0) or 0), 2)
    except Exception:
        return 0.0


def normalizar_pagamentos_mistos(pagamentos):
    normalizados = []
    for pagamento in pagamentos or []:
        if isinstance(pagamento, dict):
            forma = str(pagamento.get("forma") or "").strip()
            valor = pagamento.get("valor", 0)
        else:
            try:
                forma, valor = pagamento
            except Exception:
                continue
        if not forma:
            continue
        try:
            valor = float(valor or 0)
        except Exception:
            valor = 0.0
        if valor > 0:
            normalizados.append({"forma": forma, "valor": round(valor, 2)})
    return normalizados


def validar_pagamentos_mistos_fechados(calculo, pagamentos):
    pagamentos = normalizar_pagamentos_mistos(pagamentos)
    base = _base_do_calculo(calculo)
    total_pago = round(sum(float(p.get("valor", 0) or 0) for p in pagamentos), 2)
    if not pagamentos:
        raise ValueError("Pagamento misto incompleto. Informe as formas e valores antes de salvar.")
    if abs(total_pago - base) > 0.01:
        falta = round(base - total_pago, 2)
        if falta > 0:
            raise ValueError(f"Pagamento misto não fechado. Falta dividir R$ {falta:,.2f}.".replace(",", "X").replace(".", ",").replace("X", "."))
        raise ValueError(f"Pagamento misto acima do total. Valor excedente R$ {abs(falta):,.2f}.".replace(",", "X").replace(".", ",").replace("X", "."))
    return pagamentos


def resumo_pagamentos_mistos(pagamentos):
    partes = []
    for p in normalizar_pagamentos_mistos(pagamentos):
        valor = f"R$ {p['valor']:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        partes.append(f"{p['forma']} {valor}")
    return " + ".join(partes)


def calcular_total_venda(carrinho, desconto_percentual=0, forma_pagamento="Dinheiro"):
    subtotal, desconto, base = _subtotal_base(carrinho, desconto_percentual)
    forma = forma_pagamento or "Dinheiro"
    taxa = _taxa_por_forma(forma, base)
    return {"s": subtotal, "d": desconto, "tx": taxa, "tot": base + taxa}


def calcular_total_venda_misto(carrinho, desconto_percentual=0, pagamentos=None):
    subtotal, desconto, base = _subtotal_base(carrinho, desconto_percentual)
    pagamentos = normalizar_pagamentos_mistos(pagamentos)
    taxa = sum(_taxa_por_forma(p["forma"], p["valor"]) for p in pagamentos)
    return {"s": subtotal, "d": desconto, "tx": taxa, "tot": base + taxa, "base": base}


def _tentar_sincronizar_venda_sem_bloquear(venda_id):
    try:
        from services.sync_service import enfileirar_venda_para_sync
        enfileirar_venda_para_sync(venda_id)
    except Exception as exc:
        print(f"[Sync] Nao consegui enfileirar venda {venda_id}: {exc}")
        return None

    def executar():
        try:
            from services.sync_service import sincronizar_pendencias
            sincronizar_pendencias(limite=8, referencia_id_prioritaria=venda_id)
        except Exception as exc:
            print(f"[Sync] Venda {venda_id} ficou pendente: {exc}")

    try:
        threading.Thread(target=executar, daemon=True).start()
    except Exception as exc:
        print(f"[Sync] Venda {venda_id} ficou pendente: {exc}")
    return None


def registrar_venda_service(carrinho, cliente, data_venda, data_iso, calculo, forma_pagamento, vendedor, caixa_id, pagamentos_mistos=None):
    if not caixa_id:
        raise ValueError("Abra o caixa antes de registrar uma venda.")
    validar_estoque_carrinho(carrinho)
    try:
        momento_venda = datetime.strptime(str(data_iso), "%Y-%m-%d %H:%M:%S")
    except Exception:
        momento_venda = datetime.now()
    dia_operacional = etiqueta_dia_operacional(momento_venda)

    pagamentos_mistos = normalizar_pagamentos_mistos(pagamentos_mistos)
    if str(forma_pagamento or "").startswith("Misto") or pagamentos_mistos:
        pagamentos_mistos = validar_pagamentos_mistos_fechados(calculo, pagamentos_mistos)
        forma_pagamento = "Misto: " + resumo_pagamentos_mistos(pagamentos_mistos)

    conn = get_connection()
    cur = conn.cursor()
    try:
        venda_id = vendas_repo.inserir_venda_cursor(
            cur, cliente, data_venda, data_iso, calculo["s"], calculo["d"], calculo["tx"], calculo["tot"], forma_pagamento, vendedor, "Concluído", dia_operacional
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
                cur, item["id"], nome_produto, -quantidade, "Venda", f"Venda no {venda_id}", vendedor, datetime.now().strftime("%d/%m/%Y %H:%M:%S"), estoque_anterior, estoque_posterior, venda_id
            )

        if pagamentos_mistos:
            for pagamento in pagamentos_mistos:
                forma = pagamento["forma"]
                valor_base = float(pagamento["valor"] or 0)
                taxa = _taxa_por_forma(forma, valor_base)
                vendas_repo.inserir_fluxo_cursor(cur, "Entrada", f"Venda no {venda_id} (Misto - {forma}) - Dia operacional {dia_operacional}", valor_base + taxa, data_venda, data_iso, caixa_id, forma)
        else:
            vendas_repo.inserir_fluxo_cursor(cur, "Entrada", f"Venda no {venda_id} ({forma_pagamento}) - Dia operacional {dia_operacional}", calculo["tot"], data_venda, data_iso, caixa_id, forma_pagamento)
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
                cur, codigo_p, nome_p, quantidade, "Cancelamento", f"Cancelamento venda no {venda_id}", usuario, datetime.now().strftime("%d/%m/%Y %H:%M:%S"), estoque_anterior, estoque_posterior, venda_id
            )

        vendas_repo.marcar_cancelada_cursor(cur, venda_id)
        agora_data = datetime.now().strftime("%d/%m/%Y %H:%M")
        agora_iso = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        pagamentos_mistos = extrair_pagamentos_mistos(forma_estorno)
        if pagamentos_mistos:
            for pagamento in pagamentos_mistos:
                vendas_repo.inserir_fluxo_cursor(cur, "Saida", f"Estorno venda no {venda_id} (Misto - {pagamento['forma']})", float(pagamento["valor"] or 0), agora_data, agora_iso, caixa_id, pagamento["forma"])
        else:
            vendas_repo.inserir_fluxo_cursor(cur, "Saida", f"Estorno venda no {venda_id} ({forma_estorno})", valor_estorno, agora_data, agora_iso, caixa_id, forma_estorno)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    _tentar_sincronizar_venda_sem_bloquear(venda_id)
    return True
