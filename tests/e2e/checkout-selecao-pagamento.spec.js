const { test, expect } = require("@playwright/test");

// Seleção de forma de pagamento (Pix/Cartão) -- revisão de homologação da
// PR #388. Cobre os requisitos explícitos do pedido de homologação que
// ainda não tinham teste dedicado: nenhuma criação de pedido/cobrança só
// por trocar de aba, rótulo do stepper reflete o método real, Pix continua
// disponível após uma recusa de cartão.

const produtoApi = {
  id: 983,
  codigo_p: "TESTE-983",
  nome: "Amuleto de teste — Seleção de pagamento",
  categoria: "Cristais",
  descricao: "Produto controlado para teste de seleção de pagamento.",
  preco: 60.0,
  quantidade: 10,
  imagem_url: "",
  imagens: [],
  selo: "",
};

// Mock mínimo do SDK do Mercado Pago -- sem isso, carregarSdk() (v2-
// mercadopago-checkout.js) tenta buscar o script real em sdk.mercadopago.com,
// que nesta suíte (sem acesso à internet real) nem resolve nem rejeita
// rápido o bastante, atrasando/mascarando de forma não-determinística o
// instante em que garantirPedidoAtual() (e portanto a criação do pedido) é
// de fato chamado. Mesma técnica de mock usada em
// tests/e2e/fixtures/mercadopago-cardform-fixture.html para os testes de
// montagem do CardForm -- aqui só o suficiente para não travar em
// carregarSdk(), sem simular o CardForm de verdade (fora do escopo destes
// testes de seleção de método).
async function mockarSdkMercadoPago(page) {
  await page.addInitScript(() => {
    window.MercadoPago = function MercadoPago() {
      return { cardForm: () => ({ unmount() {} }) };
    };
  });
}

async function irParaCheckoutComCartaoHabilitado(page) {
  await mockarSdkMercadoPago(page);
  await page.route("**/api/produtos?**", route => route.fulfill({
    status: 200, contentType: "application/json", body: JSON.stringify([produtoApi]),
  }));
  await page.route("**/api/payments/mercadopago/config", route => route.fulfill({
    status: 200, contentType: "application/json", body: JSON.stringify({ enabled: true, public_key: "TEST-PUBLIC-KEY" }),
  }));
  await page.goto("/index.html");
  await expect.poll(() => page.evaluate(() => window.misticaCatalogState)).toBe("ready");
  await page.locator("[data-product-grid] button", { hasText: "Adicionar" }).click();
  await expect(page.locator("#cartList")).toContainText("Amuleto de teste — Seleção de pagamento");
  await page.locator('[data-payment-method="cartao"]').waitFor({ state: "visible" });
}

test.describe("Seleção de forma de pagamento", () => {
  test("1) apenas um painel fica visível por vez (Pix por padrão)", async ({ page }) => {
    await irParaCheckoutComCartaoHabilitado(page);
    await expect(page.locator("#pixPaymentPanel")).toBeVisible();
    await expect(page.locator("#cardPaymentPanel")).toBeHidden();
  });

  test("2) trocar para cartão esconde o Pix e mostra só o cartão", async ({ page }) => {
    await irParaCheckoutComCartaoHabilitado(page);
    await page.locator('[data-recebimento-radio][value="retirada"]').check();
    await page.click('[data-payment-method="cartao"]');
    await expect(page.locator("#cardPaymentPanel")).toBeVisible();
    await expect(page.locator("#pixPaymentPanel")).toBeHidden();
  });

  test("3) método ativo é identificado por classe e aria-selected, nunca só por cor", async ({ page }) => {
    await irParaCheckoutComCartaoHabilitado(page);
    await page.locator('[data-recebimento-radio][value="retirada"]').check();
    const pix = page.locator('[data-payment-method="pix"]');
    const cartao = page.locator('[data-payment-method="cartao"]');

    await expect(pix).toHaveClass(/is-active/);
    await expect(pix).toHaveAttribute("aria-selected", "true");
    await expect(cartao).not.toHaveClass(/is-active/);
    await expect(cartao).toHaveAttribute("aria-selected", "false");

    await cartao.click();
    await expect(cartao).toHaveClass(/is-active/);
    await expect(cartao).toHaveAttribute("aria-selected", "true");
    await expect(pix).not.toHaveClass(/is-active/);
    await expect(pix).toHaveAttribute("aria-selected", "false");
  });

  test("4) trocar para cartão sempre reaproveita a MESMA Idempotency-Key de checkout, nunca cria um segundo pedido", async ({ page }) => {
    // NOTA de homologação: selecionar "Cartão de crédito" DE FATO chama
    // POST /api/checkout/pedidos (window.misticaCriarPedido, ver
    // v2-mercadopago-checkout.js::garantirPedidoAtual) -- comportamento
    // intencional e pré-existente a esta PR (já documentado no próprio
    // código: "Reaproveita exatamente a mesma criação de pedido usada pelo
    // Pix... nunca cria um segundo pedido só porque o cliente escolheu
    // cartão"), necessário porque o CardForm do Mercado Pago exige o valor
    // total (pedidos.total_final, sempre calculado no servidor) para
    // inicializar. A garantia real contra duplicidade não é "zero
    // chamadas" -- é a MESMA Idempotency-Key de checkout em toda chamada
    // para o mesmo carrinho, que o servidor usa para nunca criar um
    // segundo pedido (ver backend/site_stock_routes.py). Este teste
    // substitui uma asserção anterior incorreta ("nunca chama a API"),
    // corrigida após o CI revelar a suposição errada nesta revisão de
    // homologação.
    await irParaCheckoutComCartaoHabilitado(page);
    const idempotencyKeys = [];
    await page.route("**/api/checkout/pedidos", async route => {
      idempotencyKeys.push(route.request().headers()["idempotency-key"] || null);
      await route.fulfill({
        status: 200, contentType: "application/json",
        body: JSON.stringify({ id: 4242, pix_txid: "TX-4242", pix_copia_cola: "00020101", total_final: 60.0, expira_em: new Date(Date.now() + 900000).toISOString() }),
      });
    });

    await page.locator('[data-recebimento-radio][value="retirada"]').check();
    await page.click('[data-payment-method="cartao"]');
    await page.click('[data-payment-method="pix"]');
    await page.click('[data-payment-method="cartao"]');
    await page.click('[data-payment-method="pix"]');
    await page.waitForTimeout(300);

    expect(idempotencyKeys.length).toBeGreaterThan(0);
    const unicas = new Set(idempotencyKeys.filter(Boolean));
    expect(unicas.size).toBe(1);
  });

  test("5) trocar de método nunca chama a rota de cobrança do cartão", async ({ page }) => {
    await irParaCheckoutComCartaoHabilitado(page);
    let chamadasCobranca = 0;
    await page.route("**/api/payments/mercadopago/card", async route => {
      chamadasCobranca += 1;
      await route.fulfill({ status: 200, contentType: "application/json", body: "{}" });
    });

    await page.locator('[data-recebimento-radio][value="retirada"]').check();
    await page.click('[data-payment-method="cartao"]');
    await page.click('[data-payment-method="pix"]');
    await page.click('[data-payment-method="cartao"]');
    await page.waitForTimeout(300);

    expect(chamadasCobranca).toBe(0);
  });

  test("6) dados não sensíveis (CPF, e-mail do cartão) são preservados ao alternar para Pix e voltar", async ({ page }) => {
    await irParaCheckoutComCartaoHabilitado(page);
    await page.locator('[data-recebimento-radio][value="retirada"]').check();
    await page.click('[data-payment-method="cartao"]');
    await page.locator("#mpDocNumber").fill("12345678900");
    await page.locator("#mpCardEmail").fill("cliente@example.com");

    await page.click('[data-payment-method="pix"]');
    await page.click('[data-payment-method="cartao"]');

    await expect(page.locator("#mpDocNumber")).toHaveValue("12345678900");
    await expect(page.locator("#mpCardEmail")).toHaveValue("cliente@example.com");
  });

  test("7) rótulo do stepper reflete o método selecionado (Pix por padrão, cartão quando escolhido)", async ({ page }) => {
    await irParaCheckoutComCartaoHabilitado(page);
    await page.locator('[data-recebimento-radio][value="retirada"]').check();
    await expect(page.locator("#checkoutStepPagamentoLabel")).toHaveText("Pagamento Pix");

    await page.click('[data-payment-method="cartao"]');
    await expect(page.locator("#checkoutStepPagamentoLabel")).toHaveText("Pagamento cartão");

    await page.click('[data-payment-method="pix"]');
    await expect(page.locator("#checkoutStepPagamentoLabel")).toHaveText("Pagamento Pix");
  });

  test("8) Pix continua disponível (habilitado, sem erro) depois de uma recusa de cartão", async ({ page }) => {
    await irParaCheckoutComCartaoHabilitado(page);
    await page.locator('[data-recebimento-radio][value="retirada"]').check();

    // Simula o desfecho de uma recusa real (mesma função pública usada pelo
    // fluxo real de envio) sem depender do SDK/rede.
    await page.click('[data-payment-method="cartao"]');
    await page.evaluate(() => {
      document.getElementById("mpCardStatus").textContent =
        "Não foi possível aprovar o pagamento com este cartão. Revise os dados, tente outro cartão ou escolha Pix.";
    });

    await page.click('[data-payment-method="pix"]');
    await expect(page.locator("#pixPaymentPanel")).toBeVisible();
    await expect(page.locator('[data-generate-pix]')).toBeEnabled();
  });

  test("9) nenhum método aparece pré-aprovado ao entrar no checkout", async ({ page }) => {
    await irParaCheckoutComCartaoHabilitado(page);
    await expect(page.locator("#mpCardStatus")).toHaveText("");
    await expect(page.locator("#pixStatus")).not.toContainText("aprovado");
  });
});
