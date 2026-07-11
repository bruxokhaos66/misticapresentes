import os
import secrets

from fastapi import HTTPException

ORIGENS_PERMITIDAS = [
    "https://misticaesotericos.com.br",
    "https://www.misticaesotericos.com.br",
    "https://api.misticaesotericos.com.br",
    "https://bruxokhaos66.github.io",
    "http://localhost:3000",
    "http://localhost:8000",
]


def validar_site_api_key(chave_recebida: str | None, mensagem_indisponivel: str | None = None) -> None:
    """Confere a chave de integração do site/API (MISTICA_SITE_API_KEY ou o
    fallback legado MISTICA_SYNC_KEY). Única implementação usada por todas as
    rotas que exigem esse segredo — antes cada arquivo de rotas tinha sua
    própria cópia quase idêntica desta função."""
    chaves_validas = [
        chave
        for chave in (os.environ.get("MISTICA_SITE_API_KEY", "").strip(), os.environ.get("MISTICA_SYNC_KEY", "").strip())
        if chave
    ]
    if not chaves_validas:
        raise HTTPException(
            status_code=503,
            detail=mensagem_indisponivel or "Configure MISTICA_SITE_API_KEY ou MISTICA_SYNC_KEY para permitir escrita pela API.",
        )
    if not chave_recebida or not any(secrets.compare_digest(str(chave_recebida), chave) for chave in chaves_validas):
        raise HTTPException(status_code=403, detail="Chave da API inválida.")
