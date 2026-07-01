import json
from repositories import isis_memoria


def _usuario(usuario):
    if isinstance(usuario, dict):
        return usuario.get("login") or usuario.get("nome") or "Sistema"
    return "Sistema"


def salvar_pendente(usuario, acao):
    isis_memoria.lembrar("acao_pendente:" + _usuario(usuario), json.dumps(acao, ensure_ascii=False), "acao_pendente", _usuario(usuario))


def obter_pendente(usuario):
    valor = isis_memoria.buscar("acao_pendente:" + _usuario(usuario), "acao_pendente")
    if not valor:
        return None
    try:
        data = json.loads(valor)
        return data if data else None
    except Exception:
        return None


def limpar_pendente(usuario):
    salvar_pendente(usuario, {})
