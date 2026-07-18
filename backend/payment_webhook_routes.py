from __future__ import annotations

"""Endpoint de webhook de provedor de pagamento externo.

Ponto único de entrada para qualquer provedor registrado em
backend/payment_providers.py::PAYMENT_PROVIDERS. O Mercado Pago
(backend/mercadopago_provider.py) é registrado logo abaixo -- se a
integração estiver desabilitada (MERCADO_PAGO_ENABLED=false ou credenciais
ausentes, ver backend/mercadopago_flags.py), o dispatch trata como provedor
não configurado (501), sem tentar validar assinatura nem processar nada.

Nunca aprova um pagamento só com os dados do corpo do webhook: cada provider
consulta o provedor server-to-server (ver MercadoPagoProvider.extrair_evento)
e a confirmação em si sempre passa por
backend/payment_routes.py::registrar_pagamento -- a MESMA função usada pela
confirmação manual e pelo webhook Pix, nunca uma cópia paralela.
"""

import hashlib
import json
import os
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request

from backend.database import conectar
from backend.logging_config import get_logger
from backend.mercadopago_client import MercadoPagoIndisponivel
from backend.mercadopago_flags import mercado_pago_habilitado
from backend.mercadopago_provider import MercadoPagoProvider
from backend.payment_providers import PAYMENT_PROVIDERS
from backend.rate_limit import limitar_requisicoes

logger = get_logger(__name__)

router = APIRouter(prefix="/api/webhooks", tags=["webhooks-pagamentos"])

# Registrado em tempo de import (não em payment_providers.py, para evitar
# import circular -- ver comentário em backend/payment_providers.py). A
# disponibilidade efetiva ainda depende de mercado_pago_habilitado(), checada
# a cada requisição em receber_webhook_pagamento.
PAYMENT_PROVIDERS.setdefault("mercadopago", MercadoPagoProvider())

limitar_webhook_provedor = limitar_requisicoes("webhook_pagamento_provedor", limite=60, janela_segundos=60)

# Mapeamento de status normalizado do provedor -> status interno aceito por
# backend/payment_routes.py::registrar_pagamento (STATUS_PAGAMENTO). Um
# status do provedor sem mapeamento explícito é tratado como "Aguardando"
# (nunca confirma, nunca recusa silenciosamente um estado desconhecido).
STATUS_PROVEDOR_PARA_INTERNO = {
    "approved": "Confirmado",
    "accredited": "Confirmado",
    "pending": "Aguardando",
    "in_process": "Aguardando",
    "authorized": "Aguardando",
    "in_mediation": "Aguardando",
    "rejected": "Recusado",
    "cancelled": "Cancelado",
    "refunded": "Estornado",
    "charged_back": "Estornado",
}

# Status do provedor que representam o pagamento ainda em análise (o pedido
# deve ficar visível ao cliente como "em processamento", nunca pedir que ele
# pague de novo imediatamente).
STATUS_PROVEDOR_EM_ANALISE = {"pending", "in_process", "authorized", "in_mediation"}


def _payload_hash(payload_bruto: bytes) -> str:
    return hashlib.sha256(payload_bruto).hexdigest()


def _atualizar_tentativa_pagamento(conn, *, pedido_id: int, provedor: str, provider_payment_id: str, status_externo: str, status_interno: str, evento_id: str, pagamento_id: int | None, valor: float, agora: str):
    """Atualiza a tentativa de pagamento correspondente (criada por
    backend/mercadopago_routes.py na cobrança inicial) ou cria um registro
    mínimo se o webhook chegou antes/sem uma tentativa local conhecida (ex.:
    reprocessamento, ou o processo do checkout caiu depois de criar a
    cobrança no provedor mas antes de gravar a tentativa localmente)."""
    atualizado = conn.execute(
        """
        UPDATE tentativas_pagamento
           SET status_externo=?, status_interno=?, evento_notificacao_id=?, pagamento_id=COALESCE(?, pagamento_id), atualizado_em=?
         WHERE provedor=? AND provider_payment_id=?
        """,
        (status_externo, status_interno, evento_id, pagamento_id, agora, provedor, provider_payment_id),
    )
    if atualizado.rowcount > 0:
        return
    conn.execute(
        """
        INSERT INTO tentativas_pagamento
            (pedido_id, pagamento_id, provedor, metodo, provider_payment_id, idempotency_key,
             status_interno, status_externo, valor, parcelas, evento_notificacao_id, criado_em, atualizado_em)
        VALUES (?, ?, ?, 'desconhecido', ?, ?, ?, ?, ?, 1, ?, ?, ?)
        """,
        (pedido_id, pagamento_id, provedor, provider_payment_id, f"webhook:{evento_id}", status_interno, status_externo, valor, evento_id, agora, agora),
    )


@router.post("/pagamentos/{provedor}", dependencies=[Depends(limitar_webhook_provedor)])
async def receber_webhook_pagamento(provedor: str, request: Request):
    """Ponto único de entrada para webhooks de provedores de pagamento
    externos. Nunca loga o corpo bruto, headers de assinatura nem
    identificadores sensíveis -- apenas o nome do provedor e o hash do
    payload, suficientes para conciliação manual sem expor dado sensível em
    log."""
    provedor_normalizado = str(provedor or "").strip().lower()
    payload_bruto = await request.body()

    implementacao = PAYMENT_PROVIDERS.get(provedor_normalizado)
    if provedor_normalizado == "mercadopago" and not mercado_pago_habilitado():
        implementacao = None
    if not implementacao:
        logger.info("webhook_pagamento_provedor_nao_configurado", extra={"provedor": provedor_normalizado})
        raise HTTPException(status_code=501, detail="Provedor de pagamento não configurado.")

    if not implementacao.validar_assinatura(payload_bruto, dict(request.headers), dict(request.query_params)):
        logger.warning("webhook_pagamento_assinatura_invalida", extra={"provedor": provedor_normalizado})
        raise HTTPException(status_code=401, detail="Assinatura do webhook inválida.")

    try:
        payload = json.loads(payload_bruto or b"{}")
    except ValueError:
        raise HTTPException(status_code=400, detail="Payload inválido.")

    try:
        evento = implementacao.extrair_evento(payload)
    except MercadoPagoIndisponivel:
        # 503: sinaliza ao provedor que deve reenviar a notificação mais
        # tarde -- nunca perdemos o evento nem o marcamos como processado.
        logger.warning("webhook_pagamento_provedor_indisponivel", extra={"provedor": provedor_normalizado})
        raise HTTPException(status_code=503, detail="Provedor de pagamento temporariamente indisponível. Tente novamente.")

    if not evento:
        return {"ok": True, "ignorado": True}

    agora = datetime.now().isoformat(timespec="seconds")
    with conectar() as conn:
        # UNIQUE(provedor, evento_id) garante idempotência: um reenvio do
        # mesmo evento (comum em webhooks assíncronos) nunca é processado
        # duas vezes -- a segunda tentativa colide na constraint e é ignorada.
        try:
            conn.execute(
                """
                INSERT INTO webhook_eventos (provedor, evento_id, tipo, payload_hash, recebido_em)
                VALUES (?,?,?,?,?)
                """,
                (evento.provedor, evento.evento_id, evento.status, _payload_hash(payload_bruto), agora),
            )
            conn.commit()
        except Exception:
            conn.rollback()
            return {"ok": True, "duplicado": True}

    status_interno_pagamento = STATUS_PROVEDOR_PARA_INTERNO.get(evento.status, "Aguardando")

    # Import tardio (dentro da função) para evitar import circular:
    # backend.payment_routes não importa este módulo, mas mantemos o padrão
    # de importar rotas "pesadas" só quando necessário no processamento de
    # webhook, igual ao restante do módulo antes desta mudança.
    from backend.payment_routes import PagamentoIn, registrar_pagamento, tentar_transicao_status_pagamento

    chave_interna = os.environ.get("MISTICA_SITE_API_KEY", "").strip() or os.environ.get("MISTICA_SYNC_KEY", "").strip()
    # A chave de idempotência inclui o status: o MESMO evento_id pode gerar
    # mais de uma notificação legítima ao longo do tempo (pendente -> depois
    # aprovado, por exemplo) e cada transição real precisa ser registrada.
    # Reenvio do MESMO status (replay do webhook) continua deduplicado
    # normalmente, pois cai na mesma chave com o mesmo payload.
    resposta = registrar_pagamento(
        PagamentoIn(
            venda_id=evento.venda_id,
            forma=f"Cartão de crédito ({evento.provedor.title()})",
            valor=evento.valor_recebido,
            status=status_interno_pagamento,
            observacao=f"Confirmado automaticamente via webhook {evento.provedor} (status do provedor: {evento.status})",
            usuario=f"Webhook {evento.provedor}",
            identificador_evento=evento.provider_payment_id,
        ),
        x_mistica_api_key=chave_interna,
        idempotency_key=f"webhook_{evento.provedor}:{evento.evento_id}",
    )

    if evento.status in STATUS_PROVEDOR_EM_ANALISE:
        # Pagamento ainda em análise no provedor: o pedido fica visível como
        # "em processamento" para o cliente, sem exigir pagamento de novo.
        # Transição best-effort (não falha o webhook se o pedido já mudou de
        # status por outro motivo concorrente).
        with conectar() as conn:
            for status_de_origem in ("Aguardando pagamento", "Pagamento divergente"):
                if tentar_transicao_status_pagamento(conn, evento.venda_id, status_de_origem, "Pagamento em análise"):
                    conn.commit()
                    break
                conn.rollback()

    with conectar() as conn:
        status_interno_tentativa = {
            "Confirmado": "aprovado",
            "Aguardando": "pendente",
            "Recusado": "recusado",
            "Cancelado": "cancelado",
            "Estornado": "estornado",
        }.get(status_interno_pagamento, "pendente")
        _atualizar_tentativa_pagamento(
            conn,
            pedido_id=evento.venda_id,
            provedor=evento.provedor,
            provider_payment_id=evento.provider_payment_id,
            status_externo=evento.status,
            status_interno=status_interno_tentativa,
            evento_id=evento.evento_id,
            pagamento_id=resposta.get("id") if isinstance(resposta, dict) else None,
            valor=evento.valor_recebido,
            agora=agora,
        )
        conn.execute(
            "UPDATE webhook_eventos SET processado_em=? WHERE provedor=? AND evento_id=?",
            (agora, evento.provedor, evento.evento_id),
        )
        if status_interno_pagamento == "Confirmado" and isinstance(resposta, dict) and resposta.get("status_conciliacao") == "ok":
            # Só grava o provedor no pedido quando a confirmação foi de fato
            # aceita (conciliação ok) -- nunca sobre um pedido que ficou
            # divergente/tardio, para o painel administrativo nunca mostrar
            # um provedor "confirmado" que na prática não confirmou nada.
            conn.execute(
                "UPDATE pedidos SET payment_provider=?, provider_payment_id=? WHERE id=?",
                (evento.provedor, evento.provider_payment_id, evento.venda_id),
            )
        conn.commit()

    return {"ok": True, "status_conciliacao": resposta.get("status_conciliacao") if isinstance(resposta, dict) else None}
