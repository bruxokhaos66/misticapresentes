// Testes de ponta a ponta (Playwright) do caminho principal de compra:
// catálogo oficial -> filtro por categoria -> carrinho -> página individual.
const { test, expect } = require("@playwright/test");

const PRODUTOS_API = [
  {
    id: 901,
    codigo_p: "TESTE-901",
    nome: "Incenso de teste",
    categoria: "Incensos",
    descricao: "Produto controlado para o fluxo principal de compra.",
    preco: 19.9,
    quantidade: 5,
    imagem_url: "",
    imagens: [],
    selo: "Mais vendido",
    avaliacoes_total: 4,
    avaliacoes_media: 4.8,
  },
  {
    id: 902,
    codigo_p: "TESTE-902",
    nome: "Cristal de teste",
    categoria: "Cristais",
    descricao: "Segundo produto para validar filtros por categoria.",
    preco: 29.9,
    quantidade: 3,
    imagem_url: "",
    imagens: [],
    selo: "",
    avaliacoes_total: 2,
    avaliacoes_media: 5,
  },
];

async function prepararApiCatalogo(page) {
  // Bloqueia chamadas externas não controladas, mas mantém o catálogo oficial
  // determinístico para o CI. O mock específico é registrado por último para
  // ter precedência sobre a regra ampla.
  await page.route(/misticaesotericos\.com\.br/, route => route.abort());
  await page.route("**/api/produtos?**", route => route.fulfill({
    status: 200,
    contentType: "application/json",
    body: JSON.stringify(PRODUTOS_API),
  }));
}

async function aguardarCatalogo(page) {
  await expect.poll(() => page.evaluate(() => window.misticaCatalogState)).toBe("ready");
}

test.describe("Catálogo público", () => {
  test.beforeEach(async ({ page }) => {
    await prepararApiCatalogo(page);
    await page.goto("/index.html");
    await aguardarCatalogo(page);
  });

  test("carrega a vitrine com produtos", async ({ page }) => {
    const grid = page.locator("[data-product-grid]");
    await expect(grid.locator(".product-card")).toHaveCount(PRODUTOS_API.length);
    await expect(grid).toContainText("Incenso de teste");
    await expect(grid).toContainText("Cristal de teste");
  });

  test("filtra produtos por categoria real", async ({ page }) => {
    const chips = page.locator(".v2-category-chips .v2-chip");
    await expect(chips).not.toHaveCount(0);

    const targetChip = chips.filter({ hasText: "Cristais" }).first();
    await expect(targetChip).toBeVisible();
    const categoryName = (await targetChip.textContent()).trim();
    await targetChip.click();

    const visibleCards = page.locator("[data-product-grid] .product-card:not([hidden])");
    await expect(visibleCards).toHaveCount(1);
    await expect(visibleCards.first()).toHaveAttribute("data-category", categoryName);
    await expect(visibleCards.first()).toContainText("Cristal de teste");
  });

  test("adiciona um produto ao carrinho e atualiza o total", async ({ page }) => {
    const firstCard = page.locator("[data-product-grid] .product-card").first();
    await firstCard.locator(".btn", { hasText: "Adicionar" }).click();

    const cartTotal = page.locator("#cartTotal");
    await expect(cartTotal).not.toHaveText("R$ 0,00");
    await expect(page.locator("#cartList")).toContainText("Incenso de teste");
  });
});

test.describe("Página individual de produto", () => {
  test.beforeEach(async ({ page }) => {
    await prepararApiCatalogo(page);
  });

  test("mostra confiança, avaliações e políticas", async ({ page }) => {
    await page.goto("/produto.html?id=api-901");
    await aguardarCatalogo(page);

    await expect(page.locator(".product-page-card h1")).toHaveText("Incenso de teste");
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
    await aguardarCatalogo(page);
    await expect(page.getByText("Não encontramos este produto.")).toBeVisible();
  });

  test("adiciona ao carrinho pela página de produto e mostra o carrinho flutuante", async ({ page }) => {
    await page.goto("/produto.html?id=api-901");
    await aguardarCatalogo(page);

    const floatingCart = page.locator(".floating-cart");
    await expect(floatingCart).not.toHaveClass(/has-items/);
    await page.locator("#addProductToCart").click();
    await expect(floatingCart).toHaveClass(/has-items/);
    await expect(page.locator(".floating-cart-count")).toHaveText("1");
    await expect(page.locator("#addProductFeedback")).toBeVisible();
  });
});
