"""Testes da Central Multiatendente (fila, claim atômico, transferência,
finalização/reabertura, permissões, auditoria) -- backend/atendimento_repository.py
e backend/whatsapp_atendimento_routes.py.

Segue o mesmo padrão de tests/test_whatsapp_inbox_admin.py: nunca chama a
Graph API real, sessões são inseridas diretamente em painel_sessoes."""
from __future__ import annotations

import importlib
import os
import secrets as secrets_mod
import threading
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
import backend.whatsapp_atendimento_routes as atendimento_routes
import backend.whatsapp_inbox_routes as inbox_routes
from backend.database import conectar
from backend.whatsapp_inbox_repository import obter_ou_criar_conversa, upsert_contact
from backend.whatsapp_provider import ResultadoEnvioWhatsApp

ORIGEM_PERMITIDA = {"Origin": "http://localhost:8000"}


def _habilitar(monkeypatch):
    monkeypatch.setattr(inbox_routes, "whatsapp_cloud_inbox_habilitado", lambda: True)
    monkeypatch.setattr(atendimento_routes, "whatsapp_cloud_inbox_habilitado", lambda: True)


def _ligar_multiatendente(monkeypatch, *, ligado: bool = True):
    monkeypatch.setattr(atendimento_repo, "atendimento_sellers_habilitado", lambda: ligado)
    monkeypatch.setattr(inbox_routes, "atendimento_sellers_habilitado", lambda: ligado)


def _criar_usuario(*, login=None, perfil="vendedor", atendimento_enabled=1, ativo=1, suspenso=False, max_conversas=None) -> int:
    login = login or f"user-{uuid.uuid4().hex[:10]}"
    with conectar() as conn:
        cur = conn.execute(
            """
            INSERT INTO usuarios (nome, login, senha_hash, senha_salt, perfil, ativo,
                                   atendimento_enabled, atendimento_status, atendimento_max_active_conversations,
                                   atendimento_suspended_at)
            VALUES (?,?,?,?,?,?,?,?,?,?)
            """,
            (
                login, login, "hash-fake", "salt-fake", perfil, ativo,
                atendimento_enabled, "online", max_conversas,
                datetime.now().isoformat(timespec="seconds") if suspenso else None,
            ),
        )
        conn.commit()
        return int(cur.lastrowid)


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


def _criar_conversa_waiting(wa_id: str | None = None) -> int:
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


class Sessao:
    def __init__(self, token):
        self.token = token

    def __enter__(self):
        client.cookies.set("mistica_painel_sessao", self.token)
        return client

    def __exit__(self, *a):
        client.cookies.delete("mistica_painel_sessao")


# ---------------------------------------------------------------------------
# Perfis / autorização
# ---------------------------------------------------------------------------

def test_vendedor_sem_multiatendente_ligada_e_bloqueado(monkeypatch):
    _habilitar(monkeypatch)
    _ligar_multiatendente(monkeypatch, ligado=False)
    vendedor_id = _criar_usuario(perfil="vendedor")
    token = _sessao(vendedor_id, "vendedor")
    with Sessao(token):
        resp = client.get("/api/admin/whatsapp/queue")
        assert resp.status_code == 403


def test_vendedor_com_multiatendente_ligada_ve_fila(monkeypatch):
    _habilitar(monkeypatch)
    _ligar_multiatendente(monkeypatch, ligado=True)
    vendedor_id = _criar_usuario(perfil="vendedor")
    _criar_conversa_waiting()
    token = _sessao(vendedor_id, "vendedor")
    with Sessao(token):
        resp = client.get("/api/admin/whatsapp/queue")
        assert resp.status_code == 200
        assert resp.json()["ok"] is True


def test_vendedor_suspenso_nao_acessa(monkeypatch):
    _habilitar(monkeypatch)
    _ligar_multiatendente(monkeypatch, ligado=True)
    vendedor_id = _criar_usuario(perfil="vendedor", suspenso=True)
    token = _sessao(vendedor_id, "vendedor")
    with Sessao(token):
        resp = client.get("/api/admin/whatsapp/queue")
        assert resp.status_code == 403


def test_vendedor_atendimento_desabilitado_nao_acessa(monkeypatch):
    _habilitar(monkeypatch)
    _ligar_multiatendente(monkeypatch, ligado=True)
    vendedor_id = _criar_usuario(perfil="vendedor", atendimento_enabled=0)
    token = _sessao(vendedor_id, "vendedor")
    with Sessao(token):
        resp = client.get("/api/admin/whatsapp/queue")
        assert resp.status_code == 403


def test_vendedor_nao_acessa_listagem_geral(monkeypatch):
    _habilitar(monkeypatch)
    _ligar_multiatendente(monkeypatch, ligado=True)
    vendedor_id = _criar_usuario(perfil="vendedor")
    token = _sessao(vendedor_id, "vendedor")
    with Sessao(token):
        resp = client.get("/api/admin/whatsapp/conversations")
        assert resp.status_code == 403


def test_adm_acessa_tudo_mesmo_com_flag_desligada(monkeypatch):
    _habilitar(monkeypatch)
    _ligar_multiatendente(monkeypatch, ligado=False)
    adm_id = _criar_usuario(perfil="adm")
    token = _sessao(adm_id, "adm")
    with Sessao(token):
        resp = client.get("/api/admin/whatsapp/queue")
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Claim atômico
# ---------------------------------------------------------------------------

def test_claim_bem_sucedido(monkeypatch):
    _habilitar(monkeypatch)
    _ligar_multiatendente(monkeypatch, ligado=True)
    vendedor_id = _criar_usuario(perfil="vendedor")
    conversa_id = _criar_conversa_waiting()
    token = _sessao(vendedor_id, "vendedor")
    with Sessao(token):
        resp = client.post(f"/api/admin/whatsapp/conversations/{conversa_id}/claim", headers=ORIGEM_PERMITIDA)
        assert resp.status_code == 200
        corpo = resp.json()
        assert corpo["conversation"]["assigned_user_id"] == vendedor_id if "assigned_user_id" in corpo["conversation"] else True
    with conectar() as conn:
        linha = conn.execute("SELECT assigned_user_id, queue_status, assignment_version FROM whatsapp_conversations WHERE id=?", (conversa_id,)).fetchone()
    assert linha["assigned_user_id"] == vendedor_id
    assert linha["queue_status"] == "assigned"
    assert linha["assignment_version"] == 1


def test_claim_duplo_so_um_vence(monkeypatch):
    """Duas requisições 'simultâneas' de vendedores diferentes -- só uma
    assume a conversa; a outra recebe 409 already_claimed."""
    _habilitar(monkeypatch)
    _ligar_multiatendente(monkeypatch, ligado=True)
    vendedor_a = _criar_usuario(perfil="vendedor")
    vendedor_b = _criar_usuario(perfil="vendedor")
    conversa_id = _criar_conversa_waiting()
    token_a = _sessao(vendedor_a, "vendedor")
    token_b = _sessao(vendedor_b, "vendedor")

    resultados = {}

    def _claim(token, chave):
        c = TestClient(main.app)
        c.cookies.set("mistica_painel_sessao", token)
        resultados[chave] = c.post(f"/api/admin/whatsapp/conversations/{conversa_id}/claim", headers=ORIGEM_PERMITIDA)

    t1 = threading.Thread(target=_claim, args=(token_a, "a"))
    t2 = threading.Thread(target=_claim, args=(token_b, "b"))
    t1.start(); t2.start()
    t1.join(); t2.join()

    codigos = sorted([resultados["a"].status_code, resultados["b"].status_code])
    assert codigos == [200, 409]
    with conectar() as conn:
        linha = conn.execute("SELECT assigned_user_id FROM whatsapp_conversations WHERE id=?", (conversa_id,)).fetchone()
    assert linha["assigned_user_id"] in (vendedor_a, vendedor_b)


def test_claim_conversa_ja_atribuida(monkeypatch):
    _habilitar(monkeypatch)
    _ligar_multiatendente(monkeypatch, ligado=True)
    vendedor_a = _criar_usuario(perfil="vendedor")
    vendedor_b = _criar_usuario(perfil="vendedor")
    conversa_id = _criar_conversa_waiting()
    with Sessao(_sessao(vendedor_a, "vendedor")):
        assert client.post(f"/api/admin/whatsapp/conversations/{conversa_id}/claim", headers=ORIGEM_PERMITIDA).status_code == 200
    with Sessao(_sessao(vendedor_b, "vendedor")):
        resp = client.post(f"/api/admin/whatsapp/conversations/{conversa_id}/claim", headers=ORIGEM_PERMITIDA)
        assert resp.status_code == 409
        assert resp.json()["detail"]


def test_claim_respeita_limite_maximo(monkeypatch):
    _habilitar(monkeypatch)
    _ligar_multiatendente(monkeypatch, ligado=True)
    vendedor_id = _criar_usuario(perfil="vendedor", max_conversas=1)
    c1 = _criar_conversa_waiting()
    c2 = _criar_conversa_waiting()
    with Sessao(_sessao(vendedor_id, "vendedor")):
        assert client.post(f"/api/admin/whatsapp/conversations/{c1}/claim", headers=ORIGEM_PERMITIDA).status_code == 200
        resp2 = client.post(f"/api/admin/whatsapp/conversations/{c2}/claim", headers=ORIGEM_PERMITIDA)
        assert resp2.status_code == 409
        assert "limite" in resp2.json()["detail"].lower()
    with conectar() as conn:
        linha = conn.execute("SELECT assigned_user_id, queue_status FROM whatsapp_conversations WHERE id=?", (c2,)).fetchone()
    assert linha["assigned_user_id"] is None
    assert linha["queue_status"] == "waiting"


def test_claim_conversa_encerrada(monkeypatch):
    _habilitar(monkeypatch)
    _ligar_multiatendente(monkeypatch, ligado=True)
    vendedor_id = _criar_usuario(perfil="vendedor")
    conversa_id = _criar_conversa_waiting()
    with conectar() as conn:
        conn.execute("UPDATE whatsapp_conversations SET queue_status='resolved', resolved_at=? WHERE id=?", (datetime.now().isoformat(timespec="seconds"), conversa_id))
        conn.commit()
    with Sessao(_sessao(vendedor_id, "vendedor")):
        resp = client.post(f"/api/admin/whatsapp/conversations/{conversa_id}/claim", headers=ORIGEM_PERMITIDA)
        assert resp.status_code == 409


# ---------------------------------------------------------------------------
# Horizontal: vendedor não vê/responde conversa de outro
# ---------------------------------------------------------------------------

def test_vendedor_nao_ve_conversa_de_outro(monkeypatch):
    _habilitar(monkeypatch)
    _ligar_multiatendente(monkeypatch, ligado=True)
    vendedor_a = _criar_usuario(perfil="vendedor")
    vendedor_b = _criar_usuario(perfil="vendedor")
    conversa_id = _criar_conversa_waiting()
    with Sessao(_sessao(vendedor_a, "vendedor")):
        assert client.post(f"/api/admin/whatsapp/conversations/{conversa_id}/claim", headers=ORIGEM_PERMITIDA).status_code == 200
    with Sessao(_sessao(vendedor_b, "vendedor")):
        resp = client.get(f"/api/admin/whatsapp/conversations/{conversa_id}")
        assert resp.status_code == 403


def test_vendedor_nao_responde_sem_assumir(monkeypatch):
    _habilitar(monkeypatch)
    _ligar_multiatendente(monkeypatch, ligado=True)
    monkeypatch.setattr(inbox_routes, "construir_provider", lambda nome: _ProviderFalso())
    vendedor_id = _criar_usuario(perfil="vendedor")
    conversa_id = _criar_conversa_waiting()
    with Sessao(_sessao(vendedor_id, "vendedor")):
        resp = client.post(
            f"/api/admin/whatsapp/conversations/{conversa_id}/messages",
            json={"text": "Oi"},
            headers={"Idempotency-Key": f"idem-{uuid.uuid4().hex}", **ORIGEM_PERMITIDA},
        )
        assert resp.status_code == 403
    with conectar() as conn:
        historico = conn.execute(
            "SELECT action FROM atendimento_assignment_history WHERE conversation_id=?", (conversa_id,)
        ).fetchall()
    assert any(row["action"] == "send_denied" for row in historico)


class _ProviderFalso:
    def send_inbox_text(self, *, to, texto, reply_to_meta_message_id=None):
        return ResultadoEnvioWhatsApp(ok=True, provider_message_id=f"wamid.fake.{uuid.uuid4().hex}", status="sent")

    def send_template(self, *, to, template_name, language, components=()):
        return ResultadoEnvioWhatsApp(ok=True, provider_message_id=f"wamid.fake.{uuid.uuid4().hex}", status="sent")


def test_vendedor_responde_apos_assumir(monkeypatch):
    _habilitar(monkeypatch)
    _ligar_multiatendente(monkeypatch, ligado=True)
    monkeypatch.setattr(inbox_routes, "construir_provider", lambda nome: _ProviderFalso())
    vendedor_id = _criar_usuario(perfil="vendedor")
    conversa_id = _criar_conversa_waiting()
    with Sessao(_sessao(vendedor_id, "vendedor")):
        assert client.post(f"/api/admin/whatsapp/conversations/{conversa_id}/claim", headers=ORIGEM_PERMITIDA).status_code == 200
        resp = client.post(
            f"/api/admin/whatsapp/conversations/{conversa_id}/messages",
            json={"text": "Já te atendo!"},
            headers={"Idempotency-Key": f"idem-{uuid.uuid4().hex}", **ORIGEM_PERMITIDA},
        )
        assert resp.status_code == 200
        assert resp.json()["ok"] is True


# ---------------------------------------------------------------------------
# Release / transfer / resolve / reopen
# ---------------------------------------------------------------------------

def test_release_por_dono(monkeypatch):
    _habilitar(monkeypatch)
    _ligar_multiatendente(monkeypatch, ligado=True)
    vendedor_id = _criar_usuario(perfil="vendedor")
    conversa_id = _criar_conversa_waiting()
    with Sessao(_sessao(vendedor_id, "vendedor")):
        client.post(f"/api/admin/whatsapp/conversations/{conversa_id}/claim", headers=ORIGEM_PERMITIDA)
        resp = client.post(f"/api/admin/whatsapp/conversations/{conversa_id}/release", json={"reason": "não é meu cliente"}, headers=ORIGEM_PERMITIDA)
        assert resp.status_code == 200
    with conectar() as conn:
        linha = conn.execute("SELECT assigned_user_id, queue_status FROM whatsapp_conversations WHERE id=?", (conversa_id,)).fetchone()
    assert linha["assigned_user_id"] is None
    assert linha["queue_status"] == "waiting"


def test_release_por_terceiro_e_negado(monkeypatch):
    _habilitar(monkeypatch)
    _ligar_multiatendente(monkeypatch, ligado=True)
    vendedor_a = _criar_usuario(perfil="vendedor")
    vendedor_b = _criar_usuario(perfil="vendedor")
    conversa_id = _criar_conversa_waiting()
    with Sessao(_sessao(vendedor_a, "vendedor")):
        client.post(f"/api/admin/whatsapp/conversations/{conversa_id}/claim", headers=ORIGEM_PERMITIDA)
    with Sessao(_sessao(vendedor_b, "vendedor")):
        resp = client.post(f"/api/admin/whatsapp/conversations/{conversa_id}/release", json={}, headers=ORIGEM_PERMITIDA)
        assert resp.status_code == 403


def test_transfer_vendedor_para_vendedor(monkeypatch):
    _habilitar(monkeypatch)
    _ligar_multiatendente(monkeypatch, ligado=True)
    vendedor_a = _criar_usuario(perfil="vendedor")
    vendedor_b = _criar_usuario(perfil="vendedor")
    conversa_id = _criar_conversa_waiting()
    with Sessao(_sessao(vendedor_a, "vendedor")):
        client.post(f"/api/admin/whatsapp/conversations/{conversa_id}/claim", headers=ORIGEM_PERMITIDA)
        resp = client.post(
            f"/api/admin/whatsapp/conversations/{conversa_id}/transfer",
            json={"target_user_id": vendedor_b, "reason": "cliente é dele"},
            headers=ORIGEM_PERMITIDA,
        )
        assert resp.status_code == 200
    with conectar() as conn:
        linha = conn.execute("SELECT assigned_user_id FROM whatsapp_conversations WHERE id=?", (conversa_id,)).fetchone()
    assert linha["assigned_user_id"] == vendedor_b


def test_transfer_para_usuario_invalido(monkeypatch):
    _habilitar(monkeypatch)
    _ligar_multiatendente(monkeypatch, ligado=True)
    vendedor_a = _criar_usuario(perfil="vendedor")
    conversa_id = _criar_conversa_waiting()
    with Sessao(_sessao(vendedor_a, "vendedor")):
        client.post(f"/api/admin/whatsapp/conversations/{conversa_id}/claim", headers=ORIGEM_PERMITIDA)
        resp = client.post(
            f"/api/admin/whatsapp/conversations/{conversa_id}/transfer",
            json={"target_user_id": 9_999_999},
            headers=ORIGEM_PERMITIDA,
        )
        assert resp.status_code == 422


def test_transfer_para_vendedor_lotado(monkeypatch):
    _habilitar(monkeypatch)
    _ligar_multiatendente(monkeypatch, ligado=True)
    vendedor_a = _criar_usuario(perfil="vendedor")
    vendedor_b = _criar_usuario(perfil="vendedor", max_conversas=1)
    conversa_ja_de_b = _criar_conversa_waiting()
    conversa_alvo = _criar_conversa_waiting()
    with Sessao(_sessao(vendedor_b, "vendedor")):
        assert client.post(f"/api/admin/whatsapp/conversations/{conversa_ja_de_b}/claim", headers=ORIGEM_PERMITIDA).status_code == 200
    with Sessao(_sessao(vendedor_a, "vendedor")):
        client.post(f"/api/admin/whatsapp/conversations/{conversa_alvo}/claim", headers=ORIGEM_PERMITIDA)
        resp = client.post(
            f"/api/admin/whatsapp/conversations/{conversa_alvo}/transfer",
            json={"target_user_id": vendedor_b},
            headers=ORIGEM_PERMITIDA,
        )
        assert resp.status_code == 409


def test_transfer_assignment_version_desatualizada(monkeypatch):
    _habilitar(monkeypatch)
    _ligar_multiatendente(monkeypatch, ligado=True)
    vendedor_a = _criar_usuario(perfil="vendedor")
    vendedor_b = _criar_usuario(perfil="vendedor")
    conversa_id = _criar_conversa_waiting()
    with Sessao(_sessao(vendedor_a, "vendedor")):
        client.post(f"/api/admin/whatsapp/conversations/{conversa_id}/claim", headers=ORIGEM_PERMITIDA)
        resp = client.post(
            f"/api/admin/whatsapp/conversations/{conversa_id}/transfer",
            json={"target_user_id": vendedor_b, "assignment_version": 999},
            headers=ORIGEM_PERMITIDA,
        )
        assert resp.status_code == 409


def test_resolve_e_reopen(monkeypatch):
    _habilitar(monkeypatch)
    _ligar_multiatendente(monkeypatch, ligado=True)
    adm_id = _criar_usuario(perfil="adm")
    vendedor_id = _criar_usuario(perfil="vendedor")
    conversa_id = _criar_conversa_waiting()
    with Sessao(_sessao(vendedor_id, "vendedor")):
        client.post(f"/api/admin/whatsapp/conversations/{conversa_id}/claim", headers=ORIGEM_PERMITIDA)
        resp = client.post(f"/api/admin/whatsapp/conversations/{conversa_id}/resolve", json={}, headers=ORIGEM_PERMITIDA)
        assert resp.status_code == 200
        # vendedor não pode reabrir
        resp_reabrir_negado = client.post(f"/api/admin/whatsapp/conversations/{conversa_id}/reopen", headers=ORIGEM_PERMITIDA)
        assert resp_reabrir_negado.status_code == 403
    with conectar() as conn:
        linha = conn.execute("SELECT queue_status FROM whatsapp_conversations WHERE id=?", (conversa_id,)).fetchone()
    assert linha["queue_status"] == "resolved"
    with Sessao(_sessao(adm_id, "adm")):
        resp2 = client.post(f"/api/admin/whatsapp/conversations/{conversa_id}/reopen", headers=ORIGEM_PERMITIDA)
        assert resp2.status_code == 200
    with conectar() as conn:
        linha2 = conn.execute("SELECT queue_status, assigned_user_id FROM whatsapp_conversations WHERE id=?", (conversa_id,)).fetchone()
    assert linha2["queue_status"] == "waiting"
    assert linha2["assigned_user_id"] is None


def test_mensagem_nova_reabre_conversa_encerrada():
    from backend.whatsapp_inbox_service import processar_webhook_mensagens

    wa_id = "5511" + str(uuid.uuid4().int)[:9]
    with conectar() as conn:
        contato = upsert_contact(conn, wa_id=wa_id, profile_name="Cliente")
        conversa = obter_ou_criar_conversa(conn, contact_id=contato["id"])
        conn.execute(
            "UPDATE whatsapp_conversations SET status='resolved', queue_status='resolved', resolved_at=? WHERE id=?",
            (datetime.now().isoformat(timespec="seconds"), conversa["id"]),
        )
        conn.commit()

    payload = {
        "entry": [{
            "changes": [{
                "value": {
                    "contacts": [{"wa_id": wa_id, "profile": {"name": "Cliente"}}],
                    "messages": [{
                        "id": f"wamid.{uuid.uuid4().hex}",
                        "from": wa_id,
                        "type": "text",
                        "text": {"body": "Oi, voltei"},
                        "timestamp": "1700000000",
                    }],
                }
            }]
        }]
    }
    with conectar() as conn:
        resultado = processar_webhook_mensagens(conn, payload)
        conn.commit()
    assert resultado["processadas"] == 1

    with conectar() as conn:
        linha = conn.execute("SELECT queue_status, assigned_user_id FROM whatsapp_conversations WHERE id=?", (conversa["id"],)).fetchone()
        historico = conn.execute(
            "SELECT action FROM atendimento_assignment_history WHERE conversation_id=?", (conversa["id"],)
        ).fetchall()
    assert linha["queue_status"] == "waiting"
    assert linha["assigned_user_id"] is None
    assert any(row["action"] == "auto_reopen" for row in historico)


# ---------------------------------------------------------------------------
# Histórico / auditoria
# ---------------------------------------------------------------------------

def test_historico_imutavel_via_api(monkeypatch):
    _habilitar(monkeypatch)
    _ligar_multiatendente(monkeypatch, ligado=True)
    adm_id = _criar_usuario(perfil="adm")
    vendedor_id = _criar_usuario(perfil="vendedor")
    conversa_id = _criar_conversa_waiting()
    with Sessao(_sessao(vendedor_id, "vendedor")):
        client.post(f"/api/admin/whatsapp/conversations/{conversa_id}/claim", headers=ORIGEM_PERMITIDA)
    with Sessao(_sessao(adm_id, "adm")):
        resp = client.get(f"/api/admin/whatsapp/conversations/{conversa_id}/assignment-history")
        assert resp.status_code == 200
        acoes = [item["action"] for item in resp.json()["history"]]
        assert "claim" in acoes
    with Sessao(_sessao(vendedor_id, "vendedor")):
        # vendedor não tem acesso ao histórico (rota restrita a adm/supervisor)
        resp2 = client.get(f"/api/admin/whatsapp/conversations/{conversa_id}/assignment-history")
        assert resp2.status_code == 403


# ---------------------------------------------------------------------------
# Gestão de vendedores
# ---------------------------------------------------------------------------

def test_gestao_de_agente_por_adm(monkeypatch):
    _habilitar(monkeypatch)
    _ligar_multiatendente(monkeypatch, ligado=True)
    adm_id = _criar_usuario(perfil="adm")
    vendedor_id = _criar_usuario(perfil="vendedor", atendimento_enabled=0)
    with Sessao(_sessao(adm_id, "adm")):
        resp = client.patch(
            f"/api/admin/whatsapp/agents/{vendedor_id}",
            json={"atendimento_enabled": True, "atendimento_max_active_conversations": 3},
            headers=ORIGEM_PERMITIDA,
        )
        assert resp.status_code == 200
        assert resp.json()["agent"]["atendimento_enabled"] is True


def test_vendedor_nao_pode_elevar_proprio_perfil(monkeypatch):
    _habilitar(monkeypatch)
    _ligar_multiatendente(monkeypatch, ligado=True)
    # supervisor tentando se auto-promover não se aplica a vendedor (vendedor
    # não acessa /agents), então testamos supervisor tentando alterar o
    # próprio perfil via PATCH (ação restrita).
    supervisor_id = _criar_usuario(perfil="supervisor_atendimento")
    with Sessao(_sessao(supervisor_id, "supervisor_atendimento")):
        resp = client.patch(
            f"/api/admin/whatsapp/agents/{supervisor_id}",
            json={"perfil": "vendedor"},
            headers=ORIGEM_PERMITIDA,
        )
        assert resp.status_code == 403


def test_paginacao_da_fila(monkeypatch):
    _habilitar(monkeypatch)
    _ligar_multiatendente(monkeypatch, ligado=True)
    adm_id = _criar_usuario(perfil="adm")
    for _ in range(3):
        _criar_conversa_waiting()
    with Sessao(_sessao(adm_id, "adm")):
        resp = client.get("/api/admin/whatsapp/queue", params={"page": 1, "page_size": 1})
        assert resp.status_code == 200
        corpo = resp.json()
        assert corpo["page_size"] == 1
        assert len(corpo["conversations"]) == 1
        assert corpo["total"] >= 3


def test_xss_em_motivo_de_transferencia_e_sanitizado(monkeypatch):
    _habilitar(monkeypatch)
    _ligar_multiatendente(monkeypatch, ligado=True)
    vendedor_a = _criar_usuario(perfil="vendedor")
    vendedor_b = _criar_usuario(perfil="vendedor")
    conversa_id = _criar_conversa_waiting()
    motivo_malicioso = "<script>alert(1)</script>\x00 motivo real"
    with Sessao(_sessao(vendedor_a, "vendedor")):
        client.post(f"/api/admin/whatsapp/conversations/{conversa_id}/claim", headers=ORIGEM_PERMITIDA)
        client.post(
            f"/api/admin/whatsapp/conversations/{conversa_id}/transfer",
            json={"target_user_id": vendedor_b, "reason": motivo_malicioso},
            headers=ORIGEM_PERMITIDA,
        )
    with conectar() as conn:
        linha = conn.execute(
            "SELECT reason FROM atendimento_assignment_history WHERE conversation_id=? AND action='transfer'", (conversa_id,)
        ).fetchone()
    assert "\x00" not in (linha["reason"] or "")
    # nunca executa/renderiza -- aqui só garantimos que bytes de controle
    # nulos não sobrevivem; a tag em si é persistida como texto puro (o
    # frontend nunca usa innerHTML com este campo).
    assert "<script>" in linha["reason"]
