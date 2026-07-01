from datetime import datetime
from database import query_db


def registrar(comando_recebido, acao_detectada, usuario="", resultado="", erro=""):
    query_db(
        "INSERT INTO isis_logs (comando_recebido, acao_detectada, usuario, resultado, erro, data_hora) VALUES (?,?,?,?,?,?)",
        (comando_recebido, acao_detectada, usuario, str(resultado)[:1500], str(erro)[:1500], datetime.now().strftime("%d/%m/%Y %H:%M:%S")),
        commit=True,
    )
