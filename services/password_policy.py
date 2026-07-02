import re


def validar_forca_senha(senha):
    """Retorna (ok, mensagem) para validar senha de usuários do sistema."""
    senha = str(senha or "")
    if len(senha) < 8:
        return False, "A senha precisa ter pelo menos 8 caracteres."
    if not re.search(r"[A-Za-zÀ-ÿ]", senha):
        return False, "A senha precisa ter pelo menos uma letra."
    if not re.search(r"\d", senha):
        return False, "A senha precisa ter pelo menos um número."
    if senha.lower() in {"admin123", "mistica123", "12345678", "senha123"}:
        return False, "Escolha uma senha menos óbvia."
    return True, "Senha segura."


def exigir_senha_forte(senha):
    ok, mensagem = validar_forca_senha(senha)
    if not ok:
        raise ValueError(mensagem)
    return True
