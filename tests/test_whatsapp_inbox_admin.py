"""Testes da API administrativa da Central de Atendimento WhatsApp
(backend/whatsapp_inbox_routes.py). Nunca chama a Graph API real -- o envio é
sempre feito por um provider falso injetado via monkeypatch."""
from __future__ import annotations

import importlib
import os
import secrets as secrets_mod
import uuid
from datetime import datetime, timedelta

os.environ.setdefault("MISTICA_SITE_API_KEY", "test-api-key")
os.environ.setdefault("MISTICA_SYNC_KEY", "test-api-key")
os.environ.setdefault("MISTICA_PIX_KEY", "49999999999")
os.environ.setdefault("WHATSAPP_APP_SECRET", "app-secret-teste-" + uuid.uuid4().hex[:8])
os.environ.setdefault("WHATSAPP_VERIFY_TOKEN", "verify-teste-" + uuid.uuid4().hex[:8])
os.environ.setdefault("WHATSAPP_PROVIDER", "meta_cloud")
os.environ.setdefault("WHATSAPP_PHONE_NUMBER_ID", "123456")
os.environ.setdefault("WHATSAPP_ACCESS_TOKEN", "token-de-teste")

from fastapi.testclient import TestClient

main = importlib.import_module("backend.main")
client = TestClient(main.app)
client.__enter__()

from backend.database import conectar
import backend.whatsapp_inbox_routes as inbox_routes
from backend.whatsapp_inbox_repository import obter_ou_criar_conversa, upsert_contact
from backend.whatsapp_provider import ResultadoEnvioWhatsApp


def _sessao_admin(perfil: str = "adm") -> str:
    token = secrets_mod.token_urlsafe(24)
    agora = datetime.now()
    with conectar() as conn:
        conn.execute(
            """INSERT INTO painel_sessoes (token, usuario_id, login, nome, perfil, ip, user_agent, criada_em, expira_em, ultimo_acesso)
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (token, 1, "admin-teste", "Admin Teste", perfil, "127.0.0.1", "pytest", agora.isoformat(sep=" ", timespec="seconds"), (agora + timedelta(hours=1)).isoformat(sep=" ", timespec="seconds"), agora.isoformat(sep=" ", timespec="seconds")),
        )
        conn.commit()
    return token


def _criar_conversa_com_inbound(wa_id: str | None = None) -> int:
    wa_id = wa_id or ("5511" + str(uuid.uuid4().int)[:9])
    with conectar() as conn:
        contato = upsert_contact(conn, wa_id=wa_id, profile_name="Cliente Teste")
        conversa = obter_ou_criar_conversa(conn, contact_id=contato["id"])
        conn.execute(
            "UPDATE whatsapp_conversations SET last_inbound_at=? WHERE id=?",
            (datetime.now().isoformat(timespec="seconds"), conversa["id"]),
        )
        conn.commit()
    return conversa["id"]


ORIGEM_PERMITIDA = {"Origin": "http://localhost:8000"}


def _habilitar(monkeypatch):
    monkeypatch.setattr(inbox_routes, "whatsapp_cloud_inbox_habilitado", lambda: True)


def _diagnostico_ok(*a, **k):
    return {"enabled": True, "configuration_complete": True, "webhook_ready": True, "configuration_errors": []}


def test_status_exige_sessao_admin(monkeypatch):
    _habilitar(monkeypatch)
    resp = client.get("/api/admin/whatsapp/status")
    assert resp.status_code == 401


def test_status_com_sessao_nao_admin_e_negado(monkeypatch):
    _habilitar(monkeypatch)
    token = _sessao_admin(perfil="vendedor")
    client.cookies.set("mistica_painel_sessao", token)
    try:
        resp = client.get("/api/admin/whatsapp/status")
        assert resp.status_code == 403
    finally:
        client.cookies.delete("mistica_painel_sessao")


def test_status_com_sessao_admin(monkeypatch):
    _habilitar(monkeypatch)
    monkeypatch.setattr(inbox_routes, "diagnostico_configuracao_whatsapp_cloud_inbox", _diagnostico_ok)
    token = _sessao_admin()
    client.cookies.set("mistica_painel_sessao", token)
    try:
        resp = client.get("/api/admin/whatsapp/status")
        assert resp.status_code == 200
        corpo = resp.json()
        assert corpo["ok"] is True
        assert "WHATSAPP_ACCESS_TOKEN" not in str(corpo)
        assert "token-de-teste" not in str(corpo)
    finally:
        client.cookies.delete("mistica_painel_sessao")


def test_listar_e_obter_conversa(monkeypatch):
    _habilitar(monkeypatch)
    wa_id = "5511" + str(uuid.uuid4().int)[:9]
    conversa_id = _criar_conversa_com_inbound(wa_id)
    token = _sessao_admin()
    client.cookies.set("mistica_painel_sessao", token)
    try:
        # Filtra pelos últimos dígitos deste contato -- o banco de teste é
        # compartilhado entre execuções locais repetidas (não é recriado a
        # cada rodada), então uma paginação sem filtro poderia não conter
        # esta conversa se muitas outras já existirem com data mais recente.
        resp = client.get("/api/admin/whatsapp/conversations", params={"page_size": 5, "q": wa_id[-4:]})
        assert resp.status_code == 200
        assert any(c["id"] == conversa_id for c in resp.json()["conversations"])

        resp_detalhe = client.get(f"/api/admin/whatsapp/conversations/{conversa_id}")
        assert resp_detalhe.status_code == 200
        assert resp_detalhe.json()["conversation"]["id"] == conversa_id
        assert "phone_e164" not in resp_detalhe.json()["conversation"]
    finally:
        client.cookies.delete("mistica_painel_sessao")


def test_conversa_inexistente_404(monkeypatch):
    _habilitar(monkeypatch)
    token = _sessao_admin()
    client.cookies.set("mistica_painel_sessao", token)
    try:
        resp = client.get("/api/admin/whatsapp/conversations/999999999")
        assert resp.status_code == 404
    finally:
        client.cookies.delete("mistica_painel_sessao")


def test_marcar_lida_zera_contador(monkeypatch):
    _habilitar(monkeypatch)
    conversa_id = _criar_conversa_com_inbound()
    with conectar() as conn:
        conn.execute("UPDATE whatsapp_conversations SET unread_count=3 WHERE id=?", (conversa_id,))
        conn.commit()
    token = _sessao_admin()
    client.cookies.set("mistica_painel_sessao", token)
    try:
        resp = client.post(f"/api/admin/whatsapp/conversations/{conversa_id}/read", headers=ORIGEM_PERMITIDA)
        assert resp.status_code == 200
        with conectar() as conn:
            linha = conn.execute("SELECT unread_count FROM whatsapp_conversations WHERE id=?", (conversa_id,)).fetchone()
        assert linha["unread_count"] == 0
    finally:
        client.cookies.delete("mistica_painel_sessao")


def test_atualizar_status_conversa(monkeypatch):
    _habilitar(monkeypatch)
    conversa_id = _criar_conversa_com_inbound()
    token = _sessao_admin()
    client.cookies.set("mistica_painel_sessao", token)
    try:
        resp = client.patch(f"/api/admin/whatsapp/conversations/{conversa_id}", json={"status": "resolved"}, headers=ORIGEM_PERMITIDA)
        assert resp.status_code == 200
        resp_invalido = client.patch(f"/api/admin/whatsapp/conversations/{conversa_id}", json={"status": "status_invalido"}, headers=ORIGEM_PERMITIDA)
        assert resp_invalido.status_code == 422
    finally:
        client.cookies.delete("mistica_painel_sessao")


def test_vincular_cliente_inexistente_404(monkeypatch):
    _habilitar(monkeypatch)
    conversa_id = _criar_conversa_com_inbound()
    token = _sessao_admin()
    client.cookies.set("mistica_painel_sessao", token)
    try:
        resp = client.post(f"/api/admin/whatsapp/conversations/{conversa_id}/link-customer", json={"customer_id": 999999999}, headers=ORIGEM_PERMITIDA)
        assert resp.status_code == 404
    finally:
        client.cookies.delete("mistica_painel_sessao")


class _ProviderFalso:
    def send_inbox_text(self, *, to, texto, reply_to_meta_message_id=None):
        return ResultadoEnvioWhatsApp(ok=True, provider_message_id=f"wamid.fake.{uuid.uuid4().hex}", status="sent")

    def send_template(self, *, to, template_name, language, components=()):
        return ResultadoEnvioWhatsApp(ok=True, provider_message_id=f"wamid.fake.{uuid.uuid4().hex}", status="sent")


def test_enviar_texto_dentro_da_janela(monkeypatch):
    _habilitar(monkeypatch)
    monkeypatch.setattr(inbox_routes, "construir_provider", lambda nome: _ProviderFalso())
    conversa_id = _criar_conversa_com_inbound()
    token = _sessao_admin()
    client.cookies.set("mistica_painel_sessao", token)
    try:
        chave = f"idem-{uuid.uuid4().hex}"
        resp = client.post(
            f"/api/admin/whatsapp/conversations/{conversa_id}/messages",
            json={"text": "Olá! Já verifico seu pedido."},
            headers={"Idempotency-Key": chave, **ORIGEM_PERMITIDA},
        )
        assert resp.status_code == 200
        assert resp.json()["ok"] is True
        with conectar() as conn:
            mensagem = conn.execute(
                "SELECT * FROM whatsapp_messages WHERE conversation_id=? AND direction='outbound'", (conversa_id,)
            ).fetchone()
        assert mensagem["status"] == "sent"
        assert mensagem["sent_by_admin"] == "Admin Teste"

        # Reenvio com a MESMA Idempotency-Key nunca cria uma segunda mensagem.
        resp2 = client.post(
            f"/api/admin/whatsapp/conversations/{conversa_id}/messages",
            json={"text": "Olá! Já verifico seu pedido."},
            headers={"Idempotency-Key": chave, **ORIGEM_PERMITIDA},
        )
        assert resp2.status_code == 200
        with conectar() as conn:
            total = conn.execute(
                "SELECT COUNT(*) AS n FROM whatsapp_messages WHERE conversation_id=? AND direction='outbound'", (conversa_id,)
            ).fetchone()
        assert total["n"] == 1
    finally:
        client.cookies.delete("mistica_painel_sessao")


def test_enviar_texto_fora_da_janela_exige_template(monkeypatch):
    _habilitar(monkeypatch)
    monkeypatch.setattr(inbox_routes, "construir_provider", lambda nome: _ProviderFalso())
    wa_id = "5511" + str(uuid.uuid4().int)[:9]
    with conectar() as conn:
        contato = upsert_contact(conn, wa_id=wa_id, profile_name="Cliente Antigo")
        conversa = obter_ou_criar_conversa(conn, contact_id=contato["id"])
        antigo = (datetime.now() - timedelta(hours=48)).isoformat(timespec="seconds")
        conn.execute("UPDATE whatsapp_conversations SET last_inbound_at=? WHERE id=?", (antigo, conversa["id"]))
        conn.commit()
    conversa_id = conversa["id"]

    token = _sessao_admin()
    client.cookies.set("mistica_painel_sessao", token)
    try:
        resp = client.post(
            f"/api/admin/whatsapp/conversations/{conversa_id}/messages",
            json={"text": "Mensagem livre fora da janela"},
            headers={"Idempotency-Key": f"idem-{uuid.uuid4().hex}", **ORIGEM_PERMITIDA},
        )
        assert resp.status_code == 422
        assert "template" in resp.json()["detail"].lower()
    finally:
        client.cookies.delete("mistica_painel_sessao")


def test_enviar_sem_texto_nem_template_e_rejeitado(monkeypatch):
    _habilitar(monkeypatch)
    monkeypatch.setattr(inbox_routes, "construir_provider", lambda nome: _ProviderFalso())
    conversa_id = _criar_conversa_com_inbound()
    token = _sessao_admin()
    client.cookies.set("mistica_painel_sessao", token)
    try:
        resp = client.post(
            f"/api/admin/whatsapp/conversations/{conversa_id}/messages",
            json={},
            headers={"Idempotency-Key": f"idem-{uuid.uuid4().hex}", **ORIGEM_PERMITIDA},
        )
        assert resp.status_code == 422
    finally:
        client.cookies.delete("mistica_painel_sessao")


# ---------------------------------------------------------------------------
# Mídia recebida via WhatsApp (correção da imagem branca -- Fase 1)
#
# Fixture: JPEG mínimo real (1x1 pixel) -- não é mock de chamada, é conteúdo
# binário de verdade. Os testes comparam os BYTES finais servidos pelo
# endpoint com os bytes originais da fixture, não apenas se a função foi
# chamada -- é exatamente a garantia que faltava para provar que o painel
# não entrega mais um arquivo em branco/inválido.
# ---------------------------------------------------------------------------
from backend.whatsapp_inbox_repository import registrar_mensagem_recebida
import backend.whatsapp_media_service as media_service

JPEG_MINIMO = bytes.fromhex(
    "ffd8ffe000104a46494600010100000100010000ffdb0043000302020202020302020"
    "2030303030406040404040408060605070605080808080909090808080a0b0c0a"
    "0a0b0a08080b0d0b0b0c0c0c0c0c07090e0f0d0c0e0b0c0c0cffc9000b0800010001010"
    "1001100ffcc000601000101ffda0008010100003f00d2cf20ffd9"
)


def _criar_mensagem_midia(media_id: str = "wamid.media.teste", conversation_id: int | None = None) -> int:
    conversation_id = conversation_id or _criar_conversa_com_inbound()
    with conectar() as conn:
        message_id, _ = registrar_mensagem_recebida(
            conn,
            conversation_id=conversation_id,
            meta_message_id=f"wamid.{uuid.uuid4().hex}",
            message_type="image",
            media_id=media_id,
        )
        conn.commit()
    return message_id


def test_baixar_midia_bytes_identicos_a_fixture_real():
    """Não usa só mock que confirma chamada: baixa via função real do
    serviço com transporte HTTP falso e confere byte a byte."""
    import httpx

    def handler(request: httpx.Request) -> httpx.Response:
        if "graph.facebook.com" in str(request.url):
            return httpx.Response(200, json={"url": "https://lookaside.fbsbx.com/whatsapp_business/attachments/?id=abc", "file_size": len(JPEG_MINIMO)})
        if "lookaside.fbsbx.com" in str(request.url):
            return httpx.Response(200, content=JPEG_MINIMO, headers={"content-type": "image/jpeg"})
        return httpx.Response(404)

    transport = httpx.MockTransport(handler)
    original = httpx.Client

    def client_falso(*a, **kw):
        kw["transport"] = transport
        return original(*a, **kw)

    import backend.whatsapp_media_service as svc
    with mock_httpx_client(svc, client_falso):
        conteudo, extensao, mime = svc.baixar_midia("media-real")
    assert conteudo == JPEG_MINIMO
    assert extensao == "jpg"
    assert mime == "image/jpeg"


class mock_httpx_client:
    def __init__(self, modulo, cliente_falso):
        self.modulo = modulo
        self.cliente_falso = cliente_falso

    def __enter__(self):
        import httpx
        self._original = httpx.Client
        httpx.Client = self.cliente_falso
        return self

    def __exit__(self, *a):
        import httpx
        httpx.Client = self._original


def test_endpoint_media_serve_bytes_identicos_e_extensao_correta(monkeypatch, tmp_path):
    """Ponta a ponta: mensagem inbound com media_id -> endpoint autenticado
    -> bytes servidos idênticos à fixture -> Content-Disposition com
    extensão correta (o bug original: nome de arquivo sem extensão fazia o
    download 'parecer' inválido mesmo com bytes corretos)."""
    monkeypatch.setenv("WHATSAPP_MEDIA_STORAGE_DIR", str(tmp_path))
    _habilitar(monkeypatch)
    message_id = _criar_mensagem_midia()

    def baixar_falso(media_id):
        return JPEG_MINIMO, "jpg", "image/jpeg"

    monkeypatch.setattr(inbox_routes, "baixar_midia", baixar_falso)

    token = _sessao_admin()
    client.cookies.set("mistica_painel_sessao", token)
    try:
        resp = client.get(f"/api/admin/whatsapp/media/{message_id}")
        assert resp.status_code == 200
        assert resp.content == JPEG_MINIMO
        assert resp.headers["content-type"] == "image/jpeg"
        assert resp.headers["content-disposition"].endswith('.jpg"')
        assert resp.headers["cache-control"] == "private, no-store"
        assert resp.headers["x-content-type-options"] == "nosniff"

        # segunda chamada: já está em disco, não deve rebaixar da Meta
        monkeypatch.setattr(inbox_routes, "baixar_midia", lambda media_id: (_ for _ in ()).throw(AssertionError("não deveria rebaixar mídia já disponível")))
        resp2 = client.get(f"/api/admin/whatsapp/media/{message_id}")
        assert resp2.status_code == 200
        assert resp2.content == JPEG_MINIMO
    finally:
        client.cookies.delete("mistica_painel_sessao")


def test_endpoint_media_html_disfarcado_e_rejeitado(monkeypatch):
    """HTML/script disfarçado de imagem (mime_type mentiroso da Meta) é
    rejeitado pelos magic bytes reais -- nunca vira Blob no navegador."""
    _habilitar(monkeypatch)
    message_id = _criar_mensagem_midia()

    def baixar_falso(media_id):
        raise media_service.WhatsAppMediaError("Tipo de arquivo não reconhecido/permitido (magic bytes).", codigo="unsupported_media_type")

    monkeypatch.setattr(inbox_routes, "baixar_midia", baixar_falso)
    token = _sessao_admin()
    client.cookies.set("mistica_painel_sessao", token)
    try:
        resp = client.get(f"/api/admin/whatsapp/media/{message_id}")
        assert resp.status_code == 502
        assert resp.headers["content-type"].startswith("application/json")
    finally:
        client.cookies.delete("mistica_painel_sessao")


def test_endpoint_media_json_de_erro_da_meta_nao_vira_arquivo(monkeypatch):
    """Se a Meta devolve um erro (401/404) em vez da mídia, o endpoint nunca
    grava/serve um JSON como se fosse imagem."""
    _habilitar(monkeypatch)
    message_id = _criar_mensagem_midia()

    def baixar_falso(media_id):
        raise media_service.WhatsAppMediaError("Metadados da mídia indisponíveis (http 401).", codigo="metadata_unavailable")

    monkeypatch.setattr(inbox_routes, "baixar_midia", baixar_falso)
    token = _sessao_admin()
    client.cookies.set("mistica_painel_sessao", token)
    try:
        resp = client.get(f"/api/admin/whatsapp/media/{message_id}")
        assert resp.status_code == 502
        with conectar() as conn:
            linha = conn.execute("SELECT media_path, media_status FROM whatsapp_messages WHERE id=?", (message_id,)).fetchone()
        assert linha["media_path"] is None
        assert linha["media_status"] == "failed"
    finally:
        client.cookies.delete("mistica_painel_sessao")


def test_endpoint_media_arquivo_inexistente_no_disco(monkeypatch):
    """media_path aponta pra um arquivo já apagado do disco -> 404
    explícito, nunca um corpo vazio/branco silencioso."""
    _habilitar(monkeypatch)
    message_id = _criar_mensagem_midia()
    with conectar() as conn:
        conn.execute(
            "UPDATE whatsapp_messages SET media_path=?, media_mime_type=?, media_status='available' WHERE id=?",
            ("/data/uploads/whatsapp/nao-existe-" + uuid.uuid4().hex + ".jpg", "image/jpeg", message_id),
        )
        conn.commit()
    token = _sessao_admin()
    client.cookies.set("mistica_painel_sessao", token)
    try:
        resp = client.get(f"/api/admin/whatsapp/media/{message_id}")
        assert resp.status_code == 404
    finally:
        client.cookies.delete("mistica_painel_sessao")


def test_endpoint_media_duas_requisicoes_concorrentes_nao_baixam_duas_vezes(monkeypatch):
    """Reivindicação atômica (media_status pending->downloading): a segunda
    requisição concorrente nunca dispara um segundo download da Meta."""
    _habilitar(monkeypatch)
    message_id = _criar_mensagem_midia()

    chamadas = {"n": 0}

    def baixar_falso(media_id):
        chamadas["n"] += 1
        return JPEG_MINIMO, "jpg", "image/jpeg"

    monkeypatch.setattr(inbox_routes, "baixar_midia", baixar_falso)

    # simula a segunda requisição chegando enquanto a primeira já reivindicou
    # a linha (media_status='downloading') mas ainda não terminou o download
    with conectar() as conn:
        conn.execute("UPDATE whatsapp_messages SET media_status='downloading' WHERE id=?", (message_id,))
        conn.commit()

    token = _sessao_admin()
    client.cookies.set("mistica_painel_sessao", token)
    try:
        resp = client.get(f"/api/admin/whatsapp/media/{message_id}")
        assert resp.status_code == 409
        assert chamadas["n"] == 0
    finally:
        client.cookies.delete("mistica_painel_sessao")


def test_endpoint_media_mensagem_sem_midia_404(monkeypatch):
    _habilitar(monkeypatch)
    conversa_id = _criar_conversa_com_inbound()
    with conectar() as conn:
        message_id, _ = registrar_mensagem_recebida(
            conn,
            conversation_id=conversa_id,
            meta_message_id=f"wamid.{uuid.uuid4().hex}",
            message_type="text",
            text_body="oi",
        )
        conn.commit()
    token = _sessao_admin()
    client.cookies.set("mistica_painel_sessao", token)
    try:
        resp = client.get(f"/api/admin/whatsapp/media/{message_id}")
        assert resp.status_code == 404
    finally:
        client.cookies.delete("mistica_painel_sessao")


def test_endpoint_media_exige_sessao_admin(monkeypatch):
    _habilitar(monkeypatch)
    message_id = _criar_mensagem_midia()
    resp = client.get(f"/api/admin/whatsapp/media/{message_id}")
    assert resp.status_code == 401
