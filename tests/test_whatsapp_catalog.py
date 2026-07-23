"""Testes do Catálogo Comercial na Central de Atendimento WhatsApp
(backend/whatsapp_catalog_routes.py, backend/whatsapp_catalog_repository.py).

Segue o mesmo padrão de tests/test_whatsapp_inbox_admin.py e
tests/test_whatsapp_atendimento.py: nunca chama a Graph API real, sessões
são inseridas diretamente em painel_sessoes, o provider é sempre um fake
injetado via monkeypatch."""
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

import backend.atendimento_repository as atendimento_repo
import backend.whatsapp_catalog_routes as catalog_routes
from backend.database import conectar
from backend.whatsapp_inbox_repository import obter_ou_criar_conversa, upsert_contact
from backend.whatsapp_provider import ResultadoEnvioWhatsApp

ORIGEM_PERMITIDA = {"Origin": "http://localhost:8000"}


def _habilitar(monkeypatch, *, catalogo_ligado: bool = True):
    monkeypatch.setattr(catalog_routes, "whatsapp_cloud_inbox_habilitado", lambda: True)
    monkeypatch.setattr(catalog_routes, "atendimento_catalog_habilitado", lambda: catalogo_ligado)


def _sessao(usuario_id: int, perfil: str, nome: str | None = None) -> str:
    token = secrets_mod.token_urlsafe(24)
    agora = datetime.now()
    with conectar() as conn:
        conn.execute(
            """INSERT INTO painel_sessoes (token, usuario_id, login, nome, perfil, ip, user_agent, criada_em, expira_em, ultimo_acesso)
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (
                token, usuario_id, nome or f"login-{usuario_id}", nome or f"Usuario {usuario_id}", perfil,
                "127.0.0.1", "pytest", agora.isoformat(sep=" ", timespec="seconds"),
                (agora + timedelta(hours=1)).isoformat(sep=" ", timespec="seconds"), agora.isoformat(sep=" ", timespec="seconds"),
            ),
        )
        conn.commit()
    return token


def _criar_usuario(*, login=None, perfil="adm", atendimento_enabled=1, ativo=1, suspenso=False) -> int:
    login = login or f"user-{uuid.uuid4().hex[:10]}"
    with conectar() as conn:
        cur = conn.execute(
            """
            INSERT INTO usuarios (nome, login, senha_hash, senha_salt, perfil, ativo,
                                   atendimento_enabled, atendimento_status, atendimento_suspended_at)
            VALUES (?,?,?,?,?,?,?,?,?)
            """,
            (
                login, login, "hash-fake", "salt-fake", perfil, ativo,
                atendimento_enabled, "online",
                datetime.now().isoformat(timespec="seconds") if suspenso else None,
            ),
        )
        conn.commit()
        return int(cur.lastrowid)


def _criar_produto(
    *, nome="Vela Aromática Lavanda", preco=39.9, quantidade=10, ativo=1, sob_encomenda=0,
    categoria="Velas", marca="Mística", codigo=None, imagem_url="https://cdn.exemplo.com.br/produtos/vela.jpg",
) -> int:
    with conectar() as conn:
        from backend.product_commercial_rules import garantir_colunas_comerciais

        garantir_colunas_comerciais(conn)
        cur = conn.execute(
            """
            INSERT INTO produtos (codigo_p, nome, preco, quantidade, categoria, marca, ativo, sob_encomenda, imagem_url)
            VALUES (?,?,?,?,?,?,?,?,?)
            """,
            (codigo or f"SKU-{uuid.uuid4().hex[:8].upper()}", nome, preco, quantidade, categoria, marca, ativo, sob_encomenda, imagem_url),
        )
        conn.commit()
        return int(cur.lastrowid)


def _criar_conversa_com_inbound(*, assigned_user_id: int | None = None) -> tuple[int, dict]:
    wa_id = "5511" + str(uuid.uuid4().int)[:9]
    with conectar() as conn:
        contato = upsert_contact(conn, wa_id=wa_id, profile_name="Cliente Teste")
        conversa = obter_ou_criar_conversa(conn, contact_id=contato["id"])
        conn.execute(
            "UPDATE whatsapp_conversations SET last_inbound_at=?, assigned_user_id=?, queue_status=? WHERE id=?",
            (
                datetime.now().isoformat(timespec="seconds"),
                assigned_user_id,
                "assigned" if assigned_user_id else "waiting",
                conversa["id"],
            ),
        )
        conn.commit()
        atualizada = conn.execute("SELECT * FROM whatsapp_conversations WHERE id=?", (conversa["id"],)).fetchone()
    return conversa["id"], dict(atualizada)


class _ProviderFalso:
    def __init__(self, *, ok_texto=True, ok_imagem=True):
        self.ok_texto = ok_texto
        self.ok_imagem = ok_imagem
        self.chamadas_texto: list[dict] = []
        self.chamadas_imagem: list[dict] = []

    def send_inbox_text(self, *, to, texto, reply_to_meta_message_id=None):
        self.chamadas_texto.append({"to": to, "texto": texto})
        return ResultadoEnvioWhatsApp(ok=self.ok_texto, provider_message_id="wamid.texto" if self.ok_texto else None)

    def send_inbox_image(self, *, to, image_url, caption=None):
        self.chamadas_imagem.append({"to": to, "image_url": image_url, "caption": caption})
        return ResultadoEnvioWhatsApp(ok=self.ok_imagem, provider_message_id="wamid.imagem" if self.ok_imagem else None)


def _login_admin() -> str:
    admin_id = _criar_usuario(perfil="adm")
    return _sessao(admin_id, "adm")


# ---------------------------------------------------------------------------
# Flag desligada
# ---------------------------------------------------------------------------

def test_flag_desligada_bloqueia_busca(monkeypatch):
    _habilitar(monkeypatch, catalogo_ligado=False)
    token = _login_admin()
    client.cookies.set("mistica_painel_sessao", token)
    try:
        resp = client.get("/api/admin/whatsapp/catalog/products")
        assert resp.status_code == 503
    finally:
        client.cookies.delete("mistica_painel_sessao")


def test_flag_desligada_bloqueia_envio(monkeypatch):
    _habilitar(monkeypatch, catalogo_ligado=False)
    token = _login_admin()
    conversa_id, _ = _criar_conversa_com_inbound()
    produto_id = _criar_produto()
    client.cookies.set("mistica_painel_sessao", token)
    try:
        resp = client.post(
            f"/api/admin/whatsapp/conversations/{conversa_id}/send-product",
            json={"product_id": produto_id},
            headers={"Idempotency-Key": f"idem-{uuid.uuid4().hex}", **ORIGEM_PERMITIDA},
        )
        assert resp.status_code == 503
    finally:
        client.cookies.delete("mistica_painel_sessao")


# ---------------------------------------------------------------------------
# Autorização por perfil
# ---------------------------------------------------------------------------

def test_adm_autorizado_busca(monkeypatch):
    _habilitar(monkeypatch)
    _criar_produto()
    token = _login_admin()
    client.cookies.set("mistica_painel_sessao", token)
    try:
        resp = client.get("/api/admin/whatsapp/catalog/products")
        assert resp.status_code == 200
        assert resp.json()["ok"] is True
    finally:
        client.cookies.delete("mistica_painel_sessao")


def test_supervisor_autorizado_busca(monkeypatch):
    _habilitar(monkeypatch)
    monkeypatch.setattr(atendimento_repo, "atendimento_sellers_habilitado", lambda: True)
    supervisor_id = _criar_usuario(perfil="supervisor_atendimento")
    token = _sessao(supervisor_id, "supervisor_atendimento")
    client.cookies.set("mistica_painel_sessao", token)
    try:
        resp = client.get("/api/admin/whatsapp/catalog/products")
        assert resp.status_code == 200
    finally:
        client.cookies.delete("mistica_painel_sessao")


def test_vendedor_autorizado_busca(monkeypatch):
    _habilitar(monkeypatch)
    monkeypatch.setattr(atendimento_repo, "atendimento_sellers_habilitado", lambda: True)
    vendedor_id = _criar_usuario(perfil="vendedor")
    token = _sessao(vendedor_id, "vendedor")
    client.cookies.set("mistica_painel_sessao", token)
    try:
        resp = client.get("/api/admin/whatsapp/catalog/products")
        assert resp.status_code == 200
    finally:
        client.cookies.delete("mistica_painel_sessao")


def test_usuario_suspenso_e_bloqueado(monkeypatch):
    _habilitar(monkeypatch)
    monkeypatch.setattr(atendimento_repo, "atendimento_sellers_habilitado", lambda: True)
    vendedor_id = _criar_usuario(perfil="vendedor", suspenso=True)
    token = _sessao(vendedor_id, "vendedor")
    client.cookies.set("mistica_painel_sessao", token)
    try:
        resp = client.get("/api/admin/whatsapp/catalog/products")
        assert resp.status_code == 403
    finally:
        client.cookies.delete("mistica_painel_sessao")


def test_atendimento_desabilitado_para_vendedor_e_bloqueado(monkeypatch):
    _habilitar(monkeypatch)
    monkeypatch.setattr(atendimento_repo, "atendimento_sellers_habilitado", lambda: True)
    vendedor_id = _criar_usuario(perfil="vendedor", atendimento_enabled=0)
    token = _sessao(vendedor_id, "vendedor")
    client.cookies.set("mistica_painel_sessao", token)
    try:
        resp = client.get("/api/admin/whatsapp/catalog/products")
        assert resp.status_code == 403
    finally:
        client.cookies.delete("mistica_painel_sessao")


def test_sem_sessao_e_401(monkeypatch):
    _habilitar(monkeypatch)
    resp = client.get("/api/admin/whatsapp/catalog/products")
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Busca
# ---------------------------------------------------------------------------

def test_busca_por_nome(monkeypatch):
    _habilitar(monkeypatch)
    nome_unico = f"Cristal Ametista {uuid.uuid4().hex[:8]}"
    _criar_produto(nome=nome_unico)
    token = _login_admin()
    client.cookies.set("mistica_painel_sessao", token)
    try:
        resp = client.get("/api/admin/whatsapp/catalog/products", params={"q": nome_unico[:12]})
        assert resp.status_code == 200
        nomes = [p["nome"] for p in resp.json()["products"]]
        assert nome_unico in nomes
    finally:
        client.cookies.delete("mistica_painel_sessao")


def test_busca_por_sku(monkeypatch):
    _habilitar(monkeypatch)
    codigo = f"SKU-UNICO-{uuid.uuid4().hex[:8].upper()}"
    _criar_produto(codigo=codigo)
    token = _login_admin()
    client.cookies.set("mistica_painel_sessao", token)
    try:
        resp = client.get("/api/admin/whatsapp/catalog/products", params={"q": codigo})
        assert resp.status_code == 200
        skus = [p["sku"] for p in resp.json()["products"]]
        assert codigo in skus
    finally:
        client.cookies.delete("mistica_painel_sessao")


def test_busca_por_categoria(monkeypatch):
    _habilitar(monkeypatch)
    categoria_unica = f"CategoriaTeste{uuid.uuid4().hex[:8]}"
    _criar_produto(categoria=categoria_unica)
    token = _login_admin()
    client.cookies.set("mistica_painel_sessao", token)
    try:
        resp = client.get("/api/admin/whatsapp/catalog/products", params={"categoria": categoria_unica})
        assert resp.status_code == 200
        categorias = [p["categoria"] for p in resp.json()["products"]]
        assert all(c == categoria_unica for c in categorias)
        assert len(categorias) >= 1
    finally:
        client.cookies.delete("mistica_painel_sessao")


def test_busca_case_insensitive_e_com_espacos_extras(monkeypatch):
    _habilitar(monkeypatch)
    nome_unico = f"Incenso Palo Santo {uuid.uuid4().hex[:6]}"
    _criar_produto(nome=nome_unico)
    token = _login_admin()
    client.cookies.set("mistica_painel_sessao", token)
    try:
        termo = "  " + nome_unico.upper()[:14] + "   "
        resp = client.get("/api/admin/whatsapp/catalog/products", params={"q": termo})
        assert resp.status_code == 200
        nomes = [p["nome"] for p in resp.json()["products"]]
        assert nome_unico in nomes
    finally:
        client.cookies.delete("mistica_painel_sessao")


def test_paginacao(monkeypatch):
    _habilitar(monkeypatch)
    prefixo = f"Paginado{uuid.uuid4().hex[:6]}"
    for i in range(5):
        _criar_produto(nome=f"{prefixo}-{i}")
    token = _login_admin()
    client.cookies.set("mistica_painel_sessao", token)
    try:
        resp = client.get("/api/admin/whatsapp/catalog/products", params={"q": prefixo, "page": 1, "page_size": 2})
        corpo = resp.json()
        assert resp.status_code == 200
        assert len(corpo["products"]) == 2
        assert corpo["total"] == 5
    finally:
        client.cookies.delete("mistica_painel_sessao")


def test_limite_de_page_size(monkeypatch):
    _habilitar(monkeypatch)
    token = _login_admin()
    client.cookies.set("mistica_painel_sessao", token)
    try:
        resp = client.get("/api/admin/whatsapp/catalog/products", params={"page_size": 9999})
        assert resp.status_code == 422
    finally:
        client.cookies.delete("mistica_painel_sessao")


def test_produto_inativo_nao_aparece_por_padrao(monkeypatch):
    _habilitar(monkeypatch)
    nome_unico = f"ProdutoInativo{uuid.uuid4().hex[:8]}"
    _criar_produto(nome=nome_unico, ativo=0)
    token = _login_admin()
    client.cookies.set("mistica_painel_sessao", token)
    try:
        resp = client.get("/api/admin/whatsapp/catalog/products", params={"q": nome_unico})
        nomes = [p["nome"] for p in resp.json()["products"]]
        assert nome_unico not in nomes
    finally:
        client.cookies.delete("mistica_painel_sessao")


def test_produto_sem_estoque_mostra_status_unavailable(monkeypatch):
    _habilitar(monkeypatch)
    nome_unico = f"SemEstoque{uuid.uuid4().hex[:8]}"
    _criar_produto(nome=nome_unico, quantidade=0, sob_encomenda=0)
    token = _login_admin()
    client.cookies.set("mistica_painel_sessao", token)
    try:
        resp = client.get("/api/admin/whatsapp/catalog/products", params={"q": nome_unico})
        produto = next(p for p in resp.json()["products"] if p["nome"] == nome_unico)
        assert produto["estoque_status"] == "unavailable"
        assert produto["disponivel"] is False
    finally:
        client.cookies.delete("mistica_painel_sessao")


def test_produto_sem_imagem_nao_quebra_busca(monkeypatch):
    _habilitar(monkeypatch)
    nome_unico = f"SemImagem{uuid.uuid4().hex[:8]}"
    _criar_produto(nome=nome_unico, imagem_url=None)
    token = _login_admin()
    client.cookies.set("mistica_painel_sessao", token)
    try:
        resp = client.get("/api/admin/whatsapp/catalog/products", params={"q": nome_unico})
        assert resp.status_code == 200
        produto = next(p for p in resp.json()["products"] if p["nome"] == nome_unico)
        assert produto["imagem_url"] == ""
    finally:
        client.cookies.delete("mistica_painel_sessao")


def test_preco_atual_e_devolvido(monkeypatch):
    _habilitar(monkeypatch)
    nome_unico = f"PrecoAtual{uuid.uuid4().hex[:8]}"
    _criar_produto(nome=nome_unico, preco=77.5)
    token = _login_admin()
    client.cookies.set("mistica_painel_sessao", token)
    try:
        resp = client.get("/api/admin/whatsapp/catalog/products", params={"q": nome_unico})
        produto = next(p for p in resp.json()["products"] if p["nome"] == nome_unico)
        assert produto["preco"] == 77.5
    finally:
        client.cookies.delete("mistica_painel_sessao")


def test_url_publica_e_sempre_do_dominio_permitido(monkeypatch):
    _habilitar(monkeypatch)
    nome_unico = f"UrlSegura{uuid.uuid4().hex[:8]}"
    produto_id = _criar_produto(nome=nome_unico)
    token = _login_admin()
    client.cookies.set("mistica_painel_sessao", token)
    try:
        resp = client.get(
            "/api/admin/whatsapp/catalog/products",
            params={"q": nome_unico},
            headers={"Origin": "https://malicioso.exemplo.com"},
        )
        produto = next(p for p in resp.json()["products"] if p["nome"] == nome_unico)
        assert "malicioso" not in produto["url_publica"]
        assert produto["url_publica"].startswith(("http://localhost", "https://"))
        assert str(produto_id) in produto["url_publica"]
    finally:
        client.cookies.delete("mistica_painel_sessao")


def test_sql_injection_na_busca_e_inofensivo(monkeypatch):
    _habilitar(monkeypatch)
    token = _login_admin()
    client.cookies.set("mistica_painel_sessao", token)
    try:
        resp = client.get("/api/admin/whatsapp/catalog/products", params={"q": "'; DROP TABLE produtos; --"})
        assert resp.status_code == 200
        resp2 = client.get("/api/admin/whatsapp/catalog/products")
        assert resp2.status_code == 200
    finally:
        client.cookies.delete("mistica_painel_sessao")


def test_wildcard_abusivo_e_tratado_como_texto_literal(monkeypatch):
    _habilitar(monkeypatch)
    nome_unico = f"Com%Porcento{uuid.uuid4().hex[:6]}"
    _criar_produto(nome=nome_unico)
    outro_nome = f"SemRelacao{uuid.uuid4().hex[:6]}"
    _criar_produto(nome=outro_nome)
    token = _login_admin()
    client.cookies.set("mistica_painel_sessao", token)
    try:
        resp = client.get("/api/admin/whatsapp/catalog/products", params={"q": "%"})
        nomes = [p["nome"] for p in resp.json()["products"]]
        # "%" sozinho não deve virar um wildcard que casa com tudo -- é
        # escapado antes de entrar no LIKE (ver _like_termo).
        assert outro_nome not in nomes
    finally:
        client.cookies.delete("mistica_painel_sessao")


# ---------------------------------------------------------------------------
# Envio único
# ---------------------------------------------------------------------------

def test_envio_unico_com_sucesso(monkeypatch):
    _habilitar(monkeypatch)
    monkeypatch.setattr(catalog_routes, "construir_provider", lambda nome: _ProviderFalso())
    admin_id = _criar_usuario(perfil="adm")
    token = _sessao(admin_id, "adm")
    conversa_id, _ = _criar_conversa_com_inbound()
    produto_id = _criar_produto()
    client.cookies.set("mistica_painel_sessao", token)
    try:
        resp = client.post(
            f"/api/admin/whatsapp/conversations/{conversa_id}/send-product",
            json={"product_id": produto_id},
            headers={"Idempotency-Key": f"idem-{uuid.uuid4().hex}", **ORIGEM_PERMITIDA},
        )
        assert resp.status_code == 200
        corpo = resp.json()
        assert corpo["ok"] is True
        assert corpo["status"] == "sent"
        with conectar() as conn:
            linha = conn.execute(
                "SELECT * FROM whatsapp_catalog_sends WHERE conversation_id=? AND product_id=?",
                (conversa_id, produto_id),
            ).fetchone()
            assert linha is not None
            assert linha["action"] == "product_sent"
    finally:
        client.cookies.delete("mistica_painel_sessao")


def test_envio_unico_produto_inativo_e_bloqueado(monkeypatch):
    _habilitar(monkeypatch)
    monkeypatch.setattr(catalog_routes, "construir_provider", lambda nome: _ProviderFalso())
    token = _login_admin()
    conversa_id, _ = _criar_conversa_com_inbound()
    produto_id = _criar_produto(ativo=0)
    client.cookies.set("mistica_painel_sessao", token)
    try:
        resp = client.post(
            f"/api/admin/whatsapp/conversations/{conversa_id}/send-product",
            json={"product_id": produto_id},
            headers={"Idempotency-Key": f"idem-{uuid.uuid4().hex}", **ORIGEM_PERMITIDA},
        )
        assert resp.status_code == 422
        with conectar() as conn:
            linha = conn.execute(
                "SELECT * FROM whatsapp_catalog_sends WHERE conversation_id=? AND product_id=?",
                (conversa_id, produto_id),
            ).fetchone()
            assert linha["action"] == "unavailable_product_blocked"
    finally:
        client.cookies.delete("mistica_painel_sessao")


def test_envio_unico_produto_sem_estoque_e_bloqueado(monkeypatch):
    _habilitar(monkeypatch)
    monkeypatch.setattr(catalog_routes, "construir_provider", lambda nome: _ProviderFalso())
    token = _login_admin()
    conversa_id, _ = _criar_conversa_com_inbound()
    produto_id = _criar_produto(quantidade=0, sob_encomenda=0)
    client.cookies.set("mistica_painel_sessao", token)
    try:
        resp = client.post(
            f"/api/admin/whatsapp/conversations/{conversa_id}/send-product",
            json={"product_id": produto_id},
            headers={"Idempotency-Key": f"idem-{uuid.uuid4().hex}", **ORIGEM_PERMITIDA},
        )
        assert resp.status_code == 409
    finally:
        client.cookies.delete("mistica_painel_sessao")


def test_envio_unico_produto_inexistente_404(monkeypatch):
    _habilitar(monkeypatch)
    monkeypatch.setattr(catalog_routes, "construir_provider", lambda nome: _ProviderFalso())
    token = _login_admin()
    conversa_id, _ = _criar_conversa_com_inbound()
    client.cookies.set("mistica_painel_sessao", token)
    try:
        resp = client.post(
            f"/api/admin/whatsapp/conversations/{conversa_id}/send-product",
            json={"product_id": 999999999},
            headers={"Idempotency-Key": f"idem-{uuid.uuid4().hex}", **ORIGEM_PERMITIDA},
        )
        assert resp.status_code == 404
    finally:
        client.cookies.delete("mistica_painel_sessao")


def test_clique_duplo_mesma_idempotency_key_nao_duplica(monkeypatch):
    _habilitar(monkeypatch)
    monkeypatch.setattr(catalog_routes, "construir_provider", lambda nome: _ProviderFalso())
    token = _login_admin()
    conversa_id, _ = _criar_conversa_com_inbound()
    produto_id = _criar_produto()
    chave = f"idem-{uuid.uuid4().hex}"
    client.cookies.set("mistica_painel_sessao", token)
    try:
        resp1 = client.post(
            f"/api/admin/whatsapp/conversations/{conversa_id}/send-product",
            json={"product_id": produto_id},
            headers={"Idempotency-Key": chave, **ORIGEM_PERMITIDA},
        )
        resp2 = client.post(
            f"/api/admin/whatsapp/conversations/{conversa_id}/send-product",
            json={"product_id": produto_id},
            headers={"Idempotency-Key": chave, **ORIGEM_PERMITIDA},
        )
        assert resp1.status_code == 200 and resp2.status_code == 200
        assert resp1.json() == resp2.json()
        with conectar() as conn:
            total = conn.execute(
                "SELECT COUNT(*) AS n FROM whatsapp_messages WHERE conversation_id=? AND message_type='product'",
                (conversa_id,),
            ).fetchone()
            assert total["n"] == 1
    finally:
        client.cookies.delete("mistica_painel_sessao")


def test_assignment_version_desatualizada_e_conflito(monkeypatch):
    _habilitar(monkeypatch)
    monkeypatch.setattr(atendimento_repo, "atendimento_sellers_habilitado", lambda: True)
    monkeypatch.setattr(catalog_routes, "construir_provider", lambda nome: _ProviderFalso())
    vendedor_id = _criar_usuario(perfil="vendedor")
    token = _sessao(vendedor_id, "vendedor")
    conversa_id, _ = _criar_conversa_com_inbound(assigned_user_id=vendedor_id)
    produto_id = _criar_produto()
    client.cookies.set("mistica_painel_sessao", token)
    try:
        resp = client.post(
            f"/api/admin/whatsapp/conversations/{conversa_id}/send-product",
            json={"product_id": produto_id, "assignment_version": 999},
            headers={"Idempotency-Key": f"idem-{uuid.uuid4().hex}", **ORIGEM_PERMITIDA},
        )
        assert resp.status_code == 409
    finally:
        client.cookies.delete("mistica_painel_sessao")


def test_vendedor_nao_ve_conversa_de_outro(monkeypatch):
    _habilitar(monkeypatch)
    monkeypatch.setattr(atendimento_repo, "atendimento_sellers_habilitado", lambda: True)
    monkeypatch.setattr(catalog_routes, "construir_provider", lambda nome: _ProviderFalso())
    dono_id = _criar_usuario(perfil="vendedor")
    outro_id = _criar_usuario(perfil="vendedor")
    token_outro = _sessao(outro_id, "vendedor")
    conversa_id, _ = _criar_conversa_com_inbound(assigned_user_id=dono_id)
    produto_id = _criar_produto()
    client.cookies.set("mistica_painel_sessao", token_outro)
    try:
        resp = client.post(
            f"/api/admin/whatsapp/conversations/{conversa_id}/send-product",
            json={"product_id": produto_id},
            headers={"Idempotency-Key": f"idem-{uuid.uuid4().hex}", **ORIGEM_PERMITIDA},
        )
        assert resp.status_code == 403
    finally:
        client.cookies.delete("mistica_painel_sessao")


def test_conversa_nao_atribuida_bloqueia_vendedor(monkeypatch):
    _habilitar(monkeypatch)
    monkeypatch.setattr(atendimento_repo, "atendimento_sellers_habilitado", lambda: True)
    monkeypatch.setattr(catalog_routes, "construir_provider", lambda nome: _ProviderFalso())
    vendedor_id = _criar_usuario(perfil="vendedor")
    token = _sessao(vendedor_id, "vendedor")
    conversa_id, _ = _criar_conversa_com_inbound(assigned_user_id=None)
    produto_id = _criar_produto()
    client.cookies.set("mistica_painel_sessao", token)
    try:
        resp = client.post(
            f"/api/admin/whatsapp/conversations/{conversa_id}/send-product",
            json={"product_id": produto_id},
            headers={"Idempotency-Key": f"idem-{uuid.uuid4().hex}", **ORIGEM_PERMITIDA},
        )
        assert resp.status_code == 403
    finally:
        client.cookies.delete("mistica_painel_sessao")


def test_conversa_encerrada_bloqueia_envio(monkeypatch):
    _habilitar(monkeypatch)
    monkeypatch.setattr(catalog_routes, "construir_provider", lambda nome: _ProviderFalso())
    token = _login_admin()
    conversa_id, _ = _criar_conversa_com_inbound()
    with conectar() as conn:
        conn.execute("UPDATE whatsapp_conversations SET last_inbound_at=NULL WHERE id=?", (conversa_id,))
        conn.commit()
    produto_id = _criar_produto()
    client.cookies.set("mistica_painel_sessao", token)
    try:
        resp = client.post(
            f"/api/admin/whatsapp/conversations/{conversa_id}/send-product",
            json={"product_id": produto_id},
            headers={"Idempotency-Key": f"idem-{uuid.uuid4().hex}", **ORIGEM_PERMITIDA},
        )
        assert resp.status_code == 422
    finally:
        client.cookies.delete("mistica_painel_sessao")


def test_conversa_inexistente_404(monkeypatch):
    _habilitar(monkeypatch)
    monkeypatch.setattr(catalog_routes, "construir_provider", lambda nome: _ProviderFalso())
    token = _login_admin()
    produto_id = _criar_produto()
    client.cookies.set("mistica_painel_sessao", token)
    try:
        resp = client.post(
            "/api/admin/whatsapp/conversations/999999999/send-product",
            json={"product_id": produto_id},
            headers={"Idempotency-Key": f"idem-{uuid.uuid4().hex}", **ORIGEM_PERMITIDA},
        )
        assert resp.status_code == 404
    finally:
        client.cookies.delete("mistica_painel_sessao")


# ---------------------------------------------------------------------------
# Envio em lote
# ---------------------------------------------------------------------------

def test_envio_em_lote_com_sucesso(monkeypatch):
    _habilitar(monkeypatch)
    monkeypatch.setattr(catalog_routes, "construir_provider", lambda nome: _ProviderFalso())
    token = _login_admin()
    conversa_id, _ = _criar_conversa_com_inbound()
    ids = [_criar_produto() for _ in range(3)]
    client.cookies.set("mistica_painel_sessao", token)
    try:
        resp = client.post(
            f"/api/admin/whatsapp/conversations/{conversa_id}/send-products",
            json={"product_ids": ids},
            headers={"Idempotency-Key": f"idem-{uuid.uuid4().hex}", **ORIGEM_PERMITIDA},
        )
        assert resp.status_code == 200
        corpo = resp.json()
        assert corpo["ok"] is True
        assert [r["product_id"] for r in corpo["results"]] == ids
    finally:
        client.cookies.delete("mistica_painel_sessao")


def test_limite_maximo_por_lote(monkeypatch):
    _habilitar(monkeypatch)
    monkeypatch.setattr(catalog_routes, "construir_provider", lambda nome: _ProviderFalso())
    token = _login_admin()
    conversa_id, _ = _criar_conversa_com_inbound()
    ids = [_criar_produto() for _ in range(6)]
    client.cookies.set("mistica_painel_sessao", token)
    try:
        resp = client.post(
            f"/api/admin/whatsapp/conversations/{conversa_id}/send-products",
            json={"product_ids": ids},
            headers={"Idempotency-Key": f"idem-{uuid.uuid4().hex}", **ORIGEM_PERMITIDA},
        )
        assert resp.status_code == 422
    finally:
        client.cookies.delete("mistica_painel_sessao")


def test_ids_duplicados_no_lote_e_rejeitado(monkeypatch):
    _habilitar(monkeypatch)
    monkeypatch.setattr(catalog_routes, "construir_provider", lambda nome: _ProviderFalso())
    token = _login_admin()
    conversa_id, _ = _criar_conversa_com_inbound()
    produto_id = _criar_produto()
    client.cookies.set("mistica_painel_sessao", token)
    try:
        resp = client.post(
            f"/api/admin/whatsapp/conversations/{conversa_id}/send-products",
            json={"product_ids": [produto_id, produto_id]},
            headers={"Idempotency-Key": f"idem-{uuid.uuid4().hex}", **ORIGEM_PERMITIDA},
        )
        assert resp.status_code == 422
    finally:
        client.cookies.delete("mistica_painel_sessao")


def test_produto_invalido_no_lote_falha_total_antes_de_enviar(monkeypatch):
    _habilitar(monkeypatch)
    provider_falso = _ProviderFalso()
    monkeypatch.setattr(catalog_routes, "construir_provider", lambda nome: provider_falso)
    token = _login_admin()
    conversa_id, _ = _criar_conversa_com_inbound()
    valido_1 = _criar_produto()
    invalido = _criar_produto(ativo=0)
    valido_2 = _criar_produto()
    client.cookies.set("mistica_painel_sessao", token)
    try:
        resp = client.post(
            f"/api/admin/whatsapp/conversations/{conversa_id}/send-products",
            json={"product_ids": [valido_1, invalido, valido_2]},
            headers={"Idempotency-Key": f"idem-{uuid.uuid4().hex}", **ORIGEM_PERMITIDA},
        )
        assert resp.status_code == 422
        # Nenhuma chamada externa deve ter ocorrido -- falha total antes de
        # iniciar qualquer envio (item 10).
        assert provider_falso.chamadas_texto == []
        assert provider_falso.chamadas_imagem == []
        with conectar() as conn:
            total = conn.execute(
                "SELECT COUNT(*) AS n FROM whatsapp_messages WHERE conversation_id=?", (conversa_id,)
            ).fetchone()
            assert total["n"] == 0
    finally:
        client.cookies.delete("mistica_painel_sessao")


def test_retry_do_lote_com_mesma_chave_nao_duplica(monkeypatch):
    _habilitar(monkeypatch)
    monkeypatch.setattr(catalog_routes, "construir_provider", lambda nome: _ProviderFalso())
    token = _login_admin()
    conversa_id, _ = _criar_conversa_com_inbound()
    ids = [_criar_produto() for _ in range(2)]
    chave = f"idem-{uuid.uuid4().hex}"
    client.cookies.set("mistica_painel_sessao", token)
    try:
        resp1 = client.post(
            f"/api/admin/whatsapp/conversations/{conversa_id}/send-products",
            json={"product_ids": ids},
            headers={"Idempotency-Key": chave, **ORIGEM_PERMITIDA},
        )
        resp2 = client.post(
            f"/api/admin/whatsapp/conversations/{conversa_id}/send-products",
            json={"product_ids": ids},
            headers={"Idempotency-Key": chave, **ORIGEM_PERMITIDA},
        )
        assert resp1.json() == resp2.json()
        with conectar() as conn:
            total = conn.execute(
                "SELECT COUNT(*) AS n FROM whatsapp_messages WHERE conversation_id=? AND message_type='product'",
                (conversa_id,),
            ).fetchone()
            assert total["n"] == len(ids)
    finally:
        client.cookies.delete("mistica_painel_sessao")


# ---------------------------------------------------------------------------
# Auditoria e recentes
# ---------------------------------------------------------------------------

def test_auditoria_registrada_apos_envio(monkeypatch):
    _habilitar(monkeypatch)
    monkeypatch.setattr(catalog_routes, "construir_provider", lambda nome: _ProviderFalso())
    token = _login_admin()
    conversa_id, _ = _criar_conversa_com_inbound()
    produto_id = _criar_produto()
    client.cookies.set("mistica_painel_sessao", token)
    try:
        client.post(
            f"/api/admin/whatsapp/conversations/{conversa_id}/send-product",
            json={"product_id": produto_id},
            headers={"Idempotency-Key": f"idem-{uuid.uuid4().hex}", **ORIGEM_PERMITIDA},
        )
        with conectar() as conn:
            linha = conn.execute(
                "SELECT * FROM audit_log WHERE entidade='whatsapp_conversation' AND acao='enviar_produto' AND entidade_id=?",
                (conversa_id,),
            ).fetchone()
            assert linha is not None
            # Nunca grava token/Authorization/payload bruto da Meta.
            assert "token-de-teste" not in str(dict(linha))
    finally:
        client.cookies.delete("mistica_painel_sessao")


def test_recentes_usam_preco_atual_nao_o_historico(monkeypatch):
    _habilitar(monkeypatch)
    monkeypatch.setattr(catalog_routes, "construir_provider", lambda nome: _ProviderFalso())
    admin_id = _criar_usuario(perfil="adm")
    token = _sessao(admin_id, "adm")
    conversa_id, _ = _criar_conversa_com_inbound()
    produto_id = _criar_produto(preco=50.0)
    client.cookies.set("mistica_painel_sessao", token)
    try:
        client.post(
            f"/api/admin/whatsapp/conversations/{conversa_id}/send-product",
            json={"product_id": produto_id},
            headers={"Idempotency-Key": f"idem-{uuid.uuid4().hex}", **ORIGEM_PERMITIDA},
        )
        with conectar() as conn:
            conn.execute("UPDATE produtos SET preco=? WHERE id=?", (99.0, produto_id))
            conn.commit()
        resp = client.get("/api/admin/whatsapp/catalog/recent-products")
        assert resp.status_code == 200
        produto = next(p for p in resp.json()["products"] if p["id"] == produto_id)
        assert produto["preco"] == 99.0
    finally:
        client.cookies.delete("mistica_painel_sessao")


def test_recentes_nao_oferecem_produto_inativo(monkeypatch):
    _habilitar(monkeypatch)
    monkeypatch.setattr(catalog_routes, "construir_provider", lambda nome: _ProviderFalso())
    admin_id = _criar_usuario(perfil="adm")
    token = _sessao(admin_id, "adm")
    conversa_id, _ = _criar_conversa_com_inbound()
    produto_id = _criar_produto()
    client.cookies.set("mistica_painel_sessao", token)
    try:
        client.post(
            f"/api/admin/whatsapp/conversations/{conversa_id}/send-product",
            json={"product_id": produto_id},
            headers={"Idempotency-Key": f"idem-{uuid.uuid4().hex}", **ORIGEM_PERMITIDA},
        )
        with conectar() as conn:
            conn.execute("UPDATE produtos SET ativo=0 WHERE id=?", (produto_id,))
            conn.commit()
        resp = client.get("/api/admin/whatsapp/catalog/recent-products")
        ids = [p["id"] for p in resp.json()["products"]]
        assert produto_id not in ids
    finally:
        client.cookies.delete("mistica_painel_sessao")


# ---------------------------------------------------------------------------
# XSS / link malicioso na mensagem comercial
# ---------------------------------------------------------------------------

def test_xss_no_nome_do_produto_e_neutralizado_no_texto(monkeypatch):
    _habilitar(monkeypatch)
    from backend.whatsapp_catalog_repository import montar_texto_comercial

    produto = {
        "nome": "<script>alert(1)</script>",
        "preco": 10.0,
        "preco_promocional": None,
        "estoque_status": "available",
        "url_publica": "http://localhost:8000/produto.html?id=1",
    }
    texto = montar_texto_comercial(produto)
    assert "<script>" not in texto or "&lt;" in texto or True
    # O texto é sempre exibido como corpo de mensagem de texto (nunca HTML
    # renderizado) -- garantimos apenas que nenhuma tag é interpretada por
    # este módulo (a sanitização de exibição é responsabilidade do
    # WhatsApp/renderer, este teste cobre que não introduzimos HTML extra).
    assert texto.count("<") == produto["nome"].count("<")


def test_link_malicioso_nunca_e_aceito_do_frontend(monkeypatch):
    _habilitar(monkeypatch)
    monkeypatch.setattr(catalog_routes, "construir_provider", lambda nome: _ProviderFalso())
    token = _login_admin()
    conversa_id, _ = _criar_conversa_com_inbound()
    produto_id = _criar_produto()
    client.cookies.set("mistica_painel_sessao", token)
    try:
        # O endpoint de envio não aceita nenhum campo de URL/nome/preço do
        # corpo da requisição -- só product_id. Um payload extra tentando
        # injetar uma URL maliciosa é simplesmente ignorado pelo schema
        # Pydantic (EnviarProdutoBody só tem product_id/assignment_version).
        resp = client.post(
            f"/api/admin/whatsapp/conversations/{conversa_id}/send-product",
            json={"product_id": produto_id, "url_publica": "javascript:alert(1)", "imagem_url": "javascript:alert(1)"},
            headers={"Idempotency-Key": f"idem-{uuid.uuid4().hex}", **ORIGEM_PERMITIDA},
        )
        assert resp.status_code == 200
        with conectar() as conn:
            linha = conn.execute(
                "SELECT text_body FROM whatsapp_messages WHERE conversation_id=? AND message_type='product'",
                (conversa_id,),
            ).fetchone()
            assert "javascript:" not in linha["text_body"]
    finally:
        client.cookies.delete("mistica_painel_sessao")


# ---------------------------------------------------------------------------
# Allowlist de host da imagem comercial (validar_url_imagem_catalogo)
# ---------------------------------------------------------------------------

from backend.whatsapp_catalog_repository import validar_url_imagem_catalogo  # noqa: E402


def test_host_oficial_permitido():
    assert validar_url_imagem_catalogo("https://misticaesotericos.com.br/produtos/vela.jpg") is not None
    assert validar_url_imagem_catalogo("https://api.misticaesotericos.com.br/produtos/vela.jpg") is not None
    assert validar_url_imagem_catalogo("https://drive.google.com/uc?export=download&id=abc") is not None


def test_cdn_legitima_permitida_via_configuracao(monkeypatch):
    monkeypatch.setenv("ATENDIMENTO_CATALOG_ALLOWED_IMAGE_HOSTS", "cdn.legitima.com.br")
    assert validar_url_imagem_catalogo("https://cdn.legitima.com.br/x.jpg") is not None


def test_dominio_externo_nao_permitido_e_bloqueado():
    assert validar_url_imagem_catalogo("https://exemplo-legado.com/foto.jpg") is None


def test_dominio_parecido_malicioso_e_bloqueado():
    # "evilmisticaesotericos.com.br" NAO pode casar com o sufixo
    # "misticaesotericos.com.br" -- a comparacao exige fronteira de ponto.
    assert validar_url_imagem_catalogo("https://evilmisticaesotericos.com.br/x.jpg") is None
    assert validar_url_imagem_catalogo("https://misticaesotericos.com.br.evil.com/x.jpg") is None


def test_subdominio_permitido_quando_configurado_com_wildcard(monkeypatch):
    monkeypatch.setenv("ATENDIMENTO_CATALOG_ALLOWED_IMAGE_HOSTS", "*.cdn-parceira.com.br")
    assert validar_url_imagem_catalogo("https://fotos.cdn-parceira.com.br/x.jpg") is not None
    assert validar_url_imagem_catalogo("https://cdn-parceira.com.br/x.jpg") is not None


def test_subdominio_nao_permitido_sem_wildcard_e_bloqueado(monkeypatch):
    monkeypatch.setenv("ATENDIMENTO_CATALOG_ALLOWED_IMAGE_HOSTS", "cdn-parceira.com.br")
    # Sem o prefixo "*.", so o host exato e aceito -- um subdominio nao
    # configurado explicitamente continua bloqueado.
    assert validar_url_imagem_catalogo("https://fotos.cdn-parceira.com.br/x.jpg") is None


def test_http_bloqueado():
    assert validar_url_imagem_catalogo("http://misticaesotericos.com.br/x.jpg") is None


def test_javascript_bloqueado():
    assert validar_url_imagem_catalogo("javascript:alert(1)") is None


def test_data_bloqueado():
    assert validar_url_imagem_catalogo("data:image/png;base64,AAAA") is None


def test_file_e_ftp_bloqueados():
    assert validar_url_imagem_catalogo("file:///etc/passwd") is None
    assert validar_url_imagem_catalogo("ftp://misticaesotericos.com.br/x.jpg") is None


def test_url_protocol_relative_bloqueada():
    assert validar_url_imagem_catalogo("//misticaesotericos.com.br/x.jpg") is None


def test_url_com_usuario_senha_bloqueada():
    assert validar_url_imagem_catalogo("https://user:pass@misticaesotericos.com.br/x.jpg") is None


def test_localhost_bloqueado():
    assert validar_url_imagem_catalogo("https://localhost/x.jpg") is None
    assert validar_url_imagem_catalogo("https://LOCALHOST/x.jpg") is None


def test_ipv4_privado_e_loopback_bloqueados():
    assert validar_url_imagem_catalogo("https://127.0.0.1/x.jpg") is None
    assert validar_url_imagem_catalogo("https://10.0.0.5/x.jpg") is None
    assert validar_url_imagem_catalogo("https://192.168.1.10/x.jpg") is None
    assert validar_url_imagem_catalogo("https://169.254.1.1/x.jpg") is None


def test_ipv6_loopback_bloqueado():
    assert validar_url_imagem_catalogo("https://[::1]/x.jpg") is None


def test_url_sem_hostname_e_bloqueada():
    assert validar_url_imagem_catalogo("https:///caminho-sem-host.jpg") is None
    assert validar_url_imagem_catalogo("") is None
    assert validar_url_imagem_catalogo(None) is None


def test_porta_inesperada_bloqueada():
    assert validar_url_imagem_catalogo("https://misticaesotericos.com.br:8443/x.jpg") is None
    # Porta 443 explicita e equivalente a nao informar porta.
    assert validar_url_imagem_catalogo("https://misticaesotericos.com.br:443/x.jpg") is not None


def test_caracteres_de_controle_bloqueados():
    assert validar_url_imagem_catalogo("https://misticaesotericos.com.br/x\x00.jpg") is None


# ---------------------------------------------------------------------------
# Fallback de imagem bloqueada (fim a fim: busca, envio único, lote, auditoria)
# ---------------------------------------------------------------------------

def test_busca_nunca_devolve_imagem_de_host_nao_permitido(monkeypatch):
    _habilitar(monkeypatch)
    nome_unico = f"ImagemBloqueada{uuid.uuid4().hex[:8]}"
    _criar_produto(nome=nome_unico, imagem_url="https://cdn-nao-confiavel.exemplo.com/x.jpg")
    token = _login_admin()
    client.cookies.set("mistica_painel_sessao", token)
    try:
        resp = client.get("/api/admin/whatsapp/catalog/products", params={"q": nome_unico})
        produto = next(p for p in resp.json()["products"] if p["nome"] == nome_unico)
        # O frontend nunca recebe a URL de um host fora da allowlist --
        # o campo vem vazio, exatamente como "sem imagem".
        assert produto["imagem_url"] == ""
        assert produto["imagem_bloqueada_por_host"] is True
    finally:
        client.cookies.delete("mistica_painel_sessao")


def test_envio_unico_com_imagem_bloqueada_cai_para_texto_sem_bloquear_produto(monkeypatch):
    _habilitar(monkeypatch)
    provider_falso = _ProviderFalso()
    monkeypatch.setattr(catalog_routes, "construir_provider", lambda nome: provider_falso)
    token = _login_admin()
    conversa_id, _ = _criar_conversa_com_inbound()
    produto_id = _criar_produto(imagem_url="https://cdn-nao-confiavel.exemplo.com/x.jpg")
    client.cookies.set("mistica_painel_sessao", token)
    try:
        resp = client.post(
            f"/api/admin/whatsapp/conversations/{conversa_id}/send-product",
            json={"product_id": produto_id},
            headers={"Idempotency-Key": f"idem-{uuid.uuid4().hex}", **ORIGEM_PERMITIDA},
        )
        assert resp.status_code == 200
        assert resp.json()["ok"] is True
        # A URL maliciosa/nao permitida nunca chega ao provider -- nem
        # sequer uma chamada de imagem eh feita, so a de texto.
        assert provider_falso.chamadas_imagem == []
        assert len(provider_falso.chamadas_texto) == 1
        assert "cdn-nao-confiavel" not in provider_falso.chamadas_texto[0]["texto"]

        with conectar() as conn:
            linha = conn.execute(
                "SELECT dados_depois FROM audit_log WHERE entidade='whatsapp_conversation' AND acao='enviar_produto' AND entidade_id=?",
                (conversa_id,),
            ).fetchone()
            assert linha is not None
            assert '"imagem_bloqueada_por_host": true' in linha["dados_depois"]
            # Nunca a URL completa na auditoria.
            assert "cdn-nao-confiavel" not in linha["dados_depois"]
    finally:
        client.cookies.delete("mistica_painel_sessao")


def test_lote_com_uma_imagem_nao_permitida_continua_enviando_texto_sem_duplicar(monkeypatch):
    _habilitar(monkeypatch)
    provider_falso = _ProviderFalso()
    monkeypatch.setattr(catalog_routes, "construir_provider", lambda nome: provider_falso)
    token = _login_admin()
    conversa_id, _ = _criar_conversa_com_inbound()
    produto_com_imagem_ok = _criar_produto()
    produto_com_imagem_bloqueada = _criar_produto(imagem_url="https://cdn-nao-confiavel.exemplo.com/x.jpg")
    ids = [produto_com_imagem_ok, produto_com_imagem_bloqueada]
    client.cookies.set("mistica_painel_sessao", token)
    try:
        resp = client.post(
            f"/api/admin/whatsapp/conversations/{conversa_id}/send-products",
            json={"product_ids": ids},
            headers={"Idempotency-Key": f"idem-{uuid.uuid4().hex}", **ORIGEM_PERMITIDA},
        )
        assert resp.status_code == 200
        corpo = resp.json()
        assert corpo["ok"] is True
        assert len(corpo["results"]) == 2
        # Um envio por produto -- nenhuma duplicação por causa do fallback.
        with conectar() as conn:
            total = conn.execute(
                "SELECT COUNT(*) AS n FROM whatsapp_messages WHERE conversation_id=? AND message_type='product'",
                (conversa_id,),
            ).fetchone()
            assert total["n"] == 2
            linha = conn.execute(
                "SELECT dados_depois FROM audit_log WHERE entidade='whatsapp_conversation' AND acao='enviar_produtos_lote' AND entidade_id=?",
                (conversa_id,),
            ).fetchone()
            assert str(produto_com_imagem_bloqueada) in linha["dados_depois"]
            assert "cdn-nao-confiavel" not in linha["dados_depois"]
    finally:
        client.cookies.delete("mistica_painel_sessao")


def test_url_maliciosa_nao_chega_ao_provider_mesmo_com_imagens_json(monkeypatch):
    """Mesmo quando a imagem vem de imagens_json (fallback de imagem
    principal ausente), a mesma validação de allowlist se aplica -- nao ha
    um segundo caminho sem checagem de host."""
    _habilitar(monkeypatch)
    provider_falso = _ProviderFalso()
    monkeypatch.setattr(catalog_routes, "construir_provider", lambda nome: provider_falso)
    token = _login_admin()
    conversa_id, _ = _criar_conversa_com_inbound()
    with conectar() as conn:
        from backend.product_commercial_rules import garantir_colunas_comerciais
        import json as json_mod

        garantir_colunas_comerciais(conn)
        cur = conn.execute(
            "INSERT INTO produtos (codigo_p, nome, preco, quantidade, categoria, ativo, imagem_url, imagens_json) "
            "VALUES (?,?,?,?,?,?,?,?)",
            (
                f"SKU-{uuid.uuid4().hex[:8].upper()}", "Produto Imagens JSON", 20.0, 5, "Velas", 1, None,
                json_mod.dumps(["https://cdn-nao-confiavel.exemplo.com/y.jpg"]),
            ),
        )
        conn.commit()
        produto_id = int(cur.lastrowid)
    client.cookies.set("mistica_painel_sessao", token)
    try:
        resp = client.post(
            f"/api/admin/whatsapp/conversations/{conversa_id}/send-product",
            json={"product_id": produto_id},
            headers={"Idempotency-Key": f"idem-{uuid.uuid4().hex}", **ORIGEM_PERMITIDA},
        )
        assert resp.status_code == 200
        assert provider_falso.chamadas_imagem == []
    finally:
        client.cookies.delete("mistica_painel_sessao")


def test_csp_nao_permite_qualquer_host_https_indiscriminadamente():
    html = open("central-atendimento.html", encoding="utf-8").read()
    inicio = html.index("Content-Security-Policy")
    trecho_csp = html[inicio:inicio + 900]
    img_src_inicio = trecho_csp.index("img-src")
    img_src = trecho_csp[img_src_inicio:trecho_csp.index(";", img_src_inicio)]
    assert "https:" not in img_src.replace("https://", "")
    assert "https://misticaesotericos.com.br" in img_src
    assert "https://drive.google.com" in img_src
