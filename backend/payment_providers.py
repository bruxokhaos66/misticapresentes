from __future__ import annotations

"""Interface de provedor de pagamento externo (preparação para uma
integração futura, ex.: Mercado Pago — NÃO integrada nesta mudança).

Nenhuma lógica de geração de QR Code, payload EMV, CRC16, TXID ou chave Pix
vive aqui nem é alterada por este módulo: a confirmação automática via
provedor é um caminho adicional que, quando implementado, chamará as MESMAS
funções de conciliação já existentes em backend/payment_routes.py
(_classificar_conciliacao/_aplicar_resultado_confirmacao), nunca uma cópia
paralela delas.
"""

from dataclasses import dataclass
from typing import Optional, Protocol


@dataclass(frozen=True)
class EventoPagamentoProvider:
    """Evento de pagamento normalizado, já extraído do payload específico de
    um provedor. `evento_id` é o identificador do evento no provedor (usado
    para idempotência em webhook_eventos — nunca o pix_txid/chave Pix)."""

    provedor: str
    evento_id: str
    venda_id: int
    provider_payment_id: str
    valor_recebido: float
    status: str


class PaymentProvider(Protocol):
    """Um provedor de pagamento futuro implementa esta interface. O
    endpoint de webhook (backend/payment_webhook_routes.py) despacha para a
    implementação registrada em PAYMENT_PROVIDERS a partir do nome na URL."""

    nome: str

    def validar_assinatura(self, payload_bruto: bytes, headers: dict) -> bool:
        """Valida a assinatura/segredo do webhook antes de qualquer
        processamento. Deve usar comparação de tempo constante
        (hmac.compare_digest / secrets.compare_digest)."""
        ...

    def extrair_evento(self, payload: dict) -> Optional[EventoPagamentoProvider]:
        """Traduz o payload específico do provedor para o formato
        normalizado. Retorna None se o evento não for relevante (ex.: evento
        de outro tipo que não confirmação de pagamento)."""
        ...


# Registro de provedores habilitados. Vazio nesta mudança — nenhum provedor
# real está integrado; o endpoint de webhook responde 501 para qualquer
# provedor não registrado aqui.
PAYMENT_PROVIDERS: dict[str, PaymentProvider] = {}
