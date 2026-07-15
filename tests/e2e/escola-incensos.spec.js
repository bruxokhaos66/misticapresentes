const { test, expect } = require("@playwright/test");

const INCENSOS_IMAGES = [
  "assets/escola/incensos/incensos-curso-capa.webp",
  "assets/escola/incensos/modulo-1-capa.webp",
  "assets/escola/incensos/aula-1-o-que-e-incenso.webp",
  "assets/escola/incensos/aula-2-historia-incensos.webp",
  "assets/escola/incensos/aula-3-por-que-usamos-incensos.webp",
];

test.describe("imagens do módulo de incensos", () => {
  for (const path of INCENSOS_IMAGES) {
    test(`${path} existe, é WebP real 1200x630`, async ({ page, request }) => {
      const response = await request.get(`/${path}`);
      expect(response.status()).toBe(200);
      expect(response.headers()["content-type"]).toBe("image/webp");

      await page.goto("/escola-incensos.html");
      const dimensions = await page.evaluate(src => new Promise((resolve, reject) => {
        const img = new Image();
        img.onload = () => resolve({ width: img.naturalWidth, height: img.naturalHeight });
        img.onerror = reject;
        img.src = src;
      }), `/${path}`);
      expect(dimensions).toEqual({ width: 1200, height: 630 });
    });
  }

  test("nenhuma referência a SVG antigo ou upload temporário permanece no código", async () => {
    const fs = require("fs");
    const files = [
      "escola-incensos.html",
      "escola-incensos.js",
      "escola-incensos.css",
      "escola-incensos-catalog.js",
      "escola-incensos-assets.js",
    ];
    for (const file of files) {
      const content = fs.readFileSync(file, "utf8");
      expect(content).not.toMatch(/escola\/incensos\/.*\.svg/);
      expect(content).not.toMatch(/\.webp\.png/);
      expect(content).not.toMatch(/escola\/xamanismo\/.*incenso/i);
    }
  });
});

for (const viewport of [
  { name: "desktop", width: 1366, height: 768 },
  { name: "Pixel 7", width: 412, height: 915 },
]) {
  test.describe(`módulo de incensos — ${viewport.name}`, () => {
    test.use({ viewport: { width: viewport.width, height: viewport.height } });

    test("abre sem login, navega nas 3 aulas e salva progresso apenas na sessão", async ({ page }) => {
      const errors = [];
      const failedAssets = [];
      page.on("console", msg => { if (msg.type() === "error" && !/Failed to load resource/i.test(msg.text())) errors.push(msg.text()); });
      page.on("response", response => { if (response.status() >= 400 && response.url().includes("assets/escola/incensos")) failedAssets.push(response.url()); });

      const heroBackground = async () => page.locator(".incensos-article:not([hidden]) .incensos-hero").evaluate(el => getComputedStyle(el).backgroundImage);

      await page.goto("/escola-incensos.html");
      await expect(page.getByRole("heading", { name: "O que é um incenso?" }).first()).toBeVisible();
      await expect(page.getByText("0 de 3 aulas concluídas")).toBeVisible();
      await expect.poll(heroBackground).toContain("aula-1-o-que-e-incenso.webp");

      await page.getByRole("button", { name: /Marcar como concluída e continuar/ }).click();
      await expect(page.getByRole("heading", { name: "A história dos incensos" }).first()).toBeVisible();
      await expect(page.getByText("1 de 3 aulas concluídas")).toBeVisible();
      await expect.poll(heroBackground).toContain("aula-2-historia-incensos.webp");

      await page.getByRole("button", { name: /Marcar como concluída e continuar/ }).click();
      await expect(page.getByRole("heading", { name: "Por que ainda usamos incensos?" }).first()).toBeVisible();
      await expect.poll(heroBackground).toContain("aula-3-por-que-usamos-incensos.webp");
      await page.getByRole("button", { name: "Concluir o módulo ✓" }).click();
      await expect(page.getByRole("heading", { name: "Módulo concluído" })).toBeVisible();
      await expect(page.getByText("3 de 3 aulas concluídas")).toBeVisible();

      const storage = await page.evaluate(() => ({
        session: sessionStorage.getItem("misticaIncensosModulo1"),
        local: localStorage.getItem("misticaIncensosModulo1"),
        overflow: document.documentElement.scrollWidth > window.innerWidth + 1,
      }));
      expect(JSON.parse(storage.session).done).toEqual([1, 2, 3]);
      expect(storage.local).toBeNull();
      expect(storage.overflow).toBe(false);
      expect(failedAssets).toEqual([]);
      expect(errors).toEqual([]);
    });

    test("hero nunca fica vazio e altura permanece estável ao alternar aulas 10x", async ({ page }) => {
      const errors = [];
      const failedAssets = [];
      page.on("console", msg => { if (msg.type() === "error" && !/Failed to load resource/i.test(msg.text())) errors.push(msg.text()); });
      page.on("response", response => { if (response.status() >= 400 && response.url().includes("assets/escola/incensos")) failedAssets.push(response.url()); });

      await page.goto("/escola-incensos.html");
      const hero = page.locator(".incensos-article:not([hidden]) .incensos-hero");
      const heights = new Set();

      for (let i = 0; i < 10; i += 1) {
        const lessonId = (i % 3) + 1;
        await page.locator(`[data-lesson="${lessonId}"]`).click();
        const bg = await hero.evaluate(el => getComputedStyle(el).backgroundImage);
        expect(bg).not.toBe("none");
        expect(bg.length).toBeGreaterThan(0);
        heights.add(await hero.evaluate(el => Math.round(el.getBoundingClientRect().height)));
      }

      expect(heights.size).toBe(1);
      expect(failedAssets).toEqual([]);
      expect(errors).toEqual([]);
    });
  });
}

test.describe("catálogo da Escola", () => {
  test("card de incensos usa capa WebP, sem SVG", async ({ page }) => {
    await page.goto("/escola.html");
    const cover = page.locator('[data-course="incensos-introducao"] .escola-card-cover');
    await expect(cover).toBeVisible();
    const src = await cover.getAttribute("src");
    expect(src).toContain("incensos-curso-capa.webp");
    expect(src).not.toContain(".svg");
  });
});
