"""Feature flags e configuração do provedor Mercado Pago (cartão de crédito).

Mesmo padrão de backend/isis_chat_flags.py: cada flag/credencial é lida só
da variável de ambiente do processo (nunca de query string, header, cookie
ou hostname), nasce desligada em qualquer ambiente sem configuração
explícita -- inclusive produção. O Access Token NUNCA é devolvido por
nenhuma função pública deste módulo nem por nenhuma rota; só
`chave_publica_mercadopago()` (Public Key) pode ir para o frontend.
"""
from __future__ import annotations

import os

_VALORES_VERDADEIROS = {"1", "true", "yes", "on", "sim"}


def _flag_env(nome: str, default: str = "") -> bool:
    return os.environ.get(nome, default).strip().lower() in _VALORES_VERDADEIROS


def mercado_pago_ligado_por_flag() -> bool:
    """MERCADO_PAGO_ENABLED -- interruptor administrativo explícito,
    independente de haver ou não credencial configurada."""
    return _flag_env("MERCADO_PAGO_ENABLED")


def access_token_mercadopago() -> str:
    """Access Token -- uso exclusivo do backend (chamadas server-to-server à
    API do Mercado Pago). Nunca logar, nunca serializar em resposta HTTP."""
    return os.environ.get("MERCADO_PAGO_ACCESS_TOKEN", "").strip()


def public_key_mercadopago() -> str:
    """Public Key -- única credencial que pode ser exposta ao frontend
    (necessária para a tokenização do cartão pelo SDK oficial no navegador)."""
    return os.environ.get("MERCADO_PAGO_PUBLIC_KEY", "").strip()


def webhook_secret_mercadopago() -> str:
    return os.environ.get("MERCADO_PAGO_WEBHOOK_SECRET", "").strip()


def ambiente_mercadopago() -> str:
    valor = os.environ.get("MERCADO_PAGO_ENVIRONMENT", "production").strip().lower()
    return valor if valor in {"production", "sandbox"} else "production"


def mercado_pago_habilitado() -> bool:
    """Estado efetivo: a flag precisa estar ligada E as credenciais mínimas
    (Access Token e Public Key) precisarem estar configuradas. Sem isso, o
    cartão de crédito fica indisponível de forma elegante -- nunca um erro
    no checkout, nunca uma tentativa de cobrança sem credencial válida."""
    if not mercado_pago_ligado_por_flag():
        return False
    return bool(access_token_mercadopago()) and bool(public_key_mercadopago())


def mercado_pago_webhook_configurado() -> bool:
    return mercado_pago_habilitado() and bool(webhook_secret_mercadopago())
