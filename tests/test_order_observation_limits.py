from __future__ import annotations

import importlib

import pytest
from fastapi import HTTPException


importlib.import_module("backend.main")

from backend import order_status_routes  # noqa: E402
from backend.order_observation_limits import (  # noqa: E402
    LIMITE_OBSERVACAO_PEDIDO,
    MENSAGEM_OBSERVACAO_LONGA,
    validar_observacao_payload,
)


def test_observacao_ate_o_limite_e_aceita():
    payload = order_status_routes.PedidoObservacaoIn(observacao="a" * LIMITE_OBSERVACAO_PEDIDO)
    validar_observacao_payload(payload)


def test_observacao_acima_do_limite_retorna_422():
    payload = order_status_routes.PedidoObservacaoIn(observacao="a" * (LIMITE_OBSERVACAO_PEDIDO + 1))
    with pytest.raises(HTTPException) as exc:
        validar_observacao_payload(payload)
    assert exc.value.status_code == 422
    assert exc.value.detail == MENSAGEM_OBSERVACAO_LONGA


def test_payload_sem_observacao_nao_e_afetado():
    validar_observacao_payload(None)
    validar_observacao_payload(object())


def test_bootstrap_protege_status_e_observacao():
    endpoints = {
        rota.endpoint.__name__: rota.endpoint
        for rota in order_status_routes.router.routes
        if getattr(rota, "endpoint", None)
    }
    assert getattr(endpoints["atualizar_status_pedido"], "__mistica_observacao_limitada__", False)
    assert getattr(endpoints["atualizar_observacao_pedido"], "__mistica_observacao_limitada__", False)


def test_cancelamento_continua_com_sanitizacao_mais_restrita_existente():
    texto = "x" * 500
    assert len(order_status_routes._sanitizar_motivo_cancelamento(texto)) == 280
