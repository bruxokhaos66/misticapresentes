"""Orquestrador do Estúdio de Conteúdo da Isis (backend/isis_content_studio.py).

Cobre: geração diária habilitada pela flag, idempotência por dia,
seleção de produto respeitando estoque/oculto/ativo, e que a geração de
imagem só ocorre quando MISTICA_ISIS_CONTENT_IMAGE_GENERATION_ENABLED
estiver ligada.
"""
import os

import pytest

os.environ.setdefault("MISTICA_SITE_API_KEY", "test-api-key")
os.environ.setdefault("MISTICA_SYNC_KEY", "test-api-key")
os.environ.setdefault("MISTICA_PIX_WEBHOOK_SECRET", "test-isis-content-studio-webhook-secret")
os.environ.setdefault("MISTICA_PIX_KEY", "49999999999")

import config
import database.connection as db_conn
import backend.database as backend_db
from backend import isis_content_studio


@pytest.fixture()
def banco_isolado(tmp_path, monkeypatch):
    db_path = str(tmp_path / "isis_content_studio.db")
    monkeypatch.setattr(config, "DB_PATH", db_path)
    monkeypatch.setattr(db_conn, "DB_PATH", db_path)
    monkeypatch.setattr(backend_db, "DB_PATH", db_path)

    from database import init_db

    init_db()
    return db_path


@pytest.fixture()
def estudio_habilitado(monkeypatch):
    monkeypatch.setenv("MISTICA_ISIS_CONTENT_STUDIO_ENABLED", "true")
    monkeypatch.delenv("MISTICA_ISIS_CONTENT_IMAGE_GENERATION_ENABLED", raising=False)


def _produto(codigo="ISIS001", quantidade=5, ativo=1, isis_oculto=0, preco=50.0):
    with backend_db.conectar() as conn:
        cur = conn.execute(
            "INSERT INTO produtos (codigo_p, nome, preco, quantidade, categoria, ativo, isis_oculto) VALUES (?,?,?,?,?,?,?)",
            (codigo, f"Produto {codigo}", preco, quantidade, "Velas", ativo, isis_oculto),
        )
        return int(cur.lastrowid)


def test_gerar_conteudos_do_dia_bloqueado_sem_flag(banco_isolado, monkeypatch):
    monkeypatch.delenv("MISTICA_ISIS_CONTENT_STUDIO_ENABLED", raising=False)
    with pytest.raises(isis_content_studio.ContentStudioDesativadoError):
        isis_content_studio.gerar_conteudos_do_dia("2026-07-17")


def test_gerar_conteudos_do_dia_cria_dois_rascunhos(banco_isolado, estudio_habilitado):
    _produto()
    resultado = isis_content_studio.gerar_conteudos_do_dia("2026-07-17")
    assert resultado["reaproveitado"] is False
    assert len(resultado["drafts"]) == 2

    with backend_db.conectar() as conn:
        drafts = conn.execute("SELECT * FROM isis_content_drafts WHERE data_referencia=?", ("2026-07-17",)).fetchall()
    tipos = sorted(d["tipo"] for d in drafts)
    assert tipos == ["bom_dia", "produto_do_dia"]
    assert all(d["status"] == "rascunho" for d in drafts)


def test_gerar_conteudos_do_dia_e_idempotente(banco_isolado, estudio_habilitado):
    _produto()
    primeiro = isis_content_studio.gerar_conteudos_do_dia("2026-07-17")
    segundo = isis_content_studio.gerar_conteudos_do_dia("2026-07-17")
    assert segundo["reaproveitado"] is True
    assert segundo["job_id"] == primeiro["job_id"]

    with backend_db.conectar() as conn:
        total_jobs = conn.execute("SELECT COUNT(*) AS total FROM isis_content_jobs WHERE data_referencia=?", ("2026-07-17",)).fetchone()["total"]
        total_drafts = conn.execute("SELECT COUNT(*) AS total FROM isis_content_drafts WHERE data_referencia=?", ("2026-07-17",)).fetchone()["total"]
    assert total_jobs == 1
    assert total_drafts == 2


def test_forcar_recriar_substitui_rascunhos_do_dia(banco_isolado, estudio_habilitado):
    _produto()
    primeiro = isis_content_studio.gerar_conteudos_do_dia("2026-07-17")
    segundo = isis_content_studio.gerar_conteudos_do_dia("2026-07-17", forcar=True)
    assert segundo["job_id"] != primeiro["job_id"]
    with backend_db.conectar() as conn:
        total_jobs = conn.execute("SELECT COUNT(*) AS total FROM isis_content_jobs WHERE data_referencia=?", ("2026-07-17",)).fetchone()["total"]
    assert total_jobs == 1


def test_produto_do_dia_nunca_escolhe_sem_estoque_oculto_ou_inativo(banco_isolado, estudio_habilitado):
    _produto(codigo="SEM-ESTOQUE", quantidade=0)
    _produto(codigo="OCULTO", isis_oculto=1, quantidade=99)
    _produto(codigo="INATIVO", ativo=0, quantidade=99)
    _produto(codigo="ELEGIVEL", quantidade=3)

    resultado = isis_content_studio.gerar_conteudos_do_dia("2026-07-17")
    with backend_db.conectar() as conn:
        draft_produto = conn.execute(
            "SELECT * FROM isis_content_drafts WHERE data_referencia=? AND tipo='produto_do_dia'",
            ("2026-07-17",),
        ).fetchone()
    assert draft_produto is not None
    assert draft_produto["produto_codigo"] == "ELEGIVEL"


def test_produto_do_dia_ausente_quando_nenhum_elegivel(banco_isolado, estudio_habilitado):
    _produto(codigo="SEM-ESTOQUE", quantidade=0)
    resultado = isis_content_studio.gerar_conteudos_do_dia("2026-07-17")
    assert len(resultado["drafts"]) == 1
    with backend_db.conectar() as conn:
        draft_produto = conn.execute(
            "SELECT * FROM isis_content_drafts WHERE data_referencia=? AND tipo='produto_do_dia'",
            ("2026-07-17",),
        ).fetchone()
    assert draft_produto is None


def test_sem_imagem_gerada_quando_flag_de_imagem_desligada(banco_isolado, estudio_habilitado):
    _produto()
    isis_content_studio.gerar_conteudos_do_dia("2026-07-17")
    with backend_db.conectar() as conn:
        total_assets = conn.execute("SELECT COUNT(*) AS total FROM isis_content_assets").fetchone()["total"]
    assert total_assets == 0


def test_texto_gerado_nunca_contem_marcacao_html(banco_isolado, estudio_habilitado):
    """Ainda que um provedor de IA (real ou malicioso) devolva HTML/script
    embutido, o texto persistido nunca deve conter marcação -- proteção
    contra XSS armazenado quando o rascunho for renderizado no painel."""
    _produto()
    isis_content_studio.gerar_conteudos_do_dia("2026-07-17")
    with backend_db.conectar() as conn:
        drafts = conn.execute("SELECT * FROM isis_content_drafts WHERE data_referencia=?", ("2026-07-17",)).fetchall()
    for draft in drafts:
        for campo in ("legenda", "legenda_curta", "hashtags", "texto_alternativo", "prompt_visual"):
            valor = draft[campo] or ""
            assert "<" not in valor and ">" not in valor
