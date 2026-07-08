from datetime import datetime

from database import query_db


FORMAS_CAIXA_DETALHADAS = [
    "Dinheiro",
    "Pix",
    "Debito",
    "Credito 1x",
    "Credito 2x",
    "Credito 3x",
]


def obter_caixa_id_ativo():
    res = query_db("SELECT id FROM caixa_diario WHERE status='Aberto' ORDER BY id DESC LIMIT 1")
    return res[0][0] if res else None


def status_caixa_aberto():
    res = query_db("SELECT status, saldo_inicial, data_abertura FROM caixa_diario WHERE status='Aberto' ORDER BY id DESC LIMIT 1")
    return res[0] if res else None


def abrir_caixa(valor_inicial, operador, descricao="Abertura de Caixa"):
    if obter_caixa_id_ativo():
        raise ValueError("Ja existe um caixa aberto. Feche o caixa atual antes de abrir outro.")
    data_ini = datetime.now().strftime("%d/%m/%Y %H:%M")
    query_db("INSERT INTO caixa_diario (data_abertura, saldo_inicial, status, operador) VALUES (?,?,?,?)", (data_ini, float(valor_inicial or 0), "Aberto", operador), commit=True)
    cx_id = obter_caixa_id_ativo()
    query_db("INSERT INTO fluxo_caixa (tipo, descricao, valor, data_hora, caixa_id, forma_pagamento) VALUES (?,?,?,?,?,?)", ("Entrada", descricao, float(valor_inicial or 0), data_ini, cx_id, "Dinheiro"), commit=True)
    return cx_id


def _soma_fluxo(caixa_id, tipo=None, forma_pagamento=None):
    sql = "SELECT COALESCE(SUM(valor),0) FROM fluxo_caixa WHERE caixa_id=?"
    params = [caixa_id]
    if tipo:
        sql += " AND tipo=?"
        params.append(tipo)
    if forma_pagamento:
        sql += " AND forma_pagamento=?"
        params.append(forma_pagamento)
    res = query_db(sql, tuple(params))
    return float(res[0][0] or 0.0) if res else 0.0


def _saldo_por_forma(caixa_id, forma):
    entradas = _soma_fluxo(caixa_id, "Entrada", forma)
    saidas = _soma_fluxo(caixa_id, "Saida", forma) + _soma_fluxo(caixa_id, "Saída", forma)
    return float(entradas or 0.0) - float(saidas or 0.0)


def _fallback_antigo(caixa_id, padrao):
    res = query_db(
        "SELECT COALESCE(SUM(valor),0) FROM fluxo_caixa WHERE caixa_id=? AND COALESCE(forma_pagamento,'')='' AND descricao LIKE ?",
        (caixa_id, padrao),
    )
    return float(res[0][0] or 0.0) if res else 0.0


def resumo_fechamento_caixa():
    cx = query_db("SELECT id, saldo_inicial FROM caixa_diario WHERE status='Aberto' ORDER BY id DESC LIMIT 1")
    if not cx:
        return None
    cx_id = cx[0][0]
    entradas = _soma_fluxo(cx_id, "Entrada")
    saidas = _soma_fluxo(cx_id, "Saida") + _soma_fluxo(cx_id, "Saída")
    saldo = float(entradas or 0.0) - float(saidas or 0.0)

    pix = _saldo_por_forma(cx_id, "Pix")
    debito = _saldo_por_forma(cx_id, "Debito")
    credito_1x = _saldo_por_forma(cx_id, "Credito 1x")
    credito_2x = _saldo_por_forma(cx_id, "Credito 2x")
    credito_3x = _saldo_por_forma(cx_id, "Credito 3x")

    # Fallback para lançamentos antigos sem forma_pagamento gravada.
    pix += _fallback_antigo(cx_id, "%(Pix)%")
    debito += _fallback_antigo(cx_id, "%(Debito)%") + _fallback_antigo(cx_id, "%(Débito)%")
    credito_1x += _fallback_antigo(cx_id, "%(Credito 1x)%") + _fallback_antigo(cx_id, "%(Crédito 1x)%")
    credito_2x += _fallback_antigo(cx_id, "%(Credito 2x)%") + _fallback_antigo(cx_id, "%(Crédito 2x)%")
    credito_3x += _fallback_antigo(cx_id, "%(Credito 3x)%") + _fallback_antigo(cx_id, "%(Crédito 3x)%")

    credito_total = float(credito_1x or 0.0) + float(credito_2x or 0.0) + float(credito_3x or 0.0)
    dinheiro = saldo - float(pix or 0.0) - float(debito or 0.0) - credito_total

    formas_detalhadas = {
        "Dinheiro": float(dinheiro or 0.0),
        "Pix": float(pix or 0.0),
        "Debito": float(debito or 0.0),
        "Credito 1x": float(credito_1x or 0.0),
        "Credito 2x": float(credito_2x or 0.0),
        "Credito 3x": float(credito_3x or 0.0),
    }
    formas = dict(formas_detalhadas)
    formas["Credito"] = credito_total

    return {
        "caixa_id": cx_id,
        "entradas": float(entradas or 0.0),
        "saidas": float(saidas or 0.0),
        "saldo": saldo,
        "formas": formas,
        "formas_detalhadas": formas_detalhadas,
    }


def fechar_caixa_conferido(caixa_id, saldo, formas, informado):
    formas = formas or {}
    informado = informado or {}
    credito_sistema = formas.get("Credito", None)
    if credito_sistema is None:
        credito_sistema = sum(float(formas.get(f, 0.0) or 0.0) for f in ("Credito 1x", "Credito 2x", "Credito 3x"))
    credito_informado = informado.get("Credito", None)
    if credito_informado is None:
        credito_informado = sum(float(informado.get(f, 0.0) or 0.0) for f in ("Credito 1x", "Credito 2x", "Credito 3x"))

    total_sistema = float(formas.get("Dinheiro", 0.0) or 0.0) + float(formas.get("Pix", 0.0) or 0.0) + float(formas.get("Debito", 0.0) or 0.0) + float(credito_sistema or 0.0)
    total_informado = float(informado.get("Dinheiro", 0.0) or 0.0) + float(informado.get("Pix", 0.0) or 0.0) + float(informado.get("Debito", 0.0) or 0.0) + float(credito_informado or 0.0)
    diferenca = total_informado - total_sistema

    query_db(
        """
        UPDATE caixa_diario
        SET status='Fechado', data_fechamento=?, saldo_final=?, dinheiro_sistema=?, pix_sistema=?, debito_sistema=?, credito_sistema=?, dinheiro_informado=?, pix_informado=?, debito_informado=?, credito_informado=?, diferenca_caixa=?
        WHERE id=?
        """,
        (datetime.now().strftime("%d/%m/%Y %H:%M"), saldo, formas.get("Dinheiro", 0.0), formas.get("Pix", 0.0), formas.get("Debito", 0.0), credito_sistema, informado.get("Dinheiro", 0.0), informado.get("Pix", 0.0), informado.get("Debito", 0.0), credito_informado, diferenca, caixa_id),
        commit=True,
    )
    return diferenca


def fechar_caixa_simples(caixa_id, saldo):
    query_db("UPDATE caixa_diario SET status='Fechado', data_fechamento=?, saldo_final=? WHERE id=?", (datetime.now().strftime("%d/%m/%Y %H:%M"), saldo, caixa_id), commit=True)


def lancar_fluxo(tipo, descricao, valor, caixa_id, rotulo=None, forma_pagamento=None):
    if not caixa_id:
        raise ValueError("Abra o caixa antes de fazer lançamentos.")
    rotulo = rotulo or ("Reforco de caixa" if tipo == "Entrada" else "Sangria")
    query_db(
        "INSERT INTO fluxo_caixa (tipo, descricao, valor, data_hora, data_iso, caixa_id, forma_pagamento) VALUES (?,?,?,?,?,?,?)",
        (tipo, f"{rotulo}: {descricao}", float(valor or 0), datetime.now().strftime("%d/%m/%Y %H:%M"), datetime.now().strftime("%Y-%m-%d %H:%M:%S"), caixa_id, forma_pagamento),
        commit=True,
    )


def listar_fluxo(caixa_id=None):
    if caixa_id:
        return query_db("SELECT tipo, descricao, valor, data_hora FROM fluxo_caixa WHERE caixa_id=? ORDER BY id DESC", (caixa_id,))
    return query_db("SELECT tipo, descricao, valor, data_hora FROM fluxo_caixa ORDER BY id DESC LIMIT 50")


def salvar_conta(descricao, valor, vencimento, categoria):
    query_db("INSERT INTO contas_a_pagar (descricao, valor, data_vencimento, categoria, status) VALUES (?,?,?,?,?)", (descricao, float(valor or 0), vencimento, categoria, "Pendente"), commit=True)


def obter_conta(conta_id):
    res = query_db("SELECT descricao, valor, categoria, status FROM contas_a_pagar WHERE id=?", (conta_id,))
    return res[0] if res else None


def marcar_conta_paga(conta_id, caixa_id):
    if not caixa_id:
        raise ValueError("Abra o caixa antes de marcar uma conta como paga.")
    conta = obter_conta(conta_id)
    if not conta:
        raise ValueError("Conta nao localizada.")
    if str(conta[3]).lower() == "pago":
        raise ValueError("Esta conta ja esta marcada como paga.")
    query_db("UPDATE contas_a_pagar SET status='Pago' WHERE id=?", (conta_id,), commit=True)
    query_db(
        "INSERT INTO fluxo_caixa (tipo, descricao, valor, data_hora, data_iso, caixa_id, forma_pagamento) VALUES (?,?,?,?,?,?,?)",
        ("Saida", f"[{conta[2]}] {conta[0]}", conta[1], datetime.now().strftime("%d/%m/%Y %H:%M"), datetime.now().strftime("%Y-%m-%d %H:%M:%S"), caixa_id, None),
        commit=True,
    )
    return conta


def excluir_conta(conta_id):
    query_db("UPDATE contas_a_pagar SET status='Excluido', cancelado_em=? WHERE id=?", (datetime.now().strftime("%d/%m/%Y %H:%M:%S"), conta_id), commit=True)


def listar_contas():
    return query_db(
        """
        SELECT id, descricao, valor, data_vencimento, categoria, status
        FROM contas_a_pagar
        WHERE COALESCE(status,'Pendente') != 'Excluido'
        ORDER BY status DESC, id DESC
        """
    )


def caixa_abertos_count():
    res = query_db("SELECT COUNT(*) FROM caixa_diario WHERE status='Aberto'")
    return int(res[0][0] or 0) if res else 0
