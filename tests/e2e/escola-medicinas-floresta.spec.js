const { test, expect } = require("@playwright/test");

for (const viewport of [
  { name: "desktop", width: 1366, height: 768 },
  { name: "Pixel 7", width: 412, height: 915 },
]) {
  test.describe(`aula de rapé e ayahuasca — ${viewport.name}`, () => {
    test.use({ viewport: { width: viewport.width, height: viewport.height } });

    test("abre sem login, conclui a aula e salva progresso só na sessão", async ({ page }) => {
      const errors = [];
      page.on("console", msg => {
        if (msg.type() === "error" && !msg.text().includes("fonts.googleapis.com")) errors.push(msg.text());
      });

      await page.goto("/escola-medicinas-floresta.html");
      await expect(page.getByRole("heading", { name: "Rapé e ayahuasca: primeiros caminhos" }).first()).toBeVisible();
      await expect(page.getByText("0 de 1 aula concluída")).toBeVisible();
      await expect(page.getByText(/não ensina preparo, dosagem, aplicação ou condução de cerimônias/i)).toBeVisible();
      await expect(page.getByRole("link", { name: "Conhecer o curso de Rapé" })).toBeVisible();
      await expect(page.getByRole("link", { name: "Conhecer o curso de Ayahuasca" })).toBeVisible();

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
      expect(errors).toEqual([]);
    });
  });
}
