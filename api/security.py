"""Autenticação simples para a API local.

A API nasce para rede local e painel somente leitura. Para produção externa,
use VPN/Tailscale/Cloudflare Tunnel e defina um token forte por variável de
ambiente.
"""
import os
from fastapi import Header, HTTPException, status

DEFAULT_LOCAL_TOKEN = "mistica-local"


def api_token_configurado() -> str:
    return os.getenv("MISTICA_API_TOKEN", DEFAULT_LOCAL_TOKEN)


def validar_token(x_mistica_token: str | None = Header(default=None)):
    esperado = api_token_configurado()
    if not esperado:
        return True
    if x_mistica_token != esperado:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token da API ausente ou inválido.",
        )
    return True
