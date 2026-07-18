"""Implementação de PaymentProvider (backend/payment_providers.py) para o
Mercado Pago -- o primeiro provedor real registrado em PAYMENT_PROVIDERS.

Nunca decide sozinho se um pagamento foi aprovado a partir do corpo do
webhook: `extrair_evento` sempre consulta o Mercado Pago server-to-server
(GET /v1/payments/{id}) para obter o status/valor autoritativos antes de
devolver o evento normalizado -- o payload do webhook só informa QUAL
pagamento mudou, nunca o estado final dele (ver documentação oficial do
Mercado Pago: notificações de webhook trazem apenas um id de referência).
"""
from __future__ import annotations

import hashlib
import hmac
import json
from typing import Optional

from backend.logging_config import get_logger
from backend.mercadopago_client import MercadoPagoIndisponivel, consultar_pagamento
from backend.mercadopago_flags import mercado_pago_webhook_configurado, webhook_secret_mercadopago
from backend.payment_providers import EventoPagamentoProvider

logger = get_logger(__name__)

# Tipos de notificação do Mercado Pago que representam um pagamento (cartão
# ou Pix nativo do MP). Outros tipos (ex.: "merchant_order", "chargebacks"
# quando enviados fora do formato de payment) são ignorados -- não é erro,
# apenas um evento que este integração não trata.
_TIPOS_RELEVANTES = {"payment"}


class MercadoPagoProvider:
    nome = "mercadopago"

    def validar_assinatura(self, payload_bruto: bytes, headers: dict) -> bool:
        if not mercado_pago_webhook_configurado():
            # Sem segredo configurado (integração desligada ou webhook ainda
            # não cadastrado no painel do Mercado Pago), nunca aceitamos uma
            # notificação como autêntica -- falha fechada, não aberta.
            return False

        cabecalhos = {str(k).lower(): v for k, v in (headers or {}).items()}
        assinatura = cabecalhos.get("x-signature", "")
        request_id = cabecalhos.get("x-request-id", "")
        if not assinatura or not request_id:
            return False

        partes = {}
        for pedaco in assinatura.split(","):
            if "=" not in pedaco:
                continue
            chave, _, valor = pedaco.partition("=")
            partes[chave.strip()] = valor.strip()
        ts = partes.get("ts")
        v1 = partes.get("v1")
        if not ts or not v1:
            return False

        try:
            corpo = json.loads(payload_bruto or b"{}")
        except ValueError:
            return False
        data_id = str((corpo.get("data") or {}).get("id") or "").strip()
        if not data_id:
            return False

        manifesto = f"id:{data_id};request-id:{request_id};ts:{ts};"
        esperado = hmac.new(
            webhook_secret_mercadopago().encode("utf-8"),
            manifesto.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        return hmac.compare_digest(esperado, v1)

    def extrair_evento(self, payload: dict) -> Optional[EventoPagamentoProvider]:
        tipo = str(payload.get("type") or payload.get("topic") or "").strip().lower()
        if tipo not in _TIPOS_RELEVANTES:
            return None

        payment_id = str((payload.get("data") or {}).get("id") or "").strip()
        if not payment_id:
            return None

        try:
            resultado = consultar_pagamento(payment_id)
        except MercadoPagoIndisponivel:
            # Propaga para o chamador (backend/payment_webhook_routes.py)
            # decidir a resposta HTTP -- deve resultar em uma resposta que
            # faça o Mercado Pago reenviar a notificação mais tarde, nunca em
            # um "ignorado" silencioso que perderia o evento.
            raise

        if not resultado.external_reference or not resultado.external_reference.isdigit():
            logger.warning(
                "mercadopago_webhook_sem_referencia_externa",
                extra={"evento": "mp_webhook_external_reference_invalida"},
            )
            return None

        # evento_id combina o id do pagamento com o status consultado no
        # momento: dedupa exatamente o mesmo evento financeiro (mesmo
        # pagamento, mesmo status) contra reenvio/replay, mas permite que uma
        # transição real de status (ex.: pending -> approved) seja tratada
        # como um evento novo -- nunca colide com uma notificação anterior
        # do mesmo pagamento em outro status. Não depende do campo "id" de
        # nível superior do payload (formato observado como inconsistente
        # entre versões/fontes de notificação do Mercado Pago).
        return EventoPagamentoProvider(
            provedor=self.nome,
            evento_id=f"{resultado.id}:{resultado.status}",
            venda_id=int(resultado.external_reference),
            provider_payment_id=str(resultado.id),
            valor_recebido=float(resultado.transaction_amount),
            status=resultado.status,
        )
