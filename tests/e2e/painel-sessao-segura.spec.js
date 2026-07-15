const { test, expect } = require("@playwright/test");

// Cobre os dois achados corrigidos no PR fix/sessao-admin-segura:
// - api/painel.html gravava o token de API em localStorage.
// - painel-operacional.html gravava a sessão completa em sessionStorage.

test("api/painel.html não grava token/perfil/nome do app em localStorage", async ({ request }) => {
  const response = await request.get("/api/painel.html");
  expect(response.ok()).toBe(true);
  const source = await response.text();
  expect(source.includes("localStorage.setItem('MISTICA_API_TOKEN'")).toBe(false);
  expect(source.includes("localStorage.setItem('MISTICA_APP_NOME'")).toBe(false);
  expect(source.includes("localStorage.setItem('MISTICA_APP_PERFIL'")).toBe(false);
  expect(source.includes("localStorage.getItem('MISTICA_API_TOKEN')")).toBe(false);
});

test("painel-operacional.html não grava a sessão completa em sessionStorage", async ({ request }) => {
  const response = await request.get("/painel-operacional.html");
  expect(response.ok()).toBe(true);
  const source = await response.text();
  expect(source.includes('sessionStorage.setItem("misticaPainelSessao"')).toBe(false);
});

test.describe("api/painel.html: legado é apagado e nova sessão depende do cookie", () => {
  test.beforeEach(async ({ page }) => {
    await page.route("**/api/app/painel**", (route) => {
      const cookie = route.request().headers()["cookie"] || "";
      if (cookie.includes("mistica_app_sessao=valida")) {
        route.fulfill({
          status: 200,
          contentType: "application/json",
          headers: { "cache-control": "no-store" },
          body: JSON.stringify({
            gerado_em: "15/07/2026 10:00:00",
            usuario: { nome: "Teste", login: "teste", perfil: "adm" },
            metas_vendas: {},
            vendas_hoje: { quantidade: 0, faturamento: 0 },
            caixa: { aberto: false },
            ultimas_vendas: [],
            estoque_baixo: [],
            cancelamentos: [],
            contas_alerta: [],
            alertas_isis: { texto: "" },
          }),
        });
      } else {
        route.fulfill({ status: 401, contentType: "application/json", body: JSON.stringify({ detail: "sem sessao" }) });
      }
    });
    await page.route("**/api/app/login", (route) => {
      route.fulfill({
        status: 200,
        contentType: "application/json",
        headers: { "cache-control": "no-store", "set-cookie": "mistica_app_sessao=valida; Path=/; HttpOnly" },
        body: JSON.stringify({ ok: true, usuario: { nome: "Teste", login: "teste", perfil: "adm" }, mensagem: "ok" }),
      });
    });
    await page.route("**/api/app/logout", (route) => {
      route.fulfill({
        status: 200,
        contentType: "application/json",
        headers: { "cache-control": "no-store", "set-cookie": "mistica_app_sessao=; Path=/; Max-Age=0" },
        body: JSON.stringify({ ok: true }),
      });
    });
  });

  test("token/nome/perfil legados pré-carregados são removidos ao abrir a página, sem serem usados", async ({ page, context }) => {
    await context.addInitScript(() => {
      localStorage.setItem("MISTICA_API_TOKEN", "token-legado-vazado");
      localStorage.setItem("MISTICA_APP_NOME", "Fulano");
      localStorage.setItem("MISTICA_APP_PERFIL", "adm");
    });
    await page.goto("/api/painel.html");
    const storageAposCarga = await page.evaluate(() => ({
      token: localStorage.getItem("MISTICA_API_TOKEN"),
      nome: localStorage.getItem("MISTICA_APP_NOME"),
      perfil: localStorage.getItem("MISTICA_APP_PERFIL"),
    }));
    expect(storageAposCarga).toEqual({ token: null, nome: null, perfil: null });
    // sem cookie de sessão válido, o painel deve mostrar a tela de login, não os dados administrativos
    await expect(page.locator("#loginBox")).toBeVisible();
    await expect(page.locator("#painelConteudo")).toBeHidden();
  });

  test("login não grava token/senha/sessão em localStorage nem sessionStorage", async ({ page }) => {
    await page.goto("/api/painel.html");
    await page.fill("#loginLogin", "teste");
    await page.fill("#loginSenha", "senha-forte");
    await page.evaluate(() => { document.cookie = "mistica_app_sessao=valida; path=/"; });
    await page.click("text=Entrar");
    await expect(page.locator("#painelConteudo")).toBeVisible({ timeout: 5000 });

    const storage = await page.evaluate(() => {
      const tudoLocal = { ...localStorage };
      const tudoSessao = { ...sessionStorage };
      return { tudoLocal, tudoSessao };
    });
    const chavesProibidas = ["MISTICA_API_TOKEN", "MISTICA_APP_NOME", "MISTICA_APP_PERFIL", "sessao", "senha"];
    for (const chave of chavesProibidas) {
      expect(Object.keys(storage.tudoLocal)).not.toContain(chave);
      expect(Object.keys(storage.tudoSessao)).not.toContain(chave);
    }
    expect(JSON.stringify(storage.tudoLocal)).not.toContain("senha-forte");
    expect(JSON.stringify(storage.tudoSessao)).not.toContain("senha-forte");

    const senhaField = await page.locator("#loginSenha").inputValue();
    expect(senhaField).toBe("");
  });

  test("logout limpa a UI e reload volta a exigir sessão", async ({ page, context }) => {
    await context.addCookies([{ name: "mistica_app_sessao", value: "valida", domain: "127.0.0.1", path: "/" }]);
    await page.goto("/api/painel.html");
    await expect(page.locator("#painelConteudo")).toBeVisible({ timeout: 5000 });

    await page.click("text=Sair");
    await expect(page.locator("#loginBox")).toBeVisible();
    await expect(page.locator("#painelConteudo")).toBeHidden();

    await context.clearCookies();
    await page.reload();
    await expect(page.locator("#loginBox")).toBeVisible();
    await expect(page.locator("#painelConteudo")).toBeHidden();
  });
});
