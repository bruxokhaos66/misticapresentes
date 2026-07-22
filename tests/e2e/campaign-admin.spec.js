// Testes E2E do painel administrativo de Campanhas Promocionais
// (campaign-admin.js), injetado em admin.html só depois do login.
//
// Cobre a correção da condição de corrida relatada na auditoria ("Não foi
// possível carregar as campanhas."): campaign-admin.js chamava
// loadCampanhas() assim que o script carregava, antes de existir sessão --
// a primeira tentativa sempre recebia 401 e nada disparava uma nova busca
// depois do login. Aqui o mock de /api/campanhas só responde 200 quando o
// cookie de sessão está presente, provando que o painel se recupera sozinho
// (evento "mistica:admin-unlocked") sem precisar de F5.
//
// Cobre também a nova ação "Encerrar campanha": confirmação, chamada ao
// endpoint dedicado, atualização da lista sem F5, botão ausente para
// campanha já encerrada, e que excluir continua funcionando separadamente.
const { test, expect } = require("@playwright/test");

async function mockLoginEMe(page) {
  await page.route("**/api/auth/login", route => route.fulfill({
    status: 200,
    contentType: "application/json",
    // O painel (servido em 127.0.0.1:8910 no teste) chama a API num domínio
    // diferente (API_BASE), então o cookie de sessão é cross-site do ponto
    // de vista do navegador: precisa de SameSite=None; Secure para o
    // Chromium aceitar gravá-lo e reenviá-lo nas próximas chamadas fetch
    // com credentials:"include" -- sem isso o teste não reproduz o cenário
    // real (cookie é sempre same-site em produção, api.* e o site
    // compartilham o mesmo domínio registrável).
    headers: { "set-cookie": "mistica_painel_sessao=valida; Path=/; HttpOnly; Secure; SameSite=None" },
    body: JSON.stringify({ usuario: { nome: "Admin Teste", login: "admin-teste", perfil: "adm" } }),
  }));
  // site-config.js chama /api/auth/me automaticamente ao carregar admin.html
  // (restaurarSessao), antes de qualquer login manual -- precisa checar o
  // cookie, senão o painel "abriria sozinho" no mock.
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

// Só responde 200 (com a lista atual) quando o cookie de sessão está
// presente na requisição -- exatamente como o backend real faz. Sem essa
// checagem o teste não provaria nada sobre a condição de corrida.
function mockListaCampanhas(page, getLista) {
  return page.route("**/api/campanhas", route => {
    if (route.request().method() !== "GET") return route.continue();
    const cookie = route.request().headers()["cookie"] || "";
    if (!cookie.includes("mistica_painel_sessao=valida")) {
      return route.fulfill({
        status: 401,
        contentType: "application/json",
        body: JSON.stringify({ detail: "Sessão inválida ou expirada. Faça login novamente." }),
      });
    }
    return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(getLista()) });
  });
}

async function fazerLogin(page) {
  await page.goto("/admin.html");
  await page.fill("#adminUserLogin", "admin-teste");
  await page.fill("#adminPassword", "senha-qualquer");
  await page.click("#adminLoginForm button[type=submit]");
  await expect(page.locator("#adminContent")).toBeVisible();
}

const CAMPANHA_ATIVA = {
  id: 501,
  titulo: "Campanha E2E Ativa",
  descricao: "Descrição de teste",
  tipo: "desconto_percentual",
  valor: 10,
  codigo_cupom: "E2E10",
  link: null,
  ativo: 1,
  data_inicio: null,
  data_fim: null,
};

test.describe("Painel admin — Campanhas promocionais", () => {
  test("sem sessão, o painel de campanhas não aparece", async ({ page }) => {
    await mockLoginEMe(page);
    await mockListaCampanhas(page, () => [CAMPANHA_ATIVA]);
    await page.goto("/admin.html");
    await expect(page.locator("#adminContent")).toBeHidden();
    await expect(page.locator(".campaign-admin-panel")).toBeHidden();
  });

  test("após o login, a lista de campanhas aparece sem precisar de F5 (corrige a condição de corrida)", async ({ page }) => {
    // Só exceções JS não tratadas contam como "erro no console" para este
    // teste -- mensagens de "Failed to load resource" de recursos de
    // terceiros (fontes, analytics) não mockados são ruído do sandbox sem
    // rede externa, não sintoma do bug corrigido aqui.
    const erros = [];
    page.on("pageerror", err => erros.push(String(err)));

    await mockLoginEMe(page);
    await mockListaCampanhas(page, () => [CAMPANHA_ATIVA]);
    await fazerLogin(page);

    // Antes da correção, o fetch inicial (disparado antes do cookie
    // existir) falhava com 401 e a mensagem de erro ficava presa
    // permanentemente -- nada recarregava a lista depois do login.
    await expect(page.locator("[data-campaign-admin-status]")).not.toContainText("Não foi possível carregar as campanhas.");
    await expect(page.locator("[data-campaign-admin-status]")).toContainText("Campanhas atualizadas: 1 cadastrada(s).");
    await expect(page.locator(".admin-product-item")).toContainText("Campanha E2E Ativa");

    expect(erros).toEqual([]);
  });

  test("sessão expirada mostra mensagem clara sem detalhes internos", async ({ page }) => {
    await mockLoginEMe(page);
    // Simula sessão que expira exatamente entre o login e a busca da lista:
    // o cookie nunca "vale" para /api/campanhas.
    await page.route("**/api/campanhas", route => {
      if (route.request().method() !== "GET") return route.continue();
      return route.fulfill({ status: 401, contentType: "application/json", body: JSON.stringify({ detail: "Sessão inválida ou expirada. Faça login novamente." }) });
    });
    await fazerLogin(page);

    await expect(page.locator("[data-campaign-admin-status]")).toContainText("Sessão expirada. Faça login novamente.");
  });

  test("botão 'Encerrar campanha' pede confirmação; cancelar não altera nada", async ({ page }) => {
    let chamouEncerrar = false;
    await mockLoginEMe(page);
    await mockListaCampanhas(page, () => [CAMPANHA_ATIVA]);
    await page.route("**/api/campanhas/501/encerrar", route => { chamouEncerrar = true; route.continue(); });
    page.on("dialog", dialog => dialog.dismiss());
    await fazerLogin(page);

    await expect(page.locator('[data-end-campaign="501"]')).toBeVisible();
    await page.click('[data-end-campaign="501"]');
    await page.waitForTimeout(300);

    expect(chamouEncerrar).toBe(false);
    await expect(page.locator('[data-end-campaign="501"]')).toBeVisible();
  });

  test("confirmar 'Encerrar campanha' chama o endpoint dedicado e atualiza a lista sem F5", async ({ page }) => {
    let lista = [CAMPANHA_ATIVA];
    let mensagemDialog = "";
    await mockLoginEMe(page);
    await mockListaCampanhas(page, () => lista);
    await page.route("**/api/campanhas/501/encerrar", route => {
      lista = [{ ...CAMPANHA_ATIVA, ativo: 0, data_fim: "2026-07-22T21:00:00" }];
      route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ ok: true, id: 501, ja_encerrada: false }) });
    });
    page.on("dialog", dialog => { mensagemDialog = dialog.message(); dialog.accept(); });
    await fazerLogin(page);

    await page.click('[data-end-campaign="501"]');

    // A lista foi recarregada (GET /api/campanhas de novo) e agora reflete
    // ativo=0: o botão de encerrar não aparece mais para essa campanha. Isso
    // só é observável depois do POST /encerrar + do novo GET completarem,
    // então usamos um locator com auto-retry (não uma leitura pontual de
    // status, que pode já ter avançado para a mensagem seguinte).
    await expect(page.locator('[data-end-campaign="501"]')).toHaveCount(0);
    await expect(page.locator(".admin-product-item")).toContainText("Encerrada");
    expect(mensagemDialog.toLowerCase()).toContain("encerrar");
  });

  test("botão 'Encerrar campanha' não aparece para campanha já inativa/encerrada", async ({ page }) => {
    const campanhaEncerrada = { ...CAMPANHA_ATIVA, id: 502, ativo: 0, data_fim: "2026-07-01T10:00:00" };
    await mockLoginEMe(page);
    await mockListaCampanhas(page, () => [campanhaEncerrada]);
    await fazerLogin(page);

    await expect(page.locator(".admin-product-item")).toContainText("Encerrada");
    await expect(page.locator('[data-end-campaign="502"]')).toHaveCount(0);
    // Excluir continua disponível independente do estado da campanha.
    await expect(page.locator('[data-delete-campaign="502"]')).toBeVisible();
  });

  test("excluir continua funcionando separadamente de encerrar, com confirmação própria", async ({ page }) => {
    let lista = [CAMPANHA_ATIVA];
    let chamouExcluir = false;
    let chamouEncerrar = false;
    await mockLoginEMe(page);
    await mockListaCampanhas(page, () => lista);
    await page.route("**/api/campanhas/501/encerrar", route => { chamouEncerrar = true; route.continue(); });
    await page.route("**/api/campanhas/501", route => {
      if (route.request().method() === "DELETE") {
        chamouExcluir = true;
        lista = [];
        return route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ ok: true }) });
      }
      return route.continue();
    });
    page.on("dialog", dialog => dialog.accept());
    await fazerLogin(page);

    await page.click('[data-delete-campaign="501"]');

    // toContainText faz polling até o DELETE mockado + o reload da lista
    // completarem. (A mensagem "Campanha excluída." é só transitória: o
    // loadCampanhas() disparado em seguida já a substitui pela contagem
    // atualizada, então a checagem estável é o conteúdo final da lista.)
    await expect(page.locator("[data-campaign-admin-list]")).toContainText("Nenhuma campanha cadastrada ainda.");
    expect(chamouExcluir).toBe(true);
    expect(chamouEncerrar).toBe(false);
  });
});

test.describe("Banner público de campanhas — reflete o encerramento imediatamente", () => {
  test("campanha ativa aparece no banner; campanha encerrada não aparece", async ({ page }) => {
    await page.route("**/api/campanhas/ativas", route => route.fulfill({
      status: 200, contentType: "application/json", body: JSON.stringify([CAMPANHA_ATIVA]),
    }));
    await page.goto("/index.html");
    await expect(page.locator("#campaignBannerContainer")).toContainText("Campanha E2E Ativa");
  });

  test("após encerrar, a campanha some do banner público (rota /api/campanhas/ativas não a lista mais)", async ({ page }) => {
    await page.route("**/api/campanhas/ativas", route => route.fulfill({
      status: 200, contentType: "application/json", body: JSON.stringify([]),
    }));
    await page.goto("/index.html");
    await expect(page.locator("#campaignBannerContainer")).toHaveCount(0);
  });
});
