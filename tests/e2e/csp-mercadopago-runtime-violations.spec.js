const { test, expect } = require("@playwright/test");

/*
 * Regressão das 3 violações de CSP reportadas no Console após o merge da
 * PR #365 (iframe: true no CardForm), originadas dentro do bundle do SDK
 * MercadoPago.js v2 ("v2:1"):
 *
 *   1. style-src: o SDK aplica um atributo style="" inline no wrapper que
 *      envolve cada iframe de Secure Field (posicionamento/dimensões do
 *      campo) -- violava porque style-src não tinha 'unsafe-inline'.
 *   2. script-src: o SDK tenta executar um <script> inline (bootstrap do
 *      módulo de telemetria/device fingerprint) -- continua bloqueado
 *      DE PROPÓSITO nesta correção (ver docs/admin/CSP.md): não há hash
 *      estável confirmável neste ambiente (sem acesso de rede ao SDK real)
 *      nem nonce possível (GitHub Pages/meta CSP estática), e o SDK segue
 *      funcional sem esse script (só perde telemetria própria do Mercado
 *      Pago, não a tokenização do cartão) -- risco residual documentado.
 *   3. connect-src: o SDK envia telemetria para
 *      https://api.mercadolibre.com/tracks ("Could not send event" no
 *      console quando bloqueado) -- corrigido com o host exato (sem
 *      curinga) adicionado a connect-src.
 *
 * Este ambiente de CI/sandbox não tem acesso de rede a sdk.mercadopago.com
 * nem a api.mercadolibre.com (ver docs/admin/CSP.md), então os 3 padrões
 * acima são simulados diretamente contra a CSP real de index.html (a
 * mesma meta tag que o navegador aplicaria com o SDK de verdade) --
 * confirma a MECÂNICA da policy corrigida, não substitui a validação
 * final com o SDK/cartão reais em sandbox.
 */

function armarListenerViolacoes(page) {
  return page.addInitScript(() => {
    window.__cspRuntimeViolations = [];
    document.addEventListener("securitypolicyviolation", (event) => {
      window.__cspRuntimeViolations.push({
        directive: event.violatedDirective,
        blockedURI: event.blockedURI,
      });
    });
  });
}

async function limparViolacoes(page) {
  await page.evaluate(() => {
    window.__cspRuntimeViolations = [];
  });
}

async function lerViolacoes(page) {
  return page.evaluate(() => window.__cspRuntimeViolations || []);
}

test.describe("CSP runtime: violações reais do CardForm Mercado Pago (pós-#365)", () => {
  test.beforeEach(async ({ page }) => {
    await armarListenerViolacoes(page);
    await page.goto("/index.html", { waitUntil: "domcontentloaded" });
    await limparViolacoes(page);
  });

  test("style-src-attr permite o atributo style inline que o SDK aplica no wrapper do Secure Field", async ({ page }) => {
    await page.evaluate(() => {
      const wrapper = document.createElement("div");
      wrapper.setAttribute("data-teste-mp-secure-field-wrapper", "1");
      wrapper.setAttribute("style", "position: relative; width: 100%; height: 44px;");
      document.body.appendChild(wrapper);
    });
    await page.waitForTimeout(200);
    const violacoes = await lerViolacoes(page);
    expect(violacoes.filter((v) => v.directive.startsWith("style-src"))).toEqual([]);
    await page.evaluate(() => document.querySelector("[data-teste-mp-secure-field-wrapper]")?.remove());
  });

  test("style-src-elem continua bloqueando <style> injetado (a correção não afeta esta diretiva)", async ({ page }) => {
    const bloqueado = await page.evaluate(() => {
      return new Promise((resolve) => {
        document.addEventListener("securitypolicyviolation", function ouvinte(event) {
          if (event.violatedDirective.startsWith("style-src")) {
            document.removeEventListener("securitypolicyviolation", ouvinte);
            resolve(true);
          }
        });
        const style = document.createElement("style");
        style.textContent = "[data-teste-mp-style-tag]{color:red}";
        document.head.appendChild(style);
        setTimeout(() => resolve(false), 500);
      });
    });
    expect(bloqueado).toBe(true);
  });

  test("connect-src autoriza o host exato api.mercadolibre.com (telemetria do SDK)", async ({ page }) => {
    await page.evaluate(() => fetch("https://api.mercadolibre.com/tracks", { mode: "no-cors" }).catch(() => {}));
    await page.waitForTimeout(300);
    const violacoes = await lerViolacoes(page);
    expect(violacoes.filter((v) => v.directive === "connect-src")).toEqual([]);
  });

  test("connect-src continua bloqueando um subdomínio não autorizado de mercadolibre.com", async ({ page }) => {
    await page.evaluate(() =>
      fetch("https://outro-subdominio.mercadolibre.com/tracks", { mode: "no-cors" }).catch(() => {}),
    );
    await page.waitForTimeout(300);
    const violacoes = await lerViolacoes(page);
    expect(violacoes.some((v) => v.directive === "connect-src")).toBe(true);
  });

  test("script-src continua bloqueando execução de script inline (risco não relaxado nesta correção)", async ({ page }) => {
    await page.evaluate(() => {
      const script = document.createElement("script");
      script.textContent = "window.__testeMpInlineScriptExecutou = true;";
      document.body.appendChild(script);
    });
    await page.waitForTimeout(200);
    const executou = await page.evaluate(() => window.__testeMpInlineScriptExecutou === true);
    expect(executou).toBe(false);
    const violacoes = await lerViolacoes(page);
    expect(violacoes.some((v) => v.directive.startsWith("script-src"))).toBe(true);
  });

  test("nenhuma violação de CSP sobra ao simular o padrão completo de telemetria+estilo do CardForm", async ({ page }) => {
    await page.evaluate(() => {
      const wrapper = document.createElement("div");
      wrapper.setAttribute("data-teste-mp-completo", "1");
      wrapper.setAttribute("style", "position: absolute; inset: 0;");
      document.body.appendChild(wrapper);
      return fetch("https://api.mercadolibre.com/tracks", { mode: "no-cors" }).catch(() => {});
    });
    await page.waitForTimeout(300);
    const violacoes = await lerViolacoes(page);
    expect(violacoes).toEqual([]);
    await page.evaluate(() => document.querySelector("[data-teste-mp-completo]")?.remove());
  });
});
