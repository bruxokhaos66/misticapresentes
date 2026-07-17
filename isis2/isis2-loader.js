// Isis 2.0 — loader.
//
// Único script sempre baixado nas páginas públicas (poucas centenas de
// bytes). Lê a feature flag síncrona de site-config.js e só injeta o
// resto da Isis 2.0 (CSS + módulos comerciais + widget + bootstrap,
// ~60KB de JS) quando window.misticaSiteConfig.isis2.enabled === true.
// Com a flag desligada (default), nenhum outro arquivo da Isis 2.0 é
// requisitado — zero custo de rede/parse além deste loader. Nas páginas
// da Escola (escola.html/escola-curso.html), com MISTICA_ISIS2_ESCOLA_ENABLED
// também ligada, injeta adicionalmente os módulos da Especialista da
// Mística Escola (Fase 2, ~9 arquivos extras) — ver isis2/README.md.
(() => {
  if (window.__MISTICA_ISIS2_LOADER__) return;
  window.__MISTICA_ISIS2_LOADER__ = true;

  if (window.misticaSiteConfig?.isis2?.enabled !== true) return;

  const VERSION = "20260717-isis2-fase2-escola";
  const BASE = "isis2/";
  const CORE_MODULES = [
    "product-knowledge.js",
    "intent-engine.js",
    "safety-guardrails.js",
    "recommendation-engine.js",
    "context-memory.js",
    "analytics.js",
    "cart-assistant.js",
    "ai-providers.js",
  ];

  // Módulos da Especialista da Mística Escola (Fase 2): só baixados
  // quando a flag específica MISTICA_ISIS2_ESCOLA_ENABLED também está
  // ligada E a página atual é uma página autorizada da Escola — nunca
  // por query string/localStorage (site-config.js é a única fonte).
  // Com a flag da Escola desligada (mesmo com a flag geral ligada), zero
  // requisições extras: a Isis 2.0 comercial funciona normalmente sem
  // nenhum arquivo desta lista.
  const SCHOOL_PAGES = ["escola.html", "escola-curso.html"];
  const SCHOOL_MODULES = [
    "school-mode.js",
    "school-knowledge.js",
    "student-context.js",
    "course-recommendation-engine.js",
    "lesson-navigation.js",
    "progress-assistant.js",
    "assessment-safety.js",
    "school-intent-engine.js",
    "school-conversation-manager.js",
  ];

  // Módulos do Refinamento da Especialista da Mística Escola (Fase 2.1):
  // só baixados quando, além das duas flags acima, MISTICA_ISIS2_ESCOLA_-
  // REFINAMENTO_ENABLED também está ligada. Com ela desligada (default),
  // zero requisições extras além do que a Fase 2 já baixa — nenhum destes
  // arquivos é sequer solicitado.
  const REFINEMENT_MODULES = [
    "negation-parser.js",
    "course-payload-normalizer.js",
    "school-public-detail.js",
    "course-comparison-engine.js",
  ];

  function currentPageName() {
    try {
      return (window.location.pathname || "").split("/").filter(Boolean).pop()?.toLowerCase() || "";
    } catch {
      return "";
    }
  }

  function schoolPageActive() {
    if (window.misticaSiteConfig?.isis2?.escola?.enabled !== true) return false;
    return SCHOOL_PAGES.includes(currentPageName());
  }

  // Fase 2.1: depende das duas flags da Fase 2 já ligadas E da flag
  // adicional (site-config.js, isis2.escola.refinamento.enabled) — nunca
  // por query string/hash/localStorage/sessionStorage/cookie.
  function refinementActive() {
    return schoolPageActive() && window.misticaSiteConfig?.isis2?.escola?.refinamento?.enabled === true;
  }

  // Fonte única do catálogo real de cursos (window.MISTICA_ESCOLA_CURSOS)
  // é exposta por escola.js (ver comentário lá). escola.html já carrega
  // esse arquivo estaticamente (não duplicar aqui). escola-curso.html não
  // carrega escola.js por padrão — só quando a Escola da Isis 2.0 está
  // realmente ativa nesta página é que ele é injetado aqui, como fonte de
  // dados (a página em si não usa nada dele: `renderCatalog()` sai sem
  // fazer nada por não existir `[data-escola-grid]` nesta página).
  const CATALOG_SOURCE_SCRIPT = { page: "escola-curso.html", src: "escola.js" };

  const schoolActive = schoolPageActive();
  const refinementIsActive = refinementActive();
  const extraRootScripts = schoolActive && currentPageName() === CATALOG_SOURCE_SCRIPT.page
    ? [CATALOG_SOURCE_SCRIPT.src]
    : [];

  const scriptUrls = [
    ...extraRootScripts.map(name => `${name}?v=${VERSION}`),
    ...CORE_MODULES.map(name => `${BASE}${name}?v=${VERSION}`),
    ...(refinementIsActive ? REFINEMENT_MODULES.map(name => `${BASE}${name}?v=${VERSION}`) : []),
    ...(schoolActive ? SCHOOL_MODULES.map(name => `${BASE}${name}?v=${VERSION}`) : []),
    `${BASE}conversation-manager.js?v=${VERSION}`,
    `${BASE}widget.js?v=${VERSION}`,
    `${BASE}isis2-bootstrap.js?v=${VERSION}`,
  ];

  const link = document.createElement("link");
  link.rel = "stylesheet";
  link.href = `${BASE}widget.css?v=${VERSION}`;
  document.head.appendChild(link);

  // async=false preserva a ordem de execução entre scripts inseridos
  // dinamicamente (por padrão eles rodam async e fora de ordem) — sem
  // isso, conversation-manager.js poderia rodar antes de
  // product-knowledge.js estar registrado em window.Isis2.
  scriptUrls.forEach(src => {
    const script = document.createElement("script");
    script.src = src;
    script.async = false;
    document.head.appendChild(script);
  });
})();
