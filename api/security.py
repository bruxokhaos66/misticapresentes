"""Autenticação simples para a API local.

A API nasce para rede local e painel somente leitura. Para produção externa,
use VPN/Tailscale/Cloudflare Tunnel e defina um token forte por variável de
ambiente.
"""
from __future__ import annotations

import hmac
import os
from fastapi import Header, HTTPException, Request, status

MIN_TOKEN_FORTE = 12
APP_SESSION_COOKIE = "mistica_app_sessao"
METODOS_MUTAVEIS = {"POST", "PUT", "PATCH", "DELETE"}


def api_token_configurado() -> str | None:
    token = os.getenv("MISTICA_API_TOKEN", "").strip()
    return token or None


def token_padrao_em_uso() -> bool:
    return False


def token_forte_configurado() -> bool:
    token = api_token_configurado()
    if not token:
        return False
    return len(token) >= MIN_TOKEN_FORTE


def resumo_seguranca_api() -> dict:
    return {
        "token_padrao_em_uso": token_padrao_em_uso(),
        "token_forte_configurado": token_forte_configurado(),
        "modo_recomendado": "Token forte por MISTICA_API_TOKEN para uso externo.",
    }


def validar_token_valor(token_recebido: str | None) -> bool:
    esperado = api_token_configurado()
    if not esperado:
        return False
    return hmac.compare_digest(str(token_recebido or ""), str(esperado))


def validar_token(x_mistica_token: str | None = Header(default=None)):
    if not validar_token_valor(x_mistica_token):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token da API ausente ou inválido.",
        )
    return True


def _origens_permitidas() -> list[str]:
    padrao = "" if os.environ.get("APP_ENV", "").strip().lower() == "production" else "http://localhost,http://127.0.0.1"
    configurado = os.getenv("MISTICA_ALLOWED_ORIGINS", padrao).strip()
    return [origem.strip() for origem in configurado.split(",") if origem.strip()]


def validar_origem_csrf(request: Request) -> None:
    """Defesa em profundidade para as rotas de sessão do app (cookie
    HttpOnly + SameSite=Lax): rejeita mutações cuja Origin/Referer não bate
    com um domínio conhecido nosso, caso algum navegador ignore SameSite."""
    if request.method not in METODOS_MUTAVEIS:
        return
    permitidas = _origens_permitidas()
    if not permitidas:
        return
    origem = request.headers.get("origin") or ""
    if not origem:
        referer = request.headers.get("referer") or ""
        origem = referer.split("/", 3)[0] + "//" + referer.split("/", 3)[2] if referer.count("/") >= 2 else ""
    if origem not in permitidas:
        raise HTTPException(status_code=403, detail="Origem da requisição não permitida.")
