const { test, expect } = require("@playwright/test");

const curso = {
  slug: "xamanismo-introducao",
  titulo: "Introdução ao Xamanismo — As Origens da Sabedoria Ancestral",
  certificado: false,
  progresso: { total_aulas: 2, aulas_concluidas: 0, percentual: 0, concluido: false },
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
          conteudo: '<h2>O que é o Xamanismo?</h2><aside class="aula-box"><h3>Olhar da Ciência</h3><p>Os métodos têm limites.</p></aside><script>window.__ataque=1</script><img alt="teste de sanitização" src="data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///ywAAAAAAQABAAACAUwAOw==" onerror="window.__ataque=2">',
          ordem: 0,
          duracao_min: 12,
          obrigatoria: true,
          status: "nao_iniciada",
          percentual: 0,
        },
        {
          id: 12,
          titulo: "Por que o Xamanismo ainda existe?",
          descricao: "Tradições vivas e responsabilidade no presente.",
          tipo: "texto",
          conteudo: "<h2>Tradições vivas</h2><p>Comunidades transmitem e recriam conhecimentos.</p>",
          ordem: 1,
          duracao_min: 12,
          obrigatoria: true,
          status: "nao_iniciada",
          percentual: 0,
        },
      ],
      quiz: { id: 21, titulo: "Avaliação — O Chamado do Xamanismo", disponivel: false, aprovado: false, maior_nota: null },
    },
    {
      id: 2,
      titulo: "Módulo 2 — As Origens e os Caminhos do Xamanismo",
      liberado: false,
      concluido: false,
      aulas: [
        { id: 13, titulo: "A origem da palavra “xamã”", ordem: 0, obrigatoria: true, status: "nao_iniciada", percentual: 0 },
        { id: 14, titulo: "Tradições semelhantes em diferentes regiões", ordem: 1, obrigatoria: true, status: "nao_iniciada", percentual: 0 },
        { id: 15, titulo: "Como o xamanismo chegou ao mundo moderno", ordem: 2, obrigatoria: true, status: "nao_iniciada", percentual: 0 },
      ],
      quiz: null,
    },
  ],
};

// "Failed to load resource" é o diagnóstico automático do Chromium para toda
// resposta de rede que falha (ex.: Google Fonts bloqueado no sandbox de CI) —
// não é um erro de JavaScript da aplicação. Mesmo filtro já usado em
// escola-xamanismo-publico.spec.js; `pageerror` continua verificado sem filtro.
const ehDiagnosticoDeRecurso = texto => /Failed to load resource/i.test(texto);

test("módulo de Xamanismo renderiza responsivamente, sem console error e sanitiza HTML", async ({ page }) => {
  const erros = [];
  page.on("console", msg => { if (msg.type() === "error" && !ehDiagnosticoDeRecurso(msg.text())) erros.push(msg.text()); });
  page.on("pageerror", erro => erros.push(erro.message));
  await page.route("**/api/escola/cursos/xamanismo-introducao", route =>
    route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(curso) })
  );
  // isis2/isis2-homolog-gate.js (sempre carregado) consulta este endpoint
  // quando a flag estática está desligada; sem mock, a chamada real ao
  // domínio da API é bloqueada por CORS no ambiente de teste e vira um
  // erro de console alheio ao que este teste audita.
  await page.route("**/api/isis2/homolog-config", route =>
    route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ enabled: false, escola: false, refinamento: false, homologacao: false }) })
  );
  // isis2/chat-gate.js (Chat Inteligente da Isis 2.0, também sempre
  // carregado) consulta este outro endpoint em paralelo -- mesmo motivo
  // do mock acima.
  await page.route("**/api/isis2/chat/config", route =>
    route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ enabled: false, homolog: false, authorized: false }) })
  );

  await page.goto("/escola-curso.html?curso=xamanismo-introducao");
  await expect(page.getByRole("heading", { name: "O que é o Xamanismo?", level: 1 })).toBeVisible();
  await expect(page.getByText("Módulo 2 — As Origens e os Caminhos do Xamanismo")).toBeVisible();
  await expect(page.locator(".plataforma-modulo.is-locked")).toHaveCount(1);
  await expect(page.locator(".plataforma-texto script")).toHaveCount(0);
  await expect(page.locator(".plataforma-texto img")).not.toHaveAttribute("onerror", /.+/);
  expect(await page.evaluate(() => window.__ataque)).toBeUndefined();
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1)).toBe(true);
  expect(erros).toEqual([]);
});

// A capa da aula é sempre a primeira coisa visível do conteúdo (o
// front-end a hoisteia para o topo, antes do <h1>) — nunca está abaixo da
// dobra. Mesmo que o HTML de origem (banco, conteúdo já instalado antes da
// correção) ainda traga loading="lazy" na <img>, o player precisa forçar
// "eager": "lazy" numa imagem que já está na tela faz o navegador adiar o
// carregamento, deixando só o fundo quase preto da moldura (.aula-imagem)
// visível — um retângulo escuro entre a navegação lateral e o texto da
// aula, exatamente onde a foto deveria aparecer.
test("capa da aula nunca fica com loading=lazy, mesmo quando o conteúdo salvo já traz o atributo antigo", async ({ page }) => {
  const cursoComCapaLazy = {
    ...curso,
    modulos: [
      {
        ...curso.modulos[0],
        aulas: [
          {
            ...curso.modulos[0].aulas[0],
            conteudo:
              '<figure class="aula-imagem"><img src="assets/escola/xamanismo/modulo-1-aula-1-capa.webp" width="1200" height="630" loading="lazy" alt="capa"><figcaption>Legenda</figcaption></figure>' +
              curso.modulos[0].aulas[0].conteudo,
          },
          curso.modulos[0].aulas[1],
        ],
      },
      curso.modulos[1],
    ],
  };
  await page.route("**/api/escola/cursos/xamanismo-introducao", route =>
    route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(cursoComCapaLazy) })
  );

  await page.goto("/escola-curso.html?curso=xamanismo-introducao");
  const capaImg = page.locator(".aula-imagem img").first();
  await expect(capaImg).toBeVisible();
  await expect(capaImg).not.toHaveAttribute("loading", "lazy");
  await expect(capaImg).toHaveAttribute("loading", "eager");
});
