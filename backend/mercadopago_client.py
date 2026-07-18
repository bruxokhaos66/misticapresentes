"""Cliente HTTP mínimo para a API REST do Mercado Pago (pagamentos).

Usa httpx (já uma dependência pinada do backend, ver requirements.txt) em vez
do SDK oficial `mercadopago` em Python: a API REST usada aqui (POST/GET
/v1/payments) é pequena, estável e documentada publicamente, e evitar uma
dependência nova (não pinada nem auditada nesta mudança) reduz superfície de
supply-chain sem abrir mão de nenhum requisito de segurança -- toda chamada
usa TLS, Bearer do Access Token (lido só no servidor) e X-Idempotency-Key.

Nenhuma função aqui loga o Access Token, o corpo da requisição (pode conter
e-mail/CPF do pagador) nem a resposta bruta do Mercado Pago -- só o
resultado já normalizado que os chamadores precisam.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import httpx

from backend.logging_config import get_logger
from backend.mercadopago_flags import access_token_mercadopago

logger = get_logger(__name__)

_BASE_URL = "https://api.mercadopago.com"
_TIMEOUT_SEGUNDOS = 12.0


class MercadoPagoIndisponivel(Exception):
    """O Mercado Pago não respondeu a tempo ou está indisponível (timeout,
    erro de rede, 5xx). Nunca deve ser interpretado como pagamento recusado
    -- o chamador decide o que fazer (normalmente: não confirmar nada e
    orientar nova tentativa)."""


@dataclass(frozen=True)
class ResultadoPagamentoMP:
    id: str
    status: str
    status_detail: str
    transaction_amount: float
    installments: int
    payment_method_id: Optional[str]
    payment_type_id: Optional[str]
    external_reference: Optional[str]
    currency_id: Optional[str]
    collector_id: Optional[str]


def _cliente() -> httpx.Client:
    token = access_token_mercadopago()
    if not token:
        raise MercadoPagoIndisponivel("Mercado Pago sem Access Token configurado.")
    return httpx.Client(
        base_url=_BASE_URL,
        timeout=_TIMEOUT_SEGUNDOS,
        headers={"Authorization": f"Bearer {token}"},
    )


def _normalizar(payload: dict) -> ResultadoPagamentoMP:
    return ResultadoPagamentoMP(
        id=str(payload.get("id") or ""),
        status=str(payload.get("status") or ""),
        status_detail=str(payload.get("status_detail") or ""),
        transaction_amount=float(payload.get("transaction_amount") or 0),
        installments=int(payload.get("installments") or 1),
        payment_method_id=payload.get("payment_method_id"),
        payment_type_id=payload.get("payment_type_id"),
        external_reference=payload.get("external_reference"),
        currency_id=payload.get("currency_id"),
        collector_id=str(payload.get("collector_id")) if payload.get("collector_id") is not None else None,
    )


def criar_pagamento_cartao(
    *,
    idempotency_key: str,
    transaction_amount: float,
    token: str,
    installments: int,
    payment_method_id: Optional[str],
    issuer_id: Optional[str],
    payer_email: str,
    payer_doc_type: Optional[str],
    payer_doc_number: Optional[str],
    external_reference: str,
    description: str,
    notification_url: Optional[str] = None,
) -> ResultadoPagamentoMP:
    """Cria uma cobrança de cartão no Mercado Pago. `token` é o token de
    cartão gerado no navegador pelo SDK oficial (dados de cartão nunca
    passam por este servidor). X-Idempotency-Key garante que reenviar a
    mesma requisição (retry de rede, clique duplo) nunca gera uma segunda
    cobrança no Mercado Pago."""
    corpo = {
        "transaction_amount": round(float(transaction_amount), 2),
        "token": token,
        "installments": max(1, int(installments or 1)),
        "description": description[:255],
        "external_reference": external_reference,
        "payer": {"email": payer_email},
        "capture": True,
    }
    if payment_method_id:
        corpo["payment_method_id"] = payment_method_id
    if issuer_id:
        corpo["issuer_id"] = issuer_id
    if payer_doc_type and payer_doc_number:
        corpo["payer"]["identification"] = {"type": payer_doc_type, "number": payer_doc_number}
    if notification_url:
        corpo["notification_url"] = notification_url

    try:
        with _cliente() as cliente:
            resposta = cliente.post(
                "/v1/payments",
                json=corpo,
                headers={"X-Idempotency-Key": idempotency_key},
            )
    except httpx.HTTPError as exc:
        logger.warning("mercadopago_indisponivel", extra={"evento": "mp_criar_pagamento_erro_rede"})
        raise MercadoPagoIndisponivel("Falha de rede ao contatar o Mercado Pago.") from exc

    if resposta.status_code >= 500:
        logger.warning(
            "mercadopago_erro_servidor",
            extra={"evento": "mp_criar_pagamento_5xx", "status_code": resposta.status_code},
        )
        raise MercadoPagoIndisponivel("Mercado Pago indisponível no momento.")

    try:
        payload = resposta.json()
    except ValueError as exc:
        raise MercadoPagoIndisponivel("Resposta inválida do Mercado Pago.") from exc

    if resposta.status_code not in (200, 201) or not payload.get("id"):
        # Erro de validação (4xx): cartão/token inválido, dados incompletos
        # etc. Não é indisponibilidade -- é uma recusa/erro de requisição,
        # tratado pelo chamador como pagamento não realizado.
        logger.info(
            "mercadopago_pagamento_rejeitado_na_criacao",
            extra={"evento": "mp_criar_pagamento_rejeitado", "status_code": resposta.status_code},
        )
        return ResultadoPagamentoMP(
            id="",
            status="rejected",
            status_detail=str(payload.get("message") or payload.get("error") or "erro_desconhecido")[:200],
            transaction_amount=float(transaction_amount),
            installments=max(1, int(installments or 1)),
            payment_method_id=payment_method_id,
            payment_type_id=None,
            external_reference=external_reference,
            currency_id=None,
            collector_id=None,
        )

    return _normalizar(payload)


def consultar_pagamento(payment_id: str) -> ResultadoPagamentoMP:
    """Consulta server-to-server o estado atual de um pagamento no Mercado
    Pago -- nunca confiamos apenas no que o webhook/frontend informou."""
    try:
        with _cliente() as cliente:
            resposta = cliente.get(f"/v1/payments/{payment_id}")
    except httpx.HTTPError as exc:
        logger.warning("mercadopago_indisponivel", extra={"evento": "mp_consultar_pagamento_erro_rede"})
        raise MercadoPagoIndisponivel("Falha de rede ao consultar o Mercado Pago.") from exc

    if resposta.status_code >= 500:
        raise MercadoPagoIndisponivel("Mercado Pago indisponível no momento.")
    if resposta.status_code == 404:
        raise MercadoPagoIndisponivel("Pagamento não encontrado no Mercado Pago.")

    try:
        payload = resposta.json()
    except ValueError as exc:
        raise MercadoPagoIndisponivel("Resposta inválida do Mercado Pago.") from exc

    if not payload.get("id"):
        raise MercadoPagoIndisponivel("Resposta sem identificador do Mercado Pago.")

    return _normalizar(payload)
