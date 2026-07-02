"""Autenticação simples para a API local.

A API nasce para rede local e painel somente leitura. Para produção externa,
use VPN/Tailscale/Cloudflare Tunnel e defina um token forte por variável de
ambiente.
"""
from __future__ import annotations

import hmac
import os
from fastapi import Header, HTTPException, status

DEFAULT_LOCAL_TOKEN = "mistica-local"
MIN_TOKEN_FORTE = 12


def api_token_configurado() -> str:
    return os.getenv("MISTICA_API_TOKEN", DEFAULT_LOCAL_TOKEN)


def token_padrao_em_uso() -> bool:
    return api_token_configurado() == DEFAULT_LOCAL_TOKEN


def token_forte_configurado() -> bool:
    token = api_token_configurado()
    if not token or token == DEFAULT_LOCAL_TOKEN:
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
        return True
    return hmac.compare_digest(str(token_recebido or ""), str(esperado))


def validar_token(x_mistica_token: str | None = Header(default=None)):
    if not validar_token_valor(x_mistica_token):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token da API ausente ou inválido.",
        )
    return True
