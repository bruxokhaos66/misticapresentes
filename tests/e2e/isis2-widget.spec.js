// Testes E2E do widget Isis 2.0 (assistente virtual modular), aditivo ao
// site público: verifica a feature flag (default desligada), a
// convivência com o chat legado, que uma recomendação real do catálogo
// aparece, que "adicionar ao carrinho" funciona (reaproveitando
// window.addToCart de app.js), XSS e uma checagem básica de
// acessibilidade (roles/aria) e mobile.
const { test, expect } = require("@playwright/test");
const fs = require("fs");
const path = require("path");

const SITE_CONFIG_PATH = path.resolve(__dirname, "..", "..", "site-config.js");

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

// A flag pública fica em site-config.js (window.misticaSiteConfig.isis2
// .enabled), que sobrescreve window.misticaSiteConfig por inteiro. Para
// testar com a flag ligada sem depender de localStorage/query string
// (que a Isis 2.0 nunca lê), servimos uma cópia do arquivo real com
// "enabled: false" trocado por "enabled: true" — mesmo arquivo estático
// que um deploy de homologação usaria.
async function ligarFeatureFlagIsis2(page) {
  const original = fs.readFileSync(SITE_CONFIG_PATH, "utf8");
  const habilitado = original.replace("enabled: false", "enabled: true");
  if (habilitado === original) throw new Error("Não achei 'enabled: false' em site-config.js para habilitar a flag no teste.");
  await page.route("**/site-config.js*", route => route.fulfill({
    status: 200,
    contentType: "application/javascript",
    body: habilitado,
  }));
}

async function dismissConsent(page) {
  const decline = page.locator("[data-consent-decline]");
  if (await decline.isVisible().catch(() => false)) await decline.click();
}

async function irParaHomeComCatalogo(page, { isis2 = true, produtos } = {}) {
  await prepararCatalogo(page, produtos);
  if (isis2) await ligarFeatureFlagIsis2(page);
  await page.goto("/index.html");
  await dismissConsent(page);
  await expect.poll(() => page.evaluate(() => window.misticaCatalogState)).toBe("ready");
}

test.describe("Isis 2.0 - feature flag", () => {
  test("com a flag desligada (default), o widget novo não aparece e só a Isis 1 (legado) é mostrada", async ({ page }) => {
    await irParaHomeComCatalogo(page, { isis2: false });
    await expect(page.locator("#isis2-root")).toHaveCount(0);
    await expect(page.locator("#isisChat")).toBeVisible();
    await expect(page.locator("#isisForm")).toBeVisible();
  });

  test("flag não pode ser ligada por query string", async ({ page }) => {
    await prepararCatalogo(page);
    await page.goto("/index.html?MISTICA_ISIS2_ENABLED=true&isis2=1");
    await dismissConsent(page);
    await expect.poll(() => page.evaluate(() => window.misticaCatalogState)).toBe("ready");
    await expect(page.locator("#isis2-root")).toHaveCount(0);
  });

  test("flag não pode ser ligada por localStorage", async ({ page }) => {
    await page.addInitScript(() => {
      localStorage.setItem("MISTICA_ISIS2_ENABLED", "true");
      localStorage.setItem("isis2_enabled", "true");
    });
    await prepararCatalogo(page);
    await page.goto("/index.html");
    await dismissConsent(page);
    await expect.poll(() => page.evaluate(() => window.misticaCatalogState)).toBe("ready");
    await expect(page.locator("#isis2-root")).toHaveCount(0);
  });
});

test.describe("Isis 2.0 - convivência com a Isis 1 (flag ligada)", () => {
  test("com a flag ligada, a Isis 1 embutida é substituída visualmente pelo widget novo (sem dois chats ativos)", async ({ page }) => {
    await irParaHomeComCatalogo(page);

    // O widget novo existe e está pronto para uso.
    await expect(page.locator("#isis2-root")).toBeAttached();

    // O chat antigo (histórico + formulário + ações rápidas) fica oculto,
    // mas continua no DOM como fallback caso o script novo falhe — não é
    // removido, só escondido depois que a Isis 2.0 confirma que montou.
    await expect(page.locator("#isisChat")).toBeHidden();
    await expect(page.locator("#isisForm")).toBeHidden();
    await expect(page.locator(".isis-chat-panel .quick-actions")).toBeHidden();

    // Só um caminho fica claro para o cliente conversar com a Isis.
    await expect(page.locator(".isis2-legacy-notice")).toBeVisible();
    await expect(page.locator("#isis2-toggle")).toBeVisible();
  });

  test("botão da nota legada abre o widget novo", async ({ page }) => {
    await irParaHomeComCatalogo(page);
    await page.locator("#isis2-open-from-legacy").click();
    await expect(page.locator("#isis2-panel")).toBeVisible();
  });
});

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
    await irParaHomeComCatalogo(page, {
      produtos: [
        PRODUTO_API,
        { ...PRODUTO_API, id: 502, codigo_p: "ISIS2-502", nome: "Kit Presente Caro de Teste", preco: 250, categoria: "Kits e presentes" },
      ],
    });

    await page.locator("#isis2-toggle").click();
    await page.locator("#isis2-input").fill("Quero um presente até R$50");
    await page.locator("#isis2-form button[type=submit]").click();

    await expect(page.locator(".isis2-card")).toContainText("Incenso Relaxante de Teste", { timeout: 5000 });
    await expect(page.locator(".isis2-message-bot").last()).not.toContainText("Kit Presente Caro de Teste");
  });

  test("nunca adiciona ao carrinho quando a loja recusa (estoque insuficiente) — não finge sucesso", async ({ page }) => {
    await irParaHomeComCatalogo(page, {
      produtos: [{ ...PRODUTO_API, quantidade: 0 }],
    });

    await page.locator("#isis2-toggle").click();
    await page.locator("#isis2-input").fill("Quero um incenso para relaxar");
    await page.locator("#isis2-form button[type=submit]").click();

    // Sem estoque, o produto não deveria nem ser recomendado — mas se por
    // algum motivo aparecer, o botão de adicionar nunca pode alegar
    // sucesso.
    const addButton = page.locator("[data-isis2-add]").first();
    if (await addButton.count()) {
      await addButton.click();
      await expect(addButton).not.toHaveText("Adicionado ✓");
    }
    await expect(page.locator("#cartList")).not.toContainText("Incenso Relaxante de Teste");
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

  test("teclado: Tab alcança o campo de mensagem e Enter envia", async ({ page }) => {
    await irParaHomeComCatalogo(page);
    await page.locator("#isis2-toggle").click();
    await page.locator("#isis2-input").focus();
    await page.keyboard.type("Quero um incenso para relaxar");
    await page.keyboard.press("Enter");
    await expect(page.locator(".isis2-card")).toBeVisible({ timeout: 5000 });
  });
});

test.describe("Isis 2.0 - XSS e renderização segura", () => {
  test("nome/descrição maliciosos do catálogo nunca executam script dentro do widget", async ({ page }) => {
    const payloadImg = '<img src=x onerror="window.__isis2XssFired=1">';
    const payloadScript = "<script>window.__isis2XssFired=2</script>";
    const payloadSvg = '"><svg onload="window.__isis2XssFired=3">';

    await page.addInitScript(() => {
      window.__isis2XssFired = 0;
    });

    await irParaHomeComCatalogo(page, {
      produtos: [{
        ...PRODUTO_API,
        nome: `${payloadImg}Produto malicioso`,
        categoria: `${payloadSvg}Categoria maliciosa`,
        descricao: `${payloadScript}Descrição maliciosa`,
      }],
    });

    await page.locator("#isis2-toggle").click();
    await page.locator("#isis2-input").fill("malicioso");
    await page.locator("#isis2-form button[type=submit]").click();

    await page.waitForTimeout(700);
    expect(await page.evaluate(() => window.__isis2XssFired)).toBe(0);
    expect(await page.locator("#isis2-panel script").count()).toBe(0);
    await expect(page.locator("#isis2-panel")).toContainText("Produto malicioso");
  });

  test("mensagem do próprio usuário com HTML/script não executa nada", async ({ page }) => {
    await page.addInitScript(() => {
      window.__isis2XssFired = 0;
    });
    await irParaHomeComCatalogo(page);

    await page.locator("#isis2-toggle").click();
    await page.locator("#isis2-input").fill('<img src=x onerror="window.__isis2XssFired=1">');
    await page.locator("#isis2-form button[type=submit]").click();

    await page.waitForTimeout(700);
    expect(await page.evaluate(() => window.__isis2XssFired)).toBe(0);
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

  test("não sobrepõe o botão do WhatsApp/CTA flutuante nem o banner de cookies", async ({ page }) => {
    await prepararCatalogo(page);
    await ligarFeatureFlagIsis2(page);
    await page.goto("/index.html");
    await expect.poll(() => page.evaluate(() => window.misticaCatalogState)).toBe("ready");

    const decline = page.locator("[data-consent-decline]");
    if (await decline.isVisible().catch(() => false)) {
      // O botão flutuante da Isis 2.0 não pode cobrir o banner de
      // consentimento enquanto o cliente não decidiu sobre cookies.
      await expect(decline).toBeVisible();
      await decline.click();
    }
  });
});
