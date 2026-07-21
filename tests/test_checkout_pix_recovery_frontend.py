from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def ler(nome: str) -> str:
    return (ROOT / nome).read_text(encoding="utf-8")


def test_loader_local_carrega_modulo_de_recuperacao():
    analytics = ler("analytics.js")
    assert 'checkout-pix-recovery.js?v=20260720-homologacao-pr3' in analytics
    assert 'data-checkout-pix-recovery' in analytics
    assert 'https://' not in analytics.split('checkout-pix-recovery.js')[0][-120:]


def test_checkout_pix_tem_timeout_e_apenas_uma_repeticao():
    js = ler("checkout-pix-recovery.js")
    assert "const TIMEOUT_MS = 12000" in js
    assert "const RETRY_DELAY_MS = 700" in js
    assert js.count("funcaoOriginal(itens)") == 2
    assert "Promise.race" in js
    assert "CheckoutPixTimeoutError" in js


def test_repeticao_preserva_a_funcao_original_e_a_idempotencia_existente():
    js = ler("checkout-pix-recovery.js")
    mobile = ler("mobile-sync.js")
    assert "funcaoOriginal = window.misticaCriarPedido" in js
    assert "window.misticaCriarPedido = criarPedidoComRecuperacao" in js
    # Fase 3: a chave de idempotência também depende da modalidade/endereço
    # de entrega (ver mobile-sync.js::assinaturaCarrinho), então a chamada
    # ganhou um segundo argumento — a idempotência em si (uma chave por
    # tentativa de checkout) continua preservada.
    assert 'headers: { "Idempotency-Key": idempotencyKeyParaItens(itensPedido, dadosEntrega) }' in mobile
    assert "misticaResetIdempotencyKey" not in js


def test_chamadas_concorrentes_compartilham_a_mesma_promessa():
    js = ler("checkout-pix-recovery.js")
    assert "if (tentativaEmAndamento) return tentativaEmAndamento" in js
    assert "tentativaEmAndamento = null" in js


def test_falha_final_preserva_carrinho_e_orienta_nova_tentativa():
    js = ler("checkout-pix-recovery.js")
    assert "O carrinho foi preservado" in js
    assert "reutilizará a mesma chave de segurança" in js
    assert 'navigator.onLine === false' in js
    assert 'document.getElementById("pixStatus")' in js


def test_modulo_nao_altera_pagamento_credenciais_ou_backend():
    js = ler("checkout-pix-recovery.js")
    proibidos = ["public_key", "access_token", "mercadopago", "/api/checkout/pedidos", "pix_copia_cola", "innerHTML"]
    for termo in proibidos:
        assert termo not in js.lower()
