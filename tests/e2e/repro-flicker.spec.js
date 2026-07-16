const { test, expect } = require("@playwright/test");

const PRODUTOS_API = [
  { id: 901, codigo_p: "T-901", nome: "Incenso de teste", categoria: "Incensos", descricao: "x", preco: 19.9, quantidade: 5, imagem_url: "", imagens: [], selo: "", avaliacoes_total: 0, avaliacoes_media: 0 },
  { id: 902, codigo_p: "T-902", nome: "Cristal de teste", categoria: "Cristais", descricao: "x", preco: 29.9, quantidade: 3, imagem_url: "", imagens: [], selo: "", avaliacoes_total: 0, avaliacoes_media: 0 },
];

test("falha transitoria APOS catalogo confirmado NAO esvazia a vitrine", async ({ page }) => {
  await page.route(/misticaesotericos\.com\.br/, route => route.abort());
  let call = 0;
  await page.route("**/api/produtos?**", route => {
    call++;
    if (call === 2) return route.abort("failed");
    return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(PRODUTOS_API) });
  });

  await page.goto("/index.html");
  await expect.poll(() => page.evaluate(() => window.misticaCatalogState)).toBe("ready");
  const grid = page.locator("[data-product-grid]");
  await expect(grid.locator(".product-card")).toHaveCount(2);
  const before = await grid.boundingBox();

  await page.evaluate(() => window.misticaMobileSync.syncNow());
  await expect.poll(() => page.evaluate(() => window.misticaCatalogState)).toBe("error");

  // catalogo ja confirmado antes: cards NAO podem sumir numa falha transitoria
  await expect(grid.locator(".product-card")).toHaveCount(2);
  const after = await grid.boundingBox();
  expect(after.height).toBe(before.height);
});

test("re-sync bem sucedido com dados identicos nao reconstroi o grid (sem duplicar render)", async ({ page }) => {
  await page.route(/misticaesotericos\.com\.br/, route => route.abort());
  await page.route("**/api/produtos?**", route => route.fulfill({
    status: 200, contentType: "application/json", body: JSON.stringify(PRODUTOS_API),
  }));
  await page.goto("/index.html");
  await expect.poll(() => page.evaluate(() => window.misticaCatalogState)).toBe("ready");
  const grid = page.locator("[data-product-grid]");
  await grid.locator(".product-card").first().evaluate(el => el.setAttribute("data-marker", "same-node"));

  await page.evaluate(() => window.misticaMobileSync.syncNow());
  await page.waitForTimeout(300);

  // se o node foi recriado, o marcador injetado via DOM teria sumido
  await expect(grid.locator(".product-card[data-marker='same-node']")).toHaveCount(1);
});
