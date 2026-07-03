from datetime import datetime, time, timedelta

HORARIO_FECHAMENTO_VENDAS = time(23, 0, 0)


def inicio_dia_operacional(agora=None):
    """Retorna o início do período usado para o indicador Vendas Hoje.

    Regra da loja:
    - das 00:00 até 22:59, Vendas Hoje mostra as vendas do dia civil atual;
    - a partir das 23:00, o indicador zera e começa o próximo período de vendas.
    """
    agora = agora or datetime.now()
    inicio = datetime.combine(agora.date(), time.min)
    if agora.time() >= HORARIO_FECHAMENTO_VENDAS:
        inicio = datetime.combine(agora.date(), HORARIO_FECHAMENTO_VENDAS)
    return inicio


def fim_dia_operacional(agora=None):
    agora = agora or datetime.now()
    inicio = inicio_dia_operacional(agora)
    if inicio.time() == HORARIO_FECHAMENTO_VENDAS:
        return datetime.combine((inicio + timedelta(days=1)).date(), HORARIO_FECHAMENTO_VENDAS)
    return datetime.combine(inicio.date(), HORARIO_FECHAMENTO_VENDAS)


def etiqueta_dia_operacional(moment=None):
    """Etiqueta salva na venda para indicar a qual dia/período ela pertence."""
    moment = moment or datetime.now()
    if moment.time() >= HORARIO_FECHAMENTO_VENDAS:
        dia_ref = moment.date() + timedelta(days=1)
    else:
        dia_ref = moment.date()
    return dia_ref.strftime("%d/%m/%Y")


def intervalo_vendas_hoje(agora=None):
    inicio = inicio_dia_operacional(agora)
    fim = fim_dia_operacional(agora)
    return inicio.strftime("%Y-%m-%d %H:%M:%S"), fim.strftime("%Y-%m-%d %H:%M:%S"), etiqueta_dia_operacional(agora)
