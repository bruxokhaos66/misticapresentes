"""Worker de processamento da fila (outbox) de notificações administrativas
por WhatsApp.

Não há Redis/Celery/RQ nesta infraestrutura (ver auditoria em
docs/admin/WHATSAPP_NOTIFICACOES.md) -- o mesmo padrão já usado por
`backend.main._expirar_pedidos_periodicamente` é reaproveitado aqui: uma
tarefa periódica em processo, sobre um outbox persistido no SQLite (nunca só
em memória). Isso dá a mesma confiabilidade que o restante do sistema já
depende (o estado sobrevive a reinício/redeploy; múltiplos workers disputam
o mesmo lote com segurança via CAS na coluna `status`).

Este módulo também é executável como processo separado
(`python -m backend.whatsapp_worker`), caso a operação prefira rodar o
processamento fora do processo web (ex.: um serviço/worker dedicado no
Render) -- ver docs/admin/WHATSAPP_NOTIFICACOES.md, seção de ativação.
"""
from __future__ import annotations

import argparse
import asyncio
import random
import secrets
import time
from datetime import datetime, timedelta

from backend.database import conectar
from backend.logging_config import get_logger
from backend.whatsapp_events import ContextoEventoPedido
from backend.whatsapp_flags import (
    mascarar_numero_whatsapp,
    whatsapp_habilitado,
    whatsapp_max_retries,
    whatsapp_provider_nome,
    whatsapp_retry_base_seconds,
)
from backend.whatsapp_outbox import resolver_numero_por_referencia
from backend.whatsapp_provider import (
    ComponenteTemplate,
    WhatsAppEnvioPermanente,
    WhatsAppEnvioTransitorio,
    construir_provider,
)

logger = get_logger(__name__)

# Lock considerado abandonado (worker morreu/crashou sem liberar) depois
# deste tempo -- outro worker pode reivindicar a linha novamente.
_LOCK_TIMEOUT_SEGUNDOS = 300
_LOTE_PADRAO = 20


def _agora() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _cutoff_lock_abandonado(agora_dt: datetime) -> str:
    return (agora_dt - timedelta(seconds=_LOCK_TIMEOUT_SEGUNDOS)).isoformat(timespec="seconds")


def _proximo_intervalo_segundos(tentativa: int) -> float:
    """Backoff exponencial com jitter. Com a base padrão (60s):
    tentativa 1 ~= 60s, 2 ~= 120s, 3 ~= 240s ... até um teto de 1h --
    aproximação razoável da progressão sugerida (imediato / 1min / 5min /
    15min / 1h), configurável via WHATSAPP_RETRY_BASE_SECONDS/
    WHATSAPP_MAX_RETRIES sem exigir esses valores exatos."""
    base = whatsapp_retry_base_seconds()
    exponencial = base * (2 ** max(0, tentativa - 1))
    intervalo = min(exponencial, 3600)
    jitter = intervalo * random.uniform(0.0, 0.25)
    return intervalo + jitter


def _selecionar_lote(conn, limite: int, agora: str, cutoff_lock: str) -> list[dict]:
    rows = conn.execute(
        """
        SELECT id, status, event_type, order_id, payment_id, recipient_reference,
               template_name, template_language, attempts
        FROM notification_outbox
        WHERE (status IN ('pending','retry') AND (next_attempt_at IS NULL OR next_attempt_at <= ?))
           OR (status='processing' AND locked_at IS NOT NULL AND locked_at < ?)
        ORDER BY id ASC
        LIMIT ?
        """,
        (agora, cutoff_lock, limite),
    ).fetchall()
    return [dict(row) for row in rows]


def _reivindicar_linha(conn, linha_id: int, status_esperado: str, worker_id: str, agora: str) -> bool:
    cur = conn.execute(
        "UPDATE notification_outbox SET status='processing', locked_at=?, locked_by=?, updated_at=? WHERE id=? AND status=?",
        (agora, worker_id, agora, linha_id, status_esperado),
    )
    return cur.rowcount > 0


def _marcar_sucesso(conn, linha_id: int, provider_message_id: str | None, agora: str) -> None:
    conn.execute(
        """
        UPDATE notification_outbox
           SET status='sent', attempts=attempts+1, provider_message_id=?,
               locked_at=NULL, locked_by=NULL, sent_at=?, updated_at=?, last_error_code=NULL, last_error_summary=NULL
         WHERE id=?
        """,
        (provider_message_id, agora, agora, linha_id),
    )


def _marcar_retry(conn, linha_id: int, tentativas_novas: int, codigo_erro: str, resumo_erro: str, proximo: str, agora: str) -> None:
    conn.execute(
        """
        UPDATE notification_outbox
           SET status='retry', attempts=?, next_attempt_at=?, locked_at=NULL, locked_by=NULL,
               last_error_code=?, last_error_summary=?, updated_at=?
         WHERE id=?
        """,
        (tentativas_novas, proximo, codigo_erro[:60], resumo_erro[:200], agora, linha_id),
    )


def _marcar_falha_permanente(conn, linha_id: int, tentativas_novas: int, codigo_erro: str, resumo_erro: str, agora: str) -> None:
    conn.execute(
        """
        UPDATE notification_outbox
           SET status='permanently_failed', attempts=?, locked_at=NULL, locked_by=NULL,
               failed_at=?, last_error_code=?, last_error_summary=?, updated_at=?
         WHERE id=?
        """,
        (tentativas_novas, agora, codigo_erro[:60], resumo_erro[:200], agora, linha_id),
    )


def _processar_linha(conn, provider, linha: dict, worker_id: str) -> str:
    linha_id = linha["id"]
    agora = _agora()
    if not _reivindicar_linha(conn, linha_id, linha["status"], worker_id, agora):
        return "lock_perdido"

    referencia = linha["recipient_reference"]
    numero = resolver_numero_por_referencia(referencia) if referencia else None
    tentativas_novas = int(linha["attempts"] or 0) + 1

    if not numero:
        _marcar_falha_permanente(conn, linha_id, tentativas_novas, "recipient_no_longer_configured", "Destinatário não está mais na lista configurada.", agora)
        return "falha_permanente"

    if not linha["template_name"]:
        _marcar_falha_permanente(conn, linha_id, tentativas_novas, "missing_template", "Template não configurado para este evento.", agora)
        return "falha_permanente"

    try:
        contexto_vazio = ContextoEventoPedido(pedido_id=linha["order_id"] or 0)
        resultado = provider.send_template(
            to=numero,
            template_name=linha["template_name"],
            language=linha["template_language"] or "pt_BR",
            components=_componentes_de_payload(conn, linha_id),
        )
        del contexto_vazio
    except WhatsAppEnvioPermanente as exc:
        _marcar_falha_permanente(conn, linha_id, tentativas_novas, exc.codigo, str(exc), agora)
        return "falha_permanente"
    except WhatsAppEnvioTransitorio as exc:
        max_retries = whatsapp_max_retries()
        if tentativas_novas >= max_retries:
            _marcar_falha_permanente(conn, linha_id, tentativas_novas, exc.codigo, str(exc), agora)
            return "falha_permanente"
        intervalo = exc.retry_after_seconds if exc.retry_after_seconds else _proximo_intervalo_segundos(tentativas_novas)
        proximo = (datetime.now() + timedelta(seconds=intervalo)).isoformat(timespec="seconds")
        _marcar_retry(conn, linha_id, tentativas_novas, exc.codigo, str(exc), proximo, agora)
        return "retry"

    if not resultado.ok:
        _marcar_falha_permanente(conn, linha_id, tentativas_novas, "send_failed", "Provedor recusou o envio sem detalhar o motivo.", agora)
        return "falha_permanente"

    _marcar_sucesso(conn, linha_id, resultado.provider_message_id, agora)
    logger.info(
        "whatsapp_notificacao_enviada",
        extra={
            "evento": "whatsapp_notificacao_enviada",
            "notification_id": linha_id,
            "order_id": linha["order_id"],
            "event_type": linha["event_type"],
            "provider": provider.nome,
            "destinatario_mascarado": mascarar_numero_whatsapp(numero),
        },
    )
    return "enviado"


def _componentes_de_payload(conn, linha_id: int) -> list[ComponenteTemplate]:
    import json as _json

    row = conn.execute("SELECT payload_json FROM notification_outbox WHERE id=?", (linha_id,)).fetchone()
    if not row or not row["payload_json"]:
        return []
    try:
        payload = _json.loads(row["payload_json"])
    except ValueError:
        return []
    campos = {k: v for k, v in payload.items() if k != "event"}
    return [ComponenteTemplate(texto=str(v)) for v in campos.values()]


def processar_lote_outbox(limite: int = _LOTE_PADRAO, worker_id: str | None = None) -> dict:
    """Processa até `limite` notificações pendentes/em retry. Seguro para
    ser chamado por múltiplos workers/processos concorrentemente (CAS na
    coluna `status`). Nunca levanta exceção para uma falha de item
    individual -- cada linha é isolada; um erro inesperado em uma linha é
    registrado como falha permanente dela, sem interromper o lote."""
    if not whatsapp_habilitado():
        return {"skipped": True, "reason": "disabled", "processed": 0}

    worker_id = worker_id or f"worker-{secrets.token_hex(4)}"
    provider = construir_provider(whatsapp_provider_nome())
    agora_dt = datetime.now()
    agora = agora_dt.isoformat(timespec="seconds")
    cutoff_lock = _cutoff_lock_abandonado(agora_dt)

    resultados = {"enviado": 0, "retry": 0, "falha_permanente": 0, "lock_perdido": 0}
    with conectar() as conn:
        lote = _selecionar_lote(conn, limite, agora, cutoff_lock)
        for linha in lote:
            try:
                resultado = _processar_linha(conn, provider, linha, worker_id)
            except Exception as exc:  # nunca deixa uma linha travar o lote inteiro
                logger.warning(
                    "whatsapp_notificacao_erro_inesperado",
                    extra={"evento": "whatsapp_notificacao_erro_inesperado", "notification_id": linha.get("id"), "erro": type(exc).__name__},
                )
                _marcar_retry(conn, linha["id"], int(linha["attempts"] or 0) + 1, "unexpected_error", type(exc).__name__, (agora_dt + timedelta(seconds=60)).isoformat(timespec="seconds"), agora)
                resultado = "retry"
            resultados[resultado] = resultados.get(resultado, 0) + 1
        conn.commit()

    return {"skipped": False, "processed": len(lote), **resultados}


async def _worker_periodico(intervalo_segundos: int = 30):
    while True:
        try:
            resultado = processar_lote_outbox()
            if resultado.get("processed"):
                logger.info("whatsapp_worker_ciclo", extra={"evento": "whatsapp_worker_ciclo", **resultado})
        except Exception as exc:
            logger.warning("whatsapp_worker_ciclo_falhou", extra={"evento": "whatsapp_worker_ciclo_falhou", "erro": str(exc)})
        await asyncio.sleep(intervalo_segundos)


def iniciar_tarefa_periodica_worker(intervalo_segundos: int = 30):
    """Cria a tarefa asyncio a ser gerenciada pelo lifespan de
    backend/main.py -- só deve ser chamada se whatsapp_habilitado() (o
    chamador decide isso, para não criar uma tarefa que nunca faz nada)."""
    return asyncio.create_task(_worker_periodico(intervalo_segundos))


def main():  # pragma: no cover - ponto de entrada de processo separado
    parser = argparse.ArgumentParser(description="Worker standalone do outbox de notificações WhatsApp.")
    parser.add_argument("--loop", action="store_true", help="Roda continuamente em vez de processar um único lote.")
    parser.add_argument("--intervalo", type=int, default=30, help="Segundos entre ciclos no modo --loop.")
    parser.add_argument("--limite", type=int, default=_LOTE_PADRAO, help="Tamanho máximo do lote por ciclo.")
    args = parser.parse_args()

    if not args.loop:
        resultado = processar_lote_outbox(limite=args.limite)
        print(resultado)
        return

    while True:
        resultado = processar_lote_outbox(limite=args.limite)
        print(resultado)
        time.sleep(args.intervalo)


if __name__ == "__main__":  # pragma: no cover
    main()
