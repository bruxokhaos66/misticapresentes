from datetime import datetime
import unicodedata

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


def _sem_acento(texto):
    return "".join(c for c in unicodedata.normalize("NFD", str(texto or "")) if unicodedata.category(c) != "Mn")


def normalizar_forma_pagamento(forma):
    bruto = str(forma or "Dinheiro").strip()
    texto = _sem_acento(bruto).strip()
    texto_lower = texto.lower()
    if "debito" in texto_lower:
        return "Debito"
    if "credito" in texto_lower and "3" in texto_lower:
        return "Credito 3x"
    if "credito" in texto_lower and "2" in texto_lower:
        return "Credito 2x"
    if "credito" in texto_lower and "1" in texto_lower:
        return "Credito 1x"
    if "pix" in texto_lower:
        return "Pix"
    if "dinheiro" in texto_lower:
        return "Dinheiro"
    return texto or "Dinheiro"


def dinheiro_para_float(valor):
    if valor is None:
        return 0.0
    if isinstance(valor, (int, float)):
        return float(valor or 0)
    txt = str(valor).strip().replace("R$", "").replace("r$", "").replace(" ", "")
    if not txt:
        return 0.0
    negativo = txt.startswith("-")
    txt = txt.replace("-", "")
    try:
        if "," in txt and "." in txt:
            if txt.rfind(",") > txt.rfind("."):
                txt = txt.replace(".", "").replace(",", ".")
            else:
                txt = txt.replace(",", "")
        elif "," in txt:
            txt = txt.replace(".", "").replace(",", ".")
        elif "." in txt:
            partes = txt.split(".")
            if len(partes) > 1 and len(partes[-1]) == 3 and all(p.isdigit() for p in partes):
                txt = "".join(partes)
        numero = float(txt)
        return -numero if negativo else numero
    except Exception:
        limpo = "".join(c for c in txt if c.isdigit())
        numero = float(limpo) / 100 if limpo else 0.0
        return -numero if negativo else numero


def _taxa_por_forma(forma, valor_base):
    forma = normalizar_forma_pagamento(forma)
    valor_base = dinheiro_para_float(valor_base)
    if valor_base <= 0:
        return 0.0
    return float(TAXAS_FIXAS_CARTAO.get(forma, 0.0) or 0.0)


def _subtotal_base(carrinho, desconto_percentual=0):
    subtotal = sum(float(item.get("t", 0) or 0) for item in carrinho)
    try:
        desconto_percentual = dinheiro_para_float(desconto_percentual)
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
    """Normaliza valores informados no misto.

    Importante: o campo valor representa o que o cliente pagou naquela forma.
    Se for cartão, esse valor precisa incluir a taxa fixa.
    """
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
        forma = normalizar_forma_pagamento(forma)
        if not forma:
            continue
        valor = dinheiro_para_float(valor)
        if valor > 0:
            normalizados.append({"forma": forma, "valor": round(valor, 2)})
    return normalizados


def total_taxas_pagamentos_mistos(pagamentos):
    total = 0.0
    for p in normalizar_pagamentos_mistos(pagamentos):
        total += _taxa_por_forma(p["forma"], p["valor"])
    return round(total, 2)


def validar_pagamentos_mistos_fechados(calculo, pagamentos):
    pagamentos = normalizar_pagamentos_mistos(pagamentos)
    base = _base_do_calculo(calculo)
    taxas = total_taxas_pagamentos_mistos(pagamentos)
    total_final = round(base + taxas, 2)
    total_pago = round(sum(float(p.get("valor", 0) or 0) for p in pagamentos), 2)
    if not pagamentos:
        raise ValueError("Pagamento misto incompleto. Informe as formas e valores antes de salvar.")
    if abs(total_pago - total_final) > 0.01:
        falta = round(total_final - total_pago, 2)
        if falta > 0:
            raise ValueError(f"Pagamento misto não fechado. Falta receber R$ {falta:,.2f} incluindo taxas.".replace(",", "X").replace(".", ",").replace("X", "."))
        raise ValueError(f"Pagamento misto acima do total. Valor excedente R$ {abs(falta):,.2f}.".replace(",", "X").replace(".", ",").replace("X", "."))
    return pagamentos


def resumo_pagamentos_mistos(pagamentos):
    partes = []
    for p in normalizar_pagamentos_mistos(pagamentos):
        valor = f"R$ {p['valor']:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        taxa = _taxa_por_forma(p["forma"], p["valor"])
        if taxa > 0:
            taxa_txt = f"R$ {taxa:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
            partes.append(f"{p['forma']} {valor} (inclui taxa {taxa_txt})")
        else:
            partes.append(f"{p['forma']} {valor}")
    return " + ".join(partes)


def calcular_total_venda(carrinho, desconto_percentual=0, forma_pagamento="Dinheiro"):
    subtotal, desconto, base = _subtotal_base(carrinho, desconto_percentual)
    forma = normalizar_forma_pagamento(forma_pagamento or "Dinheiro")
    taxa = _taxa_por_forma(forma, base)
    return {"s": subtotal, "d": desconto, "tx": taxa, "tot": base + taxa}


def calcular_total_venda_misto(carrinho, desconto_percentual=0, pagamentos=None):
    subtotal, desconto, base = _subtotal_base(carrinho, desconto_percentual)
    pagamentos = normalizar_pagamentos_mistos(pagamentos)
    taxa = total_taxas_pagamentos_mistos(pagamentos)
    total_pago = round(sum(p["valor"] for p in pagamentos), 2)
    return {"s": subtotal, "d": desconto, "tx": taxa, "tot": base + taxa, "base": base, "total_pago": total_pago}


def _confirmar_venda_no_banco_central(venda_id):
    """Confirma a venda no banco central (fonte única de verdade) de forma
    síncrona e bloqueante: a venda só é considerada concluída quando o
    servidor confirma o recebimento. Sem essa confirmação, a venda é desfeita
    localmente (ver registrar_venda_service) — não existe mais "venda só
    local" pendente de sincronização em segundo plano."""
    from services.sync_service import sincronizar_venda_obrigatoria
    try:
        return sincronizar_venda_obrigatoria(venda_id)
    except Exception as exc:
        return False, str(exc)


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
        calculo = dict(calculo)
        calculo["tx"] = total_taxas_pagamentos_mistos(pagamentos_mistos)
        calculo["tot"] = _base_do_calculo(calculo) + calculo["tx"]
    else:
        forma_pagamento = normalizar_forma_pagamento(forma_pagamento)

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
                forma = normalizar_forma_pagamento(pagamento["forma"])
                valor_recebido = dinheiro_para_float(pagamento["valor"])
                vendas_repo.inserir_fluxo_cursor(cur, "Entrada", f"Venda no {venda_id} (Misto - {forma}) - Dia operacional {dia_operacional}", valor_recebido, data_venda, data_iso, caixa_id, forma)
        else:
            forma_fluxo = normalizar_forma_pagamento(forma_pagamento)
            vendas_repo.inserir_fluxo_cursor(cur, "Entrada", f"Venda no {venda_id} ({forma_pagamento}) - Dia operacional {dia_operacional}", calculo["tot"], data_venda, data_iso, caixa_id, forma_fluxo)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    confirmada, erro = _confirmar_venda_no_banco_central(venda_id)
    if not confirmada:
        try:
            cancelar_venda_service(venda_id, usuario=vendedor, caixa_id=caixa_id)
        except Exception as exc_desfazer:
            print(f"[Venda] Falha ao desfazer localmente a venda {venda_id} não confirmada pelo servidor: {exc_desfazer}")
        raise ConnectionError(
            "Sem conexão com o servidor central: a venda NÃO foi registrada. "
            f"Verifique a internet e tente novamente. ({erro})"
        )

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
                forma = normalizar_forma_pagamento(pagamento["forma"])
                valor = dinheiro_para_float(pagamento["valor"])
                vendas_repo.inserir_fluxo_cursor(cur, "Saida", f"Estorno venda no {venda_id} (Misto - {forma})", valor, agora_data, agora_iso, caixa_id, forma)
        else:
            forma_fluxo = normalizar_forma_pagamento(forma_estorno)
            vendas_repo.inserir_fluxo_cursor(cur, "Saida", f"Estorno venda no {venda_id} ({forma_estorno})", valor_estorno, agora_data, agora_iso, caixa_id, forma_fluxo)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

    confirmada, erro = _confirmar_venda_no_banco_central(venda_id)
    if not confirmada:
        print(f"[Venda] Cancelamento da venda {venda_id} aplicado localmente, mas não confirmado no servidor central ainda: {erro}")
    return True
