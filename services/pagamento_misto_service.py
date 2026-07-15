def valor_moeda_para_float(texto):
    texto = str(texto or "").strip().replace("R$", "").strip()
    texto = texto.replace(".", "").replace(",", ".")
    try:
        return round(float(texto), 2)
    except Exception:
        return 0.0


def float_para_moeda(valor):
    try:
        valor = float(valor or 0)
    except Exception:
        valor = 0.0
    return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def extrair_pagamentos_mistos(forma_pagamento):
    """Reconstrói {forma, valor} a partir da string salva em vendas.forma_pagamento.

    resumo_pagamentos_mistos (services/venda_service.py) grava o valor pago
    logo após o PRIMEIRO "R$" e, quando há taxa (Debito/Credito), acrescenta
    um sufixo somente informativo "(inclui taxa R$ X,XX)" com um SEGUNDO
    "R$". Por isso o corte tem que ser no primeiro "R$" (não no último via
    rsplit) e o texto do valor tem que parar no primeiro "(" que apareça,
    senão a parcela com taxa (cartão) é descartada do estorno e a saída
    financeira do estorno misto sai menor que a entrada original."""
    texto = str(forma_pagamento or "").strip()
    if not texto.lower().startswith("misto:"):
        return []

    corpo = texto.split(":", 1)[1]
    pagamentos = []
    for parte in corpo.split("+"):
        trecho = parte.strip()
        if "R$" not in trecho:
            continue
        forma, resto = trecho.split("R$", 1)
        forma = forma.strip()
        valor_txt = resto.split("(", 1)[0]
        valor = valor_moeda_para_float(valor_txt)
        if forma and valor > 0:
            pagamentos.append({"forma": forma, "valor": valor})
    return pagamentos


def montar_descricao_mista(pagamentos):
    partes = []
    for pagamento in pagamentos or []:
        forma = str(pagamento.get("forma") or "").strip()
        valor = pagamento.get("valor", 0)
        try:
            valor_num = float(valor or 0)
        except Exception:
            valor_num = 0.0
        if forma and valor_num > 0:
            partes.append(f"{forma} {float_para_moeda(valor_num)}")
    return "Misto: " + " + ".join(partes) if partes else "Misto"


def eh_pagamento_misto(forma_pagamento):
    return str(forma_pagamento or "").strip().lower().startswith("misto:")
