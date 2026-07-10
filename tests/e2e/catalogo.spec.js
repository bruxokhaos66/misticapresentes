// Testes de ponta a ponta (Playwright) do caminho principal de compra:
// catálogo -> filtro por categoria -> carrinho -> página individual do produto.
const { test, expect } = require("@playwright/test");

async function blockExternalApi(page) {
  await page.route(/misticaesotericos\.com\.br/, (route) => route.abort());
}

test.describe("Catálogo público", () => {
  test.beforeEach(async ({ page }) => {
    await blockExternalApi(page);
    await page.goto("/index.html");
  });

  test("carrega a vitrine com produtos", async ({ page }) => {
    const grid = page.locator("[data-product-grid]");
    await expect(grid.locator(".product-card")).not.toHaveCount(0);
  });

  test("filtra produtos por categoria real", async ({ page }) => {
    const chips = page.locator(".v2-category-chips .v2-chip");
    await expect(chips).not.toHaveCount(0);

    const targetChip = chips.nth(1);
    const categoryName = await targetChip.textContent();
    await targetChip.click();

    const visibleCards = page.locator("[data-product-grid] .product-card:not([hidden])");
    const count = await visibleCards.count();
    expect(count).toBeGreaterThan(0);
    for (let i = 0; i < count; i++) {
      await expect(visibleCards.nth(i)).toHaveAttribute("data-category", categoryName.trim());
    }
  });

  test("adiciona um produto ao carrinho e atualiza o total", async ({ page }) => {
    const firstCard = page.locator("[data-product-grid] .product-card").first();
    await firstCard.locator(".btn", { hasText: "Adicionar" }).click();

    const cartTotal = page.locator("#cartTotal");
    await expect(cartTotal).not.toHaveText("R$ 0,00");
    await expect(page.locator("#cartList .cart-item")).not.toHaveCount(0);
  });
});

test.describe("Página individual de produto", () => {
  test.beforeEach(async ({ page }) => {
    await blockExternalApi(page);
  });

  test("mostra confiança, avaliações e políticas", async ({ page }) => {
    await page.goto("/produto.html?id=pedra-energetica");

    await expect(page.locator(".product-page-card h1")).toHaveText("Pedras e Cristais");
    await expect(page.locator(".product-trust .trust-badge")).not.toHaveCount(0);
    await expect(page.locator(".product-reviews")).toBeVisible();
    await expect(page.locator(".product-policies")).toBeVisible();
    await expect(page.getByRole("link", { name: "Comprar pelo WhatsApp" })).toHaveAttribute(
      "href",
      /wa\.me/
    );
  });

  test("produto inexistente mostra estado de não encontrado", async ({ page }) => {
    await page.goto("/produto.html?id=produto-que-nao-existe");
    await expect(page.getByText("Não encontramos este produto.")).toBeVisible();
  });
});
