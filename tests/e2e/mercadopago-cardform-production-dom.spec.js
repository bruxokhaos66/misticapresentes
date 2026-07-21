const { test, expect } = require("@playwright/test");

/*
 * Regressão permanente: prova que o DOM e o CSS COMPLETOS de produção
 * (index.html, com todo o cascade real do site -- header sticky,
 * .form-panel::before, v2-isis-polish.css, checkout-ux.css etc.) NUNCA
 * bloqueiam clique/foco nos iframes do CardForm, quando o SDK consegue
 * montar um Secure Field de verdade.
 *
 * Origem: depois da PR #369 relatar que não há acesso de rede a
 * sdk.mercadopago.com neste ambiente, foi feita uma comparação controlada
 * usando o MESMO mock de SDK já usado em
 * tests/e2e/mercadopago-cardform-mount.spec.js (fixture isolada), desta vez
 * montado dentro do index.html real -- resultado: elementFromPoint, clique e
 * foco funcionaram exatamente igual nos dois lugares. Isso descarta CSS/DOM
 * de produção como causa de bloqueio (ver docs/admin/CSP.md, seção
 * "Comparação DOM/CSS: diagnóstico x checkout real"). Este arquivo fixa essa
 * prova como regressão automática -- se uma mudança futura de CSS
 * reintroduzir um overlay/pointer-events/z-index que cubra o campo, os testes
 * abaixo (principalmente elementFromPoint e foco) quebram.
 *
 * Continua sem cobrir o SDK real (mesma limitação de rede documentada em
 * tests/e2e/csp-mercadopago-cardform.spec.js): o mock aqui só reproduz a
 * MECÂNICA de um Secure Field (iframe do tamanho/posição calculados pelo
 * SDK) -- não prova que o conteúdo interno de um iframe do SDK real fica
 * interativo quando o script inline é bloqueado pela CSP.
 *
 * Roda nos dois projetos configurados em playwright.config.js
 * (desktop-chromium e mobile-chromium) automaticamente -- sem setup extra.
 */

// Instala o mock de MercadoPago diretamente no contexto da página (função
// real passada a page.evaluate, não uma string avaliada com eval() -- este
// projeto não usa eval/unsafe-eval em lugar nenhum, nem em teste).
function instalarMockSdk() {
  window.__mpMountCount = 0;
  window.__mpUnmountCount = 0;
  window.__mpConfigsCapturados = [];
  const CAMPOS_SEGUROS = ["mpCardNumber", "mpExpirationDate", "mpSecurityCode"];

  function MockMercadoPago() {}
  MockMercadoPago.prototype.cardForm = function (config) {
    window.__mpConfigsCapturados.push(config);
    window.__mpMountCount += 1;

    // Congela a geometria no instante da chamada, igual ao SDK real (ver
    // tests/e2e/fixtures/mercadopago-cardform-fixture.html).
    const geometriaCongelada = {};
    CAMPOS_SEGUROS.forEach((id) => {
      const el = document.getElementById(id);
      geometriaCongelada[id] = el ? el.getBoundingClientRect() : null;
    });

    if (config.autoMount) {
      setTimeout(() => {
        CAMPOS_SEGUROS.forEach((id) => {
          const el = document.getElementById(id);
          const rect = geometriaCongelada[id];
          if (el && el.querySelectorAll("iframe").length === 0 && rect) {
            const iframe = document.createElement("iframe");
            iframe.src = "about:blank";
            iframe.style.display = "block";
            iframe.style.border = "0";
            iframe.style.width = rect.width + "px";
            iframe.style.height = rect.height + "px";
            el.appendChild(iframe);
          }
        });
        const installments = document.getElementById("mpInstallments");
        if (installments && !installments.options.length) {
          const opt = document.createElement("option");
          opt.value = "1";
          opt.textContent = "1x sem juros";
          installments.appendChild(opt);
        }
        if (config.callbacks && config.callbacks.onFormMounted) config.callbacks.onFormMounted(null);
      }, 20);
    }
    return {
      unmount: function () {
        window.__mpUnmountCount += 1;
        CAMPOS_SEGUROS.forEach((id) => {
          const el = document.getElementById(id);
          if (el) el.querySelectorAll("iframe").forEach((f) => f.remove());
        });
      },
      getCardFormData: function () { return {}; },
    };
  };
  window.MercadoPago = MockMercadoPago;
}

async function prepararCheckoutComMock(page) {
  await page.route("**/api/payments/mercadopago/config", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ enabled: true, public_key: "TEST-PUBLIC-KEY" }),
    }),
  );

  await page.goto("/index.html");
  // app.js define window.misticaGetCart/misticaCriarPedido no carregamento;
  // como este arquivo os sobrescreve só DEPOIS do goto (não via
  // addInitScript), a atribuição real do app.js já aconteceu e a nossa
  // sobrescrita fica por cima -- addInitScript rodaria ANTES de app.js e
  // seria sobrescrito por ele (causa raiz de um falso-negativo já investigado
  // nesta PR).
  await page.waitForFunction(() => !!window.misticaMercadoPagoCheckout && typeof window.misticaGetCart === "function");

  // Fase 3: a escolha de modalidade é obrigatória antes de qualquer
  // tentativa de pagamento (Pix ou cartão) — window.misticaEntrega.
  // podeProsseguir() bloqueia garantirPedidoAtual() sem ela, mesmo com
  // misticaCriarPedido sobrescrito abaixo. "Retirar na loja" mantém o foco
  // deste arquivo na mecânica do CardForm (DOM/CSS), sem exigir endereço.
  await page.locator('[data-recebimento-radio][value="retirada"]').evaluate((el) => {
    el.checked = true;
    el.dispatchEvent(new Event("change", { bubbles: true }));
  });

  await page.evaluate(() => {
    window.misticaGetCart = () => [{ id: "produto-teste", qty: 1 }];
    window.misticaCriarPedido = async () => ({ id: 999, pixTxid: "txid-teste", totalFinal: 150.5 });
  });
  await page.evaluate(instalarMockSdk);
}

async function alternarECapturarMontagem(page) {
  await page.evaluate(() => window.misticaMercadoPagoCheckout.alternarFormaPagamento("cartao"));
  await expect.poll(() => page.evaluate(() => window.__mpMountCount), { timeout: 8000 }).toBeGreaterThan(0);
  await expect(page.locator("#mpCardNumber iframe")).toHaveCount(1, { timeout: 5000 });
}

test.describe("DOM/CSS completos de produção (index.html) não bloqueiam o CardForm", () => {
  test("cardForm monta exatamente 3 iframes (1 por campo seguro)", async ({ page }) => {
    await prepararCheckoutComMock(page);
    await alternarECapturarMontagem(page);

    const totalIframes = await page.evaluate(() =>
      ["mpCardNumber", "mpExpirationDate", "mpSecurityCode"]
        .reduce((total, id) => total + document.querySelectorAll(`#${id} iframe`).length, 0),
    );
    expect(totalIframes).toBe(3);
    for (const id of ["mpCardNumber", "mpExpirationDate", "mpSecurityCode"]) {
      await expect(page.locator(`#${id} iframe`)).toHaveCount(1);
    }
  });

  test("cada iframe tem largura e altura maiores que zero", async ({ page }) => {
    await prepararCheckoutComMock(page);
    await alternarECapturarMontagem(page);

    for (const id of ["mpCardNumber", "mpExpirationDate", "mpSecurityCode"]) {
      const box = await page.locator(`#${id} iframe`).boundingBox();
      expect(box, `#${id}: iframe deveria ter bounding box`).not.toBeNull();
      expect(box.width, `#${id}: largura`).toBeGreaterThan(0);
      expect(box.height, `#${id}: altura`).toBeGreaterThan(0);
    }
  });

  test("elementFromPoint no centro de cada iframe retorna o próprio iframe (nenhum overlay intercepta)", async ({ page }) => {
    await prepararCheckoutComMock(page);
    await alternarECapturarMontagem(page);

    for (const id of ["mpCardNumber", "mpExpirationDate", "mpSecurityCode"]) {
      const locator = page.locator(`#${id} iframe`);
      await locator.scrollIntoViewIfNeeded();

      const resultado = await page.evaluate(({ id }) => {
        const el = document.getElementById(id).querySelector("iframe");
        const rect = el.getBoundingClientRect();
        const cx = rect.x + rect.width / 2;
        const cy = rect.y + rect.height / 2;
        const topo = document.elementFromPoint(cx, cy);
        return {
          dentroDoViewport: cx >= 0 && cy >= 0 && cx <= window.innerWidth && cy <= window.innerHeight,
          topoEhIframe: topo === el,
          topoDescricao: topo ? `${topo.tagName}#${topo.id}.${topo.className}` : null,
        };
      }, { id });

      expect(resultado.dentroDoViewport, `#${id}: iframe deveria estar dentro do viewport após scrollIntoView`).toBe(true);
      expect(resultado.topoEhIframe, `#${id}: elementFromPoint deveria retornar o iframe, achou ${resultado.topoDescricao}`).toBe(true);
    }
  });

  test("clique no iframe faz document.activeElement ser o próprio iframe", async ({ page }) => {
    await prepararCheckoutComMock(page);
    await alternarECapturarMontagem(page);

    for (const id of ["mpCardNumber", "mpExpirationDate", "mpSecurityCode"]) {
      const locator = page.locator(`#${id} iframe`);
      await locator.scrollIntoViewIfNeeded();
      await locator.click();

      const focoNoIframe = await page.evaluate(({ id }) => {
        const el = document.getElementById(id).querySelector("iframe");
        return document.activeElement === el;
      }, { id });
      expect(focoNoIframe, `#${id}: clique deveria focar o iframe`).toBe(true);
    }
  });

  test(".form-panel::before não intercepta eventos de ponteiro sobre o CardForm", async ({ page }) => {
    await prepararCheckoutComMock(page);
    await alternarECapturarMontagem(page);

    const pointerEventsDoOverlay = await page.evaluate(() => {
      const painel = document.getElementById("cardPaymentPanel");
      return getComputedStyle(painel, "::before").pointerEvents;
    });
    expect(pointerEventsDoOverlay).toBe("none");
  });

  test("alternar Pix -> cartão -> Pix -> cartão não duplica iframes nem instâncias", async ({ page }) => {
    await prepararCheckoutComMock(page);

    for (let i = 0; i < 3; i++) {
      await page.evaluate(() => window.misticaMercadoPagoCheckout.alternarFormaPagamento("cartao"));
      await expect(page.locator("#mpCardNumber iframe")).toHaveCount(1, { timeout: 5000 });
      await page.evaluate(() => window.misticaMercadoPagoCheckout.alternarFormaPagamento("pix"));
    }
    await page.evaluate(() => window.misticaMercadoPagoCheckout.alternarFormaPagamento("cartao"));
    await expect(page.locator("#mpCardNumber iframe")).toHaveCount(1, { timeout: 5000 });

    const mountCount = await page.evaluate(() => window.__mpMountCount);
    expect(mountCount).toBe(1);
    for (const id of ["mpCardNumber", "mpExpirationDate", "mpSecurityCode"]) {
      await expect(page.locator(`#${id} iframe`)).toHaveCount(1);
    }
  });
});
