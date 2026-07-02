from __future__ import annotations

import hmac
import os
import secrets
from datetime import datetime, timedelta

from config import hash_password_pbkdf2
from database import query_db

SESSOES_APP = {}
DURACAO_SESSAO_HORAS = 12
SENHA_MINIMA_APP = 4


def _agora_txt() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _dt_txt(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def _parse_dt(valor: str | None) -> datetime | None:
    try:
        return datetime.strptime(str(valor or ""), "%Y-%m-%d %H:%M:%S")
    except Exception:
        return None


def _garantir_tabela_sessoes() -> None:
    try:
        query_db(
            """
            CREATE TABLE IF NOT EXISTS app_sessoes (
                sessao TEXT PRIMARY KEY,
                login TEXT,
                nome TEXT,
                perfil TEXT,
                criada_em TEXT,
                expira_em TEXT,
                ultimo_acesso TEXT
            )
            """,
            commit=True,
        )
    except Exception:
        pass


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
        fallback_salt = os.getenv("MISTICA_PASSWORD_SALT", "").strip()
        calculado = hash_password_pbkdf2(senha_digitada, fallback_salt.encode("utf-8") if fallback_salt else None)
    return hmac.compare_digest(str(calculado), str(senha_hash))


def _limpar_sessoes_expiradas() -> None:
    _garantir_tabela_sessoes()
    agora = datetime.now()
    expiradas = [token for token, dados in SESSOES_APP.items() if dados.get("expira_em") <= agora]
    for token in expiradas:
        SESSOES_APP.pop(token, None)
    try:
        query_db("DELETE FROM app_sessoes WHERE expira_em < ?", (_agora_txt(),), commit=True)
    except Exception:
        pass


def login_app(login: str, senha: str) -> dict:
    _limpar_sessoes_expiradas()
    login = str(login or "").strip().lower()
    senha = str(senha or "")
    if not login or not senha:
        return {"ok": False, "erro": "Informe login e senha."}
    if len(senha) < SENHA_MINIMA_APP:
        return {"ok": False, "erro": "A senha precisa ter no mínimo 4 dígitos/caracteres."}

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
    expira_em = datetime.now() + timedelta(hours=DURACAO_SESSAO_HORAS)
    SESSOES_APP[sessao] = {
        "login": login_db,
        "nome": nome,
        "perfil": perfil_norm,
        "expira_em": expira_em,
    }
    try:
        query_db(
            "INSERT OR REPLACE INTO app_sessoes (sessao, login, nome, perfil, criada_em, expira_em, ultimo_acesso) VALUES (?,?,?,?,?,?,?)",
            (sessao, login_db, nome, perfil_norm, _agora_txt(), _dt_txt(expira_em), _agora_txt()),
            commit=True,
        )
    except Exception:
        pass
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
    token = str(sessao)
    dados = SESSOES_APP.get(token)
    if not dados:
        try:
            linhas = query_db(
                "SELECT login, nome, perfil, expira_em FROM app_sessoes WHERE sessao=?",
                (token,),
            )
            if linhas:
                login, nome, perfil, expira_txt = linhas[0]
                expira_dt = _parse_dt(expira_txt)
                if expira_dt and expira_dt > datetime.now():
                    dados = {"login": login, "nome": nome, "perfil": perfil, "expira_em": expira_dt}
                    SESSOES_APP[token] = dados
        except Exception:
            dados = None
    if not dados:
        return None
    nova_expiracao = datetime.now() + timedelta(hours=DURACAO_SESSAO_HORAS)
    dados["expira_em"] = nova_expiracao
    try:
        query_db(
            "UPDATE app_sessoes SET expira_em=?, ultimo_acesso=? WHERE sessao=?",
            (_dt_txt(nova_expiracao), _agora_txt(), token),
            commit=True,
        )
    except Exception:
        pass
    return dados


def logout_app(sessao: str | None) -> dict:
    if sessao:
        token = str(sessao)
        SESSOES_APP.pop(token, None)
        try:
            query_db("DELETE FROM app_sessoes WHERE sessao=?", (token,), commit=True)
        except Exception:
            pass
    return {"ok": True}
