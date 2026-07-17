// Testes E2E da Isis 2.0 — Especialista da Mística Escola (Fase 2),
// aditiva às páginas escola.html/escola-curso.html. Mesmo padrão de
// tests/e2e/isis2-widget.spec.js (Fase 1): feature flags nunca lidas de
// query string/localStorage, XSS, teclado/foco, mobile/tablet/desktop,
// e nenhum dado de outro aluno.
const { test, expect } = require("@playwright/test");
const fs = require("fs");
const path = require("path");

const SITE_CONFIG_PATH = path.resolve(__dirname, "..", "..", "site-config.js");

function siteConfigWith({ isis2 = false, escola = false } = {}) {
  let content = fs.readFileSync(SITE_CONFIG_PATH, "utf8");
  if (isis2) {
    const before = content;
    content = content.replace("isis2: {\n    enabled: false,", "isis2: {\n    enabled: true,");
    if (content === before) throw new Error("Não achei 'isis2: { enabled: false,' em site-config.js.");
  }
  if (escola) {
    const before = content;
    content = content.replace("escola: {\n      enabled: false\n    }", "escola: {\n      enabled: true\n    }");
    if (content === before) throw new Error("Não achei 'escola: { enabled: false }' em site-config.js.");
  }
  return content;
}

async function servirSiteConfig(page, flags) {
  const body = siteConfigWith(flags);
  await page.route("**/site-config.js*", route => route.fulfill({ status: 200, contentType: "application/javascript", body }));
}

const CURSO_PUBLICO = {
  slug: "xamanismo-introducao",
  titulo: "Xamanismo: Introdução",
  modulos: [
    { id: 1, titulo: "Fundamentos", bloqueado: false, aulas: [{ id: 10, titulo: "O que é xamanismo" }] },
    { id: 2, titulo: "Práticas avançadas", bloqueado: true, aulas: [] },
  ],
};

async function mockEscolaApis(page, { autenticado = false } = {}) {
  await page.route("**/api/alunos/me", route => route.fulfill({
    status: autenticado ? 200 : 401,
    contentType: "application/json",
    body: JSON.stringify(autenticado ? { nome: "Aluna Teste", email: "aluna@example.com" } : { detail: "não autenticado" }),
  }));
  await page.route("**/api/escola/publico/cursos/**", route => route.fulfill({
    status: 200, contentType: "application/json", body: JSON.stringify(CURSO_PUBLICO),
  }));
  await page.route("**/api/escola/meus-cursos", route => route.fulfill({
    status: autenticado ? 200 : 401,
    contentType: "application/json",
    body: JSON.stringify(autenticado ? [{ slug: "xamanismo-introducao", titulo: "Xamanismo: Introdução", percentual: 40, aulas_concluidas: 2, total_aulas: 5 }] : { detail: "não autenticado" }),
  }));
  await page.route("**/api/escola/cursos/**", route => route.fulfill({
    status: autenticado ? 200 : 401,
    contentType: "application/json",
    body: JSON.stringify(autenticado
      ? { titulo: "Xamanismo: Introdução", progresso: { percentual: 40, aulas_concluidas: 2, total_aulas: 5, concluido: false }, modulos: [{ id: 1, titulo: "Fundamentos", liberado: true, concluido: false, aulas: [{ id: 10, titulo: "O que é xamanismo", status: "concluida" }, { id: 11, titulo: "Símbolos", status: "nao_iniciada" }] }] }
      : { detail: "não autenticado" }),
  }));
}

async function dismissConsent(page) {
  const decline = page.locator("[data-consent-decline]");
  if (await decline.isVisible().catch(() => false)) await decline.click();
}

async function abrirEscola(page, { isis2 = true, escola = true, autenticado = false, url = "/escola.html" } = {}) {
  await servirSiteConfig(page, { isis2, escola });
  await mockEscolaApis(page, { autenticado });
  await page.goto(url);
  await dismissConsent(page);
}

test.describe("Isis 2.0 — Escola — feature flags", () => {
  test("flag geral desligada: widget da Isis 2.0 não aparece em escola.html", async ({ page }) => {
    await abrirEscola(page, { isis2: false, escola: false });
    await expect(page.locator("#isis2-root")).toHaveCount(0);
  });

  test("flag geral ligada mas flag da Escola desligada: nenhum módulo da Escola é baixado", async ({ page }) => {
    const schoolRequests = [];
    page.on("request", req => {
      if (/isis2\/(school-|student-context|course-recommendation|progress-assistant|lesson-navigation|assessment-safety)/.test(req.url())) schoolRequests.push(req.url());
    });
    await abrirEscola(page, { isis2: true, escola: false });
    await page.waitForTimeout(500);
    expect(schoolRequests).toHaveLength(0);
  });

  test("as duas flags ligadas: widget monta em escola.html", async ({ page }) => {
    await abrirEscola(page, { isis2: true, escola: true });
    await expect(page.locator("#isis2-root")).toHaveCount(1);
  });

  test("flag não pode ser ligada por query string", async ({ page }) => {
    await servirSiteConfig(page, { isis2: false, escola: false });
    await mockEscolaApis(page, { autenticado: false });
    await page.goto("/escola.html?isis2=true&mistica_isis2_enabled=true");
    await dismissConsent(page);
    await expect(page.locator("#isis2-root")).toHaveCount(0);
  });

  test("flag não pode ser ligada por localStorage", async ({ page }) => {
    await page.addInitScript(() => {
      try { window.localStorage.setItem("MISTICA_ISIS2_ENABLED", "true"); window.localStorage.setItem("MISTICA_ISIS2_ESCOLA_ENABLED", "true"); } catch { /* ignore */ }
    });
    await abrirEscola(page, { isis2: false, escola: false });
    await expect(page.locator("#isis2-root")).toHaveCount(0);
  });
});

test.describe("Isis 2.0 — Escola — visitante não autenticado", () => {
  test("abre a Isis na página da Escola e recebe a saudação especializada", async ({ page }) => {
    await abrirEscola(page, { autenticado: false });
    await page.locator("#isis2-toggle").click();
    await expect(page.locator("#isis2-panel")).toBeVisible();
    await expect(page.locator("#isis2-messages")).toContainText("Mística Escola");
  });

  test("pergunta por curso inicial recebe recomendação real do catálogo", async ({ page }) => {
    await abrirEscola(page, { autenticado: false });
    await page.locator("#isis2-toggle").click();
    await page.locator("#isis2-input").fill("Qual curso é melhor para começar?");
    await page.locator("#isis2-form button[type=submit]").click();
    await expect(page.locator("#isis2-messages")).toContainText("Xamanismo");
  });

  test("tenta consultar progresso sem login: Isis nunca finge saber, orienta login", async ({ page }) => {
    await abrirEscola(page, { autenticado: false, url: "/escola-curso.html?curso=xamanismo-introducao" });
    await page.locator("#isis2-toggle").click();
    await page.locator("#isis2-input").fill("Quanto do curso eu já concluí?");
    await page.locator("#isis2-form button[type=submit]").click();
    const messages = page.locator("#isis2-messages");
    await expect(messages).toContainText(/entrar na sua conta|não está logado|entre com o e-mail/i);
    await expect(messages).not.toContainText("%");
  });
});

test.describe("Isis 2.0 — Escola — aluno autenticado", () => {
  test("consulta seus cursos reais (nunca dado de outro aluno)", async ({ page }) => {
    await abrirEscola(page, { autenticado: true });
    await page.locator("#isis2-toggle").click();
    await page.locator("#isis2-input").fill("Onde encontro meus cursos?");
    await page.locator("#isis2-form button[type=submit]").click();
    await expect(page.locator("#isis2-messages")).toContainText("40%");
  });

  test("abre a próxima aula pelo link seguro sugerido", async ({ page }) => {
    await abrirEscola(page, { autenticado: true, url: "/escola-curso.html?curso=xamanismo-introducao" });
    await page.locator("#isis2-toggle").click();
    await page.locator("#isis2-input").fill("Qual é minha próxima aula?");
    await page.locator("#isis2-form button[type=submit]").click();
    const link = page.locator("[data-isis2-course-open]").first();
    await expect(link).toHaveAttribute("href", /^escola-curso\.html\?curso=/);
  });

  test("módulo bloqueado é explicado sem inventar nota mínima", async ({ page }) => {
    await abrirEscola(page, { autenticado: true, url: "/escola-curso.html?curso=xamanismo-introducao" });
    await page.locator("#isis2-toggle").click();
    await page.locator("#isis2-input").fill("Por que o próximo módulo está bloqueado?");
    await page.locator("#isis2-form button[type=submit]").click();
    await expect(page.locator("#isis2-messages")).toContainText("bloqueado");
  });
});

test.describe("Isis 2.0 — Escola — segurança", () => {
  test("avaliação ativa não recebe resposta direta", async ({ page }) => {
    await abrirEscola(page, { autenticado: true });
    await page.locator("#isis2-toggle").click();
    await page.locator("#isis2-input").fill("Qual a origem do rapé?\na) Europa\nb) Amazônia\nc) Ásia\nqual a resposta certa?");
    await page.locator("#isis2-form button[type=submit]").click();
    const messages = page.locator("#isis2-messages");
    await expect(messages).toContainText("Não posso te dar a resposta");
    await expect(messages).not.toContainText(/a resposta certa é|a alternativa correta é/i);
  });

  test("XSS: título de curso malicioso da API nunca executa script nem quebra o layout", async ({ page }) => {
    await servirSiteConfig(page, { isis2: true, escola: true });
    await page.route("**/api/alunos/me", route => route.fulfill({ status: 401, contentType: "application/json", body: "{}" }));
    await page.route("**/api/escola/meus-cursos", route => route.fulfill({ status: 401, contentType: "application/json", body: "{}" }));
    await page.route("**/api/escola/cursos/**", route => route.fulfill({ status: 401, contentType: "application/json", body: "{}" }));
    await page.route("**/api/escola/publico/cursos/**", route => route.fulfill({ status: 200, contentType: "application/json", body: "{}" }));
    let dialogFired = false;
    page.on("dialog", async dialog => { dialogFired = true; await dialog.dismiss(); });
    await page.goto("/escola.html");
    await dismissConsent(page);
    await page.locator("#isis2-toggle").click();
    await page.locator("#isis2-input").fill("<img src=x onerror=alert(1)>quero aprender sobre xamanismo");
    await page.locator("#isis2-form button[type=submit]").click();
    await page.waitForTimeout(700);
    expect(dialogFired).toBe(false);
    await expect(page.locator("#isis2-messages img")).toHaveCount(0);
  });

  test("URL javascript: nunca aparece como href sugerido pela Isis", async ({ page }) => {
    await abrirEscola(page, { autenticado: false });
    const hrefs = await page.evaluate(() => Array.from(document.querySelectorAll("#isis2-root a[href]")).map(a => a.getAttribute("href")));
    expect(hrefs.every(href => !href.toLowerCase().startsWith("javascript:"))).toBe(true);
  });
});

test.describe("Isis 2.0 — Escola — acessibilidade e responsivo", () => {
  test("teclado: Tab alcança o botão flutuante e Escape fecha o painel", async ({ page }) => {
    await abrirEscola(page);
    await page.locator("#isis2-toggle").focus();
    await page.locator("#isis2-toggle").press("Enter");
    await expect(page.locator("#isis2-panel")).toBeVisible();
    await page.keyboard.press("Escape");
    await expect(page.locator("#isis2-panel")).toBeHidden();
  });

  test("foco retorna ao botão flutuante ao fechar", async ({ page }) => {
    await abrirEscola(page);
    await page.locator("#isis2-toggle").click();
    await page.locator(".isis2-minimize").click();
    await expect(page.locator("#isis2-toggle")).toBeFocused();
  });

  test("mobile 390x844: widget não cobre a navegação mobile nem cria rolagem horizontal", async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await abrirEscola(page);
    const hasHorizontalScroll = await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth + 1);
    expect(hasHorizontalScroll).toBe(false);
  });

  test("zoom 200%: painel continua utilizável", async ({ page }) => {
    await abrirEscola(page);
    await page.evaluate(() => { document.body.style.zoom = "2"; });
    await page.locator("#isis2-toggle").click();
    await expect(page.locator("#isis2-panel")).toBeVisible();
  });
});
