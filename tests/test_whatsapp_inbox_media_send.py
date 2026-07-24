"""Testes do envio de mídia (imagem/áudio) pelo compose avançado da Central
de Atendimento -- POST /api/admin/whatsapp/conversations/{id}/media (ver
backend/whatsapp_inbox_routes.py::rota_enviar_midia). Segue o mesmo padrão
de tests/test_whatsapp_inbox_admin.py e tests/test_whatsapp_atendimento.py:
nunca chama a Graph API real, sessões são inseridas diretamente em
painel_sessoes, provider é sempre um fake injetado via monkeypatch."""
from __future__ import annotations

import importlib
import os
import secrets as secrets_mod
import tempfile
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
# O padrão de whatsapp_media_storage_dir() é "/data/uploads/whatsapp" (disco
# persistente de produção) -- inexistente/sem permissão de escrita em CI e em
# qualquer máquina de desenvolvedor sem esse ponto de montagem. Mesma correção
# de tests/test_whatsapp_inbox_admin.py/test_whatsapp_media_service.py (que
# usam monkeypatch.setenv com tmp_path por teste), mas aqui como padrão do
# módulo inteiro via setdefault, já que salvar_midia_local() é exercitado por
# quase todo teste deste arquivo.
os.environ.setdefault("WHATSAPP_MEDIA_STORAGE_DIR", tempfile.mkdtemp(prefix="whatsapp-media-teste-"))

from fastapi.testclient import TestClient

main = importlib.import_module("backend.main")
client = TestClient(main.app)
client.__enter__()

import backend.atendimento_repository as atendimento_repo
import backend.whatsapp_inbox_routes as inbox_routes
from backend.database import conectar
from backend.whatsapp_inbox_repository import obter_ou_criar_conversa, upsert_contact
from backend.whatsapp_provider import ResultadoEnvioWhatsApp

ORIGEM_PERMITIDA = {"Origin": "http://localhost:8000"}

# JPEG mínimo real (1x1 pixel) -- mesma fixture de tests/test_whatsapp_inbox_admin.py.
JPEG_MINIMO = bytes.fromhex(
    "ffd8ffe000104a46494600010100000100010000ffdb0043000302020202020302020"
    "2030303030406040404040408060605070605080808080909090808080a0b0c0a"
    "0a0b0a08080b0d0b0b0c0c0c0c0c07090e0f0d0c0e0b0c0c0cffc9000b0800010001010"
    "1001100ffcc000601000101ffda0008010100003f00d2cf20ffd9"
)

# Cabeçalho EBML real de um arquivo WebM -- suficiente para passar pela
# identificação por magic bytes (identificar_audio_saida), que é tudo que o
# endpoint valida para áudio (áudio não passa por um parser estrutural
# completo como Pillow faz para imagem).
AUDIO_WEBM_MINIMO = bytes.fromhex("1a45dfa3") + b"\x00" * 64

HTML_DISFARÇADO_DE_JPEG = b"<html><body><script>alert(1)</script></body></html>" + b"\x00" * 32

SVG_MALICIOSO = b"<svg xmlns='http://www.w3.org/2000/svg'><script>alert(1)</script></svg>"


def _habilitar(monkeypatch):
    monkeypatch.setattr(inbox_routes, "whatsapp_cloud_inbox_habilitado", lambda: True)


def _ligar_multiatendente(monkeypatch, *, ligado: bool = True):
    monkeypatch.setattr(atendimento_repo, "atendimento_sellers_habilitado", lambda: ligado)
    monkeypatch.setattr(inbox_routes, "atendimento_sellers_habilitado", lambda: ligado)


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


def _criar_usuario(*, perfil="vendedor", atendimento_enabled=1) -> int:
    login = f"user-{uuid.uuid4().hex[:10]}"
    with conectar() as conn:
        cur = conn.execute(
            """
            INSERT INTO usuarios (nome, login, senha_hash, senha_salt, perfil, ativo,
                                   atendimento_enabled, atendimento_status)
            VALUES (?,?,?,?,?,?,?,?)
            """,
            (login, login, "hash-fake", "salt-fake", perfil, 1, atendimento_enabled, "online"),
        )
        conn.commit()
        return int(cur.lastrowid)


def _sessao(usuario_id: int, perfil: str) -> str:
    token = secrets_mod.token_urlsafe(24)
    agora = datetime.now()
    with conectar() as conn:
        conn.execute(
            """INSERT INTO painel_sessoes (token, usuario_id, login, nome, perfil, ip, user_agent, criada_em, expira_em, ultimo_acesso)
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (token, usuario_id, f"login-{usuario_id}", f"Usuario {usuario_id}", perfil, "127.0.0.1", "pytest", agora.isoformat(sep=" ", timespec="seconds"), (agora + timedelta(hours=1)).isoformat(sep=" ", timespec="seconds"), agora.isoformat(sep=" ", timespec="seconds")),
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


class _ProviderFalso:
    def __init__(self, *, upload_falha=False, envio_ok=True):
        self.upload_falha = upload_falha
        self.envio_ok = envio_ok
        self.chamadas_upload = 0
        self.chamadas_envio = 0

    def upload_media(self, *, conteudo, mime_type, filename):
        self.chamadas_upload += 1
        if self.upload_falha:
            from backend.whatsapp_provider import WhatsAppEnvioPermanente
            raise WhatsAppEnvioPermanente("Falha simulada de upload.", codigo="upload_failed")
        return f"meta-media-{uuid.uuid4().hex}"

    def send_inbox_media(self, *, to, media_id, media_type, caption=None):
        self.chamadas_envio += 1
        return ResultadoEnvioWhatsApp(ok=self.envio_ok, provider_message_id=f"wamid.fake.{uuid.uuid4().hex}", status="sent" if self.envio_ok else "failed")


def _sessao_admin_client(token):
    client.cookies.set("mistica_painel_sessao", token)


def _limpar_sessao():
    client.cookies.delete("mistica_painel_sessao")


def _upload_imagem(conversa_id, *, idem=None, jpeg=JPEG_MINIMO, headers_extra=None, caption=None):
    headers = {**ORIGEM_PERMITIDA}
    if idem:
        headers["Idempotency-Key"] = idem
    if headers_extra:
        headers.update(headers_extra)
    data = {"media_kind": "image"}
    if caption is not None:
        data["caption"] = caption
    files = {"file": ("foto.jpg", jpeg, "image/jpeg")}
    return client.post(f"/api/admin/whatsapp/conversations/{conversa_id}/media", data=data, files=files, headers=headers)


def _upload_audio(conversa_id, *, idem=None, audio=AUDIO_WEBM_MINIMO):
    headers = {**ORIGEM_PERMITIDA}
    if idem:
        headers["Idempotency-Key"] = idem
    data = {"media_kind": "audio"}
    files = {"file": ("gravacao.webm", audio, "audio/webm")}
    return client.post(f"/api/admin/whatsapp/conversations/{conversa_id}/media", data=data, files=files, headers=headers)


# ---------------------------------------------------------------------------
# Autenticação / autorização
# ---------------------------------------------------------------------------

def test_enviar_midia_sem_sessao_e_401(monkeypatch):
    _habilitar(monkeypatch)
    conversa_id = _criar_conversa_com_inbound()
    resp = _upload_imagem(conversa_id, idem=f"idem-{uuid.uuid4().hex}")
    assert resp.status_code == 401


def test_enviar_midia_vendedor_sem_assumir_conversa_e_403(monkeypatch):
    _habilitar(monkeypatch)
    _ligar_multiatendente(monkeypatch, ligado=True)
    monkeypatch.setattr(inbox_routes, "construir_provider", lambda nome: _ProviderFalso())
    conversa_id = _criar_conversa_com_inbound()
    vendedor_id = _criar_usuario(perfil="vendedor")
    token = _sessao(vendedor_id, "vendedor")
    _sessao_admin_client(token)
    try:
        resp = _upload_imagem(conversa_id, idem=f"idem-{uuid.uuid4().hex}")
        assert resp.status_code == 403
    finally:
        _limpar_sessao()


# ---------------------------------------------------------------------------
# Envio bem-sucedido
# ---------------------------------------------------------------------------

def test_enviar_imagem_valida_200(monkeypatch):
    _habilitar(monkeypatch)
    fake = _ProviderFalso()
    monkeypatch.setattr(inbox_routes, "construir_provider", lambda nome: fake)
    conversa_id = _criar_conversa_com_inbound()
    token = _sessao_admin()
    _sessao_admin_client(token)
    try:
        resp = _upload_imagem(conversa_id, idem=f"idem-{uuid.uuid4().hex}", caption="Olha essa peça!")
        assert resp.status_code == 200
        corpo = resp.json()
        assert corpo["ok"] is True
        assert corpo["status"] == "sent"
        assert fake.chamadas_upload == 1
        assert fake.chamadas_envio == 1
        with conectar() as conn:
            mensagem = conn.execute(
                "SELECT * FROM whatsapp_messages WHERE conversation_id=? AND direction='outbound' ORDER BY id DESC LIMIT 1",
                (conversa_id,),
            ).fetchone()
        assert mensagem["message_type"] == "image"
        assert mensagem["status"] == "sent"
        assert mensagem["media_mime_type"] == "image/jpeg"
        assert mensagem["media_path"]
        assert mensagem["media_id"]
        assert mensagem["text_body"] == "Olha essa peça!"
    finally:
        _limpar_sessao()


def test_enviar_audio_valido_200(monkeypatch):
    _habilitar(monkeypatch)
    fake = _ProviderFalso()
    monkeypatch.setattr(inbox_routes, "construir_provider", lambda nome: fake)
    conversa_id = _criar_conversa_com_inbound()
    token = _sessao_admin()
    _sessao_admin_client(token)
    try:
        resp = _upload_audio(conversa_id, idem=f"idem-{uuid.uuid4().hex}")
        assert resp.status_code == 200
        corpo = resp.json()
        assert corpo["ok"] is True
        with conectar() as conn:
            mensagem = conn.execute(
                "SELECT * FROM whatsapp_messages WHERE conversation_id=? AND direction='outbound' ORDER BY id DESC LIMIT 1",
                (conversa_id,),
            ).fetchone()
        assert mensagem["message_type"] == "audio"
        assert mensagem["media_mime_type"] == "audio/webm"
        # Áudio nunca grava legenda/texto.
        assert mensagem["text_body"] is None
    finally:
        _limpar_sessao()


def test_legenda_em_audio_e_rejeitada(monkeypatch):
    _habilitar(monkeypatch)
    monkeypatch.setattr(inbox_routes, "construir_provider", lambda nome: _ProviderFalso())
    conversa_id = _criar_conversa_com_inbound()
    token = _sessao_admin()
    _sessao_admin_client(token)
    try:
        resp = client.post(
            f"/api/admin/whatsapp/conversations/{conversa_id}/media",
            data={"media_kind": "audio", "caption": "não deveria ser aceito"},
            files={"file": ("gravacao.webm", AUDIO_WEBM_MINIMO, "audio/webm")},
            headers={"Idempotency-Key": f"idem-{uuid.uuid4().hex}", **ORIGEM_PERMITIDA},
        )
        assert resp.status_code == 422
    finally:
        _limpar_sessao()


# ---------------------------------------------------------------------------
# Validação de tamanho (streaming, nunca bufferiza tudo antes de checar)
# ---------------------------------------------------------------------------

def test_imagem_maior_que_limite_e_rejeitada_sem_criar_mensagem(monkeypatch):
    _habilitar(monkeypatch)
    monkeypatch.setattr(inbox_routes, "whatsapp_outbound_image_max_bytes", lambda: 1024)
    monkeypatch.setattr(inbox_routes, "construir_provider", lambda nome: _ProviderFalso())
    conversa_id = _criar_conversa_com_inbound()
    token = _sessao_admin()
    _sessao_admin_client(token)
    try:
        grande = JPEG_MINIMO + (b"\x00" * 2000)
        chave = f"idem-{uuid.uuid4().hex}"
        with conectar() as conn:
            antes = conn.execute("SELECT COUNT(*) AS n FROM whatsapp_messages WHERE conversation_id=?", (conversa_id,)).fetchone()["n"]
        resp = _upload_imagem(conversa_id, idem=chave, jpeg=grande)
        assert resp.status_code in (413, 422)
        with conectar() as conn:
            depois = conn.execute("SELECT COUNT(*) AS n FROM whatsapp_messages WHERE conversation_id=?", (conversa_id,)).fetchone()["n"]
        assert depois == antes

        # A chave de idempotência foi liberada -- uma nova tentativa (com
        # arquivo válido e a MESMA chave) não fica presa a uma reivindicação
        # morta nem devolve uma resposta de erro "cacheada".
        resp2 = _upload_imagem(conversa_id, idem=chave)
        assert resp2.status_code == 200
    finally:
        _limpar_sessao()


# ---------------------------------------------------------------------------
# MIME/extensão forjados -- magic bytes sempre decidem, nunca o content-type
# declarado pelo navegador.
# ---------------------------------------------------------------------------

def test_html_disfarcado_de_jpeg_e_rejeitado(monkeypatch):
    _habilitar(monkeypatch)
    fake = _ProviderFalso()
    monkeypatch.setattr(inbox_routes, "construir_provider", lambda nome: fake)
    conversa_id = _criar_conversa_com_inbound()
    token = _sessao_admin()
    _sessao_admin_client(token)
    try:
        resp = _upload_imagem(conversa_id, idem=f"idem-{uuid.uuid4().hex}", jpeg=HTML_DISFARÇADO_DE_JPEG)
        assert resp.status_code == 422
        assert fake.chamadas_upload == 0
        with conectar() as conn:
            total = conn.execute("SELECT COUNT(*) AS n FROM whatsapp_messages WHERE conversation_id=?", (conversa_id,)).fetchone()["n"]
        assert total == 0
    finally:
        _limpar_sessao()


def test_svg_com_script_e_rejeitado_mesmo_renomeado_para_png(monkeypatch):
    _habilitar(monkeypatch)
    fake = _ProviderFalso()
    monkeypatch.setattr(inbox_routes, "construir_provider", lambda nome: fake)
    conversa_id = _criar_conversa_com_inbound()
    token = _sessao_admin()
    _sessao_admin_client(token)
    try:
        resp = client.post(
            f"/api/admin/whatsapp/conversations/{conversa_id}/media",
            data={"media_kind": "image"},
            files={"file": ("imagem.png", SVG_MALICIOSO, "image/svg+xml")},
            headers={"Idempotency-Key": f"idem-{uuid.uuid4().hex}", **ORIGEM_PERMITIDA},
        )
        assert resp.status_code == 422
        assert fake.chamadas_upload == 0
    finally:
        _limpar_sessao()


def test_media_kind_invalido_e_rejeitado(monkeypatch):
    _habilitar(monkeypatch)
    monkeypatch.setattr(inbox_routes, "construir_provider", lambda nome: _ProviderFalso())
    conversa_id = _criar_conversa_com_inbound()
    token = _sessao_admin()
    _sessao_admin_client(token)
    try:
        resp = client.post(
            f"/api/admin/whatsapp/conversations/{conversa_id}/media",
            data={"media_kind": "video"},
            files={"file": ("v.mp4", b"\x00\x00\x00\x18ftypmp42", "video/mp4")},
            headers={"Idempotency-Key": f"idem-{uuid.uuid4().hex}", **ORIGEM_PERMITIDA},
        )
        assert resp.status_code == 422
    finally:
        _limpar_sessao()


# ---------------------------------------------------------------------------
# Janela de atendimento de 24h -- mesma regra da Meta aplicada a texto.
# ---------------------------------------------------------------------------

def test_midia_fora_da_janela_de_24h_e_rejeitada(monkeypatch):
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
    _sessao_admin_client(token)
    try:
        resp = _upload_imagem(conversa_id, idem=f"idem-{uuid.uuid4().hex}")
        assert resp.status_code == 422
        assert "janela" in resp.json()["detail"].lower()
    finally:
        _limpar_sessao()


# ---------------------------------------------------------------------------
# Idempotência
# ---------------------------------------------------------------------------

def test_duplicata_com_mesma_idempotency_key_nao_reenvia(monkeypatch):
    _habilitar(monkeypatch)
    fake = _ProviderFalso()
    monkeypatch.setattr(inbox_routes, "construir_provider", lambda nome: fake)
    conversa_id = _criar_conversa_com_inbound()
    token = _sessao_admin()
    _sessao_admin_client(token)
    try:
        chave = f"idem-{uuid.uuid4().hex}"
        resp1 = _upload_imagem(conversa_id, idem=chave)
        assert resp1.status_code == 200
        resp2 = _upload_imagem(conversa_id, idem=chave)
        assert resp2.status_code == 200
        assert resp1.json() == resp2.json()
        assert fake.chamadas_upload == 1
        assert fake.chamadas_envio == 1
        with conectar() as conn:
            total = conn.execute(
                "SELECT COUNT(*) AS n FROM whatsapp_messages WHERE conversation_id=? AND direction='outbound'", (conversa_id,)
            ).fetchone()
        assert total["n"] == 1
    finally:
        _limpar_sessao()


# ---------------------------------------------------------------------------
# Regressão: mídia OUTBOUND é servida de volta pelo endpoint de download
# autenticado, existente e direction-agnostic (item 9 da especificação).
# ---------------------------------------------------------------------------

def test_imagem_outbound_pode_ser_recuperada_via_endpoint_de_midia(monkeypatch):
    _habilitar(monkeypatch)
    fake = _ProviderFalso()
    monkeypatch.setattr(inbox_routes, "construir_provider", lambda nome: fake)
    conversa_id = _criar_conversa_com_inbound()
    token = _sessao_admin()
    _sessao_admin_client(token)
    try:
        resp_envio = _upload_imagem(conversa_id, idem=f"idem-{uuid.uuid4().hex}")
        assert resp_envio.status_code == 200
        message_id = resp_envio.json()["message_id"]

        resp_midia = client.get(f"/api/admin/whatsapp/media/{message_id}")
        assert resp_midia.status_code == 200
        assert resp_midia.content == JPEG_MINIMO
        assert resp_midia.headers["content-type"] == "image/jpeg"
    finally:
        _limpar_sessao()
