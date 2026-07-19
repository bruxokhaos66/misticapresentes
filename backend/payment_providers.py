from __future__ import annotations

"""Interface de provedor de pagamento externo.

Nenhuma lógica de geração de QR Code, payload EMV, CRC16, TXID ou chave Pix
vive aqui nem é alterada por este módulo: a confirmação automática via
provedor é um caminho adicional que sempre chama as MESMAS funções de
conciliação já existentes em backend/payment_routes.py (registrar_pagamento,
que por sua vez usa _classificar_conciliacao/_aplicar_resultado_confirmacao),
nunca uma cópia paralela delas.

O Mercado Pago (backend/mercadopago_provider.py::MercadoPagoProvider) é
registrado em PAYMENT_PROVIDERS por backend/payment_webhook_routes.py (não
aqui, para evitar import circular: MercadoPagoProvider depende de
EventoPagamentoProvider, definido neste módulo).
"""

from dataclasses import dataclass
from typing import Optional, Protocol


@dataclass(frozen=True)
class EventoPagamentoProvider:
    """Evento de pagamento normalizado, já extraído do payload específico de
    um provedor. `evento_id` é o identificador do evento no provedor (usado
    para idempotência em webhook_eventos — nunca o pix_txid/chave Pix).

    payment_type_id/payment_method_id/installments/status_detail vêm sempre
    do provedor (nunca inferidos, ex.: nunca deduzidos do número de
    parcelas) — usados pelo painel para diferenciar Pix, crédito e débito
    (ver backend/pedido_comercial.py::rotulo_forma_pagamento). Podem ser
    None para provedores/eventos que não os informam."""

    provedor: str
    evento_id: str
    venda_id: int
    provider_payment_id: str
    valor_recebido: float
    status: str
    payment_type_id: Optional[str] = None
    payment_method_id: Optional[str] = None
    installments: Optional[int] = None
    status_detail: Optional[str] = None


class PaymentProvider(Protocol):
    """Um provedor de pagamento futuro implementa esta interface. O
    endpoint de webhook (backend/payment_webhook_routes.py) despacha para a
    implementação registrada em PAYMENT_PROVIDERS a partir do nome na URL."""

    nome: str

    def validar_assinatura(self, payload_bruto: bytes, headers: dict, query_params: Optional[dict] = None) -> bool:
        """Valida a assinatura/segredo do webhook antes de qualquer
        processamento. Deve usar comparação de tempo constante
        (hmac.compare_digest / secrets.compare_digest).

        `query_params` (parâmetros da URL da notificação, ex.: `?data.id=...`)
        é opcional na assinatura desta interface para não quebrar um provider
        futuro mais simples, mas o Mercado Pago exige especificamente o
        `data.id` da query string (não do corpo) para montar o manifesto
        assinado -- ver MercadoPagoProvider.validar_assinatura."""
        ...

    def extrair_evento(self, payload: dict) -> Optional[EventoPagamentoProvider]:
        """Traduz o payload específico do provedor para o formato
        normalizado. Retorna None se o evento não for relevante (ex.: evento
        de outro tipo que não confirmação de pagamento)."""
        ...


# Registro de provedores habilitados, preenchido em tempo de import por
# backend/payment_webhook_routes.py. O endpoint de webhook responde 501 para
# qualquer provedor não registrado aqui (ou registrado mas desabilitado por
# feature flag -- ver backend/mercadopago_flags.py::mercado_pago_habilitado).
PAYMENT_PROVIDERS: dict[str, PaymentProvider] = {}
