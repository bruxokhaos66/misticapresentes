"""Rotas administrativas do Estúdio de Conteúdo (backend/isis_content_routes.py):
transições de status do fluxo de aprovação, autorização e a regressão de
`regenerar-imagem` (falha parcial nunca deve deixar um arquivo novo sem
linha no banco, nem apagar os assets antigos antes dos novos existirem).
"""
import importlib
import os
from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("MISTICA_SITE_API_KEY", "test-api-key")
os.environ.setdefault("MISTICA_SYNC_KEY", "test-api-key")
os.environ.setdefault("MISTICA_PIX_WEBHOOK_SECRET", "test-isis-content-routes-webhook-secret")
os.environ.setdefault("MISTICA_PIX_KEY", "49999999999")

import config
import database.connection as db_conn
import backend.database as backend_db
from backend import isis_content_storage

main = importlib.import_module("backend.main")
ORIGIN_HEADER = {"Origin": "http://localhost:3000"}


@pytest.fixture()
def banco_isolado(tmp_path, monkeypatch):
    db_path = str(tmp_path / "isis_content_routes.db")
    monkeypatch.setattr(config, "DB_PATH", db_path)
    monkeypatch.setattr(db_conn, "DB_PATH", db_path)
    monkeypatch.setattr(backend_db, "DB_PATH", db_path)

    from database import init_db

    init_db()
    return db_path


@pytest.fixture()
def estudio_habilitado(monkeypatch):
    monkeypatch.setenv("MISTICA_ISIS_CONTENT_STUDIO_ENABLED", "true")
    monkeypatch.setenv("MISTICA_ISIS_CONTENT_IMAGE_GENERATION_ENABLED", "true")


def _sessao_admin(client) -> None:
    import secrets as secrets_mod

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


def _criar_draft_com_um_asset(tmp_path, monkeypatch) -> int:
    monkeypatch.setenv("ISIS_CONTENT_IMAGES_LOCAL_DIR", str(tmp_path / "isis-conteudo"))
    monkeypatch.setattr(isis_content_storage, "_storage", None)
    with backend_db.conectar() as conn:
        agora = datetime.now().isoformat(timespec="seconds")
        cur = conn.execute(
            """
            INSERT INTO isis_content_drafts (data_referencia, tipo, legenda, prompt_visual, status, criado_em, atualizado_em)
            VALUES (?,?,?,?,?,?,?)
            """,
            ("2026-07-17", "bom_dia", "Legenda original", "Prompt visual", "rascunho", agora, agora),
        )
        draft_id = int(cur.lastrowid)
        import io

        from PIL import Image

        buffer = io.BytesIO()
        Image.new("RGB", (10, 10)).save(buffer, format="PNG")
        asset = isis_content_storage.salvar_asset(buffer.getvalue(), draft_id=draft_id, variante="feed", content_type="image/png")
        conn.execute(
            """
            INSERT INTO isis_content_assets (draft_id, variante, largura, altura, arquivo, mime_type, tamanho_bytes, hash_sha256, criado_em)
            VALUES (?,?,?,?,?,?,?,?,?)
            """,
            (draft_id, "feed", asset["largura"], asset["altura"], asset["arquivo"], asset["mime_type"], asset["tamanho_bytes"], asset["hash_sha256"], agora),
        )
    return draft_id


class _ImageProviderFalhaNaSegundaVariante:
    nome = "fake"

    def __init__(self):
        self.chamadas = 0

    def gerar_imagem(self, prompt, *, largura, altura):
        from backend.isis_ai_providers import AIProviderIndisponivelError, ImageGenerationResult

        self.chamadas += 1
        if self.chamadas >= 2:
            raise AIProviderIndisponivelError("simulado")
        import io

        from PIL import Image

        buffer = io.BytesIO()
        Image.new("RGB", (largura, altura)).save(buffer, format="PNG")
        return ImageGenerationResult(dados=buffer.getvalue(), mime_type="image/png")


def test_regenerar_imagem_com_falha_parcial_preserva_assets_antigos(banco_isolado, estudio_habilitado, tmp_path, monkeypatch):
    draft_id = _criar_draft_com_um_asset(tmp_path, monkeypatch)
    with backend_db.conectar() as conn:
        asset_antigo = dict(conn.execute("SELECT * FROM isis_content_assets WHERE draft_id=?", (draft_id,)).fetchone())
    monkeypatch.setattr("backend.isis_content_routes.obter_image_provider", lambda: _ImageProviderFalhaNaSegundaVariante())

    with TestClient(main.app) as cliente:
        _sessao_admin(cliente)
        resposta = cliente.post(f"/api/admin/isis-conteudo/drafts/{draft_id}/regenerar-imagem", headers=ORIGIN_HEADER)

    assert resposta.status_code == 503
    with backend_db.conectar() as conn:
        assets_depois = [dict(a) for a in conn.execute("SELECT * FROM isis_content_assets WHERE draft_id=?", (draft_id,)).fetchall()]
    assert len(assets_depois) == 1
    assert assets_depois[0]["arquivo"] == asset_antigo["arquivo"]
    assert os.path.exists(str(tmp_path / "isis-conteudo" / asset_antigo["arquivo"].rsplit("/", 1)[-1]))


def test_regenerar_imagem_com_sucesso_remove_arquivos_antigos_do_storage(banco_isolado, estudio_habilitado, tmp_path, monkeypatch):
    draft_id = _criar_draft_com_um_asset(tmp_path, monkeypatch)
    with backend_db.conectar() as conn:
        asset_antigo = dict(conn.execute("SELECT * FROM isis_content_assets WHERE draft_id=?", (draft_id,)).fetchone())
    caminho_antigo = tmp_path / "isis-conteudo" / asset_antigo["arquivo"].rsplit("/", 1)[-1]
    assert caminho_antigo.exists()

    class _ImageProviderSempreOk:
        nome = "fake"

        def gerar_imagem(self, prompt, *, largura, altura):
            import io

            from PIL import Image

            from backend.isis_ai_providers import ImageGenerationResult

            buffer = io.BytesIO()
            Image.new("RGB", (largura, altura)).save(buffer, format="PNG")
            return ImageGenerationResult(dados=buffer.getvalue(), mime_type="image/png")

    monkeypatch.setattr("backend.isis_content_routes.obter_image_provider", lambda: _ImageProviderSempreOk())

    with TestClient(main.app) as cliente:
        _sessao_admin(cliente)
        resposta = cliente.post(f"/api/admin/isis-conteudo/drafts/{draft_id}/regenerar-imagem", headers=ORIGIN_HEADER)

    assert resposta.status_code == 200, resposta.text
    assert not caminho_antigo.exists()
    with backend_db.conectar() as conn:
        assets_depois = [dict(a) for a in conn.execute("SELECT * FROM isis_content_assets WHERE draft_id=?", (draft_id,)).fetchall()]
    assert len(assets_depois) == 2
    assert all(a["arquivo"] != asset_antigo["arquivo"] for a in assets_depois)


def test_fluxo_aprovacao_transicoes_de_status(banco_isolado, estudio_habilitado):
    with backend_db.conectar() as conn:
        agora = datetime.now().isoformat(timespec="seconds")
        cur = conn.execute(
            "INSERT INTO isis_content_drafts (data_referencia, tipo, legenda, status, criado_em, atualizado_em) VALUES (?,?,?,?,?,?)",
            ("2026-07-17", "bom_dia", "Legenda", "rascunho", agora, agora),
        )
        draft_id = int(cur.lastrowid)

    with TestClient(main.app) as cliente:
        _sessao_admin(cliente)
        # rejeitar exige motivo
        resposta = cliente.post(f"/api/admin/isis-conteudo/drafts/{draft_id}/publicar-manual", headers=ORIGIN_HEADER)
        assert resposta.status_code == 409  # ainda em rascunho, não aprovado

        resposta = cliente.post(f"/api/admin/isis-conteudo/drafts/{draft_id}/aprovar", headers=ORIGIN_HEADER)
        assert resposta.status_code == 200

        resposta = cliente.post(f"/api/admin/isis-conteudo/drafts/{draft_id}/aprovar", headers=ORIGIN_HEADER)
        assert resposta.status_code == 409  # não pode aprovar de novo

        resposta = cliente.post(f"/api/admin/isis-conteudo/drafts/{draft_id}/publicar-manual", headers=ORIGIN_HEADER)
        assert resposta.status_code == 200

        resposta = cliente.post(f"/api/admin/isis-conteudo/drafts/{draft_id}/rejeitar", json={"motivo": "tarde demais"}, headers=ORIGIN_HEADER)
        assert resposta.status_code == 409  # já publicado, não pode mais rejeitar

    with backend_db.conectar() as conn:
        status_final = conn.execute("SELECT status FROM isis_content_drafts WHERE id=?", (draft_id,)).fetchone()["status"]
    assert status_final == "publicado"


def test_rotas_administrativas_exigem_sessao(banco_isolado, estudio_habilitado):
    with backend_db.conectar() as conn:
        agora = datetime.now().isoformat(timespec="seconds")
        cur = conn.execute(
            "INSERT INTO isis_content_drafts (data_referencia, tipo, legenda, status, criado_em, atualizado_em) VALUES (?,?,?,?,?,?)",
            ("2026-07-17", "bom_dia", "Legenda", "rascunho", agora, agora),
        )
        draft_id = int(cur.lastrowid)

    with TestClient(main.app) as cliente:
        assert cliente.get("/api/admin/isis-conteudo/drafts").status_code == 401
        assert cliente.get(f"/api/admin/isis-conteudo/drafts/{draft_id}").status_code == 401
        assert cliente.post(f"/api/admin/isis-conteudo/drafts/{draft_id}/aprovar", headers=ORIGIN_HEADER).status_code == 401
