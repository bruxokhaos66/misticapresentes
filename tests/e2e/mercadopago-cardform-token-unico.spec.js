const { test, expect } = require("@playwright/test");

/*
 * Regressão do bug de produção "Invalid card_token_id" (código 3003 do
 * Mercado Pago, pedido_id 39 / tentativa_id 19 no log que motivou esta
 * correção).
 *
 * Causa raiz: o CardToken gerado pelo SDK do Mercado Pago é descartável --
 * só pode ser enviado em UMA tentativa de pagamento (ver docs/card-form.md
 * do mercadopago/sdk-js: createCardToken() é o método oficial para gerar um
 * token novo). v2-mercadopago-checkout.js agora chama createCardToken()
 * explicitamente a cada tentativa (nunca reaproveita getCardFormData().token
 * isolado) e descarta a referência local ao token assim que a requisição ao
 * backend é iniciada -- nunca reenviado, mesmo em caso de recusa/erro.
 *
 * Usa a mesma fixture de mock do SDK das suítes de montagem do CardForm
 * (tests/e2e/fixtures/mercadopago-cardform-fixture.html) -- este ambiente
 * de CI/sandbox não tem acesso de rede a sdk.mercadopago.com. A fixture
 * expõe window.__mpTokensParaEntregar (fila controlada pelo teste) e
 * window.__mpTokensCriados (todo token fictício gerado) para as asserções
 * abaixo -- nunca um token real do Mercado Pago.
 */

test.describe("CardToken de uso único (correção 'Invalid card_token_id')", () => {
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

  // A fixture mocka mpInstance.cardForm(config), não o comportamento nativo
  // do <form> (a montagem/validação HTML5 dos campos exigidos pelo
  // navegador é irrelevante para o que este arquivo testa: o ciclo do
  // CardToken). Assim como o SDK real faz ao interceptar o evento "submit"
  // do <form id="mpCardForm">, disparamos aqui diretamente o callback
  // config.callbacks.onSubmit -- o mesmo caminho de código que um clique
  // real (ou Enter) no botão tipo "submit" aciona em produção.
  async function dispararSubmit(page) {
    await page.evaluate(() => {
      const config = window.__mpConfigsCapturados[window.__mpConfigsCapturados.length - 1];
      config.callbacks.onSubmit({ preventDefault() {} });
    });
  }

  test("tentativa 1 usa TOKEN_TESTE_A (1 requisição); recusa 422 nunca reenvia o token A; tentativa 2 usa TOKEN_TESTE_B", async ({ page }) => {
    await page.addInitScript(() => {
      window.__mpTokensParaEntregar = ["TOKEN_TESTE_A", "TOKEN_TESTE_B"];
    });
    await abrirCardFormPronto(page);

    const tokensRecebidosPeloBackend = [];
    let chamadas = 0;
    let proximaResposta = {
      status: 422,
      body: {
        ok: false,
        status: "recusado",
        codigo: "cartao_token_invalido",
        mensagem: "Não foi possível validar os dados do cartão. Revise-os e tente novamente.",
        pedido_id: 999,
        tentativa_id: 1,
        parcelas: 1,
        valor: 150.5,
      },
    };
    await page.route("**/api/payments/mercadopago/card", async (route) => {
      chamadas += 1;
      const corpo = route.request().postDataJSON();
      tokensRecebidosPeloBackend.push(corpo.token);
      await route.fulfill({
        status: proximaResposta.status,
        contentType: "application/json",
        body: JSON.stringify(proximaResposta.body),
      });
    });

    // Tentativa 1: recusada pelo backend como token inválido (422).
    await dispararSubmit(page);
    await expect.poll(() => chamadas).toBe(1);
    expect(tokensRecebidosPeloBackend[0]).toBe("TOKEN_TESTE_A");

    const status1 = await page.locator("#mpCardStatus").textContent();
    expect(status1).toContain("Revise");
    // Nunca exibe o texto bruto/código técnico do Mercado Pago ao cliente.
    expect(status1.toLowerCase()).not.toContain("card_token_id");
    expect(status1).not.toContain("3003");
    expect(status1).not.toContain("Invalid card_token_id");

    // O botão volta a ficar utilizável para uma nova tentativa.
    await expect(page.locator("#mpCardSubmit")).toBeEnabled();

    // Tentativa 2: aprovada, com um token DIFERENTE do primeiro.
    proximaResposta = {
      status: 200,
      body: {
        ok: true,
        status: "aprovado",
        aprovado: true,
        mensagem: "Pagamento aprovado.",
        pedido_id: 999,
        tentativa_id: 2,
        parcelas: 1,
        valor: 150.5,
      },
    };
    await dispararSubmit(page);
    await expect.poll(() => chamadas).toBe(2);
    expect(tokensRecebidosPeloBackend[1]).toBe("TOKEN_TESTE_B");
    expect(tokensRecebidosPeloBackend[1]).not.toBe(tokensRecebidosPeloBackend[0]);

    // O SDK nunca foi solicitado a gerar o mesmo token duas vezes.
    const tokensCriados = await page.evaluate(() => window.__mpTokensCriados);
    expect(tokensCriados).toEqual(["TOKEN_TESTE_A", "TOKEN_TESTE_B"]);
  });

  test("timeout/falha de rede na tentativa 1 também consome o token -- tentativa 2 gera um token novo", async ({ page }) => {
    await page.addInitScript(() => {
      window.__mpTokensParaEntregar = ["TOKEN_TESTE_A", "TOKEN_TESTE_B"];
    });
    await abrirCardFormPronto(page);

    let chamadas = 0;
    await page.route("**/api/payments/mercadopago/card", async (route) => {
      chamadas += 1;
      if (chamadas === 1) {
        await route.abort("failed"); // simula falha de rede/timeout
        return;
      }
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ ok: true, status: "aprovado", aprovado: true, mensagem: "Pagamento aprovado.", pedido_id: 999, tentativa_id: 2, parcelas: 1, valor: 150.5 }),
      });
    });

    await dispararSubmit(page);
    await expect.poll(() => chamadas).toBe(1);
    await expect(page.locator("#mpCardStatus")).toContainText("conexão");
    await expect(page.locator("#mpCardSubmit")).toBeEnabled();

    await dispararSubmit(page);
    await expect.poll(() => chamadas).toBe(2);

    const tokensCriados = await page.evaluate(() => window.__mpTokensCriados);
    expect(tokensCriados).toEqual(["TOKEN_TESTE_A", "TOKEN_TESTE_B"]);
  });

  test("duplo clique/Enter repetido no submit gera um único token e um único POST", async ({ page }) => {
    await abrirCardFormPronto(page);

    let chamadas = 0;
    await page.route("**/api/payments/mercadopago/card", async (route) => {
      chamadas += 1;
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ ok: true, status: "aprovado", aprovado: true, mensagem: "Pagamento aprovado.", pedido_id: 999, tentativa_id: 1, parcelas: 1, valor: 150.5 }),
      });
    });

    // Simula dois eventos de submit chegando em sequência imediata (duplo
    // clique/Enter repetido) -- exatamente o caminho que
    // v2-mercadopago-checkout.js::enviarPagamentoCartao trava
    // sincronamente antes de qualquer await.
    await page.evaluate(() => {
      const config = window.__mpConfigsCapturados[window.__mpConfigsCapturados.length - 1];
      config.callbacks.onSubmit({ preventDefault() {} });
      config.callbacks.onSubmit({ preventDefault() {} });
    });

    await expect.poll(() => chamadas).toBe(1);
    await page.waitForTimeout(200); // garante que uma segunda chamada tardia não apareça
    expect(chamadas).toBe(1);

    const tokensCriados = await page.evaluate(() => window.__mpTokensCriados);
    expect(tokensCriados.length).toBe(1);
  });
});
