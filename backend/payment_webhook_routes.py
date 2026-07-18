from __future__ import annotations

"""Endpoint de webhook de provedor de pagamento externo — estrutura
preparatória para uma integração futura (ex.: Mercado Pago), NÃO integrada
nesta mudança (ver backend/payment_providers.py). Nenhum provedor está
registrado em PAYMENT_PROVIDERS ainda, então toda chamada aqui responde 501
sem tocar em pedidos.status; quando um provedor real for adicionado, este é
o único ponto que precisa mudar para despachar para
backend/payment_routes.py::_classificar_conciliacao/_aplicar_resultado_confirmacao."""

import hashlib
import json
import os
from datetime import datetime

from fastapi import APIRouter, HTTPException, Request

from backend.database import conectar
from backend.logging_config import get_logger
from backend.payment_providers import PAYMENT_PROVIDERS

logger = get_logger(__name__)

router = APIRouter(prefix="/api/webhooks", tags=["webhooks-pagamentos"])


def _payload_hash(payload_bruto: bytes) -> str:
    return hashlib.sha256(payload_bruto).hexdigest()


@router.post("/pagamentos/{provedor}")
async def receber_webhook_pagamento(provedor: str, request: Request):
    """Ponto único de entrada para webhooks de provedores de pagamento
    externos. Nunca loga o corpo bruto, headers de assinatura nem
    identificadores sensíveis — apenas o nome do provedor e o hash do
    payload, suficientes para conciliação manual sem expor dado sensível em
    log."""
    provedor_normalizado = str(provedor or "").strip().lower()
    payload_bruto = await request.body()

    implementacao = PAYMENT_PROVIDERS.get(provedor_normalizado)
    if not implementacao:
        logger.info("webhook_pagamento_provedor_nao_configurado provedor=%s", provedor_normalizado)
        raise HTTPException(status_code=501, detail="Provedor de pagamento não configurado.")

    if not implementacao.validar_assinatura(payload_bruto, dict(request.headers)):
        logger.warning("webhook_pagamento_assinatura_invalida provedor=%s", provedor_normalizado)
        raise HTTPException(status_code=401, detail="Assinatura do webhook inválida.")

    try:
        payload = json.loads(payload_bruto or b"{}")
    except ValueError:
        raise HTTPException(status_code=400, detail="Payload inválido.")

    evento = implementacao.extrair_evento(payload)
    if not evento:
        return {"ok": True, "ignorado": True}

    agora = datetime.now().isoformat(timespec="seconds")
    with conectar() as conn:
        # UNIQUE(provedor, evento_id) garante idempotência: um reenvio do
        # mesmo evento (comum em webhooks assíncronos) nunca é processado
        # duas vezes — a segunda tentativa colide na constraint e é ignorada.
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

    # Nenhum provedor está registrado nesta mudança, então este trecho nunca
    # executa hoje — fica documentado para a integração futura chamar a
    # MESMA conciliação já existente em backend/payment_routes.py, nunca uma
    # cópia paralela dela.
    raise HTTPException(status_code=501, detail="Confirmação automática por provedor ainda não implementada.")
