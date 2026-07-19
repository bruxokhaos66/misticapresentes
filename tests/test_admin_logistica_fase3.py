"""Fase 3: logística administrativa de pedidos.

Os testes usam o banco temporário da suíte e não fazem chamadas externas nem
alteram o fluxo financeiro do Mercado Pago.
"""

from backend.database import conectar
from tests.test_pedido_unificado import HEADERS, client, criar_pedido_publico


def atualizar_logistica(pedido_id: int, **dados):
    payload = {
        "forma_recebimento": "entrega",
        "codigo_rastreio": "BR123456789SC",
        "observacao": "Separar com cuidado",
    }
    payload.update(dados)
    return client.patch(
        f"/api/pedidos/{pedido_id}/logistica",
        json=payload,
        headers=HEADERS,
    )


def test_logistica_exige_autenticacao_para_leitura_e_alteracao():
    pedido = criar_pedido_publico(31.0)

    leitura = client.get(f"/api/pedidos/{pedido['id']}/logistica")
    alteracao = client.patch(
        f"/api/pedidos/{pedido['id']}/logistica",
        json={"forma_recebimento": "retirada"},
    )

    assert leitura.status_code in (401, 403)
    assert alteracao.status_code in (401, 403)


def test_entrega_atualiza_logistica_sem_alterar_financeiro():
    pedido = criar_pedido_publico(32.0)
    antes = client.get(f"/api/pedidos/{pedido['id']}", headers=HEADERS).json()

    resposta = atualizar_logistica(pedido["id"])
    assert resposta.status_code == 200, resposta.text

    depois = client.get(f"/api/pedidos/{pedido['id']}", headers=HEADERS).json()
    logistica = client.get(
        f"/api/pedidos/{pedido['id']}/logistica", headers=HEADERS
    ).json()

    assert depois["status"] == antes["status"]
    assert depois["status_pedido"] == antes["status_pedido"]
    assert logistica["forma_recebimento"] == "entrega"
    assert logistica["codigo_rastreio"] == "BR123456789SC"
    assert logistica["observacao_pedido"] == "Separar com cuidado"


def test_retirada_rejeita_codigo_de_rastreio():
    pedido = criar_pedido_publico(33.0)

    resposta = atualizar_logistica(
        pedido["id"],
        forma_recebimento="retirada",
        codigo_rastreio="NAO-DEVERIA-ACEITAR",
    )

    assert resposta.status_code == 400


def test_retirada_sem_rastreio_e_aceita():
    pedido = criar_pedido_publico(34.0)

    resposta = atualizar_logistica(
        pedido["id"],
        forma_recebimento="retirada",
        codigo_rastreio=None,
        observacao="Cliente retira na loja",
    )

    assert resposta.status_code == 200, resposta.text
    dados = client.get(
        f"/api/pedidos/{pedido['id']}/logistica", headers=HEADERS
    ).json()
    assert dados["forma_recebimento"] == "retirada"
    assert dados["codigo_rastreio"] is None


def test_pedido_cancelado_bloqueia_alteracao_logistica():
    pedido = criar_pedido_publico(35.0)
    cancelamento = client.patch(
        f"/api/pedidos/{pedido['id']}/status-comercial",
        json={"status_pedido": "cancelado", "observacao": "Teste Fase 3"},
        headers=HEADERS,
    )
    assert cancelamento.status_code == 200, cancelamento.text

    resposta = atualizar_logistica(pedido["id"])
    assert resposta.status_code == 409


def test_alteracao_logistica_e_auditada_sem_segredos_financeiros():
    pedido = criar_pedido_publico(36.0)
    resposta = atualizar_logistica(pedido["id"])
    assert resposta.status_code == 200, resposta.text

    with conectar() as conn:
        evento = conn.execute(
            """
            SELECT acao, dados_antes, dados_depois
              FROM audit_log
             WHERE entidade='pedido' AND entidade_id=?
               AND acao='atualizar_logistica'
             ORDER BY id DESC
             LIMIT 1
            """,
            (str(pedido["id"]),),
        ).fetchone()

    assert evento is not None
    texto = f"{evento['dados_antes']} {evento['dados_depois']}".lower()
    assert "forma_recebimento" in texto
    assert "codigo_rastreio" in texto
    for proibido in ("access_token", "card_token", "cvv", "pix_copia_cola"):
        assert proibido not in texto
