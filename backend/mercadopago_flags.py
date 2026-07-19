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


def _prefixo_credencial(valor: str) -> str:
    """Só um INDÍCIO textual, nunca uma prova. `TEST-`/`APP_USR-` é a
    convenção mais comum do Mercado Pago para credencial de teste/produção,
    mas a documentação oficial admite variação conforme a solução -- existem
    integrações em que a credencial de teste também começa com `APP_USR-`.
    Por isso esta função NUNCA decide sozinha se uma credencial é de teste
    ou produção; ela só devolve o texto do prefixo observado, para quem for
    investigar (nunca a credencial inteira)."""
    if valor.startswith("TEST-"):
        return "test_prefix"
    if valor.startswith("APP_USR-"):
        return "app_usr_prefix"
    if not valor:
        return "not_configured"
    return "unknown_prefix"


def diagnostico_credenciais_mercadopago() -> dict:
    """Diagnóstico HEURÍSTICO e NÃO-BLOQUEANTE (nunca impede nem falha um
    pagamento) de uma causa possível de recusa que não é "o cartão é ruim":
    Public Key e Access Token pertencerem a aplicações/ambientes diferentes
    no Mercado Pago -- o token gerado no navegador com uma Public Key ainda
    assim pode ser aceito por um Access Token de outra aplicação/ambiente na
    tokenização, mas a cobrança em si ser recusada.

    Os prefixos (`TEST-`/`APP_USR-`) são só um SINAL, não uma garantia --
    por isso esta função nunca afirma "credenciais consistentes" nem
    "inconsistentes" com certeza, só sinaliza `possible_environment_mismatch`
    quando os prefixos observados divergem, sempre com
    `credential_environment_confidence: "low"`. A única confirmação
    definitiva é manual: checar no painel do Mercado Pago
    (https://www.mercadopago.com.br/developers/panel) que a Public Key e o
    Access Token em uso foram copiados da MESMA aplicação e do MESMO modo
    (teste ou produção) -- nunca só pelo formato do texto.

    Nunca loga nem devolve a credencial em si, só o nome do prefixo
    observado."""
    public_hint = _prefixo_credencial(public_key_mercadopago())
    access_hint = _prefixo_credencial(access_token_mercadopago())
    sinais_conhecidos = {"test_prefix", "app_usr_prefix"}
    possible_mismatch = (
        public_hint in sinais_conhecidos and access_hint in sinais_conhecidos and public_hint != access_hint
    )
    return {
        "public_key_prefix_hint": public_hint,
        "access_token_prefix_hint": access_hint,
        "ambiente_declarado": ambiente_mercadopago(),
        "possible_environment_mismatch": possible_mismatch,
        "credential_environment_confidence": "low",
    }
