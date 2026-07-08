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
    texto = str(forma_pagamento or "").strip()
    if not texto.lower().startswith("misto:"):
        return []

    corpo = texto.split(":", 1)[1]
    pagamentos = []
    for parte in corpo.split("+"):
        trecho = parte.strip()
        if "R$" not in trecho:
            continue
        forma, valor_txt = trecho.rsplit("R$", 1)
        forma = forma.strip()
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
