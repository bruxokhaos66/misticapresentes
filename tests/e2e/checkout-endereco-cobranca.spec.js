const { test, expect } = require("@playwright/test");

// Endereço de cobrança do cartão (reformulação do checkout, ver
// checkout-billing-address.js). Só verifica a UI (visibilidade dos
// campos/checkbox, gate do botão de pagar) -- nunca chama o SDK real do
// Mercado Pago nem a API real (mockados via page.route), consistente com o
// restante da suíte deste projeto.

const produtoApi = {
  id: 981,
  codigo_p: "TESTE-981",
  nome: "Amuleto de teste — Cobrança",
  categoria: "Cristais",
  descricao: "Produto controlado para teste de endereço de cobrança.",
  preco: 45.0,
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
  await expect(page.locator("#cartList")).toContainText("Amuleto de teste — Cobrança");
  await page.locator('[data-payment-method="cartao"]').waitFor({ state: "visible" });
}

const enderecoValido = { cep: "89801000", rua: "Rua Teste", numero: "100", bairro: "Centro", cidade: "Chapecó", uf: "SC" };

async function preencherEnderecoEntrega(page) {
  await page.locator("#enderecoCep").fill(enderecoValido.cep);
  await page.locator("#enderecoRua").fill(enderecoValido.rua);
  await page.locator("#enderecoNumero").fill(enderecoValido.numero);
  await page.locator("#enderecoBairro").fill(enderecoValido.bairro);
  await page.locator("#enderecoCidade").fill(enderecoValido.cidade);
  await page.locator("#enderecoUf").fill(enderecoValido.uf);
}

test.describe("Endereço de cobrança do cartão", () => {
  test("1) escondido enquanto Pix está selecionado", async ({ page }) => {
    await irParaCheckoutComCartaoHabilitado(page);
    await expect(page.locator("#billingAddressBlock")).toBeHidden();
  });

  test("2) retirada + cartão: exige endereço de cobrança explícito, sem checkbox de reaproveitar", async ({ page }) => {
    await irParaCheckoutComCartaoHabilitado(page);
    await page.locator('[data-recebimento-radio][value="retirada"]').check();
    await page.click('[data-payment-method="cartao"]');

    await expect(page.locator("#billingAddressBlock")).toBeVisible();
    await expect(page.locator("#billingReuseRow")).toBeHidden();
    await expect(page.locator("#billingAddressFields")).toBeVisible();
    expect(await page.evaluate(() => window.misticaEnderecoCobranca.enderecoCobrancaValido())).toBe(false);
  });

  test("3) retirada + cartão: preencher o endereço de cobrança libera o pagamento", async ({ page }) => {
    await irParaCheckoutComCartaoHabilitado(page);
    await page.locator('[data-recebimento-radio][value="retirada"]').check();
    await page.click('[data-payment-method="cartao"]');

    await page.locator("#billingCep").fill(enderecoValido.cep);
    await page.locator("#billingRua").fill(enderecoValido.rua);
    await page.locator("#billingNumero").fill(enderecoValido.numero);
    await page.locator("#billingBairro").fill(enderecoValido.bairro);
    await page.locator("#billingCidade").fill(enderecoValido.cidade);
    await page.locator("#billingUf").fill(enderecoValido.uf);

    expect(await page.evaluate(() => window.misticaEnderecoCobranca.enderecoCobrancaValido())).toBe(true);
    const dados = await page.evaluate(() => window.misticaEnderecoCobranca.obterEnderecoCobranca());
    expect(dados.usar_mesmo_da_entrega).toBe(false);
    expect(dados.cep).toBe(enderecoValido.cep);
  });

  test("4) entrega + cartão: checkbox 'usar o mesmo endereço' começa marcado e já libera o pagamento", async ({ page }) => {
    await irParaCheckoutComCartaoHabilitado(page);
    await page.locator('[data-recebimento-radio][value="entrega"]').check();
    await preencherEnderecoEntrega(page);
    await page.click('[data-payment-method="cartao"]');

    await expect(page.locator("#billingReuseRow")).toBeVisible();
    await expect(page.locator("#billingReuseEntrega")).toBeChecked();
    await expect(page.locator("#billingAddressFields")).toBeHidden();
    expect(await page.evaluate(() => window.misticaEnderecoCobranca.enderecoCobrancaValido())).toBe(true);
    const dados = await page.evaluate(() => window.misticaEnderecoCobranca.obterEnderecoCobranca());
    expect(dados.usar_mesmo_da_entrega).toBe(true);
  });

  test("5) entrega + cartão: desmarcar 'usar o mesmo endereço' revela os campos de cobrança, inicialmente vazios", async ({ page }) => {
    await irParaCheckoutComCartaoHabilitado(page);
    await page.locator('[data-recebimento-radio][value="entrega"]').check();
    await preencherEnderecoEntrega(page);
    await page.click('[data-payment-method="cartao"]');

    await page.locator("#billingReuseEntrega").uncheck();
    await expect(page.locator("#billingAddressFields")).toBeVisible();
    await expect(page.locator("#billingCep")).toHaveValue("");
    expect(await page.evaluate(() => window.misticaEnderecoCobranca.enderecoCobrancaValido())).toBe(false);
  });

  test("6) alternar de cartão para Pix e voltar preserva os dados de cobrança já preenchidos", async ({ page }) => {
    await irParaCheckoutComCartaoHabilitado(page);
    await page.locator('[data-recebimento-radio][value="retirada"]').check();
    await page.click('[data-payment-method="cartao"]');
    await page.locator("#billingCep").fill(enderecoValido.cep);
    await page.locator("#billingRua").fill(enderecoValido.rua);

    await page.click('[data-payment-method="pix"]');
    await page.click('[data-payment-method="cartao"]');

    await expect(page.locator("#billingCep")).toHaveValue(enderecoValido.cep);
    await expect(page.locator("#billingRua")).toHaveValue(enderecoValido.rua);
  });

  test("7) botão de pagar com cartão fica desabilitado sem endereço de cobrança válido", async ({ page }) => {
    await irParaCheckoutComCartaoHabilitado(page);
    await page.locator('[data-recebimento-radio][value="retirada"]').check();
    await page.click('[data-payment-method="cartao"]');
    await expect(page.locator("#mpCardSubmit")).toBeDisabled();
  });
});
