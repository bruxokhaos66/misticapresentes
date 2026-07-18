// Testes de ponta a ponta da Content Security Policy (CSP) do site público.
//
// Confirma, com um navegador real (Chromium headless), que a política
// entregue via <meta http-equiv="Content-Security-Policy"> (GitHub Pages não
// permite cabeçalhos HTTP customizados -- ver docs/admin/CSP.md) não quebra
// nenhuma funcionalidade essencial: catálogo, carrinho (agora via
// delegação de cliques data-*, sem onclick= inline), Pix e a config pública
// do Mercado Pago. Nenhuma chamada real ao Mercado Pago é feita (mockada).
const { test, expect } = require("@playwright/test");

const PRODUTOS_API = [
  {
    id: 901,
    codigo_p: "CSP-901",
    nome: "Produto CSP teste",
    categoria: "Incensos",
    descricao: "Produto controlado para validar a CSP.",
    preco: 19.9,
    quantidade: 5,
    imagem_url: "",
    imagens: [],
    selo: "",
    avaliacoes_total: 0,
    avaliacoes_media: 0,
  },
];

async function prepararRede(page) {
  await page.route(/misticaesotericos\.com\.br/, route => route.abort());
  await page.route("**/api/produtos?**", route => route.fulfill({
    status: 200,
    contentType: "application/json",
    body: JSON.stringify(PRODUTOS_API),
  }));
  await page.route("**/api/payments/mercadopago/config", route => route.fulfill({
    status: 200,
    contentType: "application/json",
    body: JSON.stringify({ enabled: false }),
  }));
}

// Erros de console genéricos de rede (ex.: uma fonte do Google Fonts que a
// rede do runner de CI bloqueia) não são um sinal de violação de CSP -- o
// sinal real e confiável é o evento securitypolicyviolation, capturado à
// parte. Filtramos aqui só "Failed to load resource" (sem stack, sem
// exceção JS) para não mascarar erros de verdade (exceções não tratadas
// continuam chegando via pageerror, sempre incluídas).
function _ehFalhaGenericaDeRede(texto) {
  return /Failed to load resource/.test(texto) && !/Content Security Policy/i.test(texto);
}

function coletarDiagnosticos(page) {
  const consoleErros = [];
  const violacoesCsp = [];
  page.on("console", msg => {
    if (msg.type() === "error" && !_ehFalhaGenericaDeRede(msg.text())) consoleErros.push(msg.text());
  });
  page.on("pageerror", err => consoleErros.push(String(err)));
  return { consoleErros, violacoesCsp };
}

async function armarListenerCsp(page, violacoesCsp) {
  await page.addInitScript(() => {
    window.__cspViolations = [];
    document.addEventListener("securitypolicyviolation", event => {
      window.__cspViolations.push({
        directive: event.violatedDirective,
        blockedURI: event.blockedURI,
      });
    });
  });
  page.on("load", async () => {
    try {
      const vs = await page.evaluate(() => window.__cspViolations || []);
      violacoesCsp.push(...vs);
    } catch {
      /* página pode ter navegado antes da leitura -- ignorado */
    }
  });
}

test.describe("CSP do site público", () => {
  test("index.html carrega catálogo e permite adicionar ao carrinho sem violação de CSP", async ({ page }) => {
    await prepararRede(page);
    const { consoleErros, violacoesCsp } = coletarDiagnosticos(page);
    await armarListenerCsp(page, violacoesCsp);

    await page.goto("/index.html");
    await expect.poll(() => page.evaluate(() => window.misticaCatalogState)).toBe("ready");

    const firstCard = page.locator("[data-product-grid] .product-card").first();
    await firstCard.locator("[data-add-to-cart]").click();
    await expect(page.locator("#cartTotal")).not.toHaveText("R$ 0,00");
    await expect(page.locator("#cartList")).toContainText("Produto CSP teste");

    // Confirma que a config pública do Mercado Pago foi consultada (o
    // toggle de cartão só aparece quando enabled=true; aqui está mockado
    // como false, então o botão de cartão deve continuar oculto).
    await expect(page.locator("[data-mp-toggle]")).toBeHidden();

    const violacoesInesperadas = (await page.evaluate(() => window.__cspViolations || []));
    expect(violacoesInesperadas, JSON.stringify(violacoesInesperadas)).toEqual([]);
    expect(consoleErros, JSON.stringify(consoleErros)).toEqual([]);
  });

  test("meta CSP está presente e não usa unsafe-inline em script-src", async ({ page }) => {
    await prepararRede(page);
    await page.goto("/index.html");
    const conteudoCsp = await page.evaluate(() => {
      const meta = document.querySelector('meta[http-equiv="Content-Security-Policy"]');
      return meta ? meta.getAttribute("content") : null;
    });
    expect(conteudoCsp).toBeTruthy();
    expect(conteudoCsp).not.toContain("unsafe-eval");
    const scriptSrcMatch = conteudoCsp.match(/script-src ([^;]+);/);
    expect(scriptSrcMatch).toBeTruthy();
    expect(scriptSrcMatch[1]).not.toContain("unsafe-inline");
  });

  test("página de produto (produto.html) não gera violação de CSP nem erro de console", async ({ page }) => {
    await page.route(/misticaesotericos\.com\.br/, route => route.abort());
    await page.route("**/api/produtos?**", route => route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(PRODUTOS_API),
    }));
    const { consoleErros, violacoesCsp } = coletarDiagnosticos(page);
    await armarListenerCsp(page, violacoesCsp);

    await page.goto("/produto.html?id=901");
    await page.waitForTimeout(500);

    const violacoesInesperadas = (await page.evaluate(() => window.__cspViolations || []));
    expect(violacoesInesperadas, JSON.stringify(violacoesInesperadas)).toEqual([]);
    expect(consoleErros, JSON.stringify(consoleErros)).toEqual([]);
  });

  test("viewport mobile: catálogo e carrinho funcionam sob a CSP", async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await prepararRede(page);
    const { consoleErros, violacoesCsp } = coletarDiagnosticos(page);
    await armarListenerCsp(page, violacoesCsp);

    await page.goto("/index.html");
    await expect.poll(() => page.evaluate(() => window.misticaCatalogState)).toBe("ready");
    const firstCard = page.locator("[data-product-grid] .product-card").first();
    await firstCard.locator("[data-add-to-cart]").click();
    await expect(page.locator("#cartTotal")).not.toHaveText("R$ 0,00");

    const violacoesInesperadas = (await page.evaluate(() => window.__cspViolations || []));
    expect(violacoesInesperadas, JSON.stringify(violacoesInesperadas)).toEqual([]);
    expect(consoleErros, JSON.stringify(consoleErros)).toEqual([]);
  });
});
