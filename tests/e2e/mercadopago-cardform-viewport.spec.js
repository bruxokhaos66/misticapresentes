const { test, expect } = require("@playwright/test");

/*
 * Regressão do bug: os Secure Fields do Mercado Pago (#mpCardNumber/
 * #mpExpirationDate/#mpSecurityCode) apareciam no lugar certo visualmente,
 * mas o iframe interno do SDK ficava com getBoundingClientRect() fora do
 * viewport (ex.: top negativo) porque o SDK calcula a posição/tamanho do
 * iframe UMA VEZ, no instante em que cardForm() é chamado, e nunca reobserva
 * o layout depois. Se essa chamada acontecer com o painel do cartão ainda
 * oculto (hidden / display:none / rect zerado), o iframe nasce "congelado"
 * numa geometria inválida -- daí document.elementFromPoint() no centro do
 * campo retornar null e o clique/digitação nunca alcançar o iframe.
 *
 * Corrigido em v2-mercadopago-checkout.js (aguardarPainelCartaoVisivel):
 * mpInstance.cardForm(...) só é chamado depois de dois requestAnimationFrame
 * confirmando que #cardPaymentPanel está com display/visibility normais e
 * getBoundingClientRect().width/height > 0.
 *
 * A fixture tests/e2e/fixtures/mercadopago-cardform-fixture.html replica o
 * comportamento "congela geometria na chamada" do SDK real com um mock de
 * window.MercadoPago (não há acesso de rede a sdk.mercadopago.com neste
 * ambiente de CI/sandbox -- ver csp-mercadopago-cardform.spec.js), então
 * estes testes validam a MECÂNICA da correção com um Chromium/WebKit real:
 * se v2-mercadopago-checkout.js voltar a chamar cardForm() com o painel
 * oculto, o iframe nasce 0x0 e as asserções de bounding box/elementFromPoint
 * abaixo falham. Não substitui a validação final com o SDK e um cartão de
 * teste reais em sandbox.
 */

const CAMPOS_SEGUROS = ["mpCardNumber", "mpExpirationDate", "mpSecurityCode"];

async function irParaFixture(page, query) {
  await page.route("**/api/payments/mercadopago/config", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ enabled: true, public_key: "TEST-PUBLIC-KEY" }),
    }),
  );
  await page.goto(`/tests/e2e/fixtures/mercadopago-cardform-fixture.html${query || ""}`);
}

async function selecionarCartao(page) {
  // 1. Pix é a forma inicial (já selecionada por padrão na fixture/checkout real).
  await expect(page.locator('[data-payment-method="pix"]')).toHaveClass(/is-active/);

  // 2. Alternar para cartão.
  await page.locator('[data-payment-method="cartao"]').waitFor({ state: "visible" });
  await page.click('[data-payment-method="cartao"]');

  // 3. Aguardar a montagem (exatamente 1 iframe por campo).
  for (const id of CAMPOS_SEGUROS) {
    await expect(page.locator(`#${id} iframe`)).toHaveCount(1, { timeout: 5000 });
  }
}

async function coletarRetanguloEChecagens(page, id) {
  return page.evaluate((id) => {
    const iframe = document.querySelector(`#${id} iframe`);
    if (!iframe) return null;
    const rect = iframe.getBoundingClientRect();
    const centroX = rect.left + rect.width / 2;
    const centroY = rect.top + rect.height / 2;
    const elementoNoCentro = document.elementFromPoint(centroX, centroY);
    return {
      rect: { top: rect.top, left: rect.left, bottom: rect.bottom, right: rect.right, width: rect.width, height: rect.height },
      elementoNoCentroEhOIframe: elementoNoCentro === iframe,
    };
  }, id);
}

test.describe("Iframes dos Secure Fields ficam dentro do viewport e clicáveis", () => {
  test("após alternar Pix -> cartão, cada iframe está dentro do viewport e recebe clique no centro", async ({ page }) => {
    await irParaFixture(page);
    await selecionarCartao(page);

    const viewport = page.viewportSize();

    for (const id of CAMPOS_SEGUROS) {
      const { rect, elementoNoCentroEhOIframe } = await coletarRetanguloEChecagens(page, id);

      // 5. Retângulo dentro do viewport.
      expect(rect.top, `#${id}: top`).toBeGreaterThanOrEqual(0);
      expect(rect.left, `#${id}: left`).toBeGreaterThanOrEqual(0);
      expect(rect.bottom, `#${id}: bottom`).toBeLessThanOrEqual(viewport.height);
      expect(rect.width, `#${id}: width`).toBeGreaterThan(0);
      expect(rect.height, `#${id}: height`).toBeGreaterThan(0);

      // 6. elementFromPoint no centro retorna o próprio iframe (nada por cima).
      expect(elementoNoCentroEhOIframe, `#${id}: elementFromPoint deve retornar o iframe`).toBe(true);

      // 7. Clique no centro do campo alcança o iframe (Playwright falha se algo
      // interceptar o clique antes de chegar ao alvo).
      await page.locator(`#${id} iframe`).click();
    }
  });

  test("alternar Pix -> cartão -> Pix -> cartão mantém iframes únicos, visíveis e interativos", async ({ page }) => {
    await irParaFixture(page);

    // 8. Alterna várias vezes entre as duas formas de pagamento.
    await selecionarCartao(page);
    await page.click('[data-payment-method="pix"]');
    await page.click('[data-payment-method="cartao"]');
    await page.click('[data-payment-method="pix"]');
    await page.click('[data-payment-method="cartao"]');

    const viewport = page.viewportSize();

    // 9. Continuam únicos, visíveis e interativos.
    for (const id of CAMPOS_SEGUROS) {
      await expect(page.locator(`#${id} iframe`)).toHaveCount(1);

      const { rect, elementoNoCentroEhOIframe } = await coletarRetanguloEChecagens(page, id);
      expect(rect.top, `#${id}: top`).toBeGreaterThanOrEqual(0);
      expect(rect.left, `#${id}: left`).toBeGreaterThanOrEqual(0);
      expect(rect.bottom, `#${id}: bottom`).toBeLessThanOrEqual(viewport.height);
      expect(rect.width, `#${id}: width`).toBeGreaterThan(0);
      expect(rect.height, `#${id}: height`).toBeGreaterThan(0);
      expect(elementoNoCentroEhOIframe, `#${id}: elementFromPoint deve retornar o iframe`).toBe(true);

      await page.locator(`#${id} iframe`).click();
    }

    const mountCount = await page.evaluate(() => window.__mpMountCount);
    expect(mountCount).toBe(1);
  });

  test("continua correto depois de a página já estar rolada quando o usuário troca para cartão", async ({ page }) => {
    // 10. Página comprida, já rolada para longe do topo antes da troca.
    await irParaFixture(page, "?scrollAntes=1");
    await page.mouse.wheel(0, 900);
    await page.waitForTimeout(50);

    await selecionarCartao(page);

    const viewport = page.viewportSize();
    for (const id of CAMPOS_SEGUROS) {
      // Cada campo pode estar em uma posição diferente do formulário longo;
      // rola cada um até a área visível antes de medir, como um usuário real
      // faria, e confirma que o iframe acompanha essa posição corretamente
      // (não fica "preso" na geometria de quando a aba foi selecionada).
      await page.evaluate((id) => {
        document.querySelector(`#${id} iframe`).scrollIntoView({ block: "center" });
      }, id);
      await page.waitForTimeout(50);

      const { rect, elementoNoCentroEhOIframe } = await coletarRetanguloEChecagens(page, id);
      expect(rect.top, `#${id}: top após scroll`).toBeGreaterThanOrEqual(0);
      expect(rect.left, `#${id}: left após scroll`).toBeGreaterThanOrEqual(0);
      expect(rect.bottom, `#${id}: bottom após scroll`).toBeLessThanOrEqual(viewport.height);
      expect(rect.width, `#${id}: width após scroll`).toBeGreaterThan(0);
      expect(rect.height, `#${id}: height após scroll`).toBeGreaterThan(0);
      expect(elementoNoCentroEhOIframe, `#${id}: elementFromPoint após scroll`).toBe(true);
    }
  });

  // 11. O mesmo arquivo roda nos dois projetos configurados em
  // playwright.config.js (desktop-chromium e mobile-chromium/Pixel 7), então
  // os três testes acima já cobrem desktop e mobile.

  test("nunca monta o CardForm se o usuário voltar para Pix antes do painel assentar", async ({ page }) => {
    // Regressão direta da causa raiz: montarFormularioCartao() só chega em
    // mpInstance.cardForm(...) depois de "await garantirPedidoAtual()" (uma
    // requisição de rede de verdade para criar/reaproveitar o pedido). Se o
    // usuário voltar para "Pix" nesse intervalo, #cardPaymentPanel volta a
    // ficar hidden -- sem a guarda de aguardarPainelCartaoVisivel() em
    // v2-mercadopago-checkout.js, o SDK seria chamado do mesmo jeito com o
    // painel oculto, e o iframe nasceria "congelado" numa geometria inválida
    // (mesmo bug relatado: coordenadas presas de um momento em que o campo
    // não estava realmente visível).
    await irParaFixture(page);
    await page.locator('[data-payment-method="cartao"]').waitFor({ state: "visible" });

    // As duas trocas disparam na MESMA tarefa síncrona (sem round-trip de
    // clique real entre elas) para garantir a janela de corrida: a primeira
    // chamada roda até o primeiro "await" de verdade (fetch da config /
    // criação do pedido) e devolve o controle antes de qualquer promise
    // resolver -- é exatamente aí que a segunda chamada precisa entrar para
    // ocultar o painel de novo antes do SDK ser invocado.
    await page.evaluate(() => {
      window.misticaMercadoPagoCheckout.alternarFormaPagamento("cartao"); // dispara montarFormularioCartao() (assíncrono)
      window.misticaMercadoPagoCheckout.alternarFormaPagamento("pix"); // painel volta a ficar hidden antes do await terminar
    });

    // Dá tempo de sobra para a cadeia assíncrona (fetch mockado + rAF duplo)
    // terminar, se for o caso.
    await page.waitForTimeout(500);

    expect(await page.locator("#mpCardNumber iframe").count(), "não deveria montar iframe com o painel oculto").toBe(0);
    expect(await page.locator("#mpExpirationDate iframe").count()).toBe(0);
    expect(await page.locator("#mpSecurityCode iframe").count()).toBe(0);
    await expect(page.locator("#cardPaymentPanel")).toBeHidden();

    // Selecionar "cartão" de novo deve montar normalmente, sem duplicar.
    await page.click('[data-payment-method="cartao"]');
    for (const id of CAMPOS_SEGUROS) {
      await expect(page.locator(`#${id} iframe`)).toHaveCount(1, { timeout: 5000 });
    }
  });
});
