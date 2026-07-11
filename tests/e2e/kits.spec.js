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
    await page.waitForLoadState("networkidle");
    await expect(page).toHaveTitle(/Amor/);
  });

  test("kit.html sem intenção mostra seletor de intenções", async ({ page }) => {
    await page.goto("/kit.html");
    await expect(page.locator(".isis-followup-chips a")).toHaveCount(7);
    await expect(page.locator(".product-grid")).toHaveCount(0);
  });
});
