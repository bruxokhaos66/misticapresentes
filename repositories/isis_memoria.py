from datetime import datetime
from database import query_db


def lembrar(chave, valor, categoria="geral", usuario="Sistema"):
    agora = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    existente = query_db("SELECT id FROM isis_memoria WHERE chave=? AND COALESCE(categoria,'geral')=? ORDER BY id DESC LIMIT 1", (chave, categoria))
    if existente:
        query_db("UPDATE isis_memoria SET valor=?, usuario=?, data_atualizacao=?, data_hora=? WHERE id=?", (valor, usuario, agora, agora, existente[0][0]), commit=True)
    else:
        query_db("INSERT INTO isis_memoria (tipo, chave, valor, categoria, usuario, data_hora, data_atualizacao) VALUES (?,?,?,?,?,?,?)", ("memoria", chave, valor, categoria, usuario, agora, agora), commit=True)


def buscar(chave, categoria="geral"):
    res = query_db("SELECT valor FROM isis_memoria WHERE chave=? AND COALESCE(categoria,'geral')=? ORDER BY id DESC LIMIT 1", (chave, categoria))
    return res[0][0] if res else None


def listar(categoria=None, limite=50):
    if categoria:
        return query_db("SELECT chave, valor, categoria, data_atualizacao FROM isis_memoria WHERE COALESCE(categoria,'geral')=? ORDER BY id DESC LIMIT ?", (categoria, int(limite)))
    return query_db("SELECT chave, valor, categoria, data_atualizacao FROM isis_memoria ORDER BY id DESC LIMIT ?", (int(limite),))
