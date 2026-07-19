const { test, expect } = require("@playwright/test");

/*
 * Regressão do bug: CardForm do Mercado Pago aparece, mas número/validade/
 * CVV não recebem clique nem digitação e o seletor de parcelas fica vazio.
 *
 * Causa raiz confirmada (docs oficiais do sdk-js, card-form.md): a opção
 * `iframe` do cardForm() tem default `false`. Com `iframe: false` (ou
 * omitido), o SDK espera <input> para cardNumber/securityCode/
 * expirationDate -- os <div id="mpCardNumber/mpExpirationDate/
 * mpSecurityCode"> do checkout real nunca recebiam os iframes de Secure
 * Fields do Mercado Pago, por isso ficavam visíveis (são nossos <div>) mas
 * sem nenhum campo funcional dentro. Corrigido em v2-mercadopago-
 * checkout.js adicionando `iframe: true` na config do cardForm().
 *
 * Este ambiente de CI/sandbox não tem acesso de rede a sdk.mercadopago.com
 * (ver tests/e2e/csp-mercadopago-cardform.spec.js), então não é possível
 * carregar o SDK real e confirmar a montagem com um cartão de verdade aqui.
 * Este arquivo usa a fixture tests/e2e/fixtures/mercadopago-cardform-
 * fixture.html, que define um window.MercadoPago mock ANTES do script real
 * carregar -- como carregarSdk() só busca o SDK via rede quando
 * `!window.MercadoPago`, o mock faz v2-mercadopago-checkout.js seguir
 * exatamente o mesmo caminho de produção (mpInstance.cardForm(config),
 * autoMount, callbacks, guarda de remontagem) sem tocar a rede. Isso prova a
 * MECÂNICA da correção (config correta, 1 iframe por campo, sem
 * duplicação, sem overlay) com um Chromium real. NÃO substitui a validação
 * final com o SDK e um cartão de teste reais em sandbox -- ver instruções de
 * homologação na descrição da PR.
 */

test.describe("Montagem do CardForm (mock do SDK, ver limitação de rede acima)", () => {
  test.beforeEach(async ({ page }) => {
    await page.route("**/api/payments/mercadopago/config", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ enabled: true, public_key: "TEST-PUBLIC-KEY" }),
      }),
    );
  });

  test("cardForm() é chamado com iframe: true", async ({ page }) => {
    await page.goto("/tests/e2e/fixtures/mercadopago-cardform-fixture.html");
    await page.locator('[data-payment-method="cartao"]').waitFor({ state: "visible" });
    await page.click('[data-payment-method="cartao"]');

    await expect.poll(() => page.evaluate(() => window.__mpConfigsCapturados.length)).toBeGreaterThan(0);
    const config = await page.evaluate(() => window.__mpConfigsCapturados[0]);
    expect(config.iframe).toBe(true);
    expect(config.autoMount).toBe(true);
  });

  test("cardNumber/expirationDate/securityCode recebem style com cor de texto clara e placeholder distinto", async ({ page }) => {
    await page.goto("/tests/e2e/fixtures/mercadopago-cardform-fixture.html");
    await page.locator('[data-payment-method="cartao"]').waitFor({ state: "visible" });
    await page.click('[data-payment-method="cartao"]');

    await expect.poll(() => page.evaluate(() => window.__mpConfigsCapturados.length)).toBeGreaterThan(0);
    const config = await page.evaluate(() => window.__mpConfigsCapturados[0]);

    for (const campo of ["cardNumber", "expirationDate", "securityCode"]) {
      const style = config.form[campo].style;
      expect(style, `form.${campo}.style`).toBeTruthy();
      expect(style.color).toBe("#F7E7BE");
      expect(style.placeholderColor).toBe("rgba(247, 231, 190, 0.55)");
      expect(style.fontSize).toBe("16px");
      expect(style.fontWeight).toBe("500");
      expect(style).not.toHaveProperty("backgroundColor");
      expect(style.color).not.toBe(style.placeholderColor);
    }
  });

  test("new MercadoPago() é chamado com trackingDisabled: true e sem desativar advancedFraudPrevention", async ({ page }) => {
    await page.goto("/tests/e2e/fixtures/mercadopago-cardform-fixture.html");
    await page.locator('[data-payment-method="cartao"]').waitFor({ state: "visible" });
    await page.click('[data-payment-method="cartao"]');

    await expect.poll(() => page.evaluate(() => window.__mpConstructorOptionsCapturadas.length)).toBeGreaterThan(0);
    const options = await page.evaluate(() => window.__mpConstructorOptionsCapturadas[0]);
    expect(options.trackingDisabled).toBe(true);
    expect(options).not.toHaveProperty("advancedFraudPrevention");
  });

  test("identificationType usa <select>, não <input>", async ({ page }) => {
    await page.goto("/tests/e2e/fixtures/mercadopago-cardform-fixture.html");
    const tag = await page.evaluate(() => document.getElementById("mpIdentificationType").tagName);
    expect(tag).toBe("SELECT");
  });

  test("exatamente 1 iframe em cada campo seguro, com dimensões e sem camada por cima", async ({ page }) => {
    const pageErrors = [];
    page.on("pageerror", (err) => pageErrors.push(String(err)));

    await page.goto("/tests/e2e/fixtures/mercadopago-cardform-fixture.html");
    await page.locator('[data-payment-method="cartao"]').waitFor({ state: "visible" });
    await page.click('[data-payment-method="cartao"]');

    for (const id of ["mpCardNumber", "mpExpirationDate", "mpSecurityCode"]) {
      const locator = page.locator(`#${id} iframe`);
      await expect(locator).toHaveCount(1, { timeout: 5000 });

      const box = await locator.boundingBox();
      expect(box, `iframe #${id} deveria ter bounding box`).not.toBeNull();
      expect(box.width).toBeGreaterThan(0);
      expect(box.height).toBeGreaterThan(0);

      const pointerEvents = await locator.evaluate((el) => getComputedStyle(el).pointerEvents);
      expect(pointerEvents).not.toBe("none");

      const centro = await page.evaluate(
        ({ id }) => {
          const el = document.getElementById(id).querySelector("iframe");
          const rect = el.getBoundingClientRect();
          const topo = document.elementFromPoint(rect.x + rect.width / 2, rect.y + rect.height / 2);
          return topo === el;
        },
        { id },
      );
      expect(centro, `nenhuma camada deveria cobrir o centro do campo #${id}`).toBe(true);
    }

    const parcelas = await page.locator("#mpInstallments option").count();
    expect(parcelas).toBeGreaterThan(0);

    expect(pageErrors).toEqual([]);
  });

  test("alternar Pix -> cartão -> Pix -> cartão várias vezes não monta o CardForm nem os iframes mais de uma vez", async ({ page }) => {
    await page.goto("/tests/e2e/fixtures/mercadopago-cardform-fixture.html");
    await page.locator('[data-payment-method="cartao"]').waitFor({ state: "visible" });

    for (let i = 0; i < 3; i++) {
      await page.click('[data-payment-method="cartao"]');
      await expect(page.locator("#mpCardNumber iframe")).toHaveCount(1, { timeout: 5000 });
      await page.click('[data-payment-method="pix"]');
    }
    await page.click('[data-payment-method="cartao"]');
    await expect(page.locator("#mpCardNumber iframe")).toHaveCount(1, { timeout: 5000 });

    const mountCount = await page.evaluate(() => window.__mpMountCount);
    expect(mountCount).toBe(1);
    for (const id of ["mpCardNumber", "mpExpirationDate", "mpSecurityCode"]) {
      await expect(page.locator(`#${id} iframe`)).toHaveCount(1);
    }
  });

  test("sem violação de CSP nem erro de página durante a montagem", async ({ page }) => {
    const cspViolations = [];
    const pageErrors = [];
    page.on("console", (msg) => {
      if (msg.type() === "error" && /Content Security Policy/i.test(msg.text())) cspViolations.push(msg.text());
    });
    page.on("pageerror", (err) => pageErrors.push(String(err)));

    await page.goto("/tests/e2e/fixtures/mercadopago-cardform-fixture.html");
    await page.locator('[data-payment-method="cartao"]').waitFor({ state: "visible" });
    await page.click('[data-payment-method="cartao"]');
    await expect(page.locator("#mpCardNumber iframe")).toHaveCount(1, { timeout: 5000 });

    expect(cspViolations).toEqual([]);
    expect(pageErrors).toEqual([]);
  });

  test("quando os Secure Fields não montam, o formulário fica indisponível com mensagem clara (?modo=falha)", async ({ page }) => {
    await page.goto("/tests/e2e/fixtures/mercadopago-cardform-fixture.html?modo=falha");
    await page.locator('[data-payment-method="cartao"]').waitFor({ state: "visible" });
    await page.click('[data-payment-method="cartao"]');

    await expect(page.locator("#mpCardStatus")).toHaveText(
      "Não foi possível carregar os campos seguros do cartão. Use o Pix ou tente novamente.",
      { timeout: 5000 },
    );
    await expect(page.locator("#mpCardSubmit")).toBeDisabled();
    for (const id of ["mpCardNumber", "mpExpirationDate", "mpSecurityCode"]) {
      await expect(page.locator(`#${id} iframe`)).toHaveCount(0);
    }
  });
});
