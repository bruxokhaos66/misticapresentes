// Testes E2E do painel administrativo "Isis — Homologação"
// (isis2-homolog-admin.js), injetado em admin.html só depois do login.
// Cobre: consultar/ativar/desativar o interruptor, buscar e autorizar um
// aluno pelo ID interno (nunca pelo e-mail digitado), remover um
// testador, revogar todos, confirmação antes de ações destrutivas, XSS
// na busca/listagem e fail-safe quando o backend falha.
const { test, expect } = require("@playwright/test");

async function mockLoginEMe(page) {
  await page.route("**/api/auth/login", route => route.fulfill({
    status: 200,
    contentType: "application/json",
    headers: { "set-cookie": "mistica_painel_sessao=valida; Path=/; HttpOnly" },
    body: JSON.stringify({ usuario: { nome: "Admin Teste", login: "admin-teste", perfil: "adm" } }),
  }));
  // site-config.js chama /api/auth/me automaticamente ao carregar
  // admin.html (restaurarSessao), antes de qualquer login manual --
  // precisa checar o cookie, senão o painel "abriria sozinho" no mock.
  await page.route("**/api/auth/me", route => {
    const cookie = route.request().headers()["cookie"] || "";
    if (cookie.includes("mistica_painel_sessao=valida")) {
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ usuario: { nome: "Admin Teste", login: "admin-teste", perfil: "adm" } }),
      });
    }
    return route.fulfill({ status: 401, contentType: "application/json", body: JSON.stringify({ detail: "sem sessao" }) });
  });
}

async function fazerLogin(page) {
  await mockLoginEMe(page);
  await page.goto("/admin.html");
  await page.fill("#adminUserLogin", "admin-teste");
  await page.fill("#adminPassword", "senha-qualquer");
  await page.click("#adminLoginForm button[type=submit]");
  await expect(page.locator("#adminContent")).toBeVisible();
}

const ALUNO_BUSCA = { aluno_id: 501, nome: "Aluna Homolog Teste", email: "aluna.homolog@exemplo.com" };
const TESTADOR = { aluno_id: 501, nome: "Aluna Homolog Teste", email: "aluna.homolog@exemplo.com", adicionado_por: "admin-teste", adicionado_em: "2026-07-17 10:00:00" };

test.describe("Painel admin — Isis — Homologação", () => {
  test("aparece só depois do login e mostra o estado consultado", async ({ page }) => {
    await page.route("**/api/isis2/homolog/estado", route => route.fulfill({
      status: 200, contentType: "application/json", body: JSON.stringify({ ativo: false, total_testadores: 0 }),
    }));
    await page.route("**/api/isis2/homolog-testers", route => route.fulfill({
      status: 200, contentType: "application/json", body: JSON.stringify([]),
    }));
    await mockLoginEMe(page);
    await page.goto("/admin.html");
    // Antes do login, #adminContent (e o painel dentro dele) fica oculto
    // -- o painel só é visível para quem já entrou com sucesso.
    await expect(page.locator("#adminContent")).toBeHidden();
    await expect(page.locator("#isis2HomologAdminPanel")).toBeHidden();

    await page.fill("#adminUserLogin", "admin-teste");
    await page.fill("#adminPassword", "senha-qualquer");
    await page.click("#adminLoginForm button[type=submit]");
    await expect(page.locator("#adminContent")).toBeVisible();
    await expect(page.locator("#isis2HomologAdminPanel")).toBeVisible();
    await expect(page.locator("[data-isis2-homolog-estado]")).toContainText("DESATIVADA");
  });

  test("ativar e desativar chamam os endpoints reais e atualizam o estado exibido", async ({ page }) => {
    let ativo = false;
    const chamadas = [];
    await page.route("**/api/isis2/homolog/estado", route => route.fulfill({
      status: 200, contentType: "application/json", body: JSON.stringify({ ativo, total_testadores: 0 }),
    }));
    await page.route("**/api/isis2/homolog-testers", route => route.fulfill({
      status: 200, contentType: "application/json", body: JSON.stringify([]),
    }));
    await page.route("**/api/isis2/homolog/ativar", route => {
      chamadas.push(`${route.request().method()} ativar`);
      ativo = true;
      route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ ok: true, ativo: true }) });
    });
    await page.route("**/api/isis2/homolog/desativar", route => {
      chamadas.push(`${route.request().method()} desativar`);
      ativo = false;
      route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ ok: true, ativo: false }) });
    });
    await fazerLogin(page);

    await page.click("[data-isis2-homolog-ativar]");
    await expect(page.locator("[data-isis2-homolog-estado]")).toContainText("ATIVA -");

    await page.click("[data-isis2-homolog-desativar]");
    await expect(page.locator("[data-isis2-homolog-estado]")).toContainText("DESATIVADA");

    expect(chamadas).toEqual(["POST ativar", "POST desativar"]);
  });

  test("busca por nome/e-mail e autoriza pelo ID interno (nunca pelo e-mail)", async ({ page }) => {
    const corposAutorizar = [];
    await page.route("**/api/isis2/homolog/estado", route => route.fulfill({
      status: 200, contentType: "application/json", body: JSON.stringify({ ativo: true, total_testadores: 0 }),
    }));
    await page.route("**/api/isis2/homolog-testers", route => {
      if (route.request().method() === "GET") {
        return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify([]) });
      }
      return route.continue();
    });
    await page.route("**/api/isis2/homolog/buscar-alunos**", route => route.fulfill({
      status: 200, contentType: "application/json", body: JSON.stringify([ALUNO_BUSCA]),
    }));
    await page.route(`**/api/isis2/homolog-testers/${ALUNO_BUSCA.aluno_id}`, route => {
      corposAutorizar.push(route.request().url());
      route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ ok: true }) });
    });
    await fazerLogin(page);

    await page.fill("[data-isis2-homolog-busca]", "Aluna Homolog");
    await expect(page.locator("[data-isis2-homolog-adicionar]")).toBeVisible();
    await page.click("[data-isis2-homolog-adicionar]");

    expect(corposAutorizar).toHaveLength(1);
    expect(corposAutorizar[0]).toContain(`/homolog-testers/${ALUNO_BUSCA.aluno_id}`);
    expect(corposAutorizar[0]).not.toContain(encodeURIComponent(ALUNO_BUSCA.email));
  });

  test("busca com menos de 2 caracteres não dispara chamada de rede", async ({ page }) => {
    let chamouBusca = false;
    await page.route("**/api/isis2/homolog/estado", route => route.fulfill({
      status: 200, contentType: "application/json", body: JSON.stringify({ ativo: false, total_testadores: 0 }),
    }));
    await page.route("**/api/isis2/homolog-testers", route => route.fulfill({
      status: 200, contentType: "application/json", body: JSON.stringify([]),
    }));
    await page.route("**/api/isis2/homolog/buscar-alunos**", route => {
      chamouBusca = true;
      route.fulfill({ status: 200, contentType: "application/json", body: "[]" });
    });
    await fazerLogin(page);

    await page.fill("[data-isis2-homolog-busca]", "a");
    await page.waitForTimeout(500);
    expect(chamouBusca).toBe(false);
  });

  test("lista testadores e remove um deles após confirmação", async ({ page }) => {
    let listaAtual = [TESTADOR];
    let removeuAlunoId = null;
    await page.route("**/api/isis2/homolog/estado", route => route.fulfill({
      status: 200, contentType: "application/json", body: JSON.stringify({ ativo: true, total_testadores: listaAtual.length }),
    }));
    await page.route("**/api/isis2/homolog-testers", route => {
      if (route.request().method() === "GET") {
        return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(listaAtual) });
      }
      return route.continue();
    });
    await page.route(`**/api/isis2/homolog-testers/${TESTADOR.aluno_id}`, route => {
      if (route.request().method() === "DELETE") {
        removeuAlunoId = TESTADOR.aluno_id;
        listaAtual = [];
        return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ ok: true }) });
      }
      return route.continue();
    });
    page.on("dialog", dialog => dialog.accept());
    await fazerLogin(page);

    await expect(page.locator("[data-isis2-homolog-remover]")).toBeVisible();
    await page.click("[data-isis2-homolog-remover]");

    expect(removeuAlunoId).toBe(TESTADOR.aluno_id);
    await expect(page.locator("[data-isis2-homolog-remover]")).toHaveCount(0);
  });

  test("remoção é cancelada se o admin não confirmar o diálogo", async ({ page }) => {
    let chamouRemover = false;
    await page.route("**/api/isis2/homolog/estado", route => route.fulfill({
      status: 200, contentType: "application/json", body: JSON.stringify({ ativo: true, total_testadores: 1 }),
    }));
    await page.route("**/api/isis2/homolog-testers", route => {
      if (route.request().method() === "GET") {
        return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify([TESTADOR]) });
      }
      return route.continue();
    });
    await page.route(`**/api/isis2/homolog-testers/${TESTADOR.aluno_id}`, route => {
      if (route.request().method() === "DELETE") chamouRemover = true;
      route.continue();
    });
    page.on("dialog", dialog => dialog.dismiss());
    await fazerLogin(page);

    await page.click("[data-isis2-homolog-remover]");
    await page.waitForTimeout(300);
    expect(chamouRemover).toBe(false);
  });

  test("'Revogar todos' pede confirmação e chama o endpoint de revogação em massa", async ({ page }) => {
    let revogouTodos = false;
    await page.route("**/api/isis2/homolog/estado", route => route.fulfill({
      status: 200, contentType: "application/json", body: JSON.stringify({ ativo: true, total_testadores: 1 }),
    }));
    await page.route("**/api/isis2/homolog-testers", route => {
      if (route.request().method() === "GET") {
        return route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify(revogouTodos ? [] : [TESTADOR]),
        });
      }
      return route.continue();
    });
    await page.route("**/api/isis2/homolog-testers/revogar-todos", route => {
      revogouTodos = true;
      route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ ok: true }) });
    });
    let dialogMensagem = "";
    page.on("dialog", dialog => { dialogMensagem = dialog.message(); dialog.accept(); });
    await fazerLogin(page);

    await page.click("[data-isis2-homolog-revogar-todos]");
    expect(dialogMensagem.toLowerCase()).toContain("revogar");
    await expect(page.locator("[data-isis2-homolog-remover]")).toHaveCount(0);
  });

  test("nome malicioso na busca/listagem nunca executa script (XSS)", async ({ page }) => {
    await page.addInitScript(() => { window.__isis2AdminXssFired = 0; });
    const alunoMalicioso = {
      aluno_id: 777,
      nome: '<img src=x onerror="window.__isis2AdminXssFired=1">Maliciosa',
      email: '"><svg onload="window.__isis2AdminXssFired=2">@exemplo.com',
    };
    await page.route("**/api/isis2/homolog/estado", route => route.fulfill({
      status: 200, contentType: "application/json", body: JSON.stringify({ ativo: true, total_testadores: 1 }),
    }));
    await page.route("**/api/isis2/homolog-testers", route => {
      if (route.request().method() === "GET") {
        return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify([{ ...alunoMalicioso, adicionado_por: "admin", adicionado_em: "2026-01-01" }]) });
      }
      return route.continue();
    });
    await page.route("**/api/isis2/homolog/buscar-alunos**", route => route.fulfill({
      status: 200, contentType: "application/json", body: JSON.stringify([alunoMalicioso]),
    }));
    await fazerLogin(page);

    await page.fill("[data-isis2-homolog-busca]", "Maliciosa");
    await page.waitForTimeout(500);
    await expect(page.locator("[data-isis2-homolog-busca-resultado]")).toContainText("Maliciosa");

    expect(await page.evaluate(() => window.__isis2AdminXssFired)).toBe(0);
    expect(await page.locator("[data-isis2-homolog-busca-resultado] script").count()).toBe(0);
    expect(await page.locator("[data-isis2-homolog-testers-list] script").count()).toBe(0);
  });

  test("falha do backend ao consultar estado mantém o painel mostrando DESATIVADA", async ({ page }) => {
    await page.route("**/api/isis2/homolog/estado", route => route.fulfill({ status: 500, contentType: "application/json", body: "{}" }));
    await page.route("**/api/isis2/homolog-testers", route => route.fulfill({ status: 500, contentType: "application/json", body: "{}" }));
    await fazerLogin(page);

    await expect(page.locator("[data-isis2-homolog-estado]")).toContainText("DESATIVADA");
  });

  test("todas as chamadas de leitura/ação usam credentials:include (cookie de sessão), nunca header com token embutido", async ({ page }) => {
    let headersDeAtivar = null;
    await page.route("**/api/isis2/homolog/estado", route => route.fulfill({
      status: 200, contentType: "application/json", body: JSON.stringify({ ativo: false, total_testadores: 0 }),
    }));
    await page.route("**/api/isis2/homolog-testers", route => route.fulfill({
      status: 200, contentType: "application/json", body: JSON.stringify([]),
    }));
    await page.route("**/api/isis2/homolog/ativar", async route => {
      headersDeAtivar = route.request().headers();
      await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ ok: true, ativo: true }) });
    });
    await fazerLogin(page);

    await page.click("[data-isis2-homolog-ativar]");
    expect(headersDeAtivar).not.toBeNull();
    expect(headersDeAtivar["x-mistica-api-key"]).toBeUndefined();
    expect(headersDeAtivar["authorization"]).toBeUndefined();
  });
});
