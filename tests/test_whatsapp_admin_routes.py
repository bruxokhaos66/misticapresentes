"""Testes de backend/whatsapp_admin_routes.py -- histórico, status
operacional, reprocessamento e cancelamento no painel administrativo."""
import importlib
import os
import uuid

os.environ.setdefault("MISTICA_SITE_API_KEY", "test-api-key")
os.environ.setdefault("MISTICA_SYNC_KEY", "test-api-key")
os.environ.setdefault("MISTICA_PIX_KEY", "49999999999")

from fastapi.testclient import TestClient

main = importlib.import_module("backend.main")
client = TestClient(main.app)
client.__enter__()

from backend.database import conectar

TEST_API_KEY = os.environ["MISTICA_SITE_API_KEY"]
HEADERS = {"X-Mistica-Api-Key": TEST_API_KEY}


def _inserir_linha(order_id: int, status: str, event_type: str = "PAGAMENTO_APROVADO") -> int:
    with conectar() as conn:
        cur = conn.execute(
            """
            INSERT INTO notification_outbox
                (event_type, aggregate_type, aggregate_id, order_id, channel, provider,
                 recipient_reference, template_name, template_language, payload_json,
                 idempotency_key, status, attempts, created_at, updated_at)
            VALUES (?, 'pedido', ?, ?, 'whatsapp', 'meta_cloud', 'admin:teste', 'tpl', 'pt_BR', '{}', ?, ?, 0, '2026-01-01T00:00:00', '2026-01-01T00:00:00')
            """,
            (event_type, order_id, order_id, f"idem:{uuid.uuid4().hex}", status),
        )
        conn.commit()
        return int(cur.lastrowid)


def test_status_sem_autenticacao_e_negado():
    resp = client.get("/api/admin/whatsapp-notificacoes/status")
    assert resp.status_code == 401


def test_status_autenticado_mostra_desabilitado_por_padrao():
    resp = client.get("/api/admin/whatsapp-notificacoes/status", headers=HEADERS)
    assert resp.status_code == 200
    corpo = resp.json()
    assert corpo["ok"] is True
    assert "queue_counts" in corpo
    # Sem token/segredo neste corpo -- diagnóstico nunca expõe credencial.
    texto = str(corpo)
    assert "WHATSAPP_ACCESS_TOKEN" not in texto


def test_listar_notificacoes_filtra_por_pedido():
    order_id = abs(hash(uuid.uuid4())) % 1_000_000 + 1
    _inserir_linha(order_id, "sent")
    resp = client.get("/api/admin/whatsapp-notificacoes", params={"order_id": order_id}, headers=HEADERS)
    assert resp.status_code == 200
    corpo = resp.json()
    assert corpo["total"] == 1
    assert corpo["notificacoes"][0]["order_id"] == order_id
    # Nunca expõe a referência interna do destinatário nem payload bruto.
    assert "recipient_reference" not in corpo["notificacoes"][0]


def test_reprocessar_falha_permanente():
    order_id = abs(hash(uuid.uuid4())) % 1_000_000 + 1
    linha_id = _inserir_linha(order_id, "permanently_failed")
    resp = client.post(f"/api/admin/whatsapp-notificacoes/{linha_id}/reprocessar", headers=HEADERS)
    assert resp.status_code == 200
    with conectar() as conn:
        linha = conn.execute("SELECT status, attempts FROM notification_outbox WHERE id=?", (linha_id,)).fetchone()
    assert linha["status"] == "retry"
    assert linha["attempts"] == 0


def test_reprocessar_linha_ja_enviada_e_rejeitado():
    order_id = abs(hash(uuid.uuid4())) % 1_000_000 + 1
    linha_id = _inserir_linha(order_id, "sent")
    resp = client.post(f"/api/admin/whatsapp-notificacoes/{linha_id}/reprocessar", headers=HEADERS)
    assert resp.status_code == 409


def test_reprocessar_inexistente_404():
    resp = client.post("/api/admin/whatsapp-notificacoes/99999999/reprocessar", headers=HEADERS)
    assert resp.status_code == 404


def test_cancelar_pendente():
    order_id = abs(hash(uuid.uuid4())) % 1_000_000 + 1
    linha_id = _inserir_linha(order_id, "pending")
    resp = client.post(f"/api/admin/whatsapp-notificacoes/{linha_id}/cancelar", headers=HEADERS)
    assert resp.status_code == 200
    with conectar() as conn:
        linha = conn.execute("SELECT status FROM notification_outbox WHERE id=?", (linha_id,)).fetchone()
    assert linha["status"] == "cancelled"


def test_cancelar_linha_ja_enviada_e_rejeitado():
    order_id = abs(hash(uuid.uuid4())) % 1_000_000 + 1
    linha_id = _inserir_linha(order_id, "sent")
    resp = client.post(f"/api/admin/whatsapp-notificacoes/{linha_id}/cancelar", headers=HEADERS)
    assert resp.status_code == 409
