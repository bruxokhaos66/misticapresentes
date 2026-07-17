// Kits por intenção: vitrines geradas a partir das mesmas categorias de
// intenção detectadas pela Isis (isis-guided.js), sem backend novo.
const { test, expect } = require("@playwright/test");

test.describe("Kits por intenção", () => {
  test("index.html tem links para as vitrines de kit", async ({ page }) => {
    await page.goto("/index.html");
    const kitsSection = page.locator("#kits");
    await expect(kitsSection.locator('a[href="kit.html?intencao=protecao"]')).toBeVisible();
    await expect(kitsSection.locator("a")).toHaveCount(7);
  });

  test("kit.html?intencao=protecao mostra produtos e navegação entre intenções", async ({ page }) => {
    await page.goto("/kit.html?intencao=protecao");
    await expect(page).toHaveTitle(/Proteção/);
    const grid = page.locator(".product-grid");
    await expect(grid.locator(".product-card")).not.toHaveCount(0);
    await expect(page.locator(".isis-followup-chips a.active")).toHaveText("Proteção");

    await Promise.all([
      page.waitForURL(/intencao=amor/),
      page.locator(".isis-followup-chips a", { hasText: "Amor" }).click(),
    ]);
    // Não usa waitForLoadState("networkidle") aqui: o player ambiente
    // (v2-shamanic-player.js) mantém uma conexão de rede em aberto para o
    // áudio de fundo (preload="metadata"), que nunca fica ociosa sob o
    // servidor estático de teste (python -m http.server, sem suporte a
    // Range/206) -- fazia esta espera nunca resolver e o teste sempre
    // estourar o timeout. `toHaveTitle` já espera (com retry) o título
    // real da página mudar, sem depender de rede ociosa.
    await expect(page).toHaveTitle(/Amor/);
  });

  test("kit.html sem intenção mostra seletor de intenções", async ({ page }) => {
    await page.goto("/kit.html");
    await expect(page.locator(".isis-followup-chips a")).toHaveCount(7);
    await expect(page.locator(".product-grid")).toHaveCount(0);
  });
});
