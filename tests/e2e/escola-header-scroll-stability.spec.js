const { test, expect } = require("@playwright/test");

// A gravação de vídeo é uma opção que força worker/contexto próprio no
// Playwright. Por isso precisa ficar no nível superior do arquivo, nunca
// dentro de test.describe().
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
  await page.goto("/escola-curso.html?curso=xamanismo-introducao");
  await expect(page.locator("[data-header-sentinel]")).toHaveCount(1);
  await expect(page.locator(".aula-hero")).toBeVisible();
  return erros;
}

async function instalarMedicoes(page) {
  await page.evaluate(() => {
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
      try { observer.observe({ type: "layout-shift", buffered: true }); } catch { /* navegador sem suporte */ }
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
    const diagnostico = window.__escolaHeaderDiagnostics;
    return {
      ativacoes,
      desativacoes,
      total: eventos.length,
      cls: window.__clsEscola,
      diagnostico,
      sentinelCount: document.querySelectorAll("[data-header-sentinel]").length,
      readbarCount: document.querySelectorAll(".plataforma-readbar").length,
    };
  });

  // Dez ciclos completos + a ativação final: exatamente uma mudança por
  // travessia, sem pingue-pongue adicional no mesmo sentido.
  expect(resultado.ativacoes).toBeLessThanOrEqual(11);
  expect(resultado.desativacoes).toBeLessThanOrEqual(10);
  expect(resultado.total).toBeLessThanOrEqual(21);
  expect(resultado.cls).toBeLessThan(0.02);
  expect(resultado.sentinelCount).toBe(1);
  expect(resultado.readbarCount).toBe(1);
  expect(resultado.diagnostico.observersCriados).toBe(1);
  expect(resultado.diagnostico.listenersLegadosBloqueados).toBe(2);
  expect(resultado.diagnostico.alteracoes).toBeLessThanOrEqual(21);
  expect(erros).toEqual([]);
}

for (const cenario of [
  { nome: "desktop-1366x768", viewport: { width: 1366, height: 768 }, reducedMotion: "no-preference" },
  { nome: "desktop-1920x1080", viewport: { width: 1920, height: 1080 }, reducedMotion: "no-preference" },
  { nome: "pixel-7", viewport: { width: 412, height: 915 }, reducedMotion: "no-preference", hasTouch: true, isMobile: true },
  { nome: "iphone-14", viewport: { width: 390, height: 844 }, reducedMotion: "no-preference", hasTouch: true, isMobile: true },
  { nome: "prefers-reduced-motion", viewport: { width: 1366, height: 768 }, reducedMotion: "reduce" },
]) {
  test.describe(cenario.nome, () => {
    test.use({
      viewport: cenario.viewport,
      reducedMotion: cenario.reducedMotion,
      hasTouch: Boolean(cenario.hasTouch),
      isMobile: Boolean(cenario.isMobile),
    });

    test("header compacto muda uma vez por travessia lenta do limite", async ({ page }, testInfo) => {
      await validarCiclo(page, testInfo);
    });
  });
}
