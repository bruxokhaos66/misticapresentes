const { test, expect } = require("@playwright/test");

/*
 * Nome/sobrenome do COMPRADOR (payer.first_name/last_name) -- campos
 * próprios do checkout (#mpBuyerFirstName/#mpBuyerLastName), distintos de
 * "Nome impresso no cartão" (cardholderName, titular do cartão -- pode ser
 * outra pessoa). Usa a mesma fixture de mock do SDK das demais suítes de
 * CardForm (tests/e2e/fixtures/mercadopago-cardform-fixture.html) -- nunca
 * chama o Mercado Pago real.
 */

test.describe("Nome/sobrenome do comprador no pagamento com cartão", () => {
  test.beforeEach(async ({ page }) => {
    await page.route("**/api/payments/mercadopago/config", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ enabled: true, public_key: "TEST-PUBLIC-KEY" }),
      }),
    );
  });

  async function abrirCardFormPronto(page) {
    await page.goto("/tests/e2e/fixtures/mercadopago-cardform-fixture.html");
    await page.locator('[data-payment-method="cartao"]').waitFor({ state: "visible" });
    await page.click('[data-payment-method="cartao"]');
    await expect(page.locator("#mpCardSubmit")).toBeEnabled();
  }

  async function dispararSubmit(page) {
    await page.evaluate(() => {
      const config = window.__mpConfigsCapturados[window.__mpConfigsCapturados.length - 1];
      config.callbacks.onSubmit({ preventDefault() {} });
    });
  }

  test("nome e sobrenome preenchidos vão no payer do POST ao backend", async ({ page }) => {
    await abrirCardFormPronto(page);

    let corpoRecebido = null;
    await page.route("**/api/payments/mercadopago/card", async (route) => {
      corpoRecebido = route.request().postDataJSON();
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ ok: true, status: "aprovado", aprovado: true, mensagem: "Pagamento aprovado.", pedido_id: 999, tentativa_id: 1, parcelas: 1, valor: 150.5 }),
      });
    });

    await dispararSubmit(page);
    await expect.poll(() => corpoRecebido !== null).toBe(true);
    expect(corpoRecebido.payer.nome).toBe("Maria");
    expect(corpoRecebido.payer.sobrenome).toBe("Souza");
  });

  test("nome vazio bloqueia o envio antes de qualquer chamada ao backend", async ({ page }) => {
    await abrirCardFormPronto(page);
    await page.fill("#mpBuyerFirstName", "");

    let chamadas = 0;
    await page.route("**/api/payments/mercadopago/card", async (route) => {
      chamadas += 1;
      await route.fulfill({ status: 200, contentType: "application/json", body: "{}" });
    });

    await dispararSubmit(page);
    await expect(page.locator("#mpCardStatus")).toContainText("nome");
    expect(chamadas).toBe(0);
  });

  test("sobrenome vazio é aceito (nome de uma palavra) e nunca é enviado como campo vazio", async ({ page }) => {
    await abrirCardFormPronto(page);
    await page.fill("#mpBuyerLastName", "");

    let corpoRecebido = null;
    await page.route("**/api/payments/mercadopago/card", async (route) => {
      corpoRecebido = route.request().postDataJSON();
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ ok: true, status: "aprovado", aprovado: true, mensagem: "Pagamento aprovado.", pedido_id: 999, tentativa_id: 1, parcelas: 1, valor: 150.5 }),
      });
    });

    await dispararSubmit(page);
    await expect.poll(() => corpoRecebido !== null).toBe(true);
    expect(corpoRecebido.payer.nome).toBe("Maria");
    expect(corpoRecebido.payer.sobrenome).toBeUndefined();
  });

  test("nome com números bloqueia o envio antes de qualquer chamada ao backend", async ({ page }) => {
    await abrirCardFormPronto(page);
    await page.fill("#mpBuyerFirstName", "Ana123");

    let chamadas = 0;
    await page.route("**/api/payments/mercadopago/card", async (route) => {
      chamadas += 1;
      await route.fulfill({ status: 200, contentType: "application/json", body: "{}" });
    });

    await dispararSubmit(page);
    await expect(page.locator("#mpCardStatus")).toContainText("nome");
    expect(chamadas).toBe(0);
  });
});
