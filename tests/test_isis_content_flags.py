"""Feature flags do Estúdio de Conteúdo da Isis (Isis 2.0 — Fase 3).

Segue o mesmo padrão de tests/test_estorno_rest_feature_flag.py: cada flag
é independente, nasce desligada, não é contornável por query string/header,
e a rota bloqueada não tem efeito colateral nem expõe motivo técnico.
"""
import importlib
import os

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("MISTICA_SITE_API_KEY", "test-api-key")
os.environ.setdefault("MISTICA_SYNC_KEY", "test-api-key")
os.environ.setdefault("MISTICA_PIX_WEBHOOK_SECRET", "test-isis-content-webhook-secret")
os.environ.setdefault("MISTICA_PIX_KEY", "49999999999")

import config
import database.connection as db_conn
import backend.database as backend_db
from backend import isis_content_flags

main = importlib.import_module("backend.main")


@pytest.fixture()
def banco_isolado(tmp_path, monkeypatch):
    db_path = str(tmp_path / "isis_content_flags.db")
    monkeypatch.setattr(config, "DB_PATH", db_path)
    monkeypatch.setattr(db_conn, "DB_PATH", db_path)
    monkeypatch.setattr(backend_db, "DB_PATH", db_path)

    from database import init_db

    init_db()
    return db_path


@pytest.fixture()
def flags_desligadas(monkeypatch):
    for nome in (
        "MISTICA_ISIS_CONTENT_STUDIO_ENABLED",
        "MISTICA_ISIS_CONTENT_AUTO_GENERATION_ENABLED",
        "MISTICA_ISIS_CONTENT_IMAGE_GENERATION_ENABLED",
        "MISTICA_ISIS_CONTENT_AUTO_PUBLISH_ENABLED",
    ):
        monkeypatch.delenv(nome, raising=False)


def _sessao_admin(client, monkeypatch):
    """Cria uma sessão de admin válida direto no banco (evita rate limit
    de login), igual ao padrão usado em tests/test_lms.py."""
    import secrets as secrets_mod
    from datetime import datetime, timedelta

    token = secrets_mod.token_urlsafe(24)
    agora = datetime.now()
    with backend_db.conectar() as conn:
        conn.execute(
            """
            INSERT INTO painel_sessoes (token, usuario_id, login, nome, perfil, ip, user_agent, criada_em, expira_em, ultimo_acesso)
            VALUES (?,?,?,?,?,?,?,?,?,?)
            """,
            (token, 1, "admin", "Admin", "adm", "127.0.0.1", "pytest", agora.isoformat(sep=" ", timespec="seconds"), (agora + timedelta(hours=1)).isoformat(sep=" ", timespec="seconds"), agora.isoformat(sep=" ", timespec="seconds")),
        )
        conn.commit()
    client.cookies.set("mistica_painel_sessao", token)
    return token


def test_todas_flags_nascem_desligadas(flags_desligadas):
    assert isis_content_flags.content_studio_habilitado() is False
    assert isis_content_flags.auto_generation_habilitado() is False
    assert isis_content_flags.image_generation_habilitado() is False
    assert isis_content_flags.auto_publish_habilitado() is False


@pytest.mark.parametrize("valor_flag", ["false", "0", "nao", "qualquercoisa", "  ", "FALSE"])
def test_flag_false_ou_invalida_mantem_desligada(monkeypatch, valor_flag):
    monkeypatch.setenv("MISTICA_ISIS_CONTENT_STUDIO_ENABLED", valor_flag)
    assert isis_content_flags.content_studio_habilitado() is False


@pytest.mark.parametrize("valor_flag", ["true", "1", "yes", "on", "sim", "TRUE"])
def test_flag_true_habilita(monkeypatch, valor_flag):
    monkeypatch.setenv("MISTICA_ISIS_CONTENT_STUDIO_ENABLED", valor_flag)
    assert isis_content_flags.content_studio_habilitado() is True


def test_flags_sao_independentes(monkeypatch):
    monkeypatch.setenv("MISTICA_ISIS_CONTENT_STUDIO_ENABLED", "true")
    monkeypatch.delenv("MISTICA_ISIS_CONTENT_AUTO_GENERATION_ENABLED", raising=False)
    monkeypatch.delenv("MISTICA_ISIS_CONTENT_IMAGE_GENERATION_ENABLED", raising=False)
    monkeypatch.delenv("MISTICA_ISIS_CONTENT_AUTO_PUBLISH_ENABLED", raising=False)
    assert isis_content_flags.content_studio_habilitado() is True
    assert isis_content_flags.auto_generation_habilitado() is False
    assert isis_content_flags.image_generation_habilitado() is False
    assert isis_content_flags.auto_publish_habilitado() is False


def test_rota_drafts_bloqueada_por_padrao(banco_isolado, flags_desligadas):
    with TestClient(main.app) as cliente:
        _sessao_admin(cliente, None)
        resposta = cliente.get("/api/admin/isis-conteudo/drafts")
    assert resposta.status_code == 404


def test_rota_drafts_bloqueada_mesmo_sem_sessao(banco_isolado, flags_desligadas):
    """A checagem de flag deve, no mínimo, nunca revelar dados a quem não
    está autenticado -- aqui verificamos que sem sessão a rota também não
    devolve 200."""
    with TestClient(main.app) as cliente:
        resposta = cliente.get("/api/admin/isis-conteudo/drafts")
    assert resposta.status_code in (401, 404)


def test_query_string_nao_contorna_flag_desligada(banco_isolado, flags_desligadas):
    with TestClient(main.app) as cliente:
        _sessao_admin(cliente, None)
        resposta = cliente.get("/api/admin/isis-conteudo/drafts?enabled=true&habilitado=1&flag=on")
    assert resposta.status_code == 404


def test_gerar_diario_bloqueado_por_padrao_nao_cria_job(banco_isolado, flags_desligadas):
    with TestClient(main.app) as cliente:
        _sessao_admin(cliente, None)
        resposta = cliente.post(
            "/api/admin/isis-conteudo/gerar-diario",
            json={},
            headers={"Origin": "http://localhost:3000"},
        )
    assert resposta.status_code == 404
    with backend_db.conectar() as conn:
        total = conn.execute("SELECT COUNT(*) AS total FROM isis_content_jobs").fetchone()["total"]
    assert total == 0


def test_status_flags_disponivel_para_admin_mesmo_desligado(banco_isolado, flags_desligadas):
    """O endpoint de status é a única exceção: um admin autenticado precisa
    conseguir ver que o estúdio está desligado (para a UI mostrar uma
    mensagem amigável), sem que isso libere nenhuma funcionalidade."""
    with TestClient(main.app) as cliente:
        _sessao_admin(cliente, None)
        resposta = cliente.get("/api/admin/isis-conteudo/status")
    assert resposta.status_code == 200
    corpo = resposta.json()
    assert corpo["content_studio_enabled"] is False
    assert corpo["auto_generation_enabled"] is False
    assert corpo["image_generation_enabled"] is False
    assert corpo["auto_publish_enabled"] is False


def test_status_flags_exige_sessao_admin(banco_isolado, flags_desligadas):
    with TestClient(main.app) as cliente:
        resposta = cliente.get("/api/admin/isis-conteudo/status")
    assert resposta.status_code == 401
