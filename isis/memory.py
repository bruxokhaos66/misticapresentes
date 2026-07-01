import json
from datetime import datetime
from database import query_db


def carregar_aprendizado():
    conversas = query_db("SELECT pergunta, resposta, data_hora FROM isis_memoria WHERE tipo='conversa' ORDER BY id DESC LIMIT 100")
    conhecimentos_rows = query_db("SELECT chave, valor, data_hora FROM isis_memoria WHERE tipo='conhecimento' ORDER BY id DESC LIMIT 300")
    pesquisas = query_db("SELECT consulta, resultados, data_hora FROM pesquisas_online ORDER BY id DESC LIMIT 50")
    conhecimentos = {c[0]: {"valor": c[1], "data_hora": c[2]} for c in conhecimentos_rows}
    return {"conversas": conversas, "conhecimentos": conhecimentos, "pesquisas": pesquisas}


def salvar_aprendizado(dados, usuario="Sistema"):
    for chave, info in (dados.get("conhecimentos", {}) if isinstance(dados, dict) else {}).items():
        valor = info.get("valor", info) if isinstance(info, dict) else info
        query_db("INSERT INTO isis_memoria (tipo, chave, valor, usuario, data_hora) VALUES (?,?,?,?,?)", ("conhecimento", chave, str(valor), usuario, datetime.now().strftime("%d/%m/%Y %H:%M:%S")), commit=True)


def registrar_conversa(pergunta, resposta, usuario="Sistema"):
    query_db("INSERT INTO isis_memoria (tipo, pergunta, resposta, usuario, data_hora) VALUES (?,?,?,?,?)", ("conversa", pergunta, resposta, usuario, datetime.now().strftime("%d/%m/%Y %H:%M:%S")), commit=True)


def registrar_pesquisa(consulta, resultados, usuario="Sistema"):
    query_db("INSERT INTO pesquisas_online (consulta, resultados, usuario, data_hora, confirmado) VALUES (?,?,?,?,?)", (consulta, json.dumps(resultados, ensure_ascii=False), usuario, datetime.now().strftime("%d/%m/%Y %H:%M:%S"), 1), commit=True)


def importar_json_para_sqlite(caminho, usuario="Sistema"):
    try:
        with open(caminho, "r", encoding="utf-8") as f:
            dados = json.load(f)
    except Exception:
        return 0
    total = 0
    for chave, info in dados.get("conhecimentos", {}).items():
        valor = info.get("valor", info) if isinstance(info, dict) else info
        query_db("INSERT INTO isis_memoria (tipo, chave, valor, usuario, data_hora) VALUES (?,?,?,?,?)", ("conhecimento", chave, str(valor), usuario, datetime.now().strftime("%d/%m/%Y %H:%M:%S")), commit=True)
        total += 1
    return total
