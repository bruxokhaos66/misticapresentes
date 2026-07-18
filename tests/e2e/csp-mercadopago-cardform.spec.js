const { test, expect } = require("@playwright/test");

/*
 * Regressão do bug: "CardForm aparece, mas os campos de número/validade/CVV
 * não aceitam foco/digitação e o seletor de parcelas fica vazio".
 *
 * Causa raiz identificada: a CSP autorizava só os hosts EXATOS
 * sdk.mercadopago.com / api.mercadopago.com / www.mercadopago.com em
 * connect-src/frame-src. O Secure Fields (iframes de número/validade/CVV) e
 * as chamadas de tokenização/parcelas do SDK não têm um único subdomínio
 * documentado nem estável -- um comerciante brasileiro (BRL) pode receber
 * tráfego de subdomínios sob mercadopago.com.br, não só mercadopago.com.
 * Qualquer subdomínio fora da lista exata era bloqueado silenciosamente
 * pelo navegador: o <div> do campo aparece (é nosso), mas o iframe dentro
 * dele nunca carrega -- exatamente o sintoma relatado.
 *
 * Este ambiente de CI/sandbox não tem acesso de rede a sdk.mercadopago.com
 * (política de rede bloqueia o host), então não é possível carregar o SDK
 * real aqui. Este teste valida a MECÂNICA da CSP corrigida com um Chromium
 * real: confirma que iframes/fetches para subdomínios do Mercado Pago
 * (incluindo .com.br, que o bug expôs) não são bloqueados pela CSP da
 * página real (index.html), e que a CSP continua bloqueando uma origem de
 * terceiro não relacionada (garante que o teste não passaria por acidente
 * com uma CSP frouxa demais). A validação final com o SDK/cartão real
 * precisa ser feita em um ambiente com acesso à rede do Mercado Pago (ver
 * docs/admin/CSP.md).
 */

function coletarViolacoesCsp(page) {
  const violacoes = [];
  page.on("console", (msg) => {
    if (msg.type() === "error" && /Content Security Policy/i.test(msg.text())) {
      violacoes.push(msg.text());
    }
  });
  return violacoes;
}

test.describe("CSP permite a infraestrutura real do CardForm (Secure Fields + tokenização)", () => {
  test("frame-src autoriza iframe em subdomínio .com e .com.br do Mercado Pago", async ({ page }) => {
    const violacoes = coletarViolacoesCsp(page);
    await page.goto("/index.html", { waitUntil: "domcontentloaded" });

    for (const src of [
      "https://www.mercadopago.com/secure-fields/card-number",
      "https://www.mercadopago.com.br/secure-fields/card-number",
      "https://xyz123.mercadopago.com.br/secure-fields/expiration-date",
    ]) {
      violacoes.length = 0;
      await page.evaluate((url) => {
        const iframe = document.createElement("iframe");
        iframe.src = url;
        iframe.setAttribute("data-teste-csp-mercadopago", "1");
        document.body.appendChild(iframe);
      }, src);
      // Dá tempo para o navegador processar a navegação do iframe (e, se
      // bloqueado, emitir o console.error de CSP) antes de checar.
      await page.waitForTimeout(300);
      expect(violacoes, `iframe para ${src} não deveria violar frame-src`).toEqual([]);
      await page.evaluate(() => {
        document.querySelector('[data-teste-csp-mercadopago]')?.remove();
      });
    }
  });

  test("frame-src continua bloqueando uma origem de terceiro não relacionada", async ({ page }) => {
    const violacoes = coletarViolacoesCsp(page);
    await page.goto("/index.html", { waitUntil: "domcontentloaded" });

    await page.evaluate(() => {
      const iframe = document.createElement("iframe");
      iframe.src = "https://exemplo-terceiro-nao-autorizado.invalid/pagina";
      iframe.setAttribute("data-teste-csp-terceiro", "1");
      document.body.appendChild(iframe);
    });
    await page.waitForTimeout(300);
    expect(violacoes.some((texto) => /frame-src/i.test(texto))).toBe(true);
  });

  test("connect-src autoriza fetch para subdomínio .com e .com.br do Mercado Pago", async ({ page }) => {
    const violacoes = coletarViolacoesCsp(page);
    await page.goto("/index.html", { waitUntil: "domcontentloaded" });

    for (const url of [
      "https://api.mercadopago.com/v1/payment_methods",
      "https://api.mercadopago.com.br/v1/payment_methods",
    ]) {
      violacoes.length = 0;
      await page.evaluate((u) => {
        // Não importa se a rede do sandbox rejeita a conexão em si (não há
        // acesso de saída a mercadopago.com aqui) -- o que este teste
        // verifica é se a CSP deixou a tentativa passar sem violação.
        return fetch(u, { mode: "no-cors" }).catch(() => {});
      }, url);
      await page.waitForTimeout(300);
      expect(violacoes, `fetch para ${url} não deveria violar connect-src`).toEqual([]);
    }
  });

  test("connect-src continua bloqueando uma origem de terceiro não relacionada", async ({ page }) => {
    const violacoes = coletarViolacoesCsp(page);
    await page.goto("/index.html", { waitUntil: "domcontentloaded" });

    await page.evaluate(() => {
      return fetch("https://exemplo-terceiro-nao-autorizado.invalid/api", { mode: "no-cors" }).catch(() => {});
    });
    await page.waitForTimeout(300);
    expect(violacoes.some((texto) => /connect-src/i.test(texto))).toBe(true);
  });
});
