import json
import urllib.request

from config import API_URL
from database import query_db


def listar_usuarios_para_sync():
    rows = query_db(
        """
        SELECT nome, login, senha_hash, senha_salt, perfil, COALESCE(ativo,1) AS ativo
        FROM usuarios
        WHERE COALESCE(login,'')!='' AND COALESCE(senha_hash,'')!=''
        """
    ) or []
    return [
        {
            "nome": r[0] or r[1],
            "login": r[1],
            "senha_hash": r[2],
            "senha_salt": r[3] or "mistica_presentes",
            "perfil": r[4] or "vendedor",
            "ativo": int(r[5] or 0),
        }
        for r in rows
    ]


def sincronizar_usuarios_com_api(timeout=10):
    usuarios = listar_usuarios_para_sync()
    if not usuarios:
        return {"status": "sem_usuarios", "usuarios_sincronizados": 0}
    url = (API_URL or "https://api.misticaesotericos.com.br").rstrip("/") + "/api/sync/usuarios"
    dados = json.dumps({"usuarios": usuarios}, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(url, data=dados, headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        texto = resp.read().decode("utf-8", errors="ignore")
    return json.loads(texto)
