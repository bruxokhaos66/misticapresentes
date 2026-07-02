from datetime import datetime, timedelta
import secrets


ACOES_CRITICAS = {
    "cancelar_venda": "cancelar uma venda",
    "estornar_venda": "estornar uma venda",
    "excluir_conta": "excluir uma conta",
    "pagar_conta": "marcar uma conta como paga",
    "reparar_banco": "reparar o banco de dados",
    "remover_demo": "remover dados de demonstração",
    "backup": "gerar backup manual",
}

_confirmacoes_pendentes = {}


def acao_exige_confirmacao(acao):
    return acao in ACOES_CRITICAS


def solicitar_confirmacao(acao, detalhes="", usuario="Sistema"):
    if not acao_exige_confirmacao(acao):
        return {"confirmado": True, "token": None, "mensagem": "Ação não crítica."}
    token = secrets.token_hex(3).upper()
    expira = datetime.now() + timedelta(minutes=10)
    _confirmacoes_pendentes[token] = {
        "acao": acao,
        "detalhes": detalhes,
        "usuario": usuario,
        "expira": expira,
    }
    descricao = ACOES_CRITICAS.get(acao, acao)
    return {
        "confirmado": False,
        "token": token,
        "mensagem": (
            f"Confirmação necessária para {descricao}.\n"
            f"Detalhes: {detalhes or 'sem detalhes'}\n"
            f"Para confirmar, informe o código: {token}\n"
            "Este código expira em 10 minutos."
        ),
    }


def confirmar_acao(token, acao=None):
    token = str(token or "").strip().upper()
    dados = _confirmacoes_pendentes.get(token)
    if not dados:
        return False, "Código de confirmação não localizado."
    if dados["expira"] < datetime.now():
        _confirmacoes_pendentes.pop(token, None)
        return False, "Código de confirmação expirado."
    if acao and dados["acao"] != acao:
        return False, "Código não pertence a esta ação."
    _confirmacoes_pendentes.pop(token, None)
    return True, "Ação confirmada."


def limpar_confirmacoes_expiradas():
    agora = datetime.now()
    expirados = [token for token, dados in _confirmacoes_pendentes.items() if dados["expira"] < agora]
    for token in expirados:
        _confirmacoes_pendentes.pop(token, None)
    return len(expirados)
