"""Fase 2: painel administrativo unificado de pedidos.

Os testes usam o banco temporário configurado pela suíte. Nenhum banco real é
aberto e nenhuma chamada ao Mercado Pago é realizada.
"""

from pathlib import Path

from backend.database import conectar
from tests.test_pedido_unificado import HEADERS, client, criar_pedido_publico


def alterar(pedido_id: int, status: str, observacao: str = "Teste Fase 2"):
    return client.patch(
        f"/api/pedidos/{pedido_id}/status-comercial",
        json={"status_pedido": status, "observacao": observacao},
        headers=HEADERS,
    )


def test_rota_comercial_exige_autenticacao():
    pedido = criar_pedido_publico(21.0)
    resposta = client.patch(
        f"/api/pedidos/{pedido['id']}/status-comercial",
        json={"status_pedido": "confirmado"},
    )
    assert resposta.status_code in (401, 403)


def test_transicao_comercial_valida_nao_altera_financeiro():
    pedido = criar_pedido_publico(22.0)
    antes = client.get(f"/api/pedidos/{pedido['id']}", headers=HEADERS).json()
    resposta = alterar(pedido["id"], "confirmado")
    assert resposta.status_code == 200, resposta.text
    depois = client.get(f"/api/pedidos/{pedido['id']}", headers=HEADERS).json()
    assert depois["status_pedido"] == "confirmado"
    assert depois["status"] == antes["status"]


def test_transicao_invalida_e_bloqueada():
    pedido = criar_pedido_publico(23.0)
    resposta = alterar(pedido["id"], "enviado")
    assert resposta.status_code == 409
    detalhe = client.get(f"/api/pedidos/{pedido['id']}", headers=HEADERS).json()
    assert detalhe["status_pedido"] == "novo"


def test_repeticao_nao_duplica_historico():
    pedido = criar_pedido_publico(24.0)
    primeira = alterar(pedido["id"], "confirmado")
    segunda = alterar(pedido["id"], "confirmado")
    assert primeira.status_code == 200
    assert segunda.status_code == 200
    assert segunda.json()["ja_registrado"] is True
    with conectar() as conn:
        total = conn.execute(
            """
            SELECT COUNT(*) AS total
              FROM pedido_status_log
             WHERE venda_id=? AND status='confirmado'
               AND tipo='pedido' AND origem='administrador'
            """,
            (pedido["id"],),
        ).fetchone()["total"]
    assert total == 1


def test_fluxo_comercial_permitido_ate_conclusao():
    # criar_pedido_publico cria um pedido de retirada (Fase 3): o fluxo válido
    # para retirada passa por "pronto_retirada", nunca por "enviado" (que é
    # exclusivo de pedidos de entrega).
    pedido = criar_pedido_publico(25.0)
    for status in ("confirmado", "em_preparacao", "pronto_retirada", "concluido"):
        resposta = alterar(pedido["id"], status)
        assert resposta.status_code == 200, resposta.text
    final = client.get(f"/api/pedidos/{pedido['id']}", headers=HEADERS).json()
    assert final["status_pedido"] == "concluido"
    assert alterar(pedido["id"], "cancelado").status_code == 409


def test_detalhe_admin_reune_itens_historicos_e_tentativas_sem_segredos():
    pedido = criar_pedido_publico(26.0)
    resposta = client.get(f"/api/pedidos/{pedido['id']}/detalhes-admin", headers=HEADERS)
    assert resposta.status_code == 200, resposta.text
    dados = resposta.json()
    assert dados["id"] == pedido["id"]
    assert isinstance(dados["itens"], list)
    assert isinstance(dados["historico_status"], list)
    assert isinstance(dados["historico_pagamentos"], list)
    assert isinstance(dados["tentativas_pagamento"], list)
    texto = resposta.text.lower()
    for proibido in ("access_token", "card_token", "numero_cartao", "número_cartão", "cvv", "pix_copia_cola", "provider_payment_id", "status_detail"):
        assert proibido not in texto


def test_cancelamento_comercial_nao_cancela_financeiro():
    pedido = criar_pedido_publico(27.0)
    antes = client.get(f"/api/pedidos/{pedido['id']}", headers=HEADERS).json()
    resposta = alterar(pedido["id"], "cancelado")
    assert resposta.status_code == 200
    depois = client.get(f"/api/pedidos/{pedido['id']}", headers=HEADERS).json()
    assert depois["status_pedido"] == "cancelado"
    assert depois["status"] == antes["status"]


def test_tela_nova_e_tela_pix_legada_continuam_presentes():
    raiz = Path(__file__).resolve().parents[1]
    assert (raiz / "admin-pedidos.html").exists()
    assert (raiz / "admin-pedidos.js").exists()
    assert (raiz / "admin-pedidos.css").exists()
    assert (raiz / "admin-pedidos-pix.html").exists()
    assert (raiz / "admin-pedidos-pix.js").exists()


def test_frontend_nao_guarda_pii_localmente_nem_expoe_segredos():
    raiz = Path(__file__).resolve().parents[1]
    javascript = (raiz / "admin-pedidos.js").read_text(encoding="utf-8").lower()
    html = (raiz / "admin-pedidos.html").read_text(encoding="utf-8").lower()
    assert "localstorage" not in javascript
    assert "sessionstorage" not in javascript
    assert ".innerhtml" not in javascript
    assert "access token" not in html
    assert "mercado_pago_access_token" not in javascript
    assert "cvv" not in html


def test_a_vista_nunca_e_renderizado_como_1x():
    javascript = (Path(__file__).resolve().parents[1] / "admin-pedidos.js").read_text(encoding="utf-8")
    assert 'return n <= 1 ? "À vista" : `${n}x`' in javascript


def test_polling_tem_intervalo_oculto_e_um_unico_timer():
    javascript = (Path(__file__).resolve().parents[1] / "admin-pedidos.js").read_text(encoding="utf-8")
    assert "POLL_VISIBLE_MS = 15000" in javascript
    assert "POLL_HIDDEN_MS = 60000" in javascript
    assert "if (pollTimer) clearTimeout(pollTimer)" in javascript
    assert "document.hidden ? POLL_HIDDEN_MS : POLL_VISIBLE_MS" in javascript
