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
    # Códigos de erro do provedor (payload["cause"][*]["code"]) quando a
    # criação é rejeitada por validação (4xx) -- ex.: 3003 = card_token_id
    # inválido/já utilizado/expirado. Vazio em qualquer outro caso (inclusive
    # sucesso). Nunca contém dado de cartão/pessoal, só o código numérico já
    # logado hoje em mercadopago_pagamento_rejeitado_na_criacao.
    causa_codigos: tuple = ()


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
    billing_address: Optional[dict] = None,
    additional_info_items: Optional[list] = None,
    device_id: Optional[str] = None,
    payer_first_name: Optional[str] = None,
    payer_last_name: Optional[str] = None,
    ip_address: Optional[str] = None,
    statement_descriptor: Optional[str] = None,
    metadata: Optional[dict] = None,
) -> ResultadoPagamentoMP:
    """Cria uma cobrança de cartão no Mercado Pago. `token` é o token de
    cartão gerado no navegador pelo SDK oficial (dados de cartão nunca
    passam por este servidor). X-Idempotency-Key garante que reenviar a
    mesma requisição (retry de rede, clique duplo) nunca gera uma segunda
    cobrança no Mercado Pago.

    `billing_address`, quando informado, já vem pronto de
    backend/mercadopago_routes.py::_resolver_endereco_cobranca com só os
    campos documentados pela API (zip_code/street_name/street_number/
    neighborhood/city/federal_unit) -- enviado em payer.address (NUNCA em
    additional_info.payer.address).

    Confirmado por revisão de homologação em duas fontes primárias
    independentes -- os SDKs oficiais do próprio Mercado Pago (GitHub,
    clonados diretamente nesta sessão porque a documentação HTML retornou
    403 por bloqueio de proxy):
      - mercadopago/sdk-nodejs, src/clients/payment/create/types.ts
        (`PayerRequest.address: AddressRequest`, com `neighborhood`/`city`/
        `federal_unit`) e src/clients/payment/commonTypes.ts
        (`PayerAdditionalInfo.address: Address`, SEM esses três campos).
      - mercadopago/sdk-dotnet, src/MercadoPago/Client/Payment/
        PaymentPayerRequest.cs (`Address: PaymentPayerAddressRequest`,
        subclasse de AddressRequest com os mesmos três campos extras) e
        PaymentAdditionalInfoPayerRequest.cs (`Address: AddressRequest`,
        base, sem eles).
    Ou seja: additional_info.payer.address só aceita zip_code/street_name/
    street_number (dado comportamental resumido, ao lado de first_name/
    last_name/registration_date -- não é o conceito de endereço de
    cobrança); o endereço COMPLETO com bairro/cidade/UF só existe em
    payer.address. Versão anterior desta função enviava para
    additional_info.payer.address -- corrigido nesta revisão.

    `additional_info_items`, quando informado, já vem pronto de
    backend/mercadopago_routes.py::_itens_additional_info só com os campos
    documentados em additional_info.items (id/title/description/quantity/
    unit_price; ver commonTypes.ts do mercadopago/sdk-nodejs) -- produto/
    quantidade/valor sempre calculados pelo backend, nunca confiados ao
    cliente; description só aparece quando o produto tem descrição
    cadastrada no catálogo, nunca inventada.

    `payer_first_name`/`payer_last_name`, quando informados, vão em
    payer.first_name/payer.last_name -- campos oficiais e opcionais de
    PayerRequest (mercadopago/sdk-nodejs, src/clients/payment/create/
    types.ts). Vêm SEMPRE de um campo explícito preenchido pelo comprador no
    checkout (nunca de cardholderName/"Nome impresso no cartão", que é o
    titular do cartão -- pode ser outra pessoa -- e nunca é dividido
    automaticamente em nome/sobrenome). `payer_last_name` é opcional: um
    comprador com nome civil de uma única palavra nunca tem um sobrenome
    inventado só para preencher o campo.

    `device_id`, quando informado, é o Device ID coletado no navegador pelo
    script oficial do Mercado Pago (https://www.mercadopago.com/v2/
    security.js) -- encaminhado SEMPRE no header X-meli-session-id (nunca
    como campo do corpo JSON), conforme documentado publicamente (Mercado
    Pago, "Integrate the Device ID"/"How to improve payment approval":
    X-meli-session-id: device_id). Nunca logado por esta função.

    `ip_address`, quando informado, vai em additional_info.ip_address --
    sinal adicional de antifraude documentado pela Payments API (mesma
    seção additional_info dos itens); nunca bloqueia o pagamento se ausente.

    `statement_descriptor`, quando informado, vai no campo de mesmo nome
    (texto exibido na fatura do cartão do comprador) -- puramente
    informativo, nunca afeta aprovação/recusa nem qualquer regra comercial.

    `metadata`, quando informado, vai no campo de mesmo nome (objeto livre
    para correlação/conciliação do lado do integrador, documentado pela
    Payments API) -- nunca lido de volta por este cliente, só encaminhado."""
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
    if payer_first_name:
        corpo["payer"]["first_name"] = payer_first_name
    if payer_last_name:
        corpo["payer"]["last_name"] = payer_last_name
    if notification_url:
        corpo["notification_url"] = notification_url
    if billing_address:
        corpo["payer"]["address"] = billing_address
    additional_info: dict = {}
    if additional_info_items:
        additional_info["items"] = additional_info_items
    if ip_address:
        additional_info["ip_address"] = ip_address
    if additional_info:
        corpo["additional_info"] = additional_info
    if statement_descriptor:
        corpo["statement_descriptor"] = statement_descriptor
    if metadata:
        corpo["metadata"] = metadata

    headers = {"X-Idempotency-Key": idempotency_key}
    if device_id:
        headers["X-meli-session-id"] = device_id

    try:
        with _cliente() as cliente:
            resposta = cliente.post(
                "/v1/payments",
                json=corpo,
                headers=headers,
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
        # tratado pelo chamador como pagamento não realizado. `cause` é uma
        # lista de códigos/descrições genéricos do provedor (ex.: {"code":
        # 2006, "description": "Invalid card_number"}) -- nunca contém o
        # número do cartão, token, CVV ou dado do pagador, só o nome do
        # campo com problema, então é seguro logar para diagnóstico.
        causas = [
            {"code": c.get("code"), "description": c.get("description")}
            for c in (payload.get("cause") or [])
            if isinstance(c, dict)
        ][:5]
        detalhe = str(payload.get("message") or payload.get("error") or "erro_desconhecido")[:200]
        logger.info(
            "mercadopago_pagamento_rejeitado_na_criacao",
            extra={
                "evento": "mp_criar_pagamento_rejeitado",
                "status_code": resposta.status_code,
                "detalhe": detalhe,
                "causas": causas,
            },
        )
        return ResultadoPagamentoMP(
            id="",
            status="rejected",
            status_detail=detalhe,
            transaction_amount=float(transaction_amount),
            installments=max(1, int(installments or 1)),
            payment_method_id=payment_method_id,
            payment_type_id=None,
            external_reference=external_reference,
            currency_id=None,
            collector_id=None,
            causa_codigos=tuple(c["code"] for c in causas if isinstance(c.get("code"), int)),
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
