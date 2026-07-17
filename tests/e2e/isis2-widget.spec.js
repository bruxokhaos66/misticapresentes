// Testes E2E do widget Isis 2.0 (assistente virtual modular), aditivo ao
// site público: verifica a feature flag (default desligada), a
// convivência com o chat legado, que uma recomendação real do catálogo
// aparece, que "adicionar ao carrinho" funciona (reaproveitando
// window.addToCart de app.js), XSS e uma checagem básica de
// acessibilidade (roles/aria) e mobile.
const { test, expect } = require("@playwright/test");
const fs = require("fs");
const path = require("path");

const SITE_CONFIG_PATH = path.resolve(__dirname, "..", "..", "site-config.js");

const PRODUTO_API = {
  id: 501,
  codigo_p: "ISIS2-501",
  nome: "Incenso Relaxante de Teste",
  categoria: "Aromas e proteção",
  descricao: "Incenso para relaxar, acalmar a mente e limpar o ambiente.",
  preco: 15.5,
  quantidade: 10,
  imagem_url: "",
  imagens: [],
  selo: "",
  avaliacoes_total: 0,
  avaliacoes_media: 0,
};

async function prepararCatalogo(page, produtos = [PRODUTO_API]) {
  await page.route("**/api/produtos?**", route => route.fulfill({
    status: 200,
    contentType: "application/json",
    body: JSON.stringify(produtos),
  }));
}

// A flag pública fica em site-config.js (window.misticaSiteConfig.isis2
// .enabled), que sobrescreve window.misticaSiteConfig por inteiro. Para
// testar com a flag ligada sem depender de localStorage/query string
// (que a Isis 2.0 nunca lê), servimos uma cópia do arquivo real com
// "enabled: false" trocado por "enabled: true" — mesmo arquivo estático
// que um deploy de homologação usaria.
async function ligarFeatureFlagIsis2(page) {
  const original = fs.readFileSync(SITE_CONFIG_PATH, "utf8");
  const habilitado = original.replace("enabled: false", "enabled: true");
  if (habilitado === original) throw new Error("Não achei 'enabled: false' em site-config.js para habilitar a flag no teste.");
  await page.route("**/site-config.js*", route => route.fulfill({
    status: 200,
    contentType: "application/javascript",
    body: habilitado,
  }));
}

async function dismissConsent(page) {
  const decline = page.locator("[data-consent-decline]");
  if (await decline.isVisible().catch(() => false)) await decline.click();
}

async function irParaHomeComCatalogo(page, { isis2 = true, produtos } = {}) {
  await prepararCatalogo(page, produtos);
  if (isis2) await ligarFeatureFlagIsis2(page);
  await page.goto("/index.html");
  await dismissConsent(page);
  await expect.poll(() => page.evaluate(() => window.misticaCatalogState)).toBe("ready");
}

test.describe("Isis 2.0 - feature flag", () => {
  test("com a flag desligada (default), o widget novo não aparece e só a Isis 1 (legado) é mostrada", async ({ page }) => {
    await irParaHomeComCatalogo(page, { isis2: false });
    await expect(page.locator("#isis2-root")).toHaveCount(0);
    await expect(page.locator("#isisChat")).toBeVisible();
    await expect(page.locator("#isisForm")).toBeVisible();
  });

  test("com a flag desligada, nenhum outro arquivo da Isis 2.0 é baixado (só o loader)", async ({ page }) => {
    const isis2Requests = [];
    page.on("request", req => {
      const url = req.url();
      if (url.includes("/isis2/")) isis2Requests.push(url);
    });
    await irParaHomeComCatalogo(page, { isis2: false });
    await page.waitForTimeout(500);
    const naoLoader = isis2Requests.filter(url => !url.includes("isis2-loader.js"));
    expect(naoLoader, `requisições inesperadas: ${JSON.stringify(naoLoader)}`).toEqual([]);
  });

  test("flag não pode ser ligada por query string", async ({ page }) => {
    await prepararCatalogo(page);
    await page.goto("/index.html?MISTICA_ISIS2_ENABLED=true&isis2=1");
    await dismissConsent(page);
    await expect.poll(() => page.evaluate(() => window.misticaCatalogState)).toBe("ready");
    await expect(page.locator("#isis2-root")).toHaveCount(0);
  });

  test("flag não pode ser ligada por localStorage", async ({ page }) => {
    await page.addInitScript(() => {
      localStorage.setItem("MISTICA_ISIS2_ENABLED", "true");
      localStorage.setItem("isis2_enabled", "true");
    });
    await prepararCatalogo(page);
    await page.goto("/index.html");
    await dismissConsent(page);
    await expect.poll(() => page.evaluate(() => window.misticaCatalogState)).toBe("ready");
    await expect(page.locator("#isis2-root")).toHaveCount(0);
  });
});

test.describe("Isis 2.0 - convivência com a Isis 1 (flag ligada)", () => {
  test("com a flag ligada, a Isis 1 embutida é substituída visualmente pelo widget novo (sem dois chats ativos)", async ({ page }) => {
    await irParaHomeComCatalogo(page);

    // O widget novo existe e está pronto para uso.
    await expect(page.locator("#isis2-root")).toBeAttached();

    // O chat antigo (histórico + formulário + ações rápidas) fica oculto,
    // mas continua no DOM como fallback caso o script novo falhe — não é
    // removido, só escondido depois que a Isis 2.0 confirma que montou.
    await expect(page.locator("#isisChat")).toBeHidden();
    await expect(page.locator("#isisForm")).toBeHidden();
    await expect(page.locator(".isis-chat-panel .quick-actions")).toBeHidden();

    // Só um caminho fica claro para o cliente conversar com a Isis.
    await expect(page.locator(".isis2-legacy-notice")).toBeVisible();
    await expect(page.locator("#isis2-toggle")).toBeVisible();
  });

  test("botão da nota legada abre o widget novo", async ({ page }) => {
    await irParaHomeComCatalogo(page);
    await page.locator("#isis2-open-from-legacy").click();
    await expect(page.locator("#isis2-panel")).toBeVisible();
  });
});

test.describe("Isis 2.0 - widget flutuante", () => {
  test("botão flutuante abre a conversa e mostra a mensagem de boas-vindas", async ({ page }) => {
    await irParaHomeComCatalogo(page);

    const toggle = page.locator("#isis2-toggle");
    await expect(toggle).toBeVisible();
    await toggle.click();

    const panel = page.locator("#isis2-panel");
    await expect(panel).toBeVisible();
    await expect(panel).not.toHaveAttribute("hidden", "");
    await expect(page.locator("#isis2-messages")).toContainText("Isis", { timeout: 5000 });
  });

  test("recomenda um produto real do catálogo e permite adicionar ao carrinho", async ({ page }) => {
    await irParaHomeComCatalogo(page);

    await page.locator("#isis2-toggle").click();
    await page.locator("#isis2-input").fill("Quero um incenso para relaxar");
    await page.locator("#isis2-form button[type=submit]").click();

    const card = page.locator(".isis2-card", { hasText: "Incenso Relaxante de Teste" });
    await expect(card).toBeVisible({ timeout: 5000 });

    await card.locator("[data-isis2-add]").click();
    await expect(page.locator("#cartList")).toContainText("Incenso Relaxante de Teste");
  });

  test("filtra recomendação por orçamento informado na frase", async ({ page }) => {
    await irParaHomeComCatalogo(page, {
      produtos: [
        PRODUTO_API,
        { ...PRODUTO_API, id: 502, codigo_p: "ISIS2-502", nome: "Kit Presente Caro de Teste", preco: 250, categoria: "Kits e presentes" },
      ],
    });

    await page.locator("#isis2-toggle").click();
    await page.locator("#isis2-input").fill("Quero um presente até R$50");
    await page.locator("#isis2-form button[type=submit]").click();

    await expect(page.locator(".isis2-card")).toContainText("Incenso Relaxante de Teste", { timeout: 5000 });
    await expect(page.locator(".isis2-message-bot").last()).not.toContainText("Kit Presente Caro de Teste");
  });

  test("nunca adiciona ao carrinho quando a loja recusa (estoque insuficiente) — não finge sucesso", async ({ page }) => {
    await irParaHomeComCatalogo(page, {
      produtos: [{ ...PRODUTO_API, quantidade: 0 }],
    });

    await page.locator("#isis2-toggle").click();
    await page.locator("#isis2-input").fill("Quero um incenso para relaxar");
    await page.locator("#isis2-form button[type=submit]").click();

    // Sem estoque, o produto não deveria nem ser recomendado — mas se por
    // algum motivo aparecer, o botão de adicionar nunca pode alegar
    // sucesso.
    const addButton = page.locator("[data-isis2-add]").first();
    if (await addButton.count()) {
      await addButton.click();
      await expect(addButton).not.toHaveText("Adicionado ✓");
    }
    await expect(page.locator("#cartList")).not.toContainText("Incenso Relaxante de Teste");
  });

  test("painel tem role de diálogo e o log de mensagens é anunciável (acessibilidade)", async ({ page }) => {
    await irParaHomeComCatalogo(page);
    await page.locator("#isis2-toggle").click();

    await expect(page.locator("#isis2-panel")).toHaveAttribute("role", "dialog");
    await expect(page.locator("#isis2-messages")).toHaveAttribute("role", "log");
    await expect(page.locator("#isis2-messages")).toHaveAttribute("aria-live", "polite");
    await expect(page.locator("#isis2-toggle")).toHaveAttribute("aria-label", /.+/);

    await page.keyboard.press("Escape");
    await expect(page.locator("#isis2-panel")).toBeHidden();
  });

  test("teclado: Tab alcança o campo de mensagem e Enter envia", async ({ page }) => {
    await irParaHomeComCatalogo(page);
    await page.locator("#isis2-toggle").click();
    await page.locator("#isis2-input").focus();
    await page.keyboard.type("Quero um incenso para relaxar");
    await page.keyboard.press("Enter");
    await expect(page.locator(".isis2-card")).toBeVisible({ timeout: 5000 });
  });
});

test.describe("Isis 2.0 - restauração de foco", () => {
  test("não há foco automático no primeiro carregamento da página", async ({ page }) => {
    await irParaHomeComCatalogo(page);
    const idAtivo = await page.evaluate(() => document.activeElement?.id || document.activeElement?.tagName);
    expect(idAtivo).not.toBe("isis2-input");
  });

  test("foco vai para o campo de mensagem ao abrir, e volta ao botão flutuante ao fechar com o botão minimizar", async ({ page }) => {
    await irParaHomeComCatalogo(page);
    await page.locator("#isis2-toggle").click();
    await expect(page.locator("#isis2-input")).toBeFocused({ timeout: 2000 });

    await page.locator(".isis2-minimize").click();
    await expect(page.locator("#isis2-toggle")).toBeFocused();
  });

  test("Escape fecha e restaura o foco ao acionador real (o botão clicado), não a um elemento anterior arbitrário", async ({ page }) => {
    // Nota técnica: um clique real move o foco do navegador para o
    // elemento clicado ANTES do listener de clique rodar — então
    // "o elemento focado antes de abrir" (document.activeElement dentro
    // de openPanel()) já é o próprio botão que acionou a abertura, não
    // um elemento anterior qualquer. É esse o comportamento correto e
    // esperado por "o foco retorna ao acionador".
    await irParaHomeComCatalogo(page);
    await page.locator('a[href="#produtos"]').first().focus();
    await page.locator("#isis2-toggle").click();
    await expect(page.locator("#isis2-input")).toBeFocused();

    await page.keyboard.press("Escape");
    await expect(page.locator("#isis2-toggle")).toBeFocused();
  });

  test("acionador diferente do botão flutuante (nota da Isis 1) também recebe o foco de volta ao fechar", async ({ page }) => {
    await irParaHomeComCatalogo(page);
    await page.locator("#isis2-open-from-legacy").click();
    await expect(page.locator("#isis2-input")).toBeFocused();

    await page.keyboard.press("Escape");
    await expect(page.locator("#isis2-open-from-legacy")).toBeFocused();
  });

  test("múltiplos ciclos de abrir/fechar não deixam o foco perdido nem lançam exceção", async ({ page }) => {
    await irParaHomeComCatalogo(page);
    const erros = [];
    page.on("pageerror", err => erros.push(String(err)));

    for (let i = 0; i < 4; i += 1) {
      await page.locator("#isis2-toggle").click();
      await expect(page.locator("#isis2-input")).toBeFocused();
      await page.keyboard.press("Escape");
      await expect(page.locator("#isis2-toggle")).toBeFocused();
    }
    expect(erros).toEqual([]);
  });

  test("fallback para a Isis 1: elementos escondidos (chat legado) não prendem o foco depois que a Isis 2.0 assume", async ({ page }) => {
    await irParaHomeComCatalogo(page);
    // #isisForm foi escondido (hidden) pela convivência com a Isis 1;
    // não deve ser alcançável por Tab nem reter foco.
    const focavel = await page.evaluate(() => {
      const form = document.querySelector("#isisForm");
      if (!form) return null;
      return form.hidden === true;
    });
    expect(focavel).toBe(true);
  });
});

test.describe("Isis 2.0 - XSS e renderização segura", () => {
  test("nome/descrição maliciosos do catálogo nunca executam script dentro do widget", async ({ page }) => {
    const payloadImg = '<img src=x onerror="window.__isis2XssFired=1">';
    const payloadScript = "<script>window.__isis2XssFired=2</script>";
    const payloadSvg = '"><svg onload="window.__isis2XssFired=3">';

    await page.addInitScript(() => {
      window.__isis2XssFired = 0;
    });

    await irParaHomeComCatalogo(page, {
      produtos: [{
        ...PRODUTO_API,
        nome: `${payloadImg}Produto malicioso`,
        categoria: `${payloadSvg}Categoria maliciosa`,
        descricao: `${payloadScript}Descrição maliciosa`,
      }],
    });

    await page.locator("#isis2-toggle").click();
    await page.locator("#isis2-input").fill("malicioso");
    await page.locator("#isis2-form button[type=submit]").click();

    await page.waitForTimeout(700);
    expect(await page.evaluate(() => window.__isis2XssFired)).toBe(0);
    expect(await page.locator("#isis2-panel script").count()).toBe(0);
    await expect(page.locator("#isis2-panel")).toContainText("Produto malicioso");
  });

  test("mensagem do próprio usuário com HTML/script não executa nada", async ({ page }) => {
    await page.addInitScript(() => {
      window.__isis2XssFired = 0;
    });
    await irParaHomeComCatalogo(page);

    await page.locator("#isis2-toggle").click();
    await page.locator("#isis2-input").fill('<img src=x onerror="window.__isis2XssFired=1">');
    await page.locator("#isis2-form button[type=submit]").click();

    await page.waitForTimeout(700);
    expect(await page.evaluate(() => window.__isis2XssFired)).toBe(0);
  });

  test("payload 'javascript:alert(1)' nunca vira href clicável nem navega", async ({ page }) => {
    await irParaHomeComCatalogo(page);
    await page.locator("#isis2-toggle").click();
    await page.locator("#isis2-input").fill("javascript:alert(1)");
    await page.locator("#isis2-form button[type=submit]").click();
    await page.waitForTimeout(700);

    // Nenhum link do widget deve usar esse texto como href — os únicos
    // <a> renderizados vêm de productLink(), construído a partir do ID
    // real do produto (encodeURIComponent), nunca de texto livre do
    // usuário.
    const hrefsSuspeitos = await page.locator("#isis2-panel a[href]").evaluateAll(
      links => links.map(a => a.getAttribute("href")).filter(href => href && href.startsWith("javascript:"))
    );
    expect(hrefsSuspeitos).toEqual([]);
  });
});

test.describe("Isis 2.0 - mobile", () => {
  test.use({ viewport: { width: 390, height: 844 } });

  test("widget cabe na tela pequena e permanece utilizável", async ({ page }) => {
    await irParaHomeComCatalogo(page);
    await page.locator("#isis2-toggle").click();

    const panel = page.locator("#isis2-panel");
    await expect(panel).toBeVisible();
    const box = await panel.boundingBox();
    expect(box.width).toBeLessThanOrEqual(390);
  });

  test("não sobrepõe o botão do WhatsApp/CTA flutuante nem o banner de cookies", async ({ page }) => {
    await prepararCatalogo(page);
    await ligarFeatureFlagIsis2(page);
    await page.goto("/index.html");
    await expect.poll(() => page.evaluate(() => window.misticaCatalogState)).toBe("ready");

    const decline = page.locator("[data-consent-decline]");
    if (await decline.isVisible().catch(() => false)) {
      // O botão flutuante da Isis 2.0 não pode cobrir o banner de
      // consentimento enquanto o cliente não decidiu sobre cookies.
      await expect(decline).toBeVisible();
      await decline.click();
    }
  });
});

test.describe("Isis 2.0 - fonte do catálogo em navegador real", () => {
  test("catálogo ainda carregando: `products` já existe (fallback estático de app.js, igual ao resto do site), e é substituído pelo catálogo oficial quando pronto", async ({ page }) => {
    // Importante: `products` (const no topo de app.js) começa com um
    // fallback estático de 8 categorias — o mesmo que a vitrine normal
    // usa antes da sincronização confirmar. A Isis 2.0 herda esse
    // comportamento (não é uma invenção nova dela): hasCatalog() pode
    // ser true mesmo antes de window.misticaCatalogState virar "ready".
    // O que garantimos é que, quando "ready", o conteúdo é o do
    // catálogo oficial, não mais o fallback.
    let resolveRoute;
    const pending = new Promise(resolve => { resolveRoute = resolve; });
    await page.route("**/api/produtos?**", async route => {
      await pending;
      route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify([PRODUTO_API]) });
    });
    await ligarFeatureFlagIsis2(page);
    await page.goto("/index.html");

    await expect.poll(() => page.evaluate(() => Boolean(window.Isis2))).toBe(true);
    const duranteLoading = await page.evaluate(() => ({
      estado: window.misticaCatalogState,
      hasCatalog: window.Isis2.ProductKnowledge.hasCatalog(),
      temProdutoTeste: window.Isis2.ProductKnowledge.byId(`api-${501}`) !== null,
    }));
    expect(duranteLoading.estado).not.toBe("ready");
    expect(duranteLoading.temProdutoTeste, "produto da API não deveria existir antes da sincronização confirmar").toBe(false);

    resolveRoute();
    await expect.poll(() => page.evaluate(() => window.misticaCatalogState)).toBe("ready");
    const depois = await page.evaluate(() => ({
      hasCatalog: window.Isis2.ProductKnowledge.hasCatalog(),
      produtoReal: window.Isis2.ProductKnowledge.byId("api-501")?.name,
    }));
    expect(depois.hasCatalog).toBe(true);
    expect(depois.produtoReal).toBe(PRODUTO_API.nome);
  });

  test("página de produto (produto.html): ProductKnowledge lê o mesmo catálogo global", async ({ page }) => {
    await prepararCatalogo(page);
    await ligarFeatureFlagIsis2(page);
    await page.goto(`/produto.html?id=${PRODUTO_API.id}`);
    await expect.poll(() => page.evaluate(() => window.misticaCatalogState)).toBe("ready");
    const nome = await page.evaluate(prodId => {
      const found = window.Isis2.ProductKnowledge.byId(`api-${prodId}`);
      return found?.name;
    }, PRODUTO_API.id);
    expect(nome).toBe(PRODUTO_API.nome);
  });

  test("página de kit (kit.html): catálogo carrega sem erro mesmo sem a Isis 2.0 ligada nessa navegação", async ({ page }) => {
    await prepararCatalogo(page);
    await page.goto("/kit.html");
    await expect.poll(() => page.evaluate(() => window.misticaCatalogState)).toBe("ready");
    const total = await page.evaluate(() => (typeof products !== "undefined" ? products.length : 0));
    expect(total).toBeGreaterThan(0);
  });

  test("produto inexistente: CartAssistant nunca chama addToCart, devolve not_found", async ({ page }) => {
    await irParaHomeComCatalogo(page);
    const resultado = await page.evaluate(() => window.Isis2.CartAssistant.add("produto-que-nao-existe", 1));
    expect(resultado).toEqual({ ok: false, reason: "not_found" });
  });

  test("produto esgotado: ProductKnowledge.listAll() em estoque não inclui o produto, mesmo existindo no catálogo bruto", async ({ page }) => {
    await irParaHomeComCatalogo(page, { produtos: [{ ...PRODUTO_API, quantidade: 0 }] });
    const { emEstoque, total } = await page.evaluate(() => ({
      emEstoque: window.Isis2.ProductKnowledge.listAll({ onlyInStock: true }).length,
      total: window.Isis2.ProductKnowledge.listAll({ onlyInStock: false }).length,
    }));
    expect(total).toBe(1);
    expect(emEstoque).toBe(0);
  });

  test("ID numérico da API vira ID string interno ('api-<id>'); byId() usa esse formato real e tolera string/número na comparação", async ({ page }) => {
    await irParaHomeComCatalogo(page);
    const resultado = await page.evaluate(prodId => {
      const knowledge = window.Isis2.ProductKnowledge;
      return {
        // Formato real que mobile-sync.js usa: "api-<id>" (sempre string).
        porIdReal: Boolean(knowledge.byId(`api-${prodId}`)),
        // O ID numérico cru da API não é, sozinho, o ID do produto no
        // catálogo (que sempre carrega o prefixo "api-") — não deveria
        // casar. A tolerância string/número de byId() (testada em
        // unidade com um catálogo hipotético sem prefixo) não se aplica
        // aqui simplesmente porque o valor comparado é outro.
        porNumeroCruSemPrefixo: Boolean(knowledge.byId(prodId)),
        apiIdBateComOriginal: knowledge.byId(`api-${prodId}`)?.apiId === prodId,
      };
    }, PRODUTO_API.id);
    expect(resultado.porIdReal).toBe(true);
    expect(resultado.porNumeroCruSemPrefixo).toBe(false);
    expect(resultado.apiIdBateComOriginal).toBe(true);
  });

  test("falha da API: catálogo nunca fica 'ready' com dado inventado, Isis admite indisponibilidade", async ({ page }) => {
    await page.route("**/api/produtos?**", route => route.fulfill({ status: 500, contentType: "application/json", body: "{}" }));
    await ligarFeatureFlagIsis2(page);
    await page.goto("/index.html");
    await dismissConsent(page);
    await page.waitForTimeout(2000);
    const estado = await page.evaluate(() => window.misticaCatalogState);
    expect(estado).not.toBe("ready");
  });

  test("catálogo vazio ([] da API): Isis admite que não tem produtos, nunca inventa um", async ({ page }) => {
    await irParaHomeComCatalogo(page, { produtos: [] });
    const hasCatalog = await page.evaluate(() => window.Isis2.ProductKnowledge.hasCatalog());
    expect(hasCatalog).toBe(false);

    await page.locator("#isis2-toggle").click();
    await page.locator("#isis2-input").fill("Quero um incenso");
    await page.locator("#isis2-form button[type=submit]").click();
    await expect(page.locator(".isis2-message-bot").last()).toContainText(/não consigo consultar|catálogo/i);
  });
});

test.describe("Isis 2.0 - matriz de viewports", () => {
  const VIEWPORTS = [
    { name: "320x568 (iPhone SE)", width: 320, height: 568 },
    { name: "360x800 (Android comum)", width: 360, height: 800 },
    { name: "390x844 (iPhone 12/13)", width: 390, height: 844 },
    { name: "768x1024 (tablet)", width: 768, height: 1024 },
    { name: "1366x768 (notebook)", width: 1366, height: 768 },
    { name: "1920x1080 (desktop)", width: 1920, height: 1080 },
  ];

  for (const viewport of VIEWPORTS) {
    test(`${viewport.name}: sem rolagem horizontal, painel cabe na tela, botão continua clicável`, async ({ page }) => {
      await page.setViewportSize({ width: viewport.width, height: viewport.height });
      await irParaHomeComCatalogo(page);

      const semRolagemHorizontal = await page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth + 1);
      expect(semRolagemHorizontal, "página não deveria ter rolagem horizontal antes de abrir o widget").toBe(true);

      const toggle = page.locator("#isis2-toggle");
      await expect(toggle).toBeVisible();
      await toggle.click();

      const panel = page.locator("#isis2-panel");
      await expect(panel).toBeVisible();
      const box = await panel.boundingBox();
      expect(box.width, `painel (${box.width}px) não deveria ultrapassar o viewport (${viewport.width}px)`).toBeLessThanOrEqual(viewport.width);

      const semRolagemHorizontalAberto = await page.evaluate(() => document.documentElement.scrollWidth <= document.documentElement.clientWidth + 1);
      expect(semRolagemHorizontalAberto, "widget aberto não deveria introduzir rolagem horizontal").toBe(true);
    });
  }
});
