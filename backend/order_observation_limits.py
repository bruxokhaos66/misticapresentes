from __future__ import annotations

import functools

from fastapi import HTTPException


LIMITE_OBSERVACAO_PEDIDO = 1000
MENSAGEM_OBSERVACAO_LONGA = f"Observação deve ter no máximo {LIMITE_OBSERVACAO_PEDIDO} caracteres."


def validar_observacao_payload(payload) -> None:
    """Bloqueia observações excessivas antes de qualquer escrita no banco."""
    if payload is None or not hasattr(payload, "observacao"):
        return
    observacao = getattr(payload, "observacao", None)
    if observacao is None:
        return
    if len(str(observacao)) > LIMITE_OBSERVACAO_PEDIDO:
        raise HTTPException(status_code=422, detail=MENSAGEM_OBSERVACAO_LONGA)


def _proteger_endpoint(endpoint):
    if getattr(endpoint, "__mistica_observacao_limitada__", False):
        return endpoint

    @functools.wraps(endpoint)
    def protegido(*args, **kwargs):
        payload = kwargs.get("payload")
        if payload is None:
            for argumento in args:
                if hasattr(argumento, "observacao"):
                    payload = argumento
                    break
        validar_observacao_payload(payload)
        return endpoint(*args, **kwargs)

    protegido.__mistica_observacao_limitada__ = True
    return protegido


def instalar_limite_observacao_pedido() -> None:
    """Instala a validação nas rotas administrativas já registradas."""
    from backend import order_status_routes

    endpoints_alvo = {"atualizar_status_pedido", "atualizar_observacao_pedido"}
    for rota in order_status_routes.router.routes:
        endpoint = getattr(rota, "endpoint", None)
        if not endpoint or getattr(endpoint, "__name__", "") not in endpoints_alvo:
            continue
        protegido = _proteger_endpoint(endpoint)
        rota.endpoint = protegido
        if getattr(rota, "dependant", None) is not None:
            rota.dependant.call = protegido
        setattr(order_status_routes, endpoint.__name__, protegido)
