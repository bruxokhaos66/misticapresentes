// Testes de regressão XSS: validam que payloads maliciosos em dados de
// produtos, carrinho e fornecedores NÃO executam código e aparecem apenas
// como texto ou são rejeitados.
//
// Executa contra o site estático via Python HTTP server (playwright.config.js).
const { test, expect } = require("@playwright/test");

// ── Payloads de teste ────────────────────────────────────────────────────
const XSS_PAYLOADS = {
  imgOnerror: '<img src=x onerror=alert(1)>',
  svgOnload: '"><svg onload=alert(1)>',
  singleQuote: "product');alert(1);//",
  doubleQuote: 'product" onmouseover="alert(1)',
  javascriptProto: 'javascript:alert(1)',
  dataUri: 'data:text/html,<script>alert(1)</script>',
  templateLiteral: '${alert(1)}',
  ampersand: 'a&b<c>d',
  unicode: 'produto \u003cscript\u003e',
};

// Produto controlado com todos os campos preenchidos com payloads XSS.
const XSS_PRODUCT = {
  id: 999,
  codigo_p: "XSS-TEST-999",
  nome: XSS_PAYLOADS.imgOnerror,
  categoria: XSS_PAYLOADS.svgOnload,
  descricao: XSS_PAYLOADS.singleQuote,
  preco: 42.0,
  quantidade: 10,
  imagem_url: XSS_PAYLOADS.javascriptProto,
  imagens: [],
  selo: XSS_PAYLOADS.doubleQuote,
  avaliacoes_total: 3,
  avaliacoes_media: 4.5,
};

const NORMAL_PRODUCT = {
  id: 901,
  codigo_p: "TESTE-901",
  nome: "Incenso de teste",
  categoria: "Incensos",
  descricao: "Produto controlado para teste XSS.",
  preco: 19.9,
  quantidade: 5,
  imagem_url: "",
  imagens: [],
  selo: "Mais vendido",
  avaliacoes_total: 4,
  avaliacoes_media: 4.8,
};

async function prepararApiComXss(page) {
  await page.route(/misticaesotericos\.com\.br/, (route) => route.abort());
  await page.route("**/api/produtos?**", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify([XSS_PRODUCT, NORMAL_PRODUCT]),
    })
  );
}

async function aguardarCatalogo(page) {
  await expect
    .poll(() => page.evaluate(() => window.misticaCatalogState))
    .toBe("ready");
}

test.describe("XSS — Catálogo público", () => {
  test.beforeEach(async ({ page }) => {
    await prepararApiComXss(page);
    await page.goto("/index.html");
    await aguardarCatalogo(page);
  });

  test("nenhum alert() é executado ao renderizar produtos com payloads XSS", async ({
    page,
  }) => {
    let alertTriggered = false;
    page.on("dialog", (dialog) => {
      alertTriggered = true;
      dialog.dismiss();
    });

    // Espera um tempo suficiente para qualquer XSS síncrono ou assíncrono
    await page.waitForTimeout(2000);
    expect(alertTriggered).toBe(false);
  });

  test("payload XSS aparece como texto, não como HTML executável", async ({
    page,
  }) => {
    const grid = page.locator("[data-product-grid]");
    // O nome do produto XSS deve aparecer como texto visível
    await expect(grid).toContainText("<img src=x onerror=alert(1)>");
    // Não deve haver elementos <img> com src=x (o payload como atributo real)
    const maliciousImg = grid.locator('img[src="x"]');
    await expect(maliciousImg).toHaveCount(0);
  });

  test("nenhum atributo onclick existe nos botões de produto", async ({
    page,
  }) => {
    const buttons = page.locator(
      "[data-product-grid] button[onclick], [data-product-grid] a[onclick]"
    );
    await expect(buttons).toHaveCount(0);
  });

  test("botões usam data-action-add em vez de onclick", async ({ page }) => {
    const addButtons = page.locator("[data-product-grid] [data-action-add]");
    await expect(addButtons).not.toHaveCount(0);
  });

  test("botões de WhatsApp usam data-action-whatsapp", async ({ page }) => {
    const whatsappButtons = page.locator(
      "[data-product-grid] [data-action-whatsapp]"
    );
    await expect(whatsappButtons).not.toHaveCount(0);
  });

  test("botão de adicionar funciona via delegação de eventos", async ({
    page,
  }) => {
    const normalCard = page
      .locator(".product-card")
      .filter({ hasText: "Incenso de teste" });
    await normalCard.locator("[data-action-add]").click();

    const cartTotal = page.locator("#cartTotal");
    await expect(cartTotal).not.toHaveText("R$ 0,00");
    await expect(page.locator("#cartList")).toContainText("Incenso de teste");
  });

  test("imagem com protocolo javascript: é rejeitada (sem src perigoso)", async ({
    page,
  }) => {
    // A imagem do produto XSS tem imageUrl = "javascript:alert(1)"
    // Deve ser renderizada com src vazio ou ausente, não com javascript:
    const xssCard = page
      .locator(".product-card")
      .filter({ hasText: "<img src=x onerror=alert(1)>" });
    const img = xssCard.locator("img.product-photo");
    if (await img.count()) {
      const src = await img.getAttribute("src");
      expect(src).not.toContain("javascript:");
    }
  });
});

test.describe("XSS — Carrinho", () => {
  test.beforeEach(async ({ page }) => {
    await prepararApiComXss(page);
    await page.goto("/index.html");
    await aguardarCatalogo(page);
  });

  test("item no carrinho não contém handlers inline", async ({ page }) => {
    // Adiciona o produto normal ao carrinho
    const normalCard = page
      .locator(".product-card")
      .filter({ hasText: "Incenso de teste" });
    await normalCard.locator("[data-action-add]").click();

    // Verifica que o carrinho não tem onclick
    const removeButtons = page.locator("#cartList button[onclick]");
    await expect(removeButtons).toHaveCount(0);

    // Verifica que usa data-action-remove
    const safeButtons = page.locator("#cartList [data-action-remove]");
    await expect(safeButtons).not.toHaveCount(0);
  });

  test("removeFromCart funciona via delegação", async ({ page }) => {
    const normalCard = page
      .locator(".product-card")
      .filter({ hasText: "Incenso de teste" });
    await normalCard.locator("[data-action-add]").click();
    await expect(page.locator("#cartTotal")).not.toHaveText("R$ 0,00");

    await page.locator("#cartList [data-action-remove]").click();
    await expect(page.locator("#cartTotal")).toHaveText("R$ 0,00");
  });
});

test.describe("XSS — Nenhum onclick em toda a página", () => {
  test("index.html não contém onclick em nenhum elemento dinâmico", async ({
    page,
  }) => {
    await prepararApiComXss(page);
    await page.goto("/index.html");
    await aguardarCatalogo(page);

    // Verifica que nenhum botão/link dinâmico tem onclick
    const inlineHandlers = page.locator(
      "button[onclick], a[onclick], [data-product-grid][onclick], #cartList[onclick]"
    );
    await expect(inlineHandlers).toHaveCount(0);
  });
});

test.describe("XSS — Kit page", () => {
  test("kit.html não executa XSS via intent.label", async ({ page }) => {
    let alertTriggered = false;
    page.on("dialog", (dialog) => {
      alertTriggered = true;
      dialog.dismiss();
    });

    await page.goto("/kit.html?intencao=protecao");
    await page.waitForTimeout(2000);
    expect(alertTriggered).toBe(false);

    // Verifica que o título contém texto escapado
    await expect(page).toHaveTitle(/Proteção/);
  });
});
