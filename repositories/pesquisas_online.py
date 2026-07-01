import json
from datetime import datetime
from database import query_db


def salvar(consulta, resultados, usuario="Sistema", confirmado=0):
    query_db(
        "INSERT INTO pesquisas_online (consulta, resultados, usuario, data_hora, confirmado) VALUES (?,?,?,?,?)",
        (consulta, json.dumps(resultados, ensure_ascii=False), usuario, datetime.now().strftime("%d/%m/%Y %H:%M:%S"), int(confirmado)),
        commit=True,
    )


def listar(limite=30):
    return query_db("SELECT id, consulta, resultados, usuario, data_hora, confirmado FROM pesquisas_online ORDER BY id DESC LIMIT ?", (int(limite),))
