from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
import unicodedata

from backend.audit import registrar_auditoria
from database import get_connection, query_db


FORMAS_CAIXA_DETALHADAS = [
    "Dinheiro",
    "Pix",
    "Debito",
    "Credito 1x",
    "Credito 2x",
    "Credito 3x",
]


def _centavos(valor) -> Decimal:
    """Converte para Decimal arredondado em centavos (ROUND_HALF_UP), evitando
    que a soma de muitos lançamentos de fluxo de caixa acumule erro de ponto
    flutuante antes do fechamento do caixa."""
    try:
        return Decimal(str(valor if valor is not None else 0)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    except Exception:
        return Decimal("0.00")


def _sem_acento(texto):
    return "".join(c for c in unicodedata.normalize("NFD", str(texto or "")) if unicodedata.category(c) != "Mn")


def normalizar_forma_caixa(forma):
    texto = _sem_acento(forma).strip().lower()
    if "debito" in texto:
        return "Debito"
    if "credito" in texto and "3" in texto:
        return "Credito 3x"
    if "credito" in texto and "2" in texto:
        return "Credito 2x"
    if "credito" in texto and "1" in texto:
        return "Credito 1x"
    if "pix" in texto:
        return "Pix"
    if "dinheiro" in texto:
        return "Dinheiro"
    return str(forma or "").strip()


def obter_caixa_id_ativo():
    res = query_db("SELECT id FROM caixa_diario WHERE status='Aberto' ORDER BY id DESC LIMIT 1")
    return res[0][0] if res else None


def status_caixa_aberto():
    res = query_db("SELECT status, saldo_inicial, data_abertura FROM caixa_diario WHERE status='Aberto' ORDER BY id DESC LIMIT 1")
    return res[0] if res else None


def caixa_abertos_count():
    try:
        res = query_db("SELECT COUNT(*) FROM caixa_diario WHERE status='Aberto'")
        return int(res[0][0] or 0) if res else 0
    except Exception:
        return 0


def abrir_caixa(valor_inicial, operador, descricao="Abertura de Caixa"):
    """Abre o caixa de forma atômica: a checagem de que não há caixa aberto e
    o INSERT que abre um novo ficam na mesma transação, com uma guarda por
    subquery no próprio INSERT — nunca um SELECT seguido de um INSERT
    incondicional em conexões/commits separados. Duas aberturas concorrentes
    (duplo clique, dois operadores) nunca criam dois caixas 'Aberto'
    simultâneos: só uma reivindica a linha (rowcount==1) e grava o
    lançamento inicial de saldo na mesma transação; a outra vê rowcount==0 e
    aborta sem deixar caixa aberto sem lançamento inicial (efeito parcial)."""
    data_ini = datetime.now().strftime("%d/%m/%Y %H:%M")
    valor_inicial = float(valor_inicial or 0)
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            INSERT INTO caixa_diario (data_abertura, saldo_inicial, status, operador)
            SELECT ?, ?, 'Aberto', ?
            WHERE NOT EXISTS (SELECT 1 FROM caixa_diario WHERE status='Aberto')
            """,
            (data_ini, valor_inicial, operador),
        )
        if cur.rowcount != 1:
            raise ValueError("Ja existe um caixa aberto. Feche o caixa atual antes de abrir outro.")
        cx_id = cur.lastrowid
        cur.execute(
            "INSERT INTO fluxo_caixa (tipo, descricao, valor, data_hora, caixa_id, forma_pagamento) VALUES (?,?,?,?,?,?)",
            ("Entrada", descricao, valor_inicial, data_ini, cx_id, "Dinheiro"),
        )
        registrar_auditoria(conn, "caixa", cx_id, "abrir", operador, depois={"saldo_inicial": valor_inicial})
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
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
    alvo = normalizar_forma_caixa(forma)
    res = query_db("SELECT tipo, valor, forma_pagamento, descricao FROM fluxo_caixa WHERE caixa_id=?", (caixa_id,))
    total = Decimal("0.00")
    for tipo, valor, forma_pagamento, descricao in res or []:
        forma_linha = normalizar_forma_caixa(forma_pagamento or descricao or "")
        if forma_linha != alvo:
            continue
        valor = _centavos(valor)
        if str(tipo or "").lower() in ("saida", "saída"):
            total -= valor
        else:
            total += valor
    return float(total)


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
    entradas = _centavos(_soma_fluxo(cx_id, "Entrada"))
    saidas = _centavos(_soma_fluxo(cx_id, "Saida")) + _centavos(_soma_fluxo(cx_id, "Saída"))
    saldo = entradas - saidas

    pix = _centavos(_saldo_por_forma(cx_id, "Pix"))
    debito = _centavos(_saldo_por_forma(cx_id, "Debito"))
    credito_1x = _centavos(_saldo_por_forma(cx_id, "Credito 1x"))
    credito_2x = _centavos(_saldo_por_forma(cx_id, "Credito 2x"))
    credito_3x = _centavos(_saldo_por_forma(cx_id, "Credito 3x"))

    pix += _centavos(_fallback_antigo(cx_id, "%(Pix)%"))
    debito += _centavos(_fallback_antigo(cx_id, "%(Debito)%")) + _centavos(_fallback_antigo(cx_id, "%(Débito)%"))
    credito_1x += _centavos(_fallback_antigo(cx_id, "%(Credito 1x)%")) + _centavos(_fallback_antigo(cx_id, "%(Crédito 1x)%"))
    credito_2x += _centavos(_fallback_antigo(cx_id, "%(Credito 2x)%")) + _centavos(_fallback_antigo(cx_id, "%(Crédito 2x)%"))
    credito_3x += _centavos(_fallback_antigo(cx_id, "%(Credito 3x)%")) + _centavos(_fallback_antigo(cx_id, "%(Crédito 3x)%"))

    credito_total = credito_1x + credito_2x + credito_3x
    dinheiro = saldo - pix - debito - credito_total

    formas_detalhadas = {
        "Dinheiro": float(dinheiro),
        "Pix": float(pix),
        "Debito": float(debito),
        "Credito 1x": float(credito_1x),
        "Credito 2x": float(credito_2x),
        "Credito 3x": float(credito_3x),
    }
    formas = dict(formas_detalhadas)
    formas["Credito"] = float(credito_total)

    return {"caixa_id": cx_id, "entradas": float(entradas), "saidas": float(saidas), "saldo": float(saldo), "formas": formas, "formas_detalhadas": formas_detalhadas}


def _reivindicar_fechamento_cursor(cur, caixa_id):
    """Reivindica atomicamente a transição do caixa para 'Fechado'.

    A checagem (caixa ainda aberto) e a escrita (marca Fechado) acontecem
    no mesmo UPDATE, com guarda no próprio WHERE — nunca um SELECT de
    status seguido de um UPDATE incondicional. Isso dá um ponto de corte
    determinístico para a corrida entre um fechamento de caixa e um
    estorno concorrente (services.venda_service.cancelar_venda_service):
    ou o estorno reivindica seu UPDATE em vendas antes deste claim vencer
    — e o lançamento de saída entra no caixa antes dele fechar —, ou este
    claim vence primeiro e o estorno, ao checar 'status=Aberto' do caixa
    dentro da própria transação, vê 'Fechado' e aborta (rollback) em vez
    de lançar valor num caixa já encerrado. Nunca os dois half-completam."""
    cur.execute("UPDATE caixa_diario SET status='Fechado' WHERE id=? AND status='Aberto'", (caixa_id,))
    return cur.rowcount


def fechar_caixa_conferido(caixa_id, saldo, formas, informado):
    formas = formas or {}
    informado = informado or {}
    credito_sistema = formas.get("Credito", None)
    if credito_sistema is None:
        credito_sistema = float(sum((_centavos(formas.get(f, 0.0)) for f in ("Credito 1x", "Credito 2x", "Credito 3x")), Decimal("0.00")))
    credito_informado = informado.get("Credito", None)
    if credito_informado is None:
        credito_informado = float(sum((_centavos(informado.get(f, 0.0)) for f in ("Credito 1x", "Credito 2x", "Credito 3x")), Decimal("0.00")))

    total_sistema = _centavos(formas.get("Dinheiro", 0.0)) + _centavos(formas.get("Pix", 0.0)) + _centavos(formas.get("Debito", 0.0)) + _centavos(credito_sistema)
    total_informado = _centavos(informado.get("Dinheiro", 0.0)) + _centavos(informado.get("Pix", 0.0)) + _centavos(informado.get("Debito", 0.0)) + _centavos(credito_informado)
    diferenca = float(total_informado - total_sistema)

    conn = get_connection()
    cur = conn.cursor()
    try:
        if _reivindicar_fechamento_cursor(cur, caixa_id) != 1:
            raise ValueError("Caixa ja esta fechado.")
        cur.execute(
            """
            UPDATE caixa_diario
            SET data_fechamento=?, saldo_final=?, dinheiro_sistema=?, pix_sistema=?, debito_sistema=?, credito_sistema=?, dinheiro_informado=?, pix_informado=?, debito_informado=?, credito_informado=?, diferenca_caixa=?
            WHERE id=?
            """,
            (datetime.now().strftime("%d/%m/%Y %H:%M"), saldo, formas.get("Dinheiro", 0.0), formas.get("Pix", 0.0), formas.get("Debito", 0.0), credito_sistema, informado.get("Dinheiro", 0.0), informado.get("Pix", 0.0), informado.get("Debito", 0.0), credito_informado, diferenca, caixa_id),
        )
        registrar_auditoria(conn, "caixa", caixa_id, "fechar_conferido", depois={"saldo_final": saldo, "formas_sistema": formas, "formas_informado": informado, "diferenca": diferenca})
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    return diferenca


def fechar_caixa_simples(caixa_id, saldo):
    conn = get_connection()
    cur = conn.cursor()
    try:
        if _reivindicar_fechamento_cursor(cur, caixa_id) != 1:
            raise ValueError("Caixa ja esta fechado.")
        cur.execute(
            "UPDATE caixa_diario SET data_fechamento=?, saldo_final=? WHERE id=?",
            (datetime.now().strftime("%d/%m/%Y %H:%M"), saldo, caixa_id),
        )
        registrar_auditoria(conn, "caixa", caixa_id, "fechar_simples", depois={"saldo_final": saldo})
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def lancar_fluxo(tipo, descricao, valor, caixa_id, rotulo=None, forma_pagamento=None):
    """Lança sangria/reforço no caixa aberto. A checagem de que o caixa
    informado segue 'Aberto' e o INSERT do lançamento acontecem na mesma
    transação (subquery no próprio INSERT + rowcount), para que um
    fechamento de caixa concorrente nunca fique com um lançamento gravado
    depois que o caixa já foi marcado 'Fechado' (mesma classe de corrida já
    fechada em cancelar_venda_service/fechar_caixa_*)."""
    if not caixa_id:
        raise ValueError("Abra o caixa antes de fazer lançamentos.")
    rotulo = rotulo or ("Reforco de caixa" if tipo == "Entrada" else "Sangria")
    forma_pagamento = normalizar_forma_caixa(forma_pagamento) if forma_pagamento else forma_pagamento
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            INSERT INTO fluxo_caixa (tipo, descricao, valor, data_hora, data_iso, caixa_id, forma_pagamento)
            SELECT ?, ?, ?, ?, ?, ?, ?
            WHERE EXISTS (SELECT 1 FROM caixa_diario WHERE id=? AND status='Aberto')
            """,
            (tipo, f"{rotulo}: {descricao}", float(valor or 0), datetime.now().strftime("%d/%m/%Y %H:%M"), datetime.now().strftime("%Y-%m-%d %H:%M:%S"), caixa_id, forma_pagamento, caixa_id),
        )
        if cur.rowcount != 1:
            raise ValueError("O caixa foi fechado durante a operação; lançamento cancelado. Reabra o caixa e tente novamente.")
        registrar_auditoria(conn, "caixa", caixa_id, "lancar_fluxo", depois={"tipo": tipo, "rotulo": rotulo, "valor": float(valor or 0)})
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def listar_fluxo(caixa_id=None):
    if caixa_id:
        return query_db("SELECT tipo, descricao, valor, data_hora FROM fluxo_caixa WHERE caixa_id=? ORDER BY id DESC", (caixa_id,))
    return query_db("SELECT tipo, descricao, valor, data_hora FROM fluxo_caixa ORDER BY id DESC LIMIT 50")


def salvar_conta(descricao, valor, vencimento, categoria):
    query_db("INSERT INTO contas_a_pagar (descricao, valor, data_vencimento, categoria, status) VALUES (?,?,?,?,?)", (descricao, float(valor or 0), vencimento, categoria, "Pendente"), commit=True)


def listar_contas(status=None):
    if status:
        return query_db("SELECT id, descricao, valor, data_vencimento, categoria, status FROM contas_a_pagar WHERE status=? ORDER BY data_vencimento ASC, id DESC", (status,))
    return query_db("SELECT id, descricao, valor, data_vencimento, categoria, status FROM contas_a_pagar ORDER BY data_vencimento ASC, id DESC")


def obter_conta(conta_id):
    res = query_db("SELECT id, descricao, valor, data_vencimento, categoria, status FROM contas_a_pagar WHERE id=?", (conta_id,))
    return res[0] if res else None


def marcar_conta_paga(conta_id, caixa_id=None, operador="Sistema"):
    """Marca uma conta a pagar como paga e lança a saída correspondente no
    caixa, de forma atômica: a reivindicação do pagamento (UPDATE com guarda
    de status no WHERE, checado por rowcount) e o lançamento da saída no
    caixa acontecem na mesma transação/conexão. Duas chamadas concorrentes
    (duplo clique, dois operadores) para a mesma conta nunca decidem com
    base no mesmo estado "antigo": só uma reivindica (rowcount==1) e lança a
    saída; a outra vê rowcount==0 e retorna sem repetir o lançamento
    financeiro."""
    conta = obter_conta(conta_id)
    if not conta:
        raise ValueError("Conta nao localizada.")
    _, descricao, valor, vencimento, categoria, status = conta
    valor = float(valor or 0)
    cx_id = caixa_id or obter_caixa_id_ativo()

    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("UPDATE contas_a_pagar SET status='Paga' WHERE id=? AND status!='Paga'", (conta_id,))
        if cur.rowcount != 1:
            conn.rollback()
            return True

        if cx_id:
            cur.execute(
                """
                INSERT INTO fluxo_caixa (tipo, descricao, valor, data_hora, data_iso, caixa_id, forma_pagamento)
                SELECT 'Saida', ?, ?, ?, ?, ?, 'Dinheiro'
                WHERE EXISTS (SELECT 1 FROM caixa_diario WHERE id=? AND status='Aberto')
                """,
                (f"Conta a pagar: Conta paga: {descricao}", valor, datetime.now().strftime("%d/%m/%Y %H:%M"), datetime.now().strftime("%Y-%m-%d %H:%M:%S"), cx_id, cx_id),
            )
            if cur.rowcount != 1:
                raise ValueError("O caixa foi fechado durante a operação; pagamento cancelado. Reabra o caixa e tente novamente.")

        registrar_auditoria(conn, "conta_a_pagar", conta_id, "marcar_paga", operador, depois={"valor": valor, "caixa_id": cx_id})
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    return True


def excluir_conta(conta_id):
    conta = obter_conta(conta_id)
    if not conta:
        return False
    query_db("DELETE FROM contas_a_pagar WHERE id=?", (conta_id,), commit=True)
    return True
