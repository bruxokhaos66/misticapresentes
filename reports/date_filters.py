from datetime import datetime, timedelta


def intervalo_dia(data=None):
    data = data or datetime.now()
    inicio = data.replace(hour=0, minute=0, second=0, microsecond=0)
    fim = inicio + timedelta(days=1)
    return inicio.strftime("%Y-%m-%d %H:%M:%S"), fim.strftime("%Y-%m-%d %H:%M:%S")


def intervalo_mes(mes=None, ano=None):
    agora = datetime.now()
    mes = int(mes or agora.strftime("%m"))
    ano = int(ano or agora.strftime("%Y"))
    inicio = datetime(ano, mes, 1)
    if mes == 12:
        fim = datetime(ano + 1, 1, 1)
    else:
        fim = datetime(ano, mes + 1, 1)
    return inicio.strftime("%Y-%m-%d %H:%M:%S"), fim.strftime("%Y-%m-%d %H:%M:%S")


def filtro_data_iso_sql(coluna="data_iso"):
    return f"COALESCE({coluna}, '') >= ? AND COALESCE({coluna}, '') < ?"


def intervalo_por_filtro_texto(filtro):
    """Converte filtros usados na interface para intervalo data_iso quando possível.

    Aceita:
    - DD/MM/AAAA
    - /MM/AAAA
    - MM/AAAA
    """
    filtro = str(filtro or "").strip()
    for fmt in ("%d/%m/%Y",):
        try:
            data = datetime.strptime(filtro, fmt)
            return intervalo_dia(data)
        except Exception:
            pass

    texto_mes = filtro[1:] if filtro.startswith("/") else filtro
    try:
        data = datetime.strptime("01/" + texto_mes, "%d/%m/%Y")
        return intervalo_mes(data.month, data.year)
    except Exception:
        return None
