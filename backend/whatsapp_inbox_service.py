"""Processamento de mensagens RECEBIDAS de clientes via WhatsApp Cloud API
(Central de Atendimento) -- consumido só por backend/whatsapp_webhook_routes.py
depois que a assinatura HMAC já foi validada e o JSON já foi parseado.

Nunca confia em nenhum campo do payload sem sanitizar (telefone, nome,
texto, legendas, nomes de arquivo); nunca executa/renderiza HTML vindo da
mensagem; tipos desconhecidos são armazenados com metadados seguros em vez
de descartados silenciosamente ou de derrubar o webhook inteiro.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta

from backend.logging_config import get_logger
from backend.whatsapp_flags import whatsapp_webhook_event_retention_days
from backend.whatsapp_inbox_repository import (
    atualizar_conversa_apos_inbound,
    obter_ou_criar_conversa,
    registrar_evento_webhook,
    registrar_mensagem_recebida,
    sanitizar_nome_perfil,
    upsert_contact,
)

logger = get_logger(__name__)

TIPOS_MIDIA = {"image", "document", "audio", "video", "sticker"}
TIPOS_CONHECIDOS = TIPOS_MIDIA | {"text", "location", "contacts", "interactive", "button", "reaction", "unknown"}


def _payload_hash(valor: dict) -> str:
    canonico = json.dumps(valor, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(canonico.encode("utf-8")).hexdigest()


def _extrair_texto_por_tipo(mensagem: dict) -> str | None:
    tipo = mensagem.get("type")
    if tipo == "text":
        return str((mensagem.get("text") or {}).get("body") or "")
    if tipo == "interactive":
        interativo = mensagem.get("interactive") or {}
        for chave in ("button_reply", "list_reply"):
            sub = interativo.get(chave)
            if sub:
                return str(sub.get("title") or sub.get("id") or "[Mensagem interativa]")
        return "[Mensagem interativa]"
    if tipo == "button":
        return str((mensagem.get("button") or {}).get("text") or "[Botão de template]")
    if tipo == "location":
        return "[Localização recebida]"
    if tipo == "contacts":
        return "[Contato recebido]"
    if tipo == "reaction":
        emoji = str((mensagem.get("reaction") or {}).get("emoji") or "")
        return f"[Reação: {emoji}]" if emoji else "[Reação recebida]"
    if tipo in TIPOS_MIDIA:
        legenda = str((mensagem.get(tipo) or {}).get("caption") or "")
        return legenda or None
    return "[Tipo de mensagem ainda não suportado]"


def _extrair_media(mensagem: dict) -> tuple[str | None, str | None]:
    tipo = mensagem.get("type")
    if tipo not in TIPOS_MIDIA:
        return None, None
    bloco = mensagem.get(tipo) or {}
    media_id = str(bloco.get("id") or "").strip() or None
    mime = str(bloco.get("mime_type") or "").strip() or None
    return media_id, mime


def processar_webhook_mensagens(conn, payload: dict) -> dict:
    """Persiste as mensagens recebidas contidas em `payload` (formato oficial
    da Cloud API: entry[].changes[].value.messages[]/.contacts[]).

    Idempotente por design: cada mensagem individual é reivindicada em
    whatsapp_webhook_events por meta_message_id (fallback: hash canônico do
    bloco `value`, para o caso raro de faltar id). Reenvio da Meta do MESMO
    evento nunca duplica mensagem/conversa/notificação. Nunca levanta exceção
    para um payload parcialmente ausente ou tipo desconhecido -- sempre
    retorna um resumo de contadores."""
    processadas = 0
    duplicadas = 0
    ignoradas = 0

    try:
        entradas = payload.get("entry") or []
    except AttributeError:
        return {"processadas": 0, "duplicadas": 0, "ignoradas": 0}

    expira_em = (datetime.now() + timedelta(days=whatsapp_webhook_event_retention_days())).isoformat(timespec="seconds")

    for entrada in entradas:
        for mudanca in (entrada.get("changes") or []):
            valor = mudanca.get("value") or {}
            mensagens = valor.get("messages") or []
            if not mensagens:
                continue

            contatos_por_wa_id = {}
            for contato in (valor.get("contacts") or []):
                wa_id = str(contato.get("wa_id") or "").strip()
                if wa_id:
                    contatos_por_wa_id[wa_id] = sanitizar_nome_perfil((contato.get("profile") or {}).get("name"))

            for mensagem in mensagens:
                if not isinstance(mensagem, dict):
                    ignoradas += 1
                    continue

                meta_message_id = str(mensagem.get("id") or "").strip() or None
                event_key = meta_message_id or ("hash:" + _payload_hash(mensagem))

                reivindicado = registrar_evento_webhook(
                    conn,
                    event_key=event_key,
                    event_type="message",
                    payload_hash=_payload_hash(mensagem),
                    expires_at=expira_em,
                )
                if not reivindicado:
                    duplicadas += 1
                    continue

                try:
                    wa_id_remetente = str(mensagem.get("from") or "").strip()
                    if not wa_id_remetente:
                        ignoradas += 1
                        continue

                    contato = upsert_contact(conn, wa_id=wa_id_remetente, profile_name=contatos_por_wa_id.get(wa_id_remetente))
                    conversa = obter_ou_criar_conversa(conn, contact_id=contato["id"])

                    tipo = str(mensagem.get("type") or "unknown")
                    if tipo not in TIPOS_CONHECIDOS:
                        tipo = "unknown"
                    media_id, media_mime = _extrair_media(mensagem)
                    contexto = mensagem.get("context") or {}
                    reply_to = str(contexto.get("id") or "").strip() or None
                    timestamp_meta = str(mensagem.get("timestamp") or "").strip() or None

                    _, inserida = registrar_mensagem_recebida(
                        conn,
                        conversation_id=conversa["id"],
                        meta_message_id=meta_message_id,
                        message_type=tipo,
                        text_body=_extrair_texto_por_tipo(mensagem),
                        media_id=media_id,
                        media_mime_type=media_mime,
                        reply_to_meta_message_id=reply_to,
                        timestamp_meta=timestamp_meta,
                    )
                    if inserida:
                        atualizar_conversa_apos_inbound(conn, conversation_id=conversa["id"])
                        processadas += 1
                    else:
                        duplicadas += 1
                except Exception:
                    logger.exception("whatsapp_inbox_mensagem_falha_processamento", extra={"evento": "whatsapp_inbox_mensagem_falha_processamento"})
                    ignoradas += 1

    return {"processadas": processadas, "duplicadas": duplicadas, "ignoradas": ignoradas}
