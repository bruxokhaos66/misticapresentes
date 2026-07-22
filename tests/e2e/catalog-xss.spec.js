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
  // Sem imagem cadastrada (imagem_url inválida), o card usa a foto de
  // fallback local da própria Mística — nunca dados vindos da API.
  const img = page.locator(".product-card img");
  await expect(img).toHaveCount(1);
  await expect(img).toHaveAttribute("src", /\/assets\/images\/produto-sem-imagem\.webp$/);
  await page.waitForTimeout(200);

  expect(await page.evaluate(() => window.__catalogInjectionExecuted)).toBe(0);
  expect(await page.locator(".product-card script").count()).toBe(0);
  // O card premium não usa mais nenhum <svg> decorativo (o "Ver detalhes"
  // agora é texto simples, sem gaveta/chevron). Portanto o payload injetado
  // via categoria (<svg onload=...>) não pode aparecer como elemento SVG
  // de verdade em lugar nenhum do card.
  const svgs = page.locator(".product-card svg");
  await expect(svgs).toHaveCount(0);
});
