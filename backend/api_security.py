import logging
import os
import secrets

from fastapi import HTTPException

_AMBIENTES_VALIDOS = {"production", "development"}


def _normalizar_ambiente(valor_bruto: str) -> str:
    """Normaliza APP_ENV (espaços/caixa) e valida contra a lista de valores
    aceitos, com fallback seguro para 'development'. Nunca loga o valor bruto
    de uma variável desconhecida -- só o tamanho, para permitir diagnosticar
    um typo sem vazar o conteúdo configurado."""
    ambiente = valor_bruto.strip().lower()
    if ambiente in _AMBIENTES_VALIDOS:
        return ambiente
    if ambiente:
        logging.getLogger(__name__).warning(
            "APP_ENV com valor nao reconhecido; usando fallback seguro 'development'",
            extra={"evento": "app_env_invalido", "tamanho_valor_bruto": len(valor_bruto)},
        )
    return "development"


APP_ENV = _normalizar_ambiente(os.environ.get("APP_ENV", "development"))
IS_PRODUCTION = APP_ENV == "production"

# https://bruxokhaos66.github.io era o endereço do GitHub Pages antigo; o site
# usa domínio próprio (ver CNAME) e não deve mais receber tráfego de API.
ORIGENS_PERMITIDAS = [
    "https://misticaesotericos.com.br",
    "https://www.misticaesotericos.com.br",
    "https://api.misticaesotericos.com.br",
]
if not IS_PRODUCTION:
    ORIGENS_PERMITIDAS += ["http://localhost:3000", "http://localhost:8000"]


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
