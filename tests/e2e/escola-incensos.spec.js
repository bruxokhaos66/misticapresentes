const { test, expect } = require("@playwright/test");

for (const viewport of [
  { name: "desktop", width: 1366, height: 768 },
  { name: "Pixel 7", width: 412, height: 915 },
]) {
  test.describe(`módulo de incensos — ${viewport.name}`, () => {
    test.use({ viewport: { width: viewport.width, height: viewport.height } });

    test("abre sem login, navega nas 3 aulas e salva progresso apenas na sessão", async ({ page }) => {
      const errors = [];
      const failedAssets = [];
      page.on("console", msg => { if (msg.type() === "error" && !msg.text().includes("fonts.googleapis.com")) errors.push(msg.text()); });
      page.on("response", response => { if (response.status() >= 400 && response.url().includes("assets/escola/incensos")) failedAssets.push(response.url()); });

      await page.goto("/escola-incensos.html");
      await expect(page.getByRole("heading", { name: "O que é um incenso?" }).first()).toBeVisible();
      await expect(page.getByText("0 de 3 aulas concluídas")).toBeVisible();

      await page.getByRole("button", { name: /Marcar como concluída e continuar/ }).click();
      await expect(page.getByRole("heading", { name: "A história dos incensos" }).first()).toBeVisible();
      await expect(page.getByText("1 de 3 aulas concluídas")).toBeVisible();

      await page.getByRole("button", { name: /Marcar como concluída e continuar/ }).click();
      await expect(page.getByRole("heading", { name: "Por que ainda usamos incensos?" }).first()).toBeVisible();
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
  });
}
