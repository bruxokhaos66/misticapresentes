from datetime import datetime

from database import query_db


def obter_caixa_id_ativo():
    res = query_db("SELECT id FROM caixa_diario WHERE status='Aberto' ORDER BY id DESC LIMIT 1")
    return res[0][0] if res else None


def status_caixa_aberto():
    res = query_db("SELECT status, saldo_inicial, data_abertura FROM caixa_diario WHERE status='Aberto' ORDER BY id DESC LIMIT 1")
    return res[0] if res else None


def abrir_caixa(valor_inicial, operador, descricao="Abertura de Caixa"):
    if obter_caixa_id_ativo():
        raise ValueError("O caixa ja esta aberto.")
    data_ini = datetime.now().strftime("%d/%m/%Y %H:%M")
    query_db(
        "INSERT INTO caixa_diario (data_abertura, saldo_inicial, status, operador) VALUES (?,?,?,?)",
        (data_ini, float(valor_inicial or 0), "Aberto", operador),
        commit=True,
    )
    cx_id = obter_caixa_id_ativo()
    query_db(
        "INSERT INTO fluxo_caixa (tipo, descricao, valor, data_hora, caixa_id) VALUES (?,?,?,?,?)",
        ("Entrada", descricao, float(valor_inicial or 0), data_ini, cx_id),
        commit=True,
    )
    return cx_id


def resumo_fechamento_caixa():
    cx = query_db("SELECT id, saldo_inicial FROM caixa_diario WHERE status='Aberto' ORDER BY id DESC LIMIT 1")
    if not cx:
        return None
    cx_id = cx[0][0]
    entradas = query_db("SELECT SUM(valor) FROM fluxo_caixa WHERE tipo='Entrada' AND caixa_id=?", (cx_id,))[0][0] or 0.0
    saida_sem_acento = query_db("SELECT SUM(valor) FROM fluxo_caixa WHERE tipo='Saida' AND caixa_id=?", (cx_id,))[0][0] or 0.0
    saida_com_acento = query_db("SELECT SUM(valor) FROM fluxo_caixa WHERE tipo='Saída' AND caixa_id=?", (cx_id,))[0][0] or 0.0
    saidas = float(saida_sem_acento or 0.0) + float(saida_com_acento or 0.0)
    saldo = float(entradas or 0.0) - saidas
    pix = query_db("SELECT SUM(valor) FROM fluxo_caixa WHERE caixa_id=? AND descricao LIKE '%(Pix)%'", (cx_id,))[0][0] or 0.0
    debito = query_db(
        "SELECT SUM(valor) FROM fluxo_caixa WHERE caixa_id=? AND (descricao LIKE '%(Debito)%' OR descricao LIKE '%(Débito)%' OR descricao LIKE '%(D?bito)%')",
        (cx_id,),
    )[0][0] or 0.0
    credito = query_db(
        "SELECT SUM(valor) FROM fluxo_caixa WHERE caixa_id=? AND (descricao LIKE '%(Credito%' OR descricao LIKE '%(Crédito%' OR descricao LIKE '%(Cr?dito%')",
        (cx_id,),
    )[0][0] or 0.0
    dinheiro = saldo - float(pix or 0.0) - float(debito or 0.0) - float(credito or 0.0)
    formas = {"Dinheiro": dinheiro, "Pix": float(pix or 0.0), "Debito": float(debito or 0.0), "Credito": float(credito or 0.0)}
    return {"caixa_id": cx_id, "entradas": float(entradas or 0.0), "saidas": saidas, "saldo": saldo, "formas": formas}


def fechar_caixa_conferido(caixa_id, saldo, formas, informado):
    diferenca = sum(float(v or 0.0) for v in informado.values()) - sum(float(v or 0.0) for v in formas.values())
    query_db(
        """
        UPDATE caixa_diario
        SET status='Fechado',
            data_fechamento=?,
            saldo_final=?,
            dinheiro_sistema=?,
            pix_sistema=?,
            debito_sistema=?,
            credito_sistema=?,
            dinheiro_informado=?,
            pix_informado=?,
            debito_informado=?,
            credito_informado=?,
            diferenca_caixa=?
        WHERE id=?
        """,
        (
            datetime.now().strftime("%d/%m/%Y %H:%M"),
            saldo,
            formas.get("Dinheiro", 0.0),
            formas.get("Pix", 0.0),
            formas.get("Debito", 0.0),
            formas.get("Credito", 0.0),
            informado.get("Dinheiro", 0.0),
            informado.get("Pix", 0.0),
            informado.get("Debito", 0.0),
            informado.get("Credito", 0.0),
            diferenca,
            caixa_id,
        ),
        commit=True,
    )
    return diferenca


def fechar_caixa_simples(caixa_id, saldo):
    query_db(
        "UPDATE caixa_diario SET status='Fechado', data_fechamento=?, saldo_final=? WHERE id=?",
        (datetime.now().strftime("%d/%m/%Y %H:%M"), saldo, caixa_id),
        commit=True,
    )


def lancar_fluxo(tipo, descricao, valor, caixa_id, rotulo=None):
    if not caixa_id:
        raise ValueError("Abra o caixa antes de fazer lançamentos.")
    rotulo = rotulo or ("Reforco de caixa" if tipo == "Entrada" else "Sangria")
    query_db(
        "INSERT INTO fluxo_caixa (tipo, descricao, valor, data_hora, data_iso, caixa_id) VALUES (?,?,?,?,?,?)",
        (tipo, f"{rotulo}: {descricao}", float(valor or 0), datetime.now().strftime("%d/%m/%Y %H:%M"), datetime.now().strftime("%Y-%m-%d %H:%M:%S"), caixa_id),
        commit=True,
    )


def listar_fluxo(caixa_id=None):
    if caixa_id:
        return query_db("SELECT tipo, descricao, valor, data_hora FROM fluxo_caixa WHERE caixa_id=? ORDER BY id DESC", (caixa_id,))
    return query_db("SELECT tipo, descricao, valor, data_hora FROM fluxo_caixa ORDER BY id DESC LIMIT 50")


def salvar_conta(descricao, valor, vencimento, categoria):
    query_db(
        "INSERT INTO contas_a_pagar (descricao, valor, data_vencimento, categoria, status) VALUES (?,?,?,?,?)",
        (descricao, float(valor or 0), vencimento, categoria, "Pendente"),
        commit=True,
    )


def obter_conta(conta_id):
    res = query_db("SELECT descricao, valor, categoria, status FROM contas_a_pagar WHERE id=?", (conta_id,))
    return res[0] if res else None


def marcar_conta_paga(conta_id, caixa_id):
    conta = obter_conta(conta_id)
    if not conta:
        raise ValueError("Conta nao localizada.")
    if str(conta[3]).lower() == "pago":
        raise ValueError("Esta conta ja esta marcada como paga.")
    query_db("UPDATE contas_a_pagar SET status='Pago' WHERE id=?", (conta_id,), commit=True)
    query_db(
        "INSERT INTO fluxo_caixa (tipo, descricao, valor, data_hora, data_iso, caixa_id) VALUES (?,?,?,?,?,?)",
        ("Saida", f"[{conta[2]}] {conta[0]}", conta[1], datetime.now().strftime("%d/%m/%Y %H:%M"), datetime.now().strftime("%Y-%m-%d %H:%M:%S"), caixa_id),
        commit=True,
    )
    return conta


def excluir_conta(conta_id):
    query_db(
        "UPDATE contas_a_pagar SET status='Excluido', cancelado_em=? WHERE id=?",
        (datetime.now().strftime("%d/%m/%Y %H:%M:%S"), conta_id),
        commit=True,
    )


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
