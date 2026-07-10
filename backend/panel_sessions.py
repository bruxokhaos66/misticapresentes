from __future__ import annotations

import os
import secrets
from datetime import datetime, timedelta

from fastapi import Cookie, Depends, Header, HTTPException, Request, Response

from backend.database import conectar
from backend.rate_limit import _client_ip

COOKIE_NOME = "mistica_painel_sessao"
DURACAO_MAXIMA_HORAS = 12
INATIVIDADE_MAXIMA_MINUTOS = 30


def _agora() -> datetime:
    return datetime.now()


def _txt(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def _parse(valor: str | None) -> datetime | None:
    try:
        return datetime.strptime(str(valor or ""), "%Y-%m-%d %H:%M:%S")
    except Exception:
        return None


def registrar_tentativa_login(login: str, request: Request, sucesso: bool) -> None:
    """Registra IP, dispositivo (user-agent) e resultado de cada tentativa de login no painel."""
    try:
        with conectar() as conn:
            conn.execute(
                "INSERT INTO painel_login_tentativas (login, ip, user_agent, sucesso, data_hora) VALUES (?,?,?,?,?)",
                (
                    login,
                    _client_ip(request),
                    str(request.headers.get("user-agent", ""))[:255],
                    1 if sucesso else 0,
                    _txt(_agora()),
                ),
            )
    except Exception:
        pass


def limpar_sessoes_expiradas() -> None:
    try:
        with conectar() as conn:
            conn.execute("DELETE FROM painel_sessoes WHERE expira_em < ?", (_txt(_agora()),))
    except Exception:
        pass


def criar_sessao(usuario: dict, perfil: str, request: Request, response: Response) -> str:
    """Cria uma sessão de painel armazenada no servidor e devolve o token via cookie HttpOnly/Secure/SameSite."""
    limpar_sessoes_expiradas()
    token = secrets.token_urlsafe(32)
    agora = _agora()
    expira = agora + timedelta(minutes=INATIVIDADE_MAXIMA_MINUTOS)
    ip = _client_ip(request)
    user_agent = str(request.headers.get("user-agent", ""))[:255]
    with conectar() as conn:
        conn.execute(
            """
            INSERT INTO painel_sessoes
                (token, usuario_id, login, nome, perfil, ip, user_agent, criada_em, expira_em, ultimo_acesso)
            VALUES (?,?,?,?,?,?,?,?,?,?)
            """,
            (
                token,
                usuario.get("id"),
                usuario.get("login"),
                usuario.get("nome"),
                perfil,
                ip,
                user_agent,
                _txt(agora),
                _txt(expira),
                _txt(agora),
            ),
        )
    response.set_cookie(
        key=COOKIE_NOME,
        value=token,
        httponly=True,
        secure=request.url.scheme == "https",
        samesite="lax",
        max_age=DURACAO_MAXIMA_HORAS * 3600,
        path="/",
    )
    return token


def validar_sessao(token: str | None) -> dict | None:
    """Valida a sessão no servidor, aplicando expiração absoluta e por inatividade (sliding window)."""
    if not token:
        return None
    limpar_sessoes_expiradas()
    with conectar() as conn:
        linha = conn.execute("SELECT * FROM painel_sessoes WHERE token=?", (token,)).fetchone()
        if not linha:
            return None
        dados = dict(linha)
        agora = _agora()
        expira = _parse(dados.get("expira_em"))
        criada = _parse(dados.get("criada_em"))
        if not expira or expira < agora:
            conn.execute("DELETE FROM painel_sessoes WHERE token=?", (token,))
            return None
        if criada and (agora - criada) > timedelta(hours=DURACAO_MAXIMA_HORAS):
            conn.execute("DELETE FROM painel_sessoes WHERE token=?", (token,))
            return None
        nova_expiracao = agora + timedelta(minutes=INATIVIDADE_MAXIMA_MINUTOS)
        conn.execute(
            "UPDATE painel_sessoes SET expira_em=?, ultimo_acesso=? WHERE token=?",
            (_txt(nova_expiracao), _txt(agora), token),
        )
        dados["expira_em"] = _txt(nova_expiracao)
        return dados


def encerrar_sessao(token: str | None, response: Response) -> None:
    """Logout: apaga a sessão no servidor e remove o cookie do navegador."""
    if token:
        try:
            with conectar() as conn:
                conn.execute("DELETE FROM painel_sessoes WHERE token=?", (token,))
        except Exception:
            pass
    response.delete_cookie(COOKIE_NOME, path="/")


def sessao_atual(mistica_painel_sessao: str | None = Cookie(default=None)) -> dict:
    dados = validar_sessao(mistica_painel_sessao)
    if not dados:
        raise HTTPException(status_code=401, detail="Sessão inválida ou expirada. Faça login novamente.")
    return dados


def exigir_perfil(perfil_minimo: str = "vendedor"):
    """Dependência FastAPI para proteger rotas exigindo sessão válida (e perfil, quando informado)."""

    def dependencia(sessao: dict = Depends(sessao_atual)) -> dict:
        if perfil_minimo == "adm" and sessao.get("perfil") != "adm":
            raise HTTPException(status_code=403, detail="Acesso restrito a administradores.")
        return sessao

    return dependencia


def exigir_sessao_ou_chave_api(perfil_minimo: str = "vendedor"):
    """Dependência FastAPI que aceita a sessão de painel (uso pelo navegador) OU a chave
    estática MISTICA_SITE_API_KEY/MISTICA_SYNC_KEY (uso por integrações servidor-a-servidor).
    A chave nunca deve ser digitada ou guardada no navegador; ela fica apenas em segredos do
    servidor (Render/GitHub Secrets) e é usada por scripts de sincronização automatizados.
    """

    def dependencia(
        mistica_painel_sessao: str | None = Cookie(default=None),
        x_mistica_api_key: str | None = Header(default=None),
    ) -> dict:
        sessao = validar_sessao(mistica_painel_sessao)
        if sessao:
            if perfil_minimo == "adm" and sessao.get("perfil") != "adm":
                raise HTTPException(status_code=403, detail="Acesso restrito a administradores.")
            return sessao

        chave = os.environ.get("MISTICA_SITE_API_KEY", "").strip() or os.environ.get("MISTICA_SYNC_KEY", "").strip()
        if chave and x_mistica_api_key and secrets.compare_digest(str(x_mistica_api_key), chave):
            return {"perfil": "adm", "login": "integracao-api-key"}

        raise HTTPException(status_code=401, detail="Sessão inválida ou expirada. Faça login novamente.")

    return dependencia
