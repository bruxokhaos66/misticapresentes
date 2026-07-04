import os
from fastapi import Header, HTTPException


def validar_site_api_key(x_mistica_api_key: str | None = Header(default=None)) -> None:
    chave = os.environ.get("MISTICA_SITE_API_KEY", "").strip()
    if not chave:
        print("[API] Aviso: MISTICA_SITE_API_KEY não configurada. Endpoints sensíveis em modo desenvolvimento.")
        return
    if x_mistica_api_key != chave:
        raise HTTPException(status_code=403, detail="Chave da API do site inválida.")
