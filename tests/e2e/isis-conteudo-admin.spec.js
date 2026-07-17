// Testes E2E do painel "Conteúdos da Isis" (Estúdio de Conteúdo, Isis 2.0 —
// Fase 3): estado desativado por padrão, renderização segura de conteúdo
// (XSS) e as ações básicas do fluxo de aprovação. O backend real nunca é
// chamado — todas as rotas /api/... são interceptadas com page.route,
// igual ao padrão de tests/e2e/isis2-widget.spec.js.
const { test, expect } = require("@playwright/test");

async function mockAuthAdmin(page) {
  await page.route("**/api/auth/me", route => route.fulfill({
    status: 200,
    contentType: "application/json",
    body: JSON.stringify({ autenticado: true, perfil: "adm" }),
  }));
}

async function mockStatus(page, overrides = {}) {
  const flags = {
    content_studio_enabled: false,
    auto_generation_enabled: false,
    image_generation_enabled: false,
    auto_publish_enabled: false,
    ...overrides,
  };
  await page.route("**/api/admin/isis-conteudo/status", route => route.fulfill({
    status: 200,
    contentType: "application/json",
    body: JSON.stringify(flags),
  }));
}

test("estúdio desativado por padrão: painel mostra aviso e não lista rascunhos", async ({ page }) => {
  await mockAuthAdmin(page);
  await mockStatus(page);
  let listaChamada = false;
  await page.route("**/api/admin/isis-conteudo/drafts**", route => { listaChamada = true; route.fulfill({ status: 404, body: "{}" }); });

  await page.goto("/isis-conteudo-admin.html");
  await expect(page.getByText(/desativado/i)).toBeVisible();
  expect(listaChamada).toBe(false);
});

test("estúdio habilitado exibe rascunhos e renderiza legenda com segurança contra XSS", async ({ page }) => {
  await mockAuthAdmin(page);
  await mockStatus(page, { content_studio_enabled: true });

  const legendaMaliciosa = '<img src=x onerror="window.__xss = true">Bom dia da Mística';
  await page.route("**/api/admin/isis-conteudo/drafts**", route => route.fulfill({
    status: 200,
    contentType: "application/json",
    body: JSON.stringify({
      drafts: [
        {
          id: 1,
          tipo: "bom_dia",
          data_referencia: "2026-07-17",
          status: "rascunho",
          legenda: legendaMaliciosa,
          legenda_curta: "Bom dia",
          hashtags: "#MísticaEsotéricos",
          texto_alternativo: "Foto",
          prompt_visual: "Prompt",
          assets: [],
        },
      ],
      total: 1,
    }),
  }));

  await page.goto("/isis-conteudo-admin.html");
  await expect(page.locator("textarea[data-campo=legenda]")).toHaveValue(legendaMaliciosa);
  // O <img onerror> nunca deve executar: a legenda vai para um <textarea>
  // (conteúdo textual), nunca para innerHTML crú.
  const xssExecutou = await page.evaluate(() => window.__xss === true);
  expect(xssExecutou).toBe(false);
  expect(await page.locator("img[src=x]").count()).toBe(0);
});

test("aprovar rascunho chama a rota correta e atualiza a lista", async ({ page }) => {
  await mockAuthAdmin(page);
  await mockStatus(page, { content_studio_enabled: true });

  let draftAprovado = false;
  let chamadaAprovacao = null;
  await page.route("**/api/admin/isis-conteudo/drafts**", route => {
    const url = route.request().url();
    if (route.request().method() === "POST" && url.includes("/aprovar")) {
      chamadaAprovacao = url;
      draftAprovado = true;
      return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ ok: true }) });
    }
    return route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        drafts: [
          {
            id: 7,
            tipo: "produto_do_dia",
            data_referencia: "2026-07-17",
            status: draftAprovado ? "aprovado" : "rascunho",
            legenda: "Produto do dia",
            legenda_curta: "Produto",
            hashtags: "#Produto",
            texto_alternativo: "Foto do produto",
            prompt_visual: "Prompt do produto",
            produto_nome: "Vela Ritualística",
            produto_codigo: "V-001",
            assets: [],
          },
        ],
        total: 1,
      }),
    });
  });

  await page.goto("/isis-conteudo-admin.html");
  await page.getByRole("button", { name: "Aprovar" }).click();
  await expect.poll(() => chamadaAprovacao).toContain("/drafts/7/aprovar");
});
