from datetime import datetime, timedelta

from database import query_db


MAX_TENTATIVAS = 5
BLOQUEIO_MINUTOS = 5


def registrar_tentativa_login(login, sucesso=False, bloqueado_ate=None):
    query_db(
        """
        INSERT INTO login_tentativas (login, sucesso, data_hora, bloqueado_ate)
        VALUES (?,?,?,?)
        """,
        (
            str(login or "").strip().lower() or "desconhecido",
            1 if sucesso else 0,
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            bloqueado_ate.strftime("%Y-%m-%d %H:%M:%S") if hasattr(bloqueado_ate, "strftime") else bloqueado_ate,
        ),
        commit=True,
    )


def bloqueio_ativo(login):
    login = str(login or "").strip().lower()
    if not login:
        return None
    res = query_db(
        """
        SELECT bloqueado_ate
        FROM login_tentativas
        WHERE login=? AND bloqueado_ate IS NOT NULL
        ORDER BY id DESC
        LIMIT 1
        """,
        (login,),
    )
    if not res or not res[0][0]:
        return None
    try:
        bloqueio = datetime.strptime(res[0][0], "%Y-%m-%d %H:%M:%S")
    except Exception:
        return None
    return bloqueio if bloqueio > datetime.now() else None


def falhas_recentes(login, minutos=BLOQUEIO_MINUTOS):
    desde = (datetime.now() - timedelta(minutes=minutos)).strftime("%Y-%m-%d %H:%M:%S")
    res = query_db(
        """
        SELECT COUNT(*)
        FROM login_tentativas
        WHERE login=? AND sucesso=0 AND data_hora>=?
        """,
        (str(login or "").strip().lower(), desde),
    )
    return int(res[0][0] or 0) if res else 0


def registrar_falha_login(login):
    tentativas = falhas_recentes(login) + 1
    bloqueado_ate = None
    if tentativas >= MAX_TENTATIVAS:
        bloqueado_ate = datetime.now() + timedelta(minutes=BLOQUEIO_MINUTOS)
    registrar_tentativa_login(login, sucesso=False, bloqueado_ate=bloqueado_ate)
    return bloqueado_ate


def registrar_sucesso_login(login):
    registrar_tentativa_login(login, sucesso=True)
