// Kits por intenção: vitrines geradas a partir das mesmas categorias de
// intenção detectadas pela Isis (isis-guided.js), sem backend novo.
const { test, expect } = require("@playwright/test");

test.describe("Kits por intenção", () => {
  // index.html/kit.html carregam uma folha de estilo bloqueante do Google
  // Fonts (<link rel="stylesheet" href="https://fonts.googleapis.com/...">)
  // -- o evento "load" da página só dispara depois que o navegador resolve
  // (sucesso ou falha) esse recurso externo. Sob a rede deste ambiente de
  // teste, o tempo até essa falha é inconsistente (às vezes falha rápido,
  // às vezes demora o suficiente para estourar os 30s do teste), o que
  // deixava qualquer espera por "load"/"networkidle" (mesmo implícita, como
  // o `waitForURL` padrão) intermitentemente lenta. Interceptar e responder
  // esse recurso na hora remove essa variável de tempo externa dos testes,
  // sem alterar nada do site em produção (a interceptação existe só na
  // página do teste).
  test.beforeEach(async ({ page }) => {
    await page.route("**/fonts.googleapis.com/**", route => route.fulfill({ status: 200, contentType: "text/css", body: "" }));
  });

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
      page.waitForURL(/intencao=amor/, { waitUntil: "commit" }),
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
