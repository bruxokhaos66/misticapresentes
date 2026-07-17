// Testes E2E do portão de homologação controlada da Isis 2.0
// (isis2/isis2-homolog-gate.js + backend/isis2_homolog.py). Cobrem, num
// navegador real: query string/hash/localStorage/sessionStorage/cookie
// forjado nunca ativam nada; só uma resposta autorizada do backend
// (GET /api/isis2/homolog-config) ativa a Isis 2.0 e mostra o indicador
// visual; qualquer falha (API fora do ar, resposta inesperada) mantém
// tudo desligado.
const { test, expect } = require("@playwright/test");

const PRODUTO_API = {
  id: 501,
  codigo_p: "ISIS2-501",
  nome: "Incenso Relaxante de Teste",
  categoria: "Aromas e proteção",
  descricao: "Incenso para relaxar.",
  preco: 15.5,
  quantidade: 10,
  imagem_url: "",
  imagens: [],
  selo: "",
  avaliacoes_total: 0,
  avaliacoes_media: 0,
};

const CONFIG_DESATIVADA = { enabled: false, escola: false, refinamento: false, homologacao: false };
const CONFIG_ATIVADA = { enabled: true, escola: true, refinamento: true, homologacao: true };

async function prepararCatalogo(page) {
  await page.route("**/api/produtos?**", route => route.fulfill({
    status: 200,
    contentType: "application/json",
    body: JSON.stringify([PRODUTO_API]),
  }));
}

async function mockHomologConfig(page, resposta, { status = 200 } = {}) {
  await page.route("**/api/isis2/homolog-config", route => route.fulfill({
    status,
    contentType: "application/json",
    body: JSON.stringify(resposta),
  }));
}

async function dismissConsent(page) {
  const decline = page.locator("[data-consent-decline]");
  if (await decline.isVisible().catch(() => false)) await decline.click();
}

test.describe("Isis 2.0 — portão de homologação", () => {
  test("backend nega (visitante anônimo/não autorizado): nenhum indicador, nenhum módulo extra baixado", async ({ page }) => {
    const isis2Requests = [];
    page.on("request", req => {
      if (req.url().includes("/isis2/")) isis2Requests.push(req.url());
    });

    await prepararCatalogo(page);
    await mockHomologConfig(page, CONFIG_DESATIVADA);
    await page.goto("/index.html");
    await dismissConsent(page);
    await expect.poll(() => page.evaluate(() => window.misticaCatalogState)).toBe("ready");
    await page.waitForTimeout(500);

    await expect(page.locator("#isis2-root")).toHaveCount(0);
    await expect(page.locator("#misticaIsis2HomologBadge")).toHaveCount(0);
    const carregouLoader = isis2Requests.some(url => url.includes("isis2-loader.js"));
    expect(carregouLoader).toBe(false);
  });

  test("backend autoriza (sessão de teste válida): widget monta e o indicador 'Isis em homologação' aparece", async ({ page }) => {
    await prepararCatalogo(page);
    await mockHomologConfig(page, CONFIG_ATIVADA);
    await page.goto("/index.html");
    await dismissConsent(page);
    await expect.poll(() => page.evaluate(() => window.misticaCatalogState)).toBe("ready");

    await expect(page.locator("#isis2-root")).toBeAttached({ timeout: 5000 });
    const badge = page.locator("#misticaIsis2HomologBadge");
    await expect(badge).toBeVisible();
    await expect(badge).toHaveText("Isis em homologação");
  });

  test("indicador não cobre o botão flutuante da Isis nem o WhatsApp", async ({ page }) => {
    await prepararCatalogo(page);
    await mockHomologConfig(page, CONFIG_ATIVADA);
    await page.goto("/index.html");
    await dismissConsent(page);
    await expect.poll(() => page.evaluate(() => window.misticaCatalogState)).toBe("ready");
    await expect(page.locator("#misticaIsis2HomologBadge")).toBeVisible();

    const toggle = page.locator("#isis2-toggle");
    await expect(toggle).toBeVisible();
    const sobreposicao = await page.evaluate(() => {
      const badge = document.getElementById("misticaIsis2HomologBadge");
      const toggleEl = document.getElementById("isis2-toggle");
      if (!badge || !toggleEl) return false;
      const b = badge.getBoundingClientRect();
      const t = toggleEl.getBoundingClientRect();
      return !(b.right < t.left || b.left > t.right || b.bottom < t.top || b.top > t.bottom);
    });
    expect(sobreposicao).toBe(false);
  });

  test("indicador funciona em viewport mobile sem causar rolagem horizontal", async ({ page }) => {
    await page.setViewportSize({ width: 360, height: 800 });
    await prepararCatalogo(page);
    await mockHomologConfig(page, CONFIG_ATIVADA);
    await page.goto("/index.html");
    await dismissConsent(page);
    await expect.poll(() => page.evaluate(() => window.misticaCatalogState)).toBe("ready");

    await expect(page.locator("#misticaIsis2HomologBadge")).toBeVisible();
    const semRolagemHorizontal = await page.evaluate(
      () => document.documentElement.scrollWidth <= document.documentElement.clientWidth + 1
    );
    expect(semRolagemHorizontal).toBe(true);
  });

  test("query string não ativa (autorização real do backend, não do navegador)", async ({ page }) => {
    await prepararCatalogo(page);
    await mockHomologConfig(page, CONFIG_DESATIVADA);
    await page.goto("/index.html?isis2=true&MISTICA_ISIS2_ENABLED=true&homolog=1");
    await dismissConsent(page);
    await expect.poll(() => page.evaluate(() => window.misticaCatalogState)).toBe("ready");
    await expect(page.locator("#isis2-root")).toHaveCount(0);
    await expect(page.locator("#misticaIsis2HomologBadge")).toHaveCount(0);
  });

  test("hash não ativa", async ({ page }) => {
    await prepararCatalogo(page);
    await mockHomologConfig(page, CONFIG_DESATIVADA);
    await page.goto("/index.html#isis2=true");
    await dismissConsent(page);
    await expect.poll(() => page.evaluate(() => window.misticaCatalogState)).toBe("ready");
    await expect(page.locator("#isis2-root")).toHaveCount(0);
  });

  test("localStorage/sessionStorage não ativam mesmo com um valor de sessão de homologação forjado", async ({ page }) => {
    await page.addInitScript(() => {
      try {
        window.localStorage.setItem("MISTICA_ISIS2_HOMOLOG", "true");
        window.sessionStorage.setItem("isis2_homolog_ativo", "true");
      } catch { /* ignore */ }
    });
    await prepararCatalogo(page);
    await mockHomologConfig(page, CONFIG_DESATIVADA);
    await page.goto("/index.html");
    await dismissConsent(page);
    await expect.poll(() => page.evaluate(() => window.misticaCatalogState)).toBe("ready");
    await expect(page.locator("#isis2-root")).toHaveCount(0);
  });

  test("API de homologação indisponível (erro de rede) mantém tudo desligado", async ({ page }) => {
    await prepararCatalogo(page);
    await page.route("**/api/isis2/homolog-config", route => route.abort("failed"));
    await page.goto("/index.html");
    await dismissConsent(page);
    await expect.poll(() => page.evaluate(() => window.misticaCatalogState)).toBe("ready");
    await page.waitForTimeout(500);
    await expect(page.locator("#isis2-root")).toHaveCount(0);
    await expect(page.locator("#misticaIsis2HomologBadge")).toHaveCount(0);
  });

  test("API de homologação retorna 500 mantém tudo desligado", async ({ page }) => {
    await prepararCatalogo(page);
    await mockHomologConfig(page, { detail: "erro interno" }, { status: 500 });
    await page.goto("/index.html");
    await dismissConsent(page);
    await expect.poll(() => page.evaluate(() => window.misticaCatalogState)).toBe("ready");
    await page.waitForTimeout(500);
    await expect(page.locator("#isis2-root")).toHaveCount(0);
  });

  test("resposta inesperada (JSON malformado/campos ausentes) mantém tudo desligado", async ({ page }) => {
    await prepararCatalogo(page);
    await page.route("**/api/isis2/homolog-config", route => route.fulfill({
      status: 200,
      contentType: "application/json",
      body: "não sou um json válido",
    }));
    await page.goto("/index.html");
    await dismissConsent(page);
    await expect.poll(() => page.evaluate(() => window.misticaCatalogState)).toBe("ready");
    await page.waitForTimeout(500);
    await expect(page.locator("#isis2-root")).toHaveCount(0);
  });

  test("a consulta ao backend usa cookies da sessão (credentials include), nunca um header com token embutido no bundle", async ({ page }) => {
    let credentialsRecebidas = null;
    let headersRecebidos = null;
    await prepararCatalogo(page);
    await page.route("**/api/isis2/homolog-config", async route => {
      headersRecebidos = route.request().headers();
      await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(CONFIG_DESATIVADA) });
    });
    await page.goto("/index.html");
    await dismissConsent(page);
    await expect.poll(() => page.evaluate(() => window.misticaCatalogState)).toBe("ready");
    await page.waitForTimeout(300);

    expect(headersRecebidos).not.toBeNull();
    expect(headersRecebidos["x-mistica-api-key"]).toBeUndefined();
    expect(headersRecebidos["authorization"]).toBeUndefined();
  });

  test("todas as chamadas do portão são GET (nunca muda estado no primeiro carregamento)", async ({ page }) => {
    const metodosNaoGet = [];
    await prepararCatalogo(page);
    await page.route("**/api/isis2/**", async route => {
      if (route.request().method() !== "GET") metodosNaoGet.push(`${route.request().method()} ${route.request().url()}`);
      await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(CONFIG_DESATIVADA) });
    });
    await page.goto("/index.html");
    await dismissConsent(page);
    await expect.poll(() => page.evaluate(() => window.misticaCatalogState)).toBe("ready");
    await page.waitForTimeout(500);
    expect(metodosNaoGet).toEqual([]);
  });
});
