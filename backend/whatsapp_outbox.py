"""Outbox transacional de notificações administrativas por WhatsApp.

`enfileirar_evento_whatsapp` é o ÚNICO ponto de entrada usado pelos fluxos
de pedido/pagamento (backend/payment_routes.py, backend/site_stock_routes.py,
backend/preorder_checkout.py, backend/payment_webhook_routes.py,
backend/mercadopago_routes.py, backend/order_status_routes.py) para registrar
um evento administrativo. Deve SEMPRE ser chamado dentro da mesma transação
(mesma conexão `conn`, antes do commit) da mudança de estado que originou o
evento -- nunca depois, nunca em uma conexão separada. Isso garante que o
evento e a mudança de estado sejam atômicos: se a transação do pedido
falhar, o evento nunca é gravado; se a transação for bem-sucedida, o evento
sempre é.

Esta função NUNCA chama a rede: só grava uma linha em notification_outbox.
O envio de fato acontece depois, de forma assíncrona, em
backend/whatsapp_worker.py -- a lógica financeira nunca espera o WhatsApp.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime

from backend.whatsapp_events import (
    ContextoEventoPedido,
    montar_payload_sanitizado,
    template_para_evento,
    validar_evento,
)
from backend.whatsapp_flags import destinatarios_admin_whatsapp, whatsapp_habilitado

_STATUS_ELEGIVEIS_ENVIO = {"pending", "retry"}


def _referencia_destinatario(numero: str) -> str:
    """Referência estável e não reversível de um número administrativo --
    nunca o número em si. O worker resolve de volta ao número real
    recomputando este mesmo hash sobre a configuração ATUAL de
    WHATSAPP_ADMIN_RECIPIENTS (ver resolver_numero_por_referencia); se o
    número não estiver mais configurado, a referência simplesmente não
    resolve mais -- nunca envia para um número removido da lista."""
    return "admin:" + hashlib.sha256(numero.encode("utf-8")).hexdigest()[:16]


def resolver_numero_por_referencia(referencia: str) -> str | None:
    for numero in destinatarios_admin_whatsapp():
        if _referencia_destinatario(numero) == referencia:
            return numero
    return None


def _inserir_linha_outbox(conn, *, evento, pedido_id, payment_id, recipient_reference, template_nome, idioma, payload_json, idempotency_key, status, agora) -> int:
    cur = conn.execute(
        """
        INSERT OR IGNORE INTO notification_outbox (
            event_type, aggregate_type, aggregate_id, order_id, payment_id,
            channel, provider, recipient_reference, template_name, template_language,
            payload_json, idempotency_key, status, attempts, next_attempt_at,
            created_at, updated_at
        ) VALUES (?, 'pedido', ?, ?, ?, 'whatsapp', 'meta_cloud', ?, ?, ?, ?, ?, ?, 0, ?, ?, ?)
        """,
        (
            evento, pedido_id, pedido_id, payment_id,
            recipient_reference, template_nome or None, idioma,
            payload_json, idempotency_key, status,
            agora if status in _STATUS_ELEGIVEIS_ENVIO else None,
            agora, agora,
        ),
    )
    return int(cur.rowcount or 0)


def enfileirar_evento_whatsapp(
    conn,
    *,
    evento: str,
    pedido_id: int,
    sufixo_idempotencia: str,
    contexto: ContextoEventoPedido,
    payment_id: int | None = None,
) -> int:
    """Enfileira um evento administrativo para todos os destinatários
    configurados (ou uma única linha 'skipped_disabled' se as notificações
    estiverem desligadas/incompletas -- nunca gera erro nem interrompe o
    fluxo do pedido/pagamento).

    `sufixo_idempotencia` DEVE ser determinístico e identificar de forma
    única esta transição de estado específica (nunca um valor aleatório) --
    ex.: o id do pagamento para PAGAMENTO_APROVADO/RECUSADO, a versão do Pix
    para PIX_GERADO. Reenviar o MESMO evento (webhook duplicado, reconsulta,
    retry) deve sempre produzir o mesmo idempotency_key, para o INSERT OR
    IGNORE abaixo nunca duplicar a notificação.

    Devolve o número de linhas novas de fato inseridas (0 se todo o evento
    já havia sido enfileirado antes -- chamador não precisa tratar isso como
    erro, é o caminho esperado em reprocessamento/retry)."""
    evento = validar_evento(evento)
    agora = datetime.now().isoformat(timespec="seconds")
    template_nome, idioma = template_para_evento(evento)
    payload = montar_payload_sanitizado(evento, contexto)
    payload_json = json.dumps(payload, ensure_ascii=False, sort_keys=True)

    habilitado = whatsapp_habilitado()
    destinatarios = destinatarios_admin_whatsapp() if habilitado else []

    if not destinatarios:
        idempotency_key = f"whatsapp:pedido:{pedido_id}:{evento.lower()}:{sufixo_idempotencia}"
        return _inserir_linha_outbox(
            conn, evento=evento, pedido_id=pedido_id, payment_id=payment_id,
            recipient_reference=None, template_nome=template_nome, idioma=idioma,
            payload_json=payload_json, idempotency_key=idempotency_key,
            status="skipped_disabled", agora=agora,
        )

    linhas_novas = 0
    for numero in destinatarios:
        referencia = _referencia_destinatario(numero)
        idempotency_key = f"whatsapp:pedido:{pedido_id}:{evento.lower()}:{sufixo_idempotencia}:{referencia[-10:]}"
        linhas_novas += _inserir_linha_outbox(
            conn, evento=evento, pedido_id=pedido_id, payment_id=payment_id,
            recipient_reference=referencia, template_nome=template_nome, idioma=idioma,
            payload_json=payload_json, idempotency_key=idempotency_key,
            status="pending", agora=agora,
        )
    return linhas_novas
