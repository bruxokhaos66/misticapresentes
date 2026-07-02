"""Segurança do servidor dedicado/cloud."""
from __future__ import annotations

import hashlib
import hmac
import os
from fastapi import Header, HTTPException, status

DEFAULT_ADMIN_TOKEN = ""


def hash_token(token: str) -> str:
    return hashlib.sha256(str(token or "").encode("utf-8")).hexdigest()


def comparar_token(token: str, token_hash: str) -> bool:
    return hmac.compare_digest(hash_token(token), str(token_hash or ""))


def admin_token() -> str:
    return os.getenv("MISTICA_CLOUD_ADMIN_TOKEN", DEFAULT_ADMIN_TOKEN).strip()


def exigir_admin(x_mistica_admin_token: str | None = Header(default=None)):
    esperado = admin_token()
    if not esperado or esperado == DEFAULT_ADMIN_TOKEN:
        raise HTTPException(status_code=500, detail="Configure MISTICA_CLOUD_ADMIN_TOKEN no servidor.")
    if not hmac.compare_digest(str(x_mistica_admin_token or ""), esperado):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token administrativo inválido.")
    return True


def extrair_token_loja(x_mistica_loja_token: str | None = Header(default=None)) -> str:
    token = str(x_mistica_loja_token or "").strip()
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token da loja ausente.")
    return token
