const { test, expect } = require("@playwright/test");

// Experiência premium da plataforma de estudo (hero cinematográfico, tempo de
// leitura, indicador de nível, barra de leitura fixa e card de próxima aula).
// Tudo é apresentação: a árvore mockada abaixo tem o mesmo formato devolvido
// por GET /api/escola/cursos/{slug} — nenhuma regra de LMS muda.
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
            '<p class="aula-kicker">Módulo 1 · Aula 1</p><h2>O que é o Xamanismo?</h2><p>Texto da aula.</p><div class="aula-divisor" role="presentation"><span>☾</span></div><aside class="aula-box aula-box-ciencia"><h3>Olhar da Ciência</h3><p>Os métodos têm limites.</p></aside>',
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

  // Barra de leitura fixa (sticky progress) presente e única.
  await expect(page.locator(".plataforma-readbar")).toHaveCount(1);

  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1)).toBe(true);
  expect(erros).toEqual([]);
});

test("capa fotográfica vira o fundo do hero e o nível acompanha a duração", async ({ page }) => {
  const erros = await abrirCurso(page);

  // Volta para a aula 1 (com capa): o hero ganha a foto de fundo.
  await page.locator("[data-prev]").click();
  const hero = page.locator(".aula-hero");
  await expect(hero).toHaveClass(/has-capa/);
  await expect(hero.locator(".aula-hero-media .aula-imagem img")).toHaveCount(1);
  await expect(hero.getByRole("heading", { level: 1 })).toHaveText("O que é o Xamanismo?");
  await expect(hero.locator("[data-nivel-leitura]")).toContainText("Nível intermediário");

  // O conteúdo autorado continua renderizando os elementos editoriais.
  await expect(page.locator(".plataforma-texto .aula-divisor")).toHaveCount(1);
  await expect(page.locator(".plataforma-texto .aula-box-ciencia")).toBeVisible();

  expect(erros).toEqual([]);
});

test("próxima aula em destaque no final e navegação sem recarregar a página", async ({ page }) => {
  const erros = await abrirCurso(page);
  await page.evaluate(() => { window.__semReload = true; });

  // Card "A seguir" aponta para a aula seguinte e navega sem reload.
  const card = page.locator("[data-next-card]");
  await expect(card).toBeVisible();
  await expect(card.locator(".aula-next-titulo")).toHaveText("Encerramento do módulo");
  await card.locator("[data-proxima-aula]").click();
  await expect(page.getByRole("heading", { name: "Encerramento do módulo", level: 1 })).toBeVisible();
  await expect(page.locator("[data-nivel-leitura]")).toContainText("Leitura aprofundada");

  // Última aula liberada: o destaque vira o encerramento da trilha.
  await expect(page.locator("[data-next-card].is-fim")).toBeVisible();

  // Se a página tivesse recarregado, a flag teria se perdido.
  expect(await page.evaluate(() => window.__semReload)).toBe(true);
  expect(erros).toEqual([]);
});
