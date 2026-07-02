from __future__ import annotations

import hmac
import secrets
from datetime import datetime, timedelta

from config import hash_password_pbkdf2
from database import query_db

SESSOES_APP = {}
DURACAO_SESSAO_HORAS = 12


def _perfil_app(perfil: str | None) -> str:
    p = str(perfil or "").strip().lower()
    if p in {"adm", "admin", "administrador"}:
        return "adm"
    return "vendedor"


def _senha_confere(senha_digitada: str, senha_hash: str | None, senha_salt: str | None) -> bool:
    if not senha_digitada or not senha_hash:
        return False
    if senha_salt:
        calculado = hash_password_pbkdf2(senha_digitada, str(senha_salt).encode("utf-8"))
    else:
        calculado = hash_password_pbkdf2(senha_digitada)
    return hmac.compare_digest(str(calculado), str(senha_hash))


def _limpar_sessoes_expiradas() -> None:
    agora = datetime.now()
    expiradas = [token for token, dados in SESSOES_APP.items() if dados.get("expira_em") <= agora]
    for token in expiradas:
        SESSOES_APP.pop(token, None)


def login_app(login: str, senha: str) -> dict:
    _limpar_sessoes_expiradas()
    login = str(login or "").strip().lower()
    senha = str(senha or "")
    if not login or not senha:
        return {"ok": False, "erro": "Informe login e senha."}

    linhas = query_db(
        """
        SELECT nome, login, senha_hash, COALESCE(senha_salt,''), COALESCE(perfil,'vendedor'), COALESCE(ativo,1)
        FROM usuarios
        WHERE lower(login)=?
        """,
        (login,),
    )
    if not linhas:
        return {"ok": False, "erro": "Usuário ou senha incorretos."}

    nome, login_db, senha_hash, senha_salt, perfil, ativo = linhas[0]
    if int(ativo or 0) != 1 or not _senha_confere(senha, senha_hash, senha_salt):
        try:
            query_db(
                "INSERT INTO logs (usuario, acao, detalhes, data_hora) VALUES (?,?,?,?)",
                (login, "Login app", "Falha no login do app", datetime.now().strftime("%d/%m/%Y %H:%M:%S")),
                commit=True,
            )
        except Exception:
            pass
        return {"ok": False, "erro": "Usuário ou senha incorretos."}

    perfil_norm = _perfil_app(perfil)
    sessao = secrets.token_urlsafe(32)
    SESSOES_APP[sessao] = {
        "login": login_db,
        "nome": nome,
        "perfil": perfil_norm,
        "expira_em": datetime.now() + timedelta(hours=DURACAO_SESSAO_HORAS),
    }
    try:
        query_db(
            "INSERT INTO logs (usuario, acao, detalhes, data_hora) VALUES (?,?,?,?)",
            (nome, "Login app", f"Login no app como {perfil_norm}", datetime.now().strftime("%d/%m/%Y %H:%M:%S")),
            commit=True,
        )
    except Exception:
        pass
    return {
        "ok": True,
        "sessao": sessao,
        "usuario": {
            "nome": nome,
            "login": login_db,
            "perfil": perfil_norm,
        },
        "mensagem": "Login realizado com sucesso.",
    }


def validar_sessao_app(sessao: str | None) -> dict | None:
    _limpar_sessoes_expiradas()
    if not sessao:
        return None
    dados = SESSOES_APP.get(str(sessao))
    if not dados:
        return None
    dados["expira_em"] = datetime.now() + timedelta(hours=DURACAO_SESSAO_HORAS)
    return dados


def logout_app(sessao: str | None) -> dict:
    if sessao:
        SESSOES_APP.pop(str(sessao), None)
    return {"ok": True}
