from __future__ import annotations

import importlib


importlib.import_module("backend.main")

from backend import site_stock_routes  # noqa: E402
from backend.playlist_response_safety import (  # noqa: E402
    ERRO_PUBLICO_PLAYLIST,
    sanitizar_resposta_playlist,
)


def test_resposta_sem_erro_permanece_inalterada():
    resposta = {"ok": True, "links": [], "banco_erro": None}
    assert sanitizar_resposta_playlist(resposta) == resposta


def test_erro_interno_e_substituido_por_codigo_publico_curto():
    resposta = {
        "ok": True,
        "links": [],
        "banco_erro": "unable to open database file: /data/mistica.db",
    }
    segura = sanitizar_resposta_playlist(resposta)
    assert segura["banco_erro"] == ERRO_PUBLICO_PLAYLIST
    assert "/data" not in str(segura)
    assert "database" not in str(segura).lower()


def test_sanitizacao_nao_muta_objeto_original():
    original = {"ok": True, "banco_erro": "SQLITE_BUSY: database is locked"}
    segura = sanitizar_resposta_playlist(original)
    assert original["banco_erro"].startswith("SQLITE_BUSY")
    assert segura["banco_erro"] == ERRO_PUBLICO_PLAYLIST


def test_bootstrap_instala_protecao_no_endpoint_publico():
    endpoints = {
        rota.endpoint.__name__: rota.endpoint
        for rota in site_stock_routes.router.routes
        if getattr(rota, "endpoint", None)
    }
    endpoint = endpoints["obter_playlist_ambiente"]
    assert getattr(endpoint, "__mistica_playlist_sanitizada__", False)
    assert site_stock_routes.obter_playlist_ambiente is endpoint


def test_helper_preserva_respostas_nao_dict():
    assert sanitizar_resposta_playlist(None) is None
    assert sanitizar_resposta_playlist(["a"]) == ["a"]
