const { test, expect } = require("@playwright/test");

test.use({ video: "on" });

const paragrafoLongo = "O xamanismo reúne tradições diversas, transmitidas em contextos culturais próprios. Este conteúdo de teste cria altura suficiente para uma rolagem lenta e determinística sem alterar as regras do LMS.";
const conteudoLongo = `<h2>Leitura estável</h2>${Array.from({ length: 45 }, (_, i) => `<p>${i + 1}. ${paragrafoLongo}</p>`).join("")}`;

const curso = {
  slug: "xamanismo-introducao",
  titulo: "Introdução ao Xamanismo",
  certificado: false,
  progresso: { total_aulas: 1, aulas_concluidas: 0, percentual: 0, concluido: false },
  modulos: [{
    id: 1,
    titulo: "Módulo 1 — O Chamado do Xamanismo",
    liberado: true,
    concluido: false,
    quiz: null,
    aulas: [{
      id: 11,
      titulo: "O que é o Xamanismo?",
      descricao: "Uma introdução para validar a estabilidade visual do player.",
      tipo: "texto",
      conteudo: conteudoLongo,
      ordem: 0,
      duracao_min: 12,
      obrigatoria: true,
      status: "nao_iniciada",
      percentual: 0,
    }],
  }],
};

async function abrirCurso(page) {
  const erros = [];
  page.on("console", mensagem => {
    if (mensagem.type() === "error" && !/Failed to load resource/i.test(mensagem.text())) erros.push(mensagem.text());
  });
  page.on("pageerror", erro => erros.push(erro.message));
  await page.route("**/api/escola/cursos/xamanismo-introducao", rota =>
    rota.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(curso) })
  );
  // isis2/isis2-homolog-gate.js (sempre carregado, ver isis2/README.md)
  // consulta este endpoint quando a flag estática está desligada; sem
  // mock, a chamada real ao domínio da API é bloqueada por CORS no
  // ambiente de teste e o navegador loga um erro de console -- o que
  // faria esta suíte (que audita "zero erros de console") falhar por um
  // motivo alheio ao que ela testa.
  await page.route("**/api/isis2/homolog-config", rota =>
    rota.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ enabled: false, escola: false, refinamento: false, homologacao: false }) })
  );
  // isis2/chat-gate.js (Chat Inteligente da Isis 2.0, também sempre
  // carregado) consulta este outro endpoint em paralelo -- mesmo motivo
  // do mock acima: sem ele, a chamada real é bloqueada por CORS e vira
  // um erro de console alheio ao que esta suíte audita.
  await page.route("**/api/isis2/chat/config", rota =>
    rota.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ enabled: false, homolog: false, authorized: false }) })
  );
  await page.goto("/escola-curso.html?curso=xamanismo-introducao");
  await expect(page.locator("[data-header-sentinel]")).toHaveCount(1);
  await expect(page.locator(".aula-hero")).toBeVisible();
  return erros;
}

async function instalarMedicoes(page) {
  await page.evaluate(async () => {
    // A medição é específica da transição do header. Aguarda fontes e duas
    // pinturas estáveis para não misturar CLS da carga inicial com o CLS das
    // travessias que este teste realmente valida.
    if (document.fonts?.ready) await document.fonts.ready;
    await new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)));

    window.__mudancasClasseCompacta = [];
    window.__clsEscola = 0;

    const registrar = () => {
      window.__mudancasClasseCompacta.push({
        compacto: document.body.classList.contains("is-leitura-compacta"),
        y: window.scrollY,
        instante: performance.now(),
      });
    };

    new MutationObserver(mudancas => {
      if (mudancas.some(m => m.attributeName === "class")) registrar();
    }).observe(document.body, { attributes: true, attributeFilter: ["class"] });

    if ("PerformanceObserver" in window) {
      const observer = new PerformanceObserver(lista => {
        for (const entrada of lista.getEntries()) {
          if (!entrada.hadRecentInput) window.__clsEscola += entrada.value;
        }
      });
      try {
        // Não usa buffered:true: entradas anteriores pertencem à carga inicial,
        // não às travessias do header avaliadas abaixo.
        observer.observe({ type: "layout-shift" });
      } catch { /* navegador sem suporte */ }
    }
  });
}

async function rolarEmPassos(page, destino, passo = 4) {
  const inicio = await page.evaluate(() => window.scrollY);
  const direcao = destino >= inicio ? 1 : -1;
  for (let y = inicio; direcao > 0 ? y < destino : y > destino; y += passo * direcao) {
    await page.evaluate(valor => window.scrollTo(0, valor), y);
    await page.waitForTimeout(8);
  }
  await page.evaluate(valor => window.scrollTo(0, valor), destino);
  await page.waitForTimeout(40);
}

async function validarCiclo(page, testInfo) {
  const erros = await abrirCurso(page);
  await instalarMedicoes(page);

  const sentinelY = await page.locator("[data-header-sentinel]").evaluate(el => el.getBoundingClientRect().top + window.scrollY);
  const antes = Math.max(0, Math.floor(sentinelY - 40));
  const depois = Math.floor(sentinelY + 60);

  await rolarEmPassos(page, antes);
  await page.screenshot({ path: testInfo.outputPath("header-antes-limite.png"), fullPage: false });

  for (let i = 0; i < 10; i++) {
    await rolarEmPassos(page, depois, 3);
    await expect(page.locator("body")).toHaveClass(/is-leitura-compacta/);
    if (i === 0) await page.screenshot({ path: testInfo.outputPath("header-durante-limite.png"), fullPage: false });

    await rolarEmPassos(page, antes, 3);
    await expect(page.locator("body")).not.toHaveClass(/is-leitura-compacta/);
  }

  await rolarEmPassos(page, depois, 3);
  await page.screenshot({ path: testInfo.outputPath("header-depois-limite.png"), fullPage: false });

  const resultado = await page.evaluate(() => {
    const eventos = window.__mudancasClasseCompacta.filter((evento, indice, todos) =>
      indice === 0 || evento.compacto !== todos[indice - 1].compacto
    );
    const ativacoes = eventos.filter(e => e.compacto).length;
    const desativacoes = eventos.filter(e => !e.compacto).length;
    return {
      ativacoes,
      desativacoes,
      total: eventos.length,
      cls: window.__clsEscola,
      diagnostico: window.__escolaHeaderDiagnostics,
      sentinelCount: document.querySelectorAll("[data-header-sentinel]").length,
      readbarCount: document.querySelectorAll(".plataforma-readbar").length,
    };
  });

  expect(resultado.ativacoes).toBeLessThanOrEqual(11);
  expect(resultado.desativacoes).toBeLessThanOrEqual(10);
  expect(resultado.total).toBeLessThanOrEqual(21);
  expect(resultado.cls).toBeLessThan(0.02);
  expect(resultado.sentinelCount).toBe(1);
  expect(resultado.readbarCount).toBe(1);
  expect(resultado.diagnostico.observersCriados).toBeGreaterThanOrEqual(1);
  expect(resultado.diagnostico.interceptacoesGlobais).toBe(0);
  expect(resultado.diagnostico.alteracoes).toBeLessThanOrEqual(21);
  expect(erros).toEqual([]);
}

for (const cenario of [
  { nome: "desktop-1366x768", projeto: "desktop-chromium", viewport: { width: 1366, height: 768 }, reducedMotion: "no-preference" },
  { nome: "desktop-1920x1080", projeto: "desktop-chromium", viewport: { width: 1920, height: 1080 }, reducedMotion: "no-preference" },
  { nome: "pixel-7", projeto: "mobile-chromium", viewport: { width: 412, height: 915 }, reducedMotion: "no-preference", hasTouch: true, isMobile: true },
  { nome: "iphone-14", projeto: "mobile-chromium", viewport: { width: 390, height: 844 }, reducedMotion: "no-preference", hasTouch: true, isMobile: true },
  { nome: "prefers-reduced-motion", projeto: "desktop-chromium", viewport: { width: 1366, height: 768 }, reducedMotion: "reduce" },
]) {
  test.describe(cenario.nome, () => {
    test.use({
      viewport: cenario.viewport,
      reducedMotion: cenario.reducedMotion,
      hasTouch: Boolean(cenario.hasTouch),
      isMobile: Boolean(cenario.isMobile),
    });

    test("header compacto muda uma vez por travessia lenta do limite", async ({ page }, testInfo) => {
      test.skip(testInfo.project.name !== cenario.projeto, "cenário coberto no projeto correspondente");
      await validarCiclo(page, testInfo);
    });
  });
}
