"""Testes de backend/whatsapp_worker.py -- processamento do outbox, retry
com backoff, falha permanente, lock e concorrência. Provider sempre
mockado (nunca chama rede real)."""
import importlib
import os
import uuid
from datetime import datetime, timedelta

os.environ.setdefault("MISTICA_SITE_API_KEY", "test-api-key")

from database.migrations import init_db

init_db()

from backend.database import conectar


def _reload_habilitado(monkeypatch, max_retries="3", retry_base="1"):
    for chave in list(os.environ):
        if chave.startswith("WHATSAPP_"):
            monkeypatch.delenv(chave, raising=False)
    monkeypatch.setenv("WHATSAPP_NOTIFICATIONS_ENABLED", "true")
    monkeypatch.setenv("WHATSAPP_PROVIDER", "meta_cloud")
    monkeypatch.setenv("WHATSAPP_PHONE_NUMBER_ID", "123456")
    monkeypatch.setenv("WHATSAPP_ACCESS_TOKEN", "token-teste")
    monkeypatch.setenv("WHATSAPP_APP_SECRET", "segredo-teste")
    monkeypatch.setenv("WHATSAPP_VERIFY_TOKEN", "verify-teste")
    monkeypatch.setenv("WHATSAPP_ADMIN_RECIPIENTS", "5511999998888")
    monkeypatch.setenv("WHATSAPP_MAX_RETRIES", max_retries)
    monkeypatch.setenv("WHATSAPP_RETRY_BASE_SECONDS", retry_base)
    for evento, env_var in {
        "PEDIDO_CRIADO": "WHATSAPP_TEMPLATE_ADMIN_NOVO_PEDIDO",
        "PIX_GERADO": "WHATSAPP_TEMPLATE_ADMIN_PIX_GERADO",
        "PAGAMENTO_APROVADO": "WHATSAPP_TEMPLATE_ADMIN_PAGAMENTO_APROVADO",
        "PAGAMENTO_PENDENTE": "WHATSAPP_TEMPLATE_ADMIN_PAGAMENTO_PENDENTE",
        "PAGAMENTO_RECUSADO": "WHATSAPP_TEMPLATE_ADMIN_PAGAMENTO_RECUSADO",
        "PAGAMENTO_EXPIRADO": "WHATSAPP_TEMPLATE_ADMIN_PAGAMENTO_EXPIRADO",
        "PAGAMENTO_CANCELADO": "WHATSAPP_TEMPLATE_ADMIN_PAGAMENTO_CANCELADO",
        "PAGAMENTO_REEMBOLSADO": "WHATSAPP_TEMPLATE_ADMIN_PAGAMENTO_REEMBOLSADO",
        "CHARGEBACK_RECEBIDO": "WHATSAPP_TEMPLATE_ADMIN_CHARGEBACK",
        "FALHA_DE_RECONCILIACAO": "WHATSAPP_TEMPLATE_ADMIN_FALHA_RECONCILIACAO",
    }.items():
        monkeypatch.setenv(env_var, f"template_{evento.lower()}")

    import backend.whatsapp_flags as flags_mod
    importlib.reload(flags_mod)
    import backend.whatsapp_events as events_mod
    importlib.reload(events_mod)
    import backend.whatsapp_outbox as outbox_mod
    importlib.reload(outbox_mod)
    import backend.whatsapp_provider as provider_mod
    importlib.reload(provider_mod)
    import backend.whatsapp_worker as worker_mod
    importlib.reload(worker_mod)
    return worker_mod, outbox_mod, events_mod, provider_mod


def _pedido_id() -> int:
    return abs(hash(uuid.uuid4())) % 1_000_000 + 1


def _limpar_outbox():
    """Isola cada teste do estado deixado por outros arquivos de teste que
    compartilham o mesmo banco (ver tests/conftest.py) -- sem isso,
    resultado agregado de processar_lote_outbox() misturaria linhas de
    testes concorrentes/anteriores."""
    with conectar() as conn:
        conn.execute("DELETE FROM notification_outbox")
        conn.commit()


def _enfileirar(outbox_mod, events_mod, pedido_id, evento=None, sufixo="unico"):
    evento = evento or events_mod.EVENTO_PAGAMENTO_APROVADO
    with conectar() as conn:
        outbox_mod.enfileirar_evento_whatsapp(
            conn, evento=evento, pedido_id=pedido_id, sufixo_idempotencia=sufixo,
            contexto=events_mod.ContextoEventoPedido(pedido_id=pedido_id, valor=10.0),
        )
        conn.commit()


def test_worker_desabilitado_nao_processa(monkeypatch):
    for chave in list(os.environ):
        if chave.startswith("WHATSAPP_"):
            monkeypatch.delenv(chave, raising=False)
    import backend.whatsapp_flags as flags_mod
    importlib.reload(flags_mod)
    import backend.whatsapp_worker as worker_mod
    importlib.reload(worker_mod)
    resultado = worker_mod.processar_lote_outbox()
    assert resultado["skipped"] is True


def test_envio_com_sucesso_marca_sent(monkeypatch):
    worker_mod, outbox_mod, events_mod, provider_mod = _reload_habilitado(monkeypatch)
    _limpar_outbox()
    pedido_id = _pedido_id()
    _enfileirar(outbox_mod, events_mod, pedido_id)

    def _sucesso(self, **kwargs):
        return provider_mod.ResultadoEnvioWhatsApp(ok=True, provider_message_id="wamid.teste", status="sent")

    monkeypatch.setattr(provider_mod.MetaWhatsAppCloudProvider, "send_template", _sucesso)
    resultado = worker_mod.processar_lote_outbox()
    assert resultado["enviado"] == 1
    with conectar() as conn:
        linha = conn.execute("SELECT status, provider_message_id, attempts FROM notification_outbox WHERE order_id=?", (pedido_id,)).fetchone()
    assert linha["status"] == "sent"
    assert linha["provider_message_id"] == "wamid.teste"
    assert linha["attempts"] == 1


def test_erro_transitorio_agenda_retry(monkeypatch):
    worker_mod, outbox_mod, events_mod, provider_mod = _reload_habilitado(monkeypatch, max_retries="5")
    _limpar_outbox()
    pedido_id = _pedido_id()
    _enfileirar(outbox_mod, events_mod, pedido_id)

    def _falha_transitoria(self, **kwargs):
        raise provider_mod.WhatsAppEnvioTransitorio("timeout simulado", codigo="timeout")

    monkeypatch.setattr(provider_mod.MetaWhatsAppCloudProvider, "send_template", _falha_transitoria)
    resultado = worker_mod.processar_lote_outbox()
    assert resultado["retry"] == 1
    with conectar() as conn:
        linha = conn.execute("SELECT status, attempts, next_attempt_at, last_error_code FROM notification_outbox WHERE order_id=?", (pedido_id,)).fetchone()
    assert linha["status"] == "retry"
    assert linha["attempts"] == 1
    assert linha["last_error_code"] == "timeout"
    assert linha["next_attempt_at"] > datetime.now().isoformat(timespec="seconds")


def test_erro_permanente_marca_falha_definitiva(monkeypatch):
    worker_mod, outbox_mod, events_mod, provider_mod = _reload_habilitado(monkeypatch)
    _limpar_outbox()
    pedido_id = _pedido_id()
    _enfileirar(outbox_mod, events_mod, pedido_id)

    def _falha_permanente(self, **kwargs):
        raise provider_mod.WhatsAppEnvioPermanente("template rejeitado", codigo="template_rejected")

    monkeypatch.setattr(provider_mod.MetaWhatsAppCloudProvider, "send_template", _falha_permanente)
    resultado = worker_mod.processar_lote_outbox()
    assert resultado["falha_permanente"] == 1
    with conectar() as conn:
        linha = conn.execute("SELECT status, last_error_code FROM notification_outbox WHERE order_id=?", (pedido_id,)).fetchone()
    assert linha["status"] == "permanently_failed"
    assert linha["last_error_code"] == "template_rejected"


def test_excede_max_retries_vira_falha_permanente(monkeypatch):
    worker_mod, outbox_mod, events_mod, provider_mod = _reload_habilitado(monkeypatch, max_retries="1")
    _limpar_outbox()
    pedido_id = _pedido_id()
    _enfileirar(outbox_mod, events_mod, pedido_id)

    def _falha_transitoria(self, **kwargs):
        raise provider_mod.WhatsAppEnvioTransitorio("timeout simulado", codigo="timeout")

    monkeypatch.setattr(provider_mod.MetaWhatsAppCloudProvider, "send_template", _falha_transitoria)
    resultado = worker_mod.processar_lote_outbox()
    assert resultado["falha_permanente"] == 1
    with conectar() as conn:
        linha = conn.execute("SELECT status, attempts FROM notification_outbox WHERE order_id=?", (pedido_id,)).fetchone()
    assert linha["status"] == "permanently_failed"


def test_recipient_removido_da_config_vira_falha_permanente(monkeypatch):
    worker_mod, outbox_mod, events_mod, provider_mod = _reload_habilitado(monkeypatch)
    _limpar_outbox()
    pedido_id = _pedido_id()
    _enfileirar(outbox_mod, events_mod, pedido_id)

    # Remove o destinatário da configuração DEPOIS de enfileirar -- simula
    # um número removido de WHATSAPP_ADMIN_RECIPIENTS entre o enfileiramento
    # e o processamento.
    monkeypatch.setenv("WHATSAPP_ADMIN_RECIPIENTS", "5511900000000")
    importlib.reload(__import__("backend.whatsapp_flags", fromlist=["x"]))

    resultado = worker_mod.processar_lote_outbox()
    assert resultado["falha_permanente"] == 1
    with conectar() as conn:
        linha = conn.execute("SELECT status, last_error_code FROM notification_outbox WHERE order_id=?", (pedido_id,)).fetchone()
    assert linha["status"] == "permanently_failed"
    assert linha["last_error_code"] == "recipient_no_longer_configured"


def test_lock_recente_nao_e_reivindicado_por_outro_ciclo(monkeypatch):
    worker_mod, outbox_mod, events_mod, provider_mod = _reload_habilitado(monkeypatch)
    _limpar_outbox()
    pedido_id = _pedido_id()
    _enfileirar(outbox_mod, events_mod, pedido_id)
    agora = datetime.now().isoformat(timespec="seconds")
    with conectar() as conn:
        conn.execute(
            "UPDATE notification_outbox SET status='processing', locked_at=?, locked_by='outro-worker' WHERE order_id=?",
            (agora, pedido_id),
        )
        conn.commit()

    def _sucesso(self, **kwargs):
        return provider_mod.ResultadoEnvioWhatsApp(ok=True, provider_message_id="wamid.x", status="sent")

    monkeypatch.setattr(provider_mod.MetaWhatsAppCloudProvider, "send_template", _sucesso)
    resultado = worker_mod.processar_lote_outbox()
    assert resultado["processed"] == 0
    with conectar() as conn:
        linha = conn.execute("SELECT status, locked_by FROM notification_outbox WHERE order_id=?", (pedido_id,)).fetchone()
    assert linha["status"] == "processing"
    assert linha["locked_by"] == "outro-worker"


def test_lock_abandonado_e_recuperado(monkeypatch):
    worker_mod, outbox_mod, events_mod, provider_mod = _reload_habilitado(monkeypatch)
    _limpar_outbox()
    pedido_id = _pedido_id()
    _enfileirar(outbox_mod, events_mod, pedido_id)
    antigo = (datetime.now() - timedelta(seconds=worker_mod._LOCK_TIMEOUT_SEGUNDOS + 60)).isoformat(timespec="seconds")
    with conectar() as conn:
        conn.execute(
            "UPDATE notification_outbox SET status='processing', locked_at=?, locked_by='worker-morto' WHERE order_id=?",
            (antigo, pedido_id),
        )
        conn.commit()

    def _sucesso(self, **kwargs):
        return provider_mod.ResultadoEnvioWhatsApp(ok=True, provider_message_id="wamid.recuperado", status="sent")

    monkeypatch.setattr(provider_mod.MetaWhatsAppCloudProvider, "send_template", _sucesso)
    resultado = worker_mod.processar_lote_outbox()
    assert resultado["enviado"] == 1
    with conectar() as conn:
        linha = conn.execute("SELECT status, provider_message_id FROM notification_outbox WHERE order_id=?", (pedido_id,)).fetchone()
    assert linha["status"] == "sent"


def test_backoff_dentro_da_faixa_esperada(monkeypatch):
    worker_mod, *_ = _reload_habilitado(monkeypatch, retry_base="60")
    intervalo1 = worker_mod._proximo_intervalo_segundos(1)
    intervalo2 = worker_mod._proximo_intervalo_segundos(2)
    assert 60 <= intervalo1 <= 75
    assert 120 <= intervalo2 <= 150
    assert intervalo2 > intervalo1


def test_worker_periodico_nao_bloqueia_o_event_loop(monkeypatch):
    """processar_lote_outbox() é síncrona e pode fazer chamadas HTTP
    bloqueantes (até WHATSAPP_REQUEST_TIMEOUT_SECONDS por mensagem). Se
    _worker_periodico a chamasse direto (sem asyncio.to_thread), ela
    travaria o único event loop do processo (uvicorn roda sem --workers,
    ver render.yaml) durante todo o lote -- inclusive o webhook do Mercado
    Pago, que compartilha o mesmo processo.

    Prova por tempo de relógio (não só contagem final, que sempre bateria
    mesmo bloqueando -- asyncio.gather só espera as corrotinas
    terminarem, sem prazo): um "lote lento" de 0.3s rodando em paralelo com
    uma corrotina que leva 0.2s só pode terminar em ~0.3s (dominado pelo
    maior) se o loop nunca for bloqueado; se bloquear, o tempo total sobe
    para ~0.3s + 0.2s = 0.5s (serializado)."""
    import asyncio
    import time

    worker_mod, *_ = _reload_habilitado(monkeypatch)

    def _lote_lento(*args, **kwargs):
        time.sleep(0.3)  # simula uma chamada HTTP bloqueante lenta
        return {"skipped": False, "processed": 0, "enviado": 0, "retry": 0, "falha_permanente": 0, "lock_perdido": 0}

    monkeypatch.setattr(worker_mod, "processar_lote_outbox", _lote_lento)

    async def _outra_corrotina_concorrente():
        for _ in range(10):
            await asyncio.sleep(0.02)

    async def _cenario():
        tarefa_worker = asyncio.create_task(worker_mod._worker_periodico(intervalo_segundos=999))
        inicio = time.monotonic()
        await _outra_corrotina_concorrente()
        duracao = time.monotonic() - inicio
        tarefa_worker.cancel()
        with __import__("contextlib").suppress(asyncio.CancelledError):
            await tarefa_worker
        return duracao

    duracao = asyncio.run(_cenario())
    # Concorrente de verdade: ~0.2s (a corrotina não espera o "lote lento"
    # de 0.3s terminar). Bloqueando o loop, ficaria em ~0.5s ou mais.
    assert duracao < 0.4, f"event loop parece ter sido bloqueado pelo worker (duração={duracao:.3f}s)"
