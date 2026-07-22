"""Feature flags e configuração das notificações administrativas por
WhatsApp (WhatsApp Business Platform / Cloud API oficial da Meta).

Mesmo padrão de backend/mercadopago_flags.py e backend/isis_chat_flags.py:
cada flag/credencial é lida só da variável de ambiente do processo (nunca de
query string, header, cookie ou hostname), nasce desligada em qualquer
ambiente sem configuração explícita -- inclusive produção. O Access Token,
o App Secret e o Verify Token NUNCA são devolvidos por nenhuma função
pública deste módulo em texto integral, nem logados, nem expostos a nenhuma
rota (só um diagnóstico não sensível para o painel administrativo).
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass, field

_VALORES_VERDADEIROS = {"1", "true", "yes", "on", "sim"}

PROVEDORES_CONHECIDOS = {"meta_cloud", "disabled"}

# Versão da Graph API usada por padrão quando WHATSAPP_GRAPH_API_VERSION não
# está definida. Escolhida por ser uma versão estável recente no momento
# desta implementação -- CONFIRME a versão atualmente recomendada na
# documentação oficial da Meta (developers.facebook.com/docs/graph-api/
# changelog) antes de ativar em produção; a Meta descontinua versões antigas
# periodicamente. Nunca fixe uma versão sem essa checagem manual.
GRAPH_API_VERSION_PADRAO = "v21.0"

GRAPH_API_HOST = "graph.facebook.com"

EVENTOS_TEMPLATE_ENV = {
    "PEDIDO_CRIADO": "WHATSAPP_TEMPLATE_ADMIN_NOVO_PEDIDO",
    "PIX_GERADO": "WHATSAPP_TEMPLATE_ADMIN_PIX_GERADO",
    "PAGAMENTO_APROVADO": "WHATSAPP_TEMPLATE_ADMIN_PAGAMENTO_APROVADO",
    "PAGAMENTO_PENDENTE": "WHATSAPP_TEMPLATE_ADMIN_PAGAMENTO_PENDENTE",
    "PAGAMENTO_RECUSADO": "WHATSAPP_TEMPLATE_ADMIN_PAGAMENTO_RECUSADO",
    "PAGAMENTO_EXPIRADO": "WHATSAPP_TEMPLATE_ADMIN_PAGAMENTO_EXPIRADO",
    "PAGAMENTO_CANCELADO": "WHATSAPP_TEMPLATE_ADMIN_PAGAMENTO_CANCELADO",
    "PAGAMENTO_REEMBOLSADO": "WHATSAPP_TEMPLATE_ADMIN_PAGAMENTO_REEMBOLSADO",
    "CHARGEBACK_RECEBIDO": "WHATSAPP_TEMPLATE_ADMIN_CHARGEBACK",
    "FALHA_DE_RECONCILIACAO": "WHATSAPP_TEMPLATE_ADMIN_FALHA_RECONCILIACAO",
}

# Nome padrão de cada template (usado quando a variável de ambiente
# correspondente não está definida) -- só um valor de conveniência para
# desenvolvimento; em produção, o nome real cadastrado e APROVADO no painel
# da Meta é que deve ser configurado explicitamente (ver docs/admin/
# WHATSAPP_NOTIFICACOES.md).
TEMPLATE_NOME_PADRAO = {
    "PEDIDO_CRIADO": "admin_novo_pedido",
    "PIX_GERADO": "admin_pix_gerado",
    "PAGAMENTO_APROVADO": "admin_pagamento_aprovado",
    "PAGAMENTO_PENDENTE": "admin_pagamento_pendente",
    "PAGAMENTO_RECUSADO": "admin_pagamento_recusado",
    "PAGAMENTO_EXPIRADO": "admin_pagamento_expirado",
    "PAGAMENTO_CANCELADO": "admin_pagamento_cancelado",
    "PAGAMENTO_REEMBOLSADO": "admin_pagamento_reembolsado",
    "CHARGEBACK_RECEBIDO": "admin_chargeback",
    "FALHA_DE_RECONCILIACAO": "admin_falha_reconciliacao",
}


def _flag_env(nome: str, default: str = "") -> bool:
    return os.environ.get(nome, default).strip().lower() in _VALORES_VERDADEIROS


def _int_env(nome: str, default: int, *, minimo: int = 0, maximo: int | None = None) -> int:
    bruto = os.environ.get(nome, "").strip()
    if not bruto:
        return default
    try:
        valor = int(bruto)
    except ValueError:
        return default
    if valor < minimo:
        return minimo
    if maximo is not None and valor > maximo:
        return maximo
    return valor


def whatsapp_notificacoes_ligadas_por_flag() -> bool:
    """WHATSAPP_NOTIFICATIONS_ENABLED -- interruptor administrativo
    explícito, independente de haver ou não credencial configurada."""
    return _flag_env("WHATSAPP_NOTIFICATIONS_ENABLED")


def whatsapp_provider_nome() -> str:
    valor = os.environ.get("WHATSAPP_PROVIDER", "meta_cloud").strip().lower() or "meta_cloud"
    return valor if valor in PROVEDORES_CONHECIDOS else "disabled"


def whatsapp_graph_api_version() -> str:
    valor = os.environ.get("WHATSAPP_GRAPH_API_VERSION", "").strip()
    return valor or GRAPH_API_VERSION_PADRAO


def whatsapp_phone_number_id() -> str:
    return os.environ.get("WHATSAPP_PHONE_NUMBER_ID", "").strip()


def whatsapp_business_account_id() -> str:
    return os.environ.get("WHATSAPP_BUSINESS_ACCOUNT_ID", "").strip()


def whatsapp_access_token() -> str:
    """Uso exclusivo do backend (chamadas server-to-server à Graph API).
    Nunca logar, nunca serializar em resposta HTTP, nunca persistir no
    banco."""
    return os.environ.get("WHATSAPP_ACCESS_TOKEN", "").strip()


def whatsapp_app_secret() -> str:
    """Usado só para validar a assinatura HMAC dos callbacks de status
    (X-Hub-Signature-256). Nunca exposto."""
    return os.environ.get("WHATSAPP_APP_SECRET", "").strip()


def whatsapp_verify_token() -> str:
    """Usado só na verificação do endpoint de webhook (GET /api/webhooks/
    whatsapp, hub.verify_token). Nunca exposto em resposta HTTP nem log."""
    return os.environ.get("WHATSAPP_VERIFY_TOKEN", "").strip()


def whatsapp_template_language() -> str:
    return os.environ.get("WHATSAPP_TEMPLATE_LANGUAGE", "").strip() or "pt_BR"


def whatsapp_template_namespace() -> str:
    """Legado do WhatsApp Business API On-Premise -- a Cloud API atual
    endereça templates por nome + idioma, sem namespace. Mantido só como
    campo de configuração opcional para contas que ainda o exponham no
    painel; nunca obrigatório para o envio funcionar."""
    return os.environ.get("WHATSAPP_TEMPLATE_NAMESPACE", "").strip()


def whatsapp_template_nome(evento: str) -> str:
    env_var = EVENTOS_TEMPLATE_ENV.get(evento)
    if not env_var:
        return ""
    return os.environ.get(env_var, "").strip() or TEMPLATE_NOME_PADRAO.get(evento, "")


def whatsapp_request_timeout_seconds() -> float:
    return float(_int_env("WHATSAPP_REQUEST_TIMEOUT_SECONDS", 10, minimo=1, maximo=60))


def whatsapp_max_retries() -> int:
    return _int_env("WHATSAPP_MAX_RETRIES", 5, minimo=0, maximo=20)


def whatsapp_retry_base_seconds() -> int:
    return _int_env("WHATSAPP_RETRY_BASE_SECONDS", 60, minimo=1, maximo=3600)


def whatsapp_default_country_code() -> str:
    valor = re.sub(r"\D", "", os.environ.get("WHATSAPP_DEFAULT_COUNTRY_CODE", "55"))
    return valor or "55"


def whatsapp_admin_painel_url() -> str:
    """URL HTTPS do login administrativo, usada apenas para compor um link
    (sem token, sem query string com dados) dentro do texto/variável de
    template, quando configurada. Nunca aceita um valor não-HTTPS."""
    valor = os.environ.get("WHATSAPP_ADMIN_PAINEL_URL", "").strip()
    if valor and valor.lower().startswith("https://"):
        return valor.rstrip("/")
    return ""


def normalizar_numero_whatsapp(bruto: str) -> str | None:
    """Normaliza um número administrativo para o formato E.164 sem `+`,
    aceito pela Cloud API (`to`: código do país + DDD + número, só dígitos).

    - Remove toda formatação visual (espaços, parênteses, hífens, `+`).
    - Números com 10 ou 11 dígitos (padrão brasileiro sem código do país)
      recebem o prefixo de WHATSAPP_DEFAULT_COUNTRY_CODE -- NUNCA inventa ou
      completa um DDD ausente.
    - Números que já vêm com código de país (12-15 dígitos) são aceitos como
      estão.
    - Qualquer outro comprimento é rejeitado (retorna None) -- nunca envia
      para um número que não bate com nenhum formato válido conhecido."""
    somente_digitos = re.sub(r"\D", "", str(bruto or ""))
    if not somente_digitos:
        return None
    if len(somente_digitos) in (10, 11):
        somente_digitos = whatsapp_default_country_code() + somente_digitos
    if 12 <= len(somente_digitos) <= 15:
        return somente_digitos
    return None


def mascarar_numero_whatsapp(numero: str | None) -> str:
    """Mascara um número para exibição em logs/painel -- nunca o valor
    completo. Mantém o código do país e os 2 últimos dígitos, ex.:
    '5511999998888' -> '55*******8888'."""
    texto = re.sub(r"\D", "", str(numero or ""))
    if not texto:
        return ""
    if len(texto) <= 6:
        return "*" * len(texto)
    prefixo = texto[:2]
    sufixo = texto[-4:]
    meio = "*" * (len(texto) - len(prefixo) - len(sufixo))
    return f"{prefixo}{meio}{sufixo}"


def destinatarios_admin_whatsapp() -> list[str]:
    """Lista de números administrativos autorizados, normalizados e sem
    duplicatas -- nunca inclui telefone de cliente (essa fonte é sempre
    WHATSAPP_ADMIN_RECIPIENTS, configuração do servidor, nunca dados de
    pedido/cliente). Números inválidos são descartados silenciosamente aqui
    (a validação que bloqueia a inicialização com erro fica em
    validar_configuracao_whatsapp)."""
    bruto = os.environ.get("WHATSAPP_ADMIN_RECIPIENTS", "")
    vistos: list[str] = []
    for pedaco in bruto.split(","):
        numero = normalizar_numero_whatsapp(pedaco)
        if numero and numero not in vistos:
            vistos.append(numero)
    return vistos


@dataclass
class ResultadoValidacaoConfiguracao:
    valido: bool
    erros: list[str] = field(default_factory=list)


def validar_configuracao_whatsapp() -> ResultadoValidacaoConfiguracao:
    """Valida a configuração ANTES de permitir que o worker envie qualquer
    mensagem -- nunca falha a inicialização da API inteira só porque o
    WhatsApp está mal configurado ou desligado (ver whatsapp_habilitado());
    esta função só é chamada no caminho do worker/healthcheck, nunca no
    startup do FastAPI."""
    erros: list[str] = []
    provedor = whatsapp_provider_nome()
    if provedor not in PROVEDORES_CONHECIDOS:
        erros.append(f"Provider desconhecido: {provedor!r}.")

    if provedor == "meta_cloud" and whatsapp_notificacoes_ligadas_por_flag():
        if not whatsapp_phone_number_id():
            erros.append("WHATSAPP_PHONE_NUMBER_ID não configurado.")
        if not whatsapp_access_token():
            erros.append("WHATSAPP_ACCESS_TOKEN não configurado.")
        if not whatsapp_app_secret():
            erros.append("WHATSAPP_APP_SECRET não configurado (necessário para validar callbacks de status).")
        if not whatsapp_verify_token():
            erros.append("WHATSAPP_VERIFY_TOKEN não configurado (necessário para o endpoint de verificação do webhook).")
        if not destinatarios_admin_whatsapp():
            erros.append("WHATSAPP_ADMIN_RECIPIENTS vazio ou sem nenhum número válido.")
        if whatsapp_request_timeout_seconds() <= 0:
            erros.append("WHATSAPP_REQUEST_TIMEOUT_SECONDS inválido.")
        if whatsapp_max_retries() < 0:
            erros.append("WHATSAPP_MAX_RETRIES inválido.")
        for evento in EVENTOS_TEMPLATE_ENV:
            if not whatsapp_template_nome(evento):
                erros.append(f"Template não configurado para o evento {evento}.")

    return ResultadoValidacaoConfiguracao(valido=not erros, erros=erros)


def whatsapp_habilitado() -> bool:
    """Estado efetivo: a flag precisa estar ligada, o provider precisa ser
    'meta_cloud' E a configuração precisa ser válida (validar_configuracao_
    whatsapp). Sem isso, as notificações ficam indisponíveis de forma
    elegante -- o pedido/pagamento nunca falha por causa disso, o evento
    fica registrado no outbox como 'skipped_disabled' (ver
    backend/whatsapp_outbox.py)."""
    if not whatsapp_notificacoes_ligadas_por_flag():
        return False
    if whatsapp_provider_nome() != "meta_cloud":
        return False
    return validar_configuracao_whatsapp().valido


def diagnostico_configuracao_whatsapp() -> dict:
    """Diagnóstico NÃO sensível para o painel administrativo: nunca inclui
    token, app secret, verify token, nem a lista completa/números completos
    dos destinatários -- só contagens e o estado geral."""
    resultado = validar_configuracao_whatsapp()
    return {
        "notifications_enabled_flag": whatsapp_notificacoes_ligadas_por_flag(),
        "provider": whatsapp_provider_nome(),
        "effective_enabled": whatsapp_habilitado(),
        "configuration_valid": resultado.valido,
        "configuration_errors": resultado.erros if not resultado.valido else [],
        "graph_api_version": whatsapp_graph_api_version(),
        "template_language": whatsapp_template_language(),
        "admin_recipients_count": len(destinatarios_admin_whatsapp()),
        "max_retries": whatsapp_max_retries(),
        "retry_base_seconds": whatsapp_retry_base_seconds(),
    }
