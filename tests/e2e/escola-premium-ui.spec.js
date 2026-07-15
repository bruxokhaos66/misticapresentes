const { test, expect } = require("@playwright/test");

// Experiência premium da plataforma de estudo (hero cinematográfico, tempo de
// leitura, sidebar recolhível, CTA único de conclusão, mini índice, header
// compacto e acessibilidade). Tudo é apresentação: a árvore mockada abaixo tem
// o mesmo formato devolvido por GET /api/escola/cursos/{slug} — nenhuma regra
// de LMS muda.
const curso = {
  slug: "xamanismo-introducao",
  titulo: "Introdução ao Xamanismo — As Origens da Sabedoria Ancestral",
  certificado: false,
  progresso: { total_aulas: 3, aulas_concluidas: 1, percentual: 33, concluido: false },
  modulos: [
    {
      id: 1,
      titulo: "Módulo 1 — O Chamado do Xamanismo",
      liberado: true,
      concluido: false,
      aulas: [
        {
          id: 11,
          titulo: "O que é o Xamanismo?",
          descricao: "Um primeiro mapa para compreender um termo amplo.",
          tipo: "texto",
          conteudo:
            '<figure class="aula-imagem"><img alt="Capa da aula" src="assets/escola/xamanismo/modulo-1-aula-1-capa.webp" width="1200" height="630"><figcaption>Capa <span class="aula-imagem-credito">Imagem exclusiva — Mística Escola.</span></figcaption></figure>' +
            '<p class="aula-kicker">Módulo 1 · Aula 1</p><h2>O que é o Xamanismo?</h2><p>Texto da aula.</p><h2>Uma palavra, muitos mundos</h2><p>Seção 1.</p><h2>O que a ciência observa</h2><p>Seção 2.</p><div class="aula-divisor" role="presentation"><span>☾</span></div><aside class="aula-box aula-box-ciencia"><h3>Olhar da Ciência</h3><p>Os métodos têm limites.</p></aside>',
          ordem: 0,
          duracao_min: 12,
          obrigatoria: true,
          status: "concluida",
          percentual: 100,
        },
        {
          id: 12,
          titulo: "Por que o Xamanismo ainda existe?",
          descricao: "Tradições vivas e responsabilidade no presente.",
          tipo: "texto",
          conteudo: "<h2>Tradições vivas</h2><p>Comunidades transmitem e recriam conhecimentos.</p>",
          ordem: 1,
          duracao_min: 7,
          obrigatoria: true,
          status: "nao_iniciada",
          percentual: 0,
        },
        {
          id: 13,
          titulo: "Encerramento do módulo",
          descricao: "Síntese final.",
          tipo: "texto",
          conteudo: "<h2>Encerramento</h2><p>Síntese final da jornada.</p>",
          ordem: 2,
          duracao_min: 18,
          obrigatoria: true,
          status: "nao_iniciada",
          percentual: 0,
        },
      ],
      quiz: null,
    },
  ],
};

async function abrirCurso(page) {
  const erros = [];
  page.on("console", msg => { if (msg.type() === "error" && !/Failed to load resource/i.test(msg.text())) erros.push(msg.text()); });
  page.on("pageerror", erro => erros.push(erro.message));
  await page.route("**/api/escola/cursos/xamanismo-introducao", route =>
    route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(curso) })
  );
  await page.route("**/api/escola/aulas/*/progresso", route =>
    route.fulfill({ status: 200, contentType: "application/json", body: "{}" })
  );
  await page.goto("/escola-curso.html?curso=xamanismo-introducao");
  return erros;
}

test("hero cinematográfico com meta da aula (posição, tempo de leitura e nível)", async ({ page }) => {
  const erros = await abrirCurso(page);

  // A primeira aula pendente é a 12 (a 11 já está concluída).
  const hero = page.locator(".aula-hero");
  await expect(hero).toBeVisible();
  await expect(hero.getByRole("heading", { level: 1 })).toHaveText("Por que o Xamanismo ainda existe?");
  await expect(hero.locator(".plataforma-conteudo-modulo")).toHaveText("Módulo 1 — O Chamado do Xamanismo");

  // Meta da aula: posição, tempo estimado (usa duracao_min) e nível visual.
  await expect(hero.locator(".aula-meta")).toContainText("Aula 2 de 3");
  await expect(hero.locator("[data-tempo-leitura]")).toContainText("~7 min de leitura");
  await expect(hero.locator("[data-nivel-leitura]")).toContainText("Leitura leve");

  // A descrição vira o bloco "Em poucas palavras" no corpo (fora do hero).
  await expect(page.locator(".aula-resumo")).toContainText("Em poucas palavras");
  await expect(page.locator(".aula-resumo")).toContainText("Tradições vivas e responsabilidade no presente.");

  // document.title acompanha a aula aberta.
  await expect(page).toHaveTitle(/Por que o Xamanismo ainda existe\?/);

  // Barra de leitura fixa (sticky progress) presente e única.
  await expect(page.locator(".plataforma-readbar")).toHaveCount(1);

  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1)).toBe(true);
  expect(erros).toEqual([]);
});

test("capa fotográfica vira o fundo do hero, mini índice lista as seções e o nível acompanha a duração", async ({ page }) => {
  // Navegação intensa: valida também o caminho prefers-reduced-motion
  // (scroll instantâneo, sem animação de entrada).
  await page.emulateMedia({ reducedMotion: "reduce" });
  const erros = await abrirCurso(page);

  // Volta para a aula 1 (com capa): o hero ganha a foto de fundo.
  await page.locator("[data-prev]").click();
  const hero = page.locator(".aula-hero");
  await expect(hero).toHaveClass(/has-capa/);
  await expect(hero.locator(".aula-hero-media .aula-imagem img")).toHaveCount(1);
  await expect(hero.getByRole("heading", { level: 1 })).toHaveText("O que é o Xamanismo?");
  await expect(hero.locator("[data-nivel-leitura]")).toContainText("Nível intermediário");

  // Mini índice: só as seções reais entram (nem o h2 que repete o título da
  // aula, nem o h3 do card "Olhar da Ciência").
  const indice = page.locator(".aula-indice");
  await expect(indice).toBeVisible();
  await expect(indice.locator("li")).toHaveCount(2);
  await expect(indice).toContainText("Uma palavra, muitos mundos");
  await expect(indice).not.toContainText("Olhar da Ciência");
  await indice.locator("a").first().click();
  await expect(page.locator("#aula-secao-1")).toBeInViewport();

  // O conteúdo autorado continua renderizando os elementos editoriais.
  await expect(page.locator(".plataforma-texto .aula-divisor")).toHaveCount(1);
  await expect(page.locator(".plataforma-texto .aula-box-ciencia")).toBeVisible();

  expect(erros).toEqual([]);
});

test("uma única ação principal conclui e continua; card 'A seguir' é prévia sem botão", async ({ page }) => {
  const erros = await abrirCurso(page);
  await page.evaluate(() => { window.__semReload = true; });

  // Card "A seguir" é prévia pura: mostra a próxima aula, sem botão duplicado.
  const card = page.locator("[data-next-card]");
  await expect(card).toBeVisible();
  await expect(card.locator(".aula-next-titulo")).toHaveText("Encerramento do módulo");
  await expect(card.locator("button")).toHaveCount(0);

  // Não existe mais o antigo trio de botões: só Anterior + ação principal.
  await expect(page.locator("[data-next]")).toHaveCount(0);
  const principal = page.locator("[data-concluir-continuar]");
  await expect(principal).toHaveText(/Marcar como concluída e continuar/);

  // Concluir + continuar navega sem reload e move o foco para o novo título.
  await principal.click();
  await expect(page.getByRole("heading", { name: "Encerramento do módulo", level: 1 })).toBeVisible();
  await expect(page.locator("[data-nivel-leitura]")).toContainText("Leitura aprofundada");
  await expect(page.getByRole("heading", { name: "Encerramento do módulo", level: 1 })).toBeFocused();

  // Última aula liberada: o destaque vira o encerramento da trilha e o CTA
  // deixa de prometer continuação.
  await expect(page.locator("[data-next-card].is-fim")).toBeVisible();
  await expect(page.locator("[data-concluir-continuar]")).toHaveText("Marcar como concluída");

  // Se a página tivesse recarregado, a flag teria se perdido.
  expect(await page.evaluate(() => window.__semReload)).toBe(true);
  expect(erros).toEqual([]);
});

test("sidebar: 300–320px no desktop, aria-current na aula ativa e módulo recolhível pelo teclado", async ({ page }) => {
  const erros = await abrirCurso(page);

  const sidebar = page.locator("[data-sidebar]");
  const drawerToggle = page.locator("[data-drawer-toggle]");
  if (await drawerToggle.isVisible()) {
    // Mobile: a sidebar vive num drawer; abre para inspecionar.
    await drawerToggle.click();
  } else {
    const box = await sidebar.boundingBox();
    expect(box.width).toBeGreaterThanOrEqual(300);
    expect(box.width).toBeLessThanOrEqual(320);
  }

  // Estado do módulo: o aluno está nele ("Você está aqui"), não "Em andamento".
  await expect(sidebar.locator(".plataforma-modulo-badge")).toHaveText("Você está aqui");

  // aria-current marca a aula ativa.
  await expect(sidebar.locator('[data-aula][aria-current="true"] .plataforma-aula-titulo')).toContainText("Por que o Xamanismo ainda existe?");

  // Duração em badge compacto.
  await expect(sidebar.locator(".plataforma-aula-tempo").first()).toHaveText("12 min");

  // Cabeçalho do módulo recolhe/expande via teclado (aria-expanded).
  const cabecalho = sidebar.locator("[data-toggle-modulo]");
  await expect(cabecalho).toHaveAttribute("aria-expanded", "true");
  await cabecalho.focus();
  await page.keyboard.press("Enter");
  await expect(cabecalho).toHaveAttribute("aria-expanded", "false");
  await expect(sidebar.locator(".plataforma-aulas")).toBeHidden();
  await page.keyboard.press("Enter");
  await expect(cabecalho).toHaveAttribute("aria-expanded", "true");
  await expect(sidebar.locator(".plataforma-aulas")).toBeVisible();

  expect(erros).toEqual([]);
});

test("header compacto após rolar: some no topo, aparece durante a leitura", async ({ page }) => {
  const erros = await abrirCurso(page);

  await expect(page.locator("body")).not.toHaveClass(/is-leitura-compacta/);
  await page.evaluate(() => window.scrollTo(0, 600));
  await expect(page.locator("body")).toHaveClass(/is-leitura-compacta/);
  await expect(page.locator("[data-header-aula]")).toHaveText("Por que o Xamanismo ainda existe?");
  await page.evaluate(() => window.scrollTo(0, 0));
  await expect(page.locator("body")).not.toHaveClass(/is-leitura-compacta/);

  expect(erros).toEqual([]);
});

test("troca repetida de aulas não acumula erros nem estoura o layout", async ({ page }) => {
  // Troca rápida de aulas com prefers-reduced-motion: sem scroll suave nem
  // animações, o player precisa responder instantaneamente.
  await page.emulateMedia({ reducedMotion: "reduce" });
  const erros = await abrirCurso(page);

  // Vai e volta várias vezes entre as aulas liberadas (sem reload).
  for (let i = 0; i < 4; i++) {
    await page.locator("[data-prev]").click();
    await expect(page.getByRole("heading", { name: "O que é o Xamanismo?", level: 1 })).toBeVisible();
    // Aula 11 já está concluída: o CTA vira só "continuar", sem re-marcar.
    const principal = page.locator("[data-concluir-continuar]");
    await expect(principal).toHaveText(/Continuar para a próxima aula/);
    await principal.click();
    await expect(page.getByRole("heading", { name: "Por que o Xamanismo ainda existe?", level: 1 })).toBeVisible();
  }

  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1)).toBe(true);
  expect(erros).toEqual([]);
});
