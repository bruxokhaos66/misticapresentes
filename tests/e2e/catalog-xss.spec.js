const { test, expect } = require("@playwright/test");

const lt = "\u003c";
const gt = "\u003e";

test("dados do catálogo são exibidos como texto e não executam HTML", async ({ page }) => {
  await page.addInitScript(() => {
    window.__catalogInjectionExecuted = 0;
  });

  const imgPayload = `${lt}img src=x onerror="window.__catalogInjectionExecuted=1"${gt}`;
  const svgPayload = `${lt}svg onload="window.__catalogInjectionExecuted=2"${gt}`;
  const scriptPayload = `${lt}script${gt}window.__catalogInjectionExecuted=3${lt}/script${gt}`;

  await page.route("**/api/produtos?**", async route => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify([
        {
          id: 999001,
          codigo_p: "CATALOGO-SEGURO",
          nome: `${imgPayload}Produto seguro`,
          categoria: `${svgPayload}Categoria segura`,
          descricao: `${scriptPayload}Descrição segura`,
          selo: `${imgPayload}Destaque`,
          preco: 19.9,
          quantidade: 5,
          imagem_url: "javascript:invalido",
          imagens: [],
          sob_encomenda: false,
          limite_encomenda: 10,
          avaliacoes_total: 0,
          avaliacoes_media: 0,
        },
      ]),
    });
  });

  await page.goto("/index.html");
  await expect(page.locator(".product-card h3")).toContainText("Produto seguro");
  await expect(page.locator(".product-card img")).toHaveCount(0);
  await page.waitForTimeout(200);

  expect(await page.evaluate(() => window.__catalogInjectionExecuted)).toBe(0);
  expect(await page.locator(".product-card script").count()).toBe(0);
  expect(await page.locator(".product-card svg").count()).toBe(0);
});
