// Testes E2E do widget Isis 2.0 (assistente virtual modular), aditivo ao
// site público: verifica que o botão flutuante abre a conversa, que uma
// recomendação real do catálogo aparece, que "adicionar ao carrinho"
// funciona (reaproveitando window.addToCart de app.js) e faz uma
// checagem básica de acessibilidade (roles/aria) e mobile.
const { test, expect } = require("@playwright/test");

const PRODUTO_API = {
  id: 501,
  codigo_p: "ISIS2-501",
  nome: "Incenso Relaxante de Teste",
  categoria: "Aromas e proteção",
  descricao: "Incenso para relaxar, acalmar a mente e limpar o ambiente.",
  preco: 15.5,
  quantidade: 10,
  imagem_url: "",
  imagens: [],
  selo: "",
  avaliacoes_total: 0,
  avaliacoes_media: 0,
};

async function prepararCatalogo(page, produtos = [PRODUTO_API]) {
  await page.route("**/api/produtos?**", route => route.fulfill({
    status: 200,
    contentType: "application/json",
    body: JSON.stringify(produtos),
  }));
}

async function dismissConsent(page) {
  const decline = page.locator("[data-consent-decline]");
  if (await decline.isVisible().catch(() => false)) await decline.click();
}

async function irParaHomeComCatalogo(page) {
  await prepararCatalogo(page);
  await page.goto("/index.html");
  await dismissConsent(page);
  await expect.poll(() => page.evaluate(() => window.misticaCatalogState)).toBe("ready");
}

test.describe("Isis 2.0 - widget flutuante", () => {
  test("botão flutuante abre a conversa e mostra a mensagem de boas-vindas", async ({ page }) => {
    await irParaHomeComCatalogo(page);

    const toggle = page.locator("#isis2-toggle");
    await expect(toggle).toBeVisible();
    await toggle.click();

    const panel = page.locator("#isis2-panel");
    await expect(panel).toBeVisible();
    await expect(panel).not.toHaveAttribute("hidden", "");
    await expect(page.locator("#isis2-messages")).toContainText("Isis", { timeout: 5000 });
  });

  test("recomenda um produto real do catálogo e permite adicionar ao carrinho", async ({ page }) => {
    await irParaHomeComCatalogo(page);

    await page.locator("#isis2-toggle").click();
    await page.locator("#isis2-input").fill("Quero um incenso para relaxar");
    await page.locator("#isis2-form button[type=submit]").click();

    const card = page.locator(".isis2-card", { hasText: "Incenso Relaxante de Teste" });
    await expect(card).toBeVisible({ timeout: 5000 });

    await card.locator("[data-isis2-add]").click();
    await expect(page.locator("#cartList")).toContainText("Incenso Relaxante de Teste");
  });

  test("filtra recomendação por orçamento informado na frase", async ({ page }) => {
    await irParaHomeComCatalogo(page, [
      PRODUTO_API,
      { ...PRODUTO_API, id: 502, codigo_p: "ISIS2-502", nome: "Kit Presente Caro de Teste", preco: 250, categoria: "Kits e presentes" },
    ]);

    await page.locator("#isis2-toggle").click();
    await page.locator("#isis2-input").fill("Quero um presente até R$50");
    await page.locator("#isis2-form button[type=submit]").click();

    await expect(page.locator(".isis2-card")).toContainText("Incenso Relaxante de Teste", { timeout: 5000 });
    await expect(page.locator(".isis2-message-bot").last()).not.toContainText("Kit Presente Caro de Teste");
  });

  test("não substitui nem remove o chat legado da Isis", async ({ page }) => {
    await irParaHomeComCatalogo(page);
    await expect(page.locator("#isisChat")).toBeAttached();
    await expect(page.locator("#isisForm")).toBeAttached();
    await expect(page.locator("#isis2-root")).toBeAttached();
  });

  test("painel tem role de diálogo e o log de mensagens é anunciável (acessibilidade)", async ({ page }) => {
    await irParaHomeComCatalogo(page);
    await page.locator("#isis2-toggle").click();

    await expect(page.locator("#isis2-panel")).toHaveAttribute("role", "dialog");
    await expect(page.locator("#isis2-messages")).toHaveAttribute("role", "log");
    await expect(page.locator("#isis2-messages")).toHaveAttribute("aria-live", "polite");
    await expect(page.locator("#isis2-toggle")).toHaveAttribute("aria-label", /.+/);

    await page.keyboard.press("Escape");
    await expect(page.locator("#isis2-panel")).toBeHidden();
  });
});

test.describe("Isis 2.0 - mobile", () => {
  test.use({ viewport: { width: 390, height: 844 } });

  test("widget cabe na tela pequena e permanece utilizável", async ({ page }) => {
    await irParaHomeComCatalogo(page);
    await page.locator("#isis2-toggle").click();

    const panel = page.locator("#isis2-panel");
    await expect(panel).toBeVisible();
    const box = await panel.boundingBox();
    expect(box.width).toBeLessThanOrEqual(390);
  });
});
