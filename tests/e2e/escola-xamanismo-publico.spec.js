const { test, expect } = require("@playwright/test");

// Simula a árvore pública real (mesmo formato devolvido por
// GET /api/escola/publico/cursos/xamanismo-introducao): 2 módulos públicos
// com as 3 aulas (partes 1-3) e 1 módulo pago só com metadados bloqueados.
const arvorePublica = {
  slug: "xamanismo-introducao",
  titulo: "Introdução ao Xamanismo — As Origens da Sabedoria Ancestral",
  descricao: "Curso introdutório sobre história, diversidade cultural, espiritualidade e leitura crítica do xamanismo.",
  imagem: null,
  gratuito: true,
  modulos: [
    {
      id: 1,
      titulo: "Módulo 1 — O Chamado do Xamanismo",
      descricao: "Fundamentos históricos, diversidade cultural e permanência das tradições.",
      ordem: 0,
      publico: true,
      bloqueado: false,
      aulas: [
        {
          id: 11,
          titulo: "O que é o Xamanismo?",
          descricao: "Um primeiro mapa para compreender um termo amplo.",
          tipo: "texto",
          conteudo: "<h2>O que é o Xamanismo?</h2><p>Parte 1 pública.</p>",
          video_url: null,
          capa_url: null,
          material_url: null,
          ordem: 0,
          duracao_min: 12,
          obrigatoria: true,
        },
        {
          id: 12,
          titulo: "Por que o Xamanismo ainda existe?",
          descricao: "Tradições vivas e responsabilidade no presente.",
          tipo: "texto",
          conteudo: "<h2>Tradições vivas</h2><p>Parte 2 pública.</p>",
          video_url: null,
          capa_url: null,
          material_url: null,
          ordem: 1,
          duracao_min: 12,
          obrigatoria: true,
        },
      ],
    },
    {
      id: 2,
      titulo: "Módulo 2 — As Origens e os Caminhos do Xamanismo",
      descricao: "As origens históricas do termo, tradições rituais comparáveis em diferentes regiões e o caminho do xamanismo até o mundo contemporâneo.",
      ordem: 1,
      publico: true,
      bloqueado: false,
      aulas: [
        {
          id: 13,
          titulo: "A origem da palavra “xamã”",
          descricao: "De onde vem esse nome tão repetido.",
          tipo: "texto",
          conteudo: "<h2>A origem da palavra “xamã”</h2><p>Aula 1 do Módulo 2.</p>",
          video_url: null,
          capa_url: null,
          material_url: null,
          ordem: 0,
          duracao_min: 13,
          obrigatoria: true,
        },
        {
          id: 14,
          titulo: "Tradições semelhantes em diferentes regiões",
          descricao: "Cantos, tambores e sonhos aparecem em muitos povos.",
          tipo: "texto",
          conteudo: "<h2>Tradições semelhantes em diferentes regiões</h2><p>Aula 2 do Módulo 2.</p>",
          video_url: null,
          capa_url: null,
          material_url: null,
          ordem: 1,
          duracao_min: 14,
          obrigatoria: true,
        },
        {
          id: 15,
          titulo: "Como o xamanismo chegou ao mundo moderno",
          descricao: "De relatos de viajantes a um fenômeno urbano global.",
          tipo: "texto",
          conteudo: "<h2>Como o xamanismo chegou ao mundo moderno</h2><p>Aula 3 do Módulo 2.</p>",
          video_url: null,
          capa_url: null,
          material_url: null,
          ordem: 2,
          duracao_min: 15,
          obrigatoria: true,
        },
      ],
    },
    {
      id: 3,
      titulo: "Módulo 3 — Conteúdo premium (futuro)",
      ordem: 2,
      publico: false,
      bloqueado: true,
    },
  ],
};

async function mockApiAnonima(page) {
  await page.route("**/api/alunos/me", route => route.fulfill({ status: 401, contentType: "application/json", body: "{}" }));
  await page.route("**/api/escola/cursos/xamanismo-introducao", route =>
    route.fulfill({ status: 401, contentType: "application/json", body: JSON.stringify({ detail: "Faça login para continuar." }) })
  );
  await page.route("**/api/escola/publico/cursos/xamanismo-introducao", route =>
    route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(arvorePublica) })
  );
  // isis2/isis2-homolog-gate.js (sempre carregado) consulta este endpoint
  // quando a flag estática está desligada; sem mock, a chamada real ao
  // domínio da API é bloqueada por CORS no ambiente de teste e vira um
  // erro de console alheio ao que esta suíte audita.
  await page.route("**/api/isis2/homolog-config", route =>
    route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ enabled: false, escola: false, refinamento: false, homologacao: false }) })
  );
  // isis2/chat-gate.js (Chat Inteligente da Isis 2.0, também sempre
  // carregado) consulta este outro endpoint em paralelo -- mesmo motivo
  // do mock acima.
  await page.route("**/api/isis2/chat/config", route =>
    route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ enabled: false, homolog: false, authorized: false }) })
  );
}

// "Failed to load resource" é o diagnóstico automático do Chromium para toda
// resposta HTTP não-2xx (inclui o 401 esperado do fallback anônimo real e a
// fonte do Google Fonts, bloqueada por falta de rede externa neste sandbox de
// CI) — não é um erro de JavaScript da aplicação. `pageerror` (exceções reais
// não tratadas) continua verificado à parte, sem filtro.
const ehDiagnosticoDeRecurso = texto => /Failed to load resource/i.test(texto);

test.describe("Acesso público ao curso de Xamanismo (visitante anônimo)", () => {
  test("escola.html mostra o curso gratuito, sem card duplicado", async ({ page }) => {
    const erros = [];
    page.on("console", msg => { if (msg.type() === "error" && !ehDiagnosticoDeRecurso(msg.text())) erros.push(msg.text()); });
    page.on("pageerror", erro => erros.push(erro.message));
    await mockApiAnonima(page);

    await page.goto("/escola.html");
    const cards = page.locator('[data-course-card="xamanismo-introducao"]');
    await expect(cards).toHaveCount(1); // não duplica o card
    await expect(cards.locator(".escola-badge.gratuito")).toHaveText("Gratuito");
    await expect(cards.getByRole("link", { name: "Começar agora" })).toHaveAttribute(
      "href",
      "escola-curso.html?curso=xamanismo-introducao"
    );
    expect(erros).toEqual([]);
  });

  test("visitante abre o curso sem login e conclui as 5 aulas gratuitas com o CTA único (progresso só em sessionStorage)", async ({ page }) => {
    const erros = [];
    const chamadasArvorePublica = [];
    const postsDeProgresso = [];
    page.on("console", msg => { if (msg.type() === "error" && !ehDiagnosticoDeRecurso(msg.text())) erros.push(msg.text()); });
    page.on("pageerror", erro => erros.push(erro.message));
    page.on("request", req => { if (req.method() === "POST" && /\/progresso/.test(req.url())) postsDeProgresso.push(req.url()); });
    // Percurso longo (5 aulas + drawer + login): com prefers-reduced-motion o
    // scroll é instantâneo e os cliques ficam estáveis em qualquer viewport.
    await page.emulateMedia({ reducedMotion: "reduce" });
    await mockApiAnonima(page);
    await page.route("**/api/escola/publico/cursos/xamanismo-introducao", route => {
      chamadasArvorePublica.push(1);
      route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(arvorePublica) });
    });

    await page.goto("/escola-curso.html?curso=xamanismo-introducao");

    // Não é redirecionado para tela de login nas partes públicas.
    await expect(page.locator(".plataforma-login")).toHaveCount(0);
    await expect(page.getByRole("heading", { name: "O que é o Xamanismo?", level: 1 })).toBeVisible();

    // Contagem real das 5 aulas públicas (2 do Módulo 1 + 3 do Módulo 2) —
    // nunca "0/0", mesmo sem sessão/matrícula.
    await expect(page.locator(".plataforma-sidebar-head small")).toHaveText("0/5 aulas • 0%");

    // Estados honestos para o visitante anônimo: nada de "Em andamento".
    const badges = page.locator(".plataforma-modulo-badge");
    await expect(badges.nth(0)).toHaveText("Você está aqui");
    await expect(badges.nth(1)).toHaveText("Disponível");
    await expect(badges.nth(2)).toHaveText("🔒 Conteúdo pago");
    await expect(page.locator(".plataforma-modulo-badge", { hasText: "Em andamento" })).toHaveCount(0);

    // Percorre as 5 aulas com a ação principal única "Marcar como concluída e
    // continuar" (funciona em qualquer viewport, sem abrir o drawer).
    const principal = page.locator("[data-concluir-continuar]");
    await expect(principal).toHaveText(/Marcar como concluída e continuar/);
    await principal.click();
    await expect(page.getByRole("heading", { name: "Por que o Xamanismo ainda existe?", level: 1 })).toBeVisible();
    await principal.click();
    await expect(page.getByRole("heading", { name: "A origem da palavra “xamã”", level: 1 })).toBeVisible();
    await principal.click();
    await expect(page.getByRole("heading", { name: "Tradições semelhantes em diferentes regiões", level: 1 })).toBeVisible();
    await principal.click();
    await expect(page.getByRole("heading", { name: "Como o xamanismo chegou ao mundo moderno", level: 1 })).toBeVisible();

    // O progresso do anônimo é efêmero: vive em sessionStorage, nunca vai ao
    // servidor nem para localStorage.
    await expect(page.locator(".plataforma-sidebar-head small")).toHaveText("4/5 aulas • 80%");
    expect(postsDeProgresso).toEqual([]);
    expect(await page.evaluate(() => sessionStorage.getItem("plataforma_progresso_anonimo"))).toContain("concluida");
    expect(await page.evaluate(() => localStorage.getItem("plataforma_progresso_anonimo"))).toBeNull();

    // Módulo 1 completo nesta sessão: o estado conta a história certa.
    await expect(badges.nth(0)).toHaveText("Concluído nesta sessão");

    // No mobile a lista de módulos vive num drawer fechado por padrão; no
    // desktop já está visível na barra lateral. Abre o drawer só quando ele
    // existe (botão "☰ Módulos" visível) para ver o módulo futuro bloqueado.
    const abrirModulos = page.locator("[data-drawer-toggle]");
    const temDrawer = await abrirModulos.isVisible();
    if (temDrawer) await abrirModulos.click();
    await expect(page.getByText("Módulo 3 — Conteúdo premium (futuro)")).toBeVisible();
    await expect(page.getByText("🔒 Conteúdo pago")).toBeVisible();

    if (temDrawer) {
      // Escape fecha o drawer e devolve o foco para quem o abriu.
      await page.keyboard.press("Escape");
      await expect(page.locator(".plataforma-layout")).not.toHaveClass(/drawer-open/);
      await expect(abrirModulos).toBeFocused();
      await abrirModulos.click();
    }

    // O módulo pago recolhido expande pelo cabeçalho; só o clique no recurso
    // protegido (CTA) leva ao login.
    await page.locator('[data-toggle-modulo="3"]').click();
    await page.locator("#modulo-corpo-3 [data-login-cta]").click();
    await expect(page.locator(".plataforma-login")).toBeVisible();
    await expect(page.getByRole("heading", { name: "Entrar na Escola Mística" })).toBeVisible();

    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1)).toBe(true);
    expect(erros).toEqual([]);
    expect(chamadasArvorePublica.length).toBeLessThanOrEqual(2); // sem loop de requisições
  });
});
