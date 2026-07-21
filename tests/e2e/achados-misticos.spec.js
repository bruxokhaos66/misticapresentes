// Testes de ponta a ponta da categoria "Achados Místicos" (produtos sob
// encomenda): selo no card, link do fornecedor oculto ao cliente, seção de
// encomenda no produto, aviso/confirmação no checkout e a página da categoria.
const { test, expect } = require("@playwright/test");

const SUPPLIER_URL = "https://shopee.com.br/fornecedor-secreto";

const PRODUTO_ENCOMENDA = {
  id: 4242,
  codigo_p: "ENC-001",
  nome: "Turíbulo Ritualístico Importado",
  marca: "Curadoria Mística",
  categoria: "Achados Místicos",
  descricao: "Peça especial trazida sob encomenda para o seu ritual.",
  preco: 189.9,
  quantidade: 5,
  imagem_url: "",
  imagens: [],
  link_externo: SUPPLIER_URL,
  selo: "Sob encomenda",
  avaliacoes_total: 0,
  avaliacoes_media: 0,
};

// Intercepta a API para servir apenas o produto sob encomenda, sem tocar a
// internet. Cobre tanto o catálogo (mobile-sync) quanto a página da categoria.
async function mockApi(page, produtos = [PRODUTO_ENCOMENDA]) {
  // Ordem importa: o Playwright dá prioridade às rotas registradas por último,
  // então o abort genérico vem primeiro e as rotas específicas depois.
  await page.route(/misticaesotericos\.com\.br/, (route) => route.abort());
  await page.route("**/api/status**", (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ status: "ok" }) })
  );
  await page.route("**/api/produtos**", (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(produtos) })
  );
}

test.describe("Catálogo - produto sob encomenda", () => {
  test("mostra selo, oculta o link do fornecedor e exibe a seção de encomenda", async ({ page }) => {
    await mockApi(page);
    await page.goto("/index.html");

    const card = page.locator('[data-product-grid] .product-card', { hasText: "Turíbulo Ritualístico Importado" });
    await expect(card).toHaveCount(1);
    await expect(card.locator(".product-badge-encomenda")).toHaveText("Sob encomenda");
    await expect(card.locator(".product-encomenda-note")).toBeVisible();

    // Abre o inspetor do produto: não pode haver link do fornecedor.
    await card.locator(".product-zoom-button").click();
    const modal = page.locator("[data-product-inspector-modal]");
    await expect(modal).toBeVisible();
    await expect(modal.getByText("Como funciona a encomenda")).toBeVisible();
    await expect(modal.getByText("Ver link do produto")).toHaveCount(0);
    const html = await modal.innerHTML();
    expect(html).not.toContain(SUPPLIER_URL);
    expect(html).not.toContain("shopee");
  });

  test("checkout exige confirmação quando há item sob encomenda", async ({ page }) => {
    await mockApi(page);
    await page.goto("/index.html");

    const card = page.locator('[data-product-grid] .product-card', { hasText: "Turíbulo Ritualístico Importado" });
    await expect(card).toHaveCount(1);
    await card.locator(".btn", { hasText: "Adicionar" }).click();

    // Selo do item no carrinho e caixa de aviso visível.
    await expect(page.locator("#cartList .cart-encomenda-tag")).toBeVisible();
    const box = page.locator("#encomendaCheckoutBox");
    await expect(box).toBeVisible();

    // Fase 3: a escolha de modalidade é obrigatória e o botão "Gerar Pix"
    // começa desabilitado até uma opção ser marcada — "Retirar na loja"
    // (frete zero) mantém o foco deste teste na confirmação de encomenda.
    // .evaluate() em vez de .check(): pode haver reflow logo após um
    // reload (banners/imagens assentando), e .check() falha por
    // "element is not stable" nesse instante — marcar o radio e
    // disparar "change" direto no DOM é equivalente e não depende de
    // estabilidade visual.
    await page.locator('[data-recebimento-radio][value="retirada"]').evaluate((el) => {
    el.checked = true;
    el.dispatchEvent(new Event("change", { bubbles: true }));
    });
    await expect(page.locator("[data-generate-pix]")).toBeEnabled();

    // Gerar Pix bloqueado sem a confirmação.
    await page.locator("[data-generate-pix]").click();
    await expect(page.locator("#pixStatus")).toContainText("Confirme que está ciente");

    await page.locator("#encomendaConfirm").check();
    await expect(page.locator("#encomendaConfirm")).toBeChecked();
  });
});

test.describe("Página da categoria Achados Místicos", () => {
  test("carrega os produtos sob encomenda e leva ao produto", async ({ page }) => {
    await mockApi(page);
    await page.goto("/achados-misticos/");

    await expect(page.locator("h1")).toHaveText("Achados Místicos");
    const card = page.locator(".achados-grid .achados-card");
    await expect(card).toHaveCount(1);
    await expect(card.locator(".product-badge-encomenda")).toBeVisible();
    await expect(card).toHaveAttribute("href", /produto\.html\?id=api-4242/);
    // O link do fornecedor nunca aparece no HTML público da categoria.
    expect(await page.content()).not.toContain(SUPPLIER_URL);
  });

  test("mostra estado vazio quando não há produtos sob encomenda", async ({ page }) => {
    await mockApi(page, []);
    await page.goto("/achados-misticos/");
    await expect(page.getByText("Novos achados chegando")).toBeVisible();
  });
});

test.describe("Página do produto sob encomenda", () => {
  test("exibe 'Como funciona a encomenda' e não expõe o fornecedor", async ({ page }) => {
    await mockApi(page);
    await page.goto("/produto.html?id=api-4242");

    await expect(page.locator(".product-page-card h1")).toHaveText("Turíbulo Ritualístico Importado");
    await expect(page.locator(".encomenda-info .encomenda-info-title")).toHaveText("Como funciona a encomenda");
    await expect(page.locator(".encomenda-prazo")).toContainText("10 dias úteis");
    expect(await page.content()).not.toContain(SUPPLIER_URL);
  });
});
