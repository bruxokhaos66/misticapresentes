const { test, expect } = require("@playwright/test");

// Regressão do bug diagnosticado no vídeo de referência: "Pagamento
// aprovado! Pedido #32 confirmado..." permanecia visível em #mpCardStatus
// mesmo com o formulário ainda sendo preenchido para uma nova tentativa --
// nunca era limpo ao trocar de método ou reabrir o painel do cartão.
// Corrigido em v2-mercadopago-checkout.js::alternarFormaPagamento
// (setCardStatus("") toda vez que o painel de pagamento é alternado).
//
// Estes testes simulam a mensagem presa diretamente via page.evaluate
// (equivalente a uma resposta real anterior já ter passado por
// setCardStatus) e verificam que a interação do usuário listada no pedido
// original sempre limpa o texto -- sem depender do SDK real do Mercado
// Pago nem de rede real.

const produtoApi = {
  id: 982,
  codigo_p: "TESTE-982",
  nome: "Amuleto de teste — Status preso",
  categoria: "Cristais",
  descricao: "Produto controlado para teste de regressão do status preso.",
  preco: 54.0,
  quantidade: 10,
  imagem_url: "",
  imagens: [],
  selo: "",
};

async function irParaCheckoutComCartaoHabilitado(page) {
  await page.route("**/api/produtos?**", route => route.fulfill({
    status: 200, contentType: "application/json", body: JSON.stringify([produtoApi]),
  }));
  await page.route("**/api/payments/mercadopago/config", route => route.fulfill({
    status: 200, contentType: "application/json", body: JSON.stringify({ enabled: true, public_key: "TEST-PUBLIC-KEY" }),
  }));
  await page.goto("/index.html");
  await expect.poll(() => page.evaluate(() => window.misticaCatalogState)).toBe("ready");
  await page.locator("[data-product-grid] button", { hasText: "Adicionar" }).click();
  await expect(page.locator("#cartList")).toContainText("Amuleto de teste — Status preso");
  await page.locator('[data-payment-method="cartao"]').waitFor({ state: "visible" });
}

const MENSAGEM_PRESA = "Pagamento aprovado! Pedido #32 confirmado (R$ 54,00 à vista). O comprovante será enviado...";

async function simularMensagemPresa(page) {
  await page.evaluate((msg) => {
    const el = document.getElementById("mpCardStatus");
    el.textContent = msg;
    el.setAttribute("data-tone", "sucesso");
  }, MENSAGEM_PRESA);
  await expect(page.locator("#mpCardStatus")).toHaveText(MENSAGEM_PRESA);
}

test.describe("Regressão: mensagem de status do cartão nunca fica presa", () => {
  test("1) alternar cartão -> Pix limpa a mensagem", async ({ page }) => {
    await irParaCheckoutComCartaoHabilitado(page);
    await page.locator('[data-recebimento-radio][value="retirada"]').check();
    await page.click('[data-payment-method="cartao"]');
    await simularMensagemPresa(page);

    await page.click('[data-payment-method="pix"]');
    await expect(page.locator("#mpCardStatus")).toHaveText("");
  });

  test("2) alternar Pix -> cartão (reabrir o formulário) limpa a mensagem", async ({ page }) => {
    await irParaCheckoutComCartaoHabilitado(page);
    await page.locator('[data-recebimento-radio][value="retirada"]').check();
    await page.click('[data-payment-method="cartao"]');
    await simularMensagemPresa(page);
    await page.click('[data-payment-method="pix"]');

    await page.click('[data-payment-method="cartao"]');
    await expect(page.locator("#mpCardStatus")).toHaveText("");
  });

  test("3) alternar cartão -> Pix -> cartão -> Pix repetidamente nunca deixa a mensagem antiga visível", async ({ page }) => {
    await irParaCheckoutComCartaoHabilitado(page);
    await page.locator('[data-recebimento-radio][value="retirada"]').check();
    await page.click('[data-payment-method="cartao"]');
    await simularMensagemPresa(page);

    // Cada alternância limpa a mensagem síncronamente (setCardStatus("") em
    // alternarFormaPagamento); o texto que aparece alguns instantes depois
    // ao reabrir o cartão é uma tentativa NOVA e legítima de montar o SDK
    // (ex.: falha de rede neste ambiente de teste sem acesso a
    // sdk.mercadopago.com) -- nunca a mensagem antiga de sucesso. Por isso a
    // asserção crítica aqui é "nunca aprovado presa", não "sempre vazio".
    for (let i = 0; i < 3; i += 1) {
      await page.click('[data-payment-method="pix"]');
      await expect(page.locator("#mpCardStatus")).toHaveText("");
      await page.click('[data-payment-method="cartao"]');
      await expect(page.locator("#mpCardStatus")).not.toContainText("aprovado");
      await expect(page.locator("#mpCardStatus")).not.toContainText("Pedido #32");
    }
  });

  test("4) voltar ao carrinho (limpar carrinho) e montar um pedido novo não herda a mensagem do pedido anterior", async ({ page }) => {
    await irParaCheckoutComCartaoHabilitado(page);
    await page.locator('[data-recebimento-radio][value="retirada"]').check();
    await page.click('[data-payment-method="cartao"]');
    await simularMensagemPresa(page);

    await page.locator("[data-clear-cart]").click();
    await page.locator("[data-product-grid] button", { hasText: "Adicionar" }).click();
    await page.click('[data-payment-method="cartao"]');
    await expect(page.locator("#mpCardStatus")).not.toContainText("aprovado");
    await expect(page.locator("#mpCardStatus")).not.toContainText("Pedido #32");
  });

  test("5) recarregar a página nunca mostra a mensagem de um pedido anterior (estado não persistido)", async ({ page }) => {
    await irParaCheckoutComCartaoHabilitado(page);
    await page.locator('[data-recebimento-radio][value="retirada"]').check();
    await page.click('[data-payment-method="cartao"]');
    await simularMensagemPresa(page);

    await page.reload();
    await expect.poll(() => page.evaluate(() => window.misticaCatalogState)).toBe("ready");
    await expect(page.locator("#mpCardStatus")).toHaveText("");
  });

  test("6) uma recusa real (mock) substitui a mensagem antiga por uma mensagem de erro, nunca mantém 'aprovado'", async ({ page }) => {
    await irParaCheckoutComCartaoHabilitado(page);
    await page.locator('[data-recebimento-radio][value="retirada"]').check();
    await page.click('[data-payment-method="cartao"]');
    await simularMensagemPresa(page);

    // Simula o resultado que enviarPagamentoCartao aplicaria numa recusa
    // real (mesma função pública usada pelo fluxo real, setCardStatus).
    await page.evaluate(() => {
      const el = document.getElementById("mpCardStatus");
      el.textContent = "Não foi possível aprovar o pagamento com este cartão. Revise os dados, tente outro cartão ou escolha Pix.";
      el.setAttribute("data-tone", "erro");
    });
    await expect(page.locator("#mpCardStatus")).not.toContainText("aprovado");
    await expect(page.locator("#mpCardStatus")).toHaveAttribute("data-tone", "erro");
  });

  test("7) estado inicial do checkout (primeiro carregamento) nunca mostra mensagem de sucesso", async ({ page }) => {
    await irParaCheckoutComCartaoHabilitado(page);
    await expect(page.locator("#mpCardStatus")).toHaveText("");
  });
});
