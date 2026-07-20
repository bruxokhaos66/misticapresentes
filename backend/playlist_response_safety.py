from __future__ import annotations

import functools


ERRO_PUBLICO_PLAYLIST = "indisponivel"


def sanitizar_resposta_playlist(resposta):
    """Remove detalhes internos de banco da resposta pública da playlist.

    O endpoint pode continuar informando que houve indisponibilidade, mas nunca
    devolve texto cru de exceção, caminho de arquivo, SQL ou mensagem do SQLite.
    """
    if not isinstance(resposta, dict):
        return resposta
    segura = dict(resposta)
    if segura.get("banco_erro"):
        segura["banco_erro"] = ERRO_PUBLICO_PLAYLIST
    return segura


def _proteger_endpoint(endpoint):
    if getattr(endpoint, "__mistica_playlist_sanitizada__", False):
        return endpoint

    @functools.wraps(endpoint)
    def protegido(*args, **kwargs):
        return sanitizar_resposta_playlist(endpoint(*args, **kwargs))

    protegido.__mistica_playlist_sanitizada__ = True
    return protegido


def instalar_resposta_segura_playlist() -> None:
    """Instala a sanitização na rota pública já registrada pelo FastAPI."""
    from backend import site_stock_routes

    for rota in site_stock_routes.router.routes:
        endpoint = getattr(rota, "endpoint", None)
        if not endpoint or getattr(endpoint, "__name__", "") != "obter_playlist_ambiente":
            continue
        protegido = _proteger_endpoint(endpoint)
        rota.endpoint = protegido
        if getattr(rota, "dependant", None) is not None:
            rota.dependant.call = protegido
        site_stock_routes.obter_playlist_ambiente = protegido
        return
