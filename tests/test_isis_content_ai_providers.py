"""Provedores de IA do Estúdio de Conteúdo (backend/isis_ai_providers.py):
retry limitado, orçamento diário e registro de consumo sem vazar prompts.
"""
import os

import pytest

os.environ.setdefault("MISTICA_SITE_API_KEY", "test-api-key")
os.environ.setdefault("MISTICA_SYNC_KEY", "test-api-key")
os.environ.setdefault("MISTICA_PIX_WEBHOOK_SECRET", "test-isis-content-ai-webhook-secret")
os.environ.setdefault("MISTICA_PIX_KEY", "49999999999")

import config
import database.connection as db_conn
import backend.database as backend_db
from backend import isis_ai_providers as ai


@pytest.fixture()
def banco_isolado(tmp_path, monkeypatch):
    db_path = str(tmp_path / "isis_content_ai.db")
    monkeypatch.setattr(config, "DB_PATH", db_path)
    monkeypatch.setattr(db_conn, "DB_PATH", db_path)
    monkeypatch.setattr(backend_db, "DB_PATH", db_path)

    from database import init_db

    init_db()
    return db_path


def test_null_text_provider_sinaliza_indisponibilidade_sem_chamada_de_rede():
    provider = ai.NullTextProvider()
    with pytest.raises(ai.AIProviderIndisponivelError):
        provider.gerar_texto("qualquer prompt")


def test_null_image_provider_sinaliza_indisponibilidade_sem_chamada_de_rede():
    provider = ai.NullImageProvider()
    with pytest.raises(ai.AIProviderIndisponivelError):
        provider.gerar_imagem("qualquer prompt", largura=1080, altura=1350)


def test_obter_text_provider_cai_no_null_sem_chave_configurada(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    assert isinstance(ai.obter_text_provider(), ai.NullTextProvider)


def test_obter_image_provider_cai_no_null_sem_chave_configurada(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    assert isinstance(ai.obter_image_provider(), ai.NullImageProvider)


def test_com_retry_tenta_no_maximo_o_limite_configurado(monkeypatch):
    monkeypatch.setattr(ai, "MAX_TENTATIVAS", 3)
    chamadas = {"total": 0}

    def sempre_falha():
        chamadas["total"] += 1
        raise TimeoutError("simulado")

    with pytest.raises(ai.AIProviderIndisponivelError):
        ai._com_retry("operacao_teste", "provedor_teste", sempre_falha)
    assert chamadas["total"] == 3


def test_com_retry_nao_repete_erro_de_configuracao(monkeypatch):
    monkeypatch.setattr(ai, "MAX_TENTATIVAS", 3)
    chamadas = {"total": 0}

    def erro_configuracao():
        chamadas["total"] += 1
        raise ValueError("chave ausente")

    with pytest.raises(ValueError):
        ai._com_retry("operacao_teste", "provedor_teste", erro_configuracao)
    assert chamadas["total"] == 1


def test_com_retry_sucesso_na_segunda_tentativa_nao_levanta_erro(monkeypatch):
    monkeypatch.setattr(ai, "MAX_TENTATIVAS", 3)
    chamadas = {"total": 0}

    def falha_uma_vez():
        chamadas["total"] += 1
        if chamadas["total"] < 2:
            raise TimeoutError("simulado")
        return "ok"

    assert ai._com_retry("operacao_teste", "provedor_teste", falha_uma_vez) == "ok"
    assert chamadas["total"] == 2


def test_orcamento_diario_disponivel_com_orcamento_zerado_bloqueia_tudo(banco_isolado, monkeypatch):
    monkeypatch.setattr(ai, "ORCAMENTO_DIARIO_USD", 0.0)
    assert ai.orcamento_diario_disponivel() is False


def test_orcamento_diario_esgotado_apos_consumo_acumulado(banco_isolado, monkeypatch):
    monkeypatch.setattr(ai, "ORCAMENTO_DIARIO_USD", 1.0)
    assert ai.orcamento_diario_disponivel() is True
    ai.registrar_consumo(provedor="openai", tipo="texto", custo_estimado=0.9)
    assert ai.orcamento_diario_disponivel() is True
    ai.registrar_consumo(provedor="openai", tipo="texto", custo_estimado=0.5)
    assert ai.orcamento_diario_disponivel() is False


def test_registrar_consumo_nunca_grava_o_conteudo_gerado(banco_isolado):
    ai.registrar_consumo(provedor="openai", tipo="texto", custo_estimado=0.01)
    with backend_db.conectar() as conn:
        linha = conn.execute("SELECT * FROM isis_content_ai_usage ORDER BY id DESC LIMIT 1").fetchone()
    colunas = set(dict(linha).keys())
    assert colunas == {"id", "data_referencia", "provedor", "tipo", "custo_estimado", "unidades", "sucesso", "criado_em"}
