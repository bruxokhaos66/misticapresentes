const { test, expect } = require("@playwright/test");

const MEDICINAS_IMAGES = [
  "assets/escola/medicinas-floresta/medicinas-floresta-capa.webp",
  "assets/escola/medicinas-floresta/rape-ayahuasca-primeiros-caminhos.webp",
];

test.describe("imagens do módulo de medicinas da floresta", () => {
  for (const path of MEDICINAS_IMAGES) {
    test(`${path} existe, é WebP real 1200x630`, async ({ page, request }) => {
      const response = await request.get(`/${path}`);
      expect(response.status()).toBe(200);
      expect(response.headers()["content-type"]).toBe("image/webp");

      await page.goto("/escola-medicinas-floresta.html");
      const dimensions = await page.evaluate(src => new Promise((resolve, reject) => {
        const img = new Image();
        img.onload = () => resolve({ width: img.naturalWidth, height: img.naturalHeight });
        img.onerror = reject;
        img.src = src;
      }), `/${path}`);
      expect(dimensions).toEqual({ width: 1200, height: 630 });
    });
  }

  test("PNGs temporários de upload não existem mais e não são referenciados", async ({ request }) => {
    const fs = require("fs");
    for (const file of [
      "assets/medicinasdaflorestaprimeiroscaminhos.png",
      "assets/medicinasdaflorestayausca.png",
    ]) {
      expect(fs.existsSync(file)).toBe(false);
      const response = await request.get(`/${file}`);
      expect(response.status()).toBe(404);
    }

    const files = [
      "escola-medicinas-floresta.html",
      "escola-medicinas-floresta.js",
      "escola-medicinas-floresta.css",
      "escola-medicinas-floresta-catalog.js",
      "escola-medicinas-floresta-assets.js",
    ];
    for (const file of files) {
      const content = fs.readFileSync(file, "utf8");
      expect(content).not.toMatch(/medicinasdaflorestaprimeiroscaminhos\.png/);
      expect(content).not.toMatch(/medicinasdaflorestayausca\.png/);
    }
  });
});

for (const viewport of [
  { name: "desktop", width: 1366, height: 768 },
  { name: "Pixel 7", width: 412, height: 915 },
]) {
  test.describe(`aula de rapé e ayahuasca — ${viewport.name}`, () => {
    test.use({ viewport: { width: viewport.width, height: viewport.height } });

    test("abre sem login, conclui a aula e salva progresso só na sessão", async ({ page }) => {
      const errors = [];
      const failedAssets = [];
      page.on("console", msg => {
        if (msg.type() === "error" && !/Failed to load resource/i.test(msg.text())) errors.push(msg.text());
      });
      page.on("response", response => {
        if (response.status() >= 400 && response.url().includes("assets/escola/medicinas-floresta")) failedAssets.push(response.url());
      });

      const heroBackground = () => page.locator(".medicinas-hero").evaluate(el => getComputedStyle(el).backgroundImage);

      await page.goto("/escola-medicinas-floresta.html");
      await expect(page.getByRole("heading", { name: "Rapé e ayahuasca: primeiros caminhos" }).first()).toBeVisible();
      await expect(page.getByText("0 de 1 aula concluída")).toBeVisible();
      await expect(page.locator(".medicinas-warning")).toContainText(/não ensina preparo, dosagem, aplicação ou condução de cerimônias/i);
      await expect(page.getByRole("link", { name: "Conhecer o curso de Rapé" })).toBeVisible();
      await expect(page.getByRole("link", { name: "Conhecer o curso de Ayahuasca" })).toBeVisible();
      await expect.poll(heroBackground).toContain("rape-ayahuasca-primeiros-caminhos.webp");

      await page.getByRole("button", { name: "Concluir a aula ✓" }).click();
      await expect(page.getByRole("heading", { name: "Aula concluída" })).toBeVisible();
      await expect(page.getByText("1 de 1 aula concluída")).toBeVisible();

      const storage = await page.evaluate(() => ({
        session: sessionStorage.getItem("misticaMedicinasFlorestaAula1"),
        local: localStorage.getItem("misticaMedicinasFlorestaAula1"),
        overflow: document.documentElement.scrollWidth > window.innerWidth + 1,
      }));
      expect(storage.session).toBe("done");
      expect(storage.local).toBeNull();
      expect(storage.overflow).toBe(false);
      expect(failedAssets).toEqual([]);
      expect(errors).toEqual([]);
    });

    test("hero nunca fica vazio e altura permanece estável ao rolar 10x", async ({ page }) => {
      const errors = [];
      const failedAssets = [];
      page.on("console", msg => {
        if (msg.type() === "error" && !/Failed to load resource/i.test(msg.text())) errors.push(msg.text());
      });
      page.on("response", response => {
        if (response.status() >= 400 && response.url().includes("assets/escola/medicinas-floresta")) failedAssets.push(response.url());
      });

      await page.goto("/escola-medicinas-floresta.html");
      const hero = page.locator(".medicinas-hero");
      const heights = new Set();

      const bg0 = await hero.evaluate(el => getComputedStyle(el).backgroundImage);
      expect(bg0).not.toBe("none");

      for (let i = 0; i < 10; i += 1) {
        await page.mouse.wheel(0, i % 2 === 0 ? 600 : -600);
        const bg = await hero.evaluate(el => getComputedStyle(el).backgroundImage);
        expect(bg).not.toBe("none");
        expect(bg.length).toBeGreaterThan(0);
        heights.add(await hero.evaluate(el => Math.round(el.getBoundingClientRect().height)));
      }

      await page.getByRole("button", { name: "Concluir a aula ✓" }).click();
      await page.evaluate(() => window.scrollTo(0, 0));
      await expect(hero).toBeVisible();

      expect(heights.size).toBe(1);
      expect(failedAssets).toEqual([]);
      expect(errors).toEqual([]);
    });
  });
}

test.describe("catálogo da Escola", () => {
  test("card de medicinas da floresta usa capa WebP correta", async ({ page }) => {
    await page.goto("/escola.html");
    const cover = page.locator('[data-course="medicinas-floresta-introducao"] .escola-card-cover');
    await expect(cover).toBeVisible();
    const src = await cover.getAttribute("src");
    expect(src).toContain("medicinas-floresta-capa.webp");
    expect(src).not.toContain(".png");
  });
});
