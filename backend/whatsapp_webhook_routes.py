"""Endpoint único de webhook do WhatsApp Cloud API (Meta): callbacks de
status de entrega das notificações administrativas E (quando
WHATSAPP_CLOUD_ENABLED) mensagens RECEBIDAS de clientes para a Central de
Atendimento (ver backend/whatsapp_inbox_service.py).

Ponto de entrada SEPARADO do webhook do Mercado Pago
(backend/payment_webhook_routes.py) -- nunca compartilha rota, tabela de
idempotência ou lógica de negócio com ele; nunca processa eventos
financeiros. Os dois fluxos acima (status de saída / mensagens de entrada)
também são independentes entre si: cada um com sua própria tabela de
idempotência (whatsapp_status_eventos / whatsapp_webhook_events) e sua
própria feature flag (WHATSAPP_NOTIFICATIONS_ENABLED / WHATSAPP_CLOUD_ENABLED).

Nunca confia em nenhum dado do payload sem antes validar a assinatura
(X-Hub-Signature-256, ver backend/whatsapp_provider.py::
MetaWhatsAppCloudProvider.validate_webhook_signature). Responde rápido (não
faz chamadas de rede) e é idempotente."""
from __future__ import annotations

import hashlib
import json
import secrets
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response

from backend.database import conectar
from backend.logging_config import get_logger
from backend.rate_limit import limitar_requisicoes
from backend.whatsapp_flags import (
    whatsapp_cloud_inbox_habilitado,
    whatsapp_provider_nome,
    whatsapp_verify_token,
    whatsapp_webhook_max_body_bytes,
)
from backend.whatsapp_inbox_service import processar_webhook_mensagens
from backend.whatsapp_provider import construir_provider

logger = get_logger(__name__)

router = APIRouter(prefix="/api/webhooks/whatsapp", tags=["webhooks-whatsapp"])

limitar_webhook_whatsapp = limitar_requisicoes("webhook_whatsapp", limite=120, janela_segundos=60)


@router.get("")
def verificar_webhook_whatsapp(
    hub_mode: str = Query(default="", alias="hub.mode"),
    hub_verify_token: str = Query(default="", alias="hub.verify_token"),
    hub_challenge: str = Query(default="", alias="hub.challenge"),
):
    """Handshake oficial de verificação de webhook da Meta (Graph API
    Webhooks): confere hub.verify_token contra WHATSAPP_VERIFY_TOKEN e, se
    bater, ecoa hub.challenge em texto puro. Nunca expõe o verify_token
    configurado em nenhuma resposta."""
    token_configurado = whatsapp_verify_token()
    if not token_configurado or hub_mode != "subscribe" or not hub_verify_token or not secrets.compare_digest(hub_verify_token, token_configurado):
        raise HTTPException(status_code=403, detail="Verificação de webhook falhou.")
    return Response(content=hub_challenge, media_type="text/plain")


def _payload_hash(payload_bruto: bytes) -> str:
    return hashlib.sha256(payload_bruto).hexdigest()


@router.post("", dependencies=[Depends(limitar_webhook_whatsapp)])
async def receber_webhook_whatsapp(request: Request):
    payload_bruto = await request.body()
    if len(payload_bruto) > whatsapp_webhook_max_body_bytes():
        raise HTTPException(status_code=413, detail="Payload muito grande.")

    provider = construir_provider(whatsapp_provider_nome())
    if not provider.validate_webhook_signature(payload_bruto, dict(request.headers)):
        logger.warning("whatsapp_webhook_assinatura_invalida", extra={"evento": "whatsapp_webhook_assinatura_invalida"})
        raise HTTPException(status_code=401, detail="Assinatura inválida.")

    try:
        payload = json.loads(payload_bruto or b"{}")
    except ValueError:
        raise HTTPException(status_code=400, detail="Payload inválido.")

    if not isinstance(payload, dict):
        return {"ok": True, "ignorado": True}

    eventos_status = provider.parse_delivery_webhook(payload)

    # Mensagens RECEBIDAS de clientes (Central de Atendimento) -- só
    # processadas/persistidas quando a feature está explicitamente habilitada
    # e configurada (fail-closed); com a flag desligada, o handshake GET
    # continua funcionando normalmente mas nenhuma mensagem é armazenada. Isso
    # é INDEPENDENTE dos callbacks de status acima (WHATSAPP_NOTIFICATIONS_ENABLED),
    # que continuam funcionando sem alteração de comportamento.
    resultado_mensagens = {"processadas": 0, "duplicadas": 0, "ignoradas": 0}

    if not eventos_status and not whatsapp_cloud_inbox_habilitado():
        return {"ok": True, "ignorado": True}

    agora = datetime.now().isoformat(timespec="seconds")
    processados_status = 0
    with conectar() as conn:
        for evento in eventos_status:
            try:
                conn.execute(
                    """
                    INSERT INTO whatsapp_status_eventos (provider_message_id, status, timestamp_provedor, payload_hash, recebido_em)
                    VALUES (?,?,?,?,?)
                    """,
                    (evento.provider_message_id, evento.status, evento.timestamp, _payload_hash(payload_bruto), agora),
                )
            except Exception:
                # Já processado (mesma mensagem + status + timestamp) --
                # nunca reaplica a mesma atualização duas vezes.
                continue

            _aplicar_status_entrega(conn, evento, agora)
            processados_status += 1

        if whatsapp_cloud_inbox_habilitado():
            resultado_mensagens = processar_webhook_mensagens(conn, payload)

        conn.commit()

    return {"ok": True, "processados": processados_status, "mensagens": resultado_mensagens}


def _aplicar_status_entrega(conn, evento, agora: str) -> None:
    """Atualiza a linha correspondente do outbox por provider_message_id.
    Ignora com segurança um provider_message_id desconhecido (mensagem
    enviada antes desta integração existir, ou de outro ambiente) -- nunca
    levanta erro para um evento sem correspondência local."""
    coluna_data = {"sent": "sent_at", "delivered": "delivered_at", "read": "read_at", "failed": "failed_at"}.get(evento.status)
    novo_status = evento.status if evento.status != "sent" else None  # 'sent' já é aplicado no envio; não regride nem sobrescreve estados mais avançados

    if evento.status == "failed":
        conn.execute(
            """
            UPDATE notification_outbox
               SET status='permanently_failed', failed_at=COALESCE(failed_at, ?), last_error_code=?, last_error_summary=?, updated_at=?
             WHERE provider_message_id=? AND status NOT IN ('permanently_failed','cancelled')
            """,
            (agora, evento.error_code, evento.error_summary, agora, evento.provider_message_id),
        )
        return

    if novo_status is None:
        return

    # Nunca regride: 'read' nunca volta para 'delivered', 'delivered' nunca
    # volta para 'sent'. A ordem de precedência abaixo é a única forma de
    # avanço aceita.
    precedencia = {"sent": 0, "delivered": 1, "read": 2}
    ordem_novo = precedencia.get(novo_status, -1)
    linha = conn.execute("SELECT status FROM notification_outbox WHERE provider_message_id=?", (evento.provider_message_id,)).fetchone()
    if not linha:
        return
    ordem_atual = precedencia.get(str(linha["status"]), -1)
    if ordem_novo <= ordem_atual:
        return

    conn.execute(
        f"UPDATE notification_outbox SET status=?, {coluna_data}=COALESCE({coluna_data}, ?), updated_at=? WHERE provider_message_id=?",
        (novo_status, agora, agora, evento.provider_message_id),
    )
