// Isis 2.0 — School Mode (Fase 2 — Especialista da Mística Escola).
//
// Decide se os recursos da Escola devem estar ativos nesta página:
// depende da flag geral (MISTICA_ISIS2_ENABLED) E da flag específica
// (MISTICA_ISIS2_ESCOLA_ENABLED), e só é verdadeiro nas páginas
// autorizadas (escola.html, escola-curso.html). Nunca lê query string
// nem localStorage/sessionStorage para decidir isso — só site-config.js
// (estático) e o pathname real da página.
(() => {
  window.Isis2 = window.Isis2 || {};
  if (window.Isis2.SchoolMode) return;

  // Só o nome do arquivo importa (não a origem/host) — evita qualquer
  // acoplamento com querystring ou domínio.
  const SCHOOL_PAGES = ["escola.html", "escola-curso.html"];

  function currentPageName() {
    try {
      const path = window.location.pathname || "";
      const last = path.split("/").filter(Boolean).pop() || "";
      // Site serve "/" como escola.html seria incomum; index vazio nunca
      // é página da Escola.
      return last.toLowerCase();
    } catch {
      return "";
    }
  }

  function isSchoolPage() {
    return SCHOOL_PAGES.includes(currentPageName());
  }

  function flagsEnabled() {
    const cfg = window.misticaSiteConfig || {};
    return cfg.isis2?.enabled === true && cfg.isis2?.escola?.enabled === true;
  }

  // Verdadeiro só quando as duas flags estão ligadas E a página atual é
  // uma página autorizada da Escola — nunca pode ser ativado por ação do
  // usuário (sem query string, sem localStorage).
  function isActive() {
    return flagsEnabled() && isSchoolPage();
  }

  // Fase 2.1: flag adicional MISTICA_ISIS2_ESCOLA_REFINAMENTO_ENABLED.
  // Só é lida (e só pode valer true) quando as duas flags da Fase 2 já
  // estão ligadas — nunca isoladamente, nunca por query string, hash,
  // atributo HTML, localStorage, sessionStorage ou cookie. Com ela
  // desligada (default), o comportamento é idêntico à Fase 2: nenhum
  // módulo novo é consultado, nenhuma requisição adicional acontece.
  function refinementFlagEnabled() {
    const cfg = window.misticaSiteConfig || {};
    return cfg.isis2?.escola?.refinamento?.enabled === true;
  }

  function isRefinementActive() {
    return isActive() && refinementFlagEnabled();
  }

  function currentSlugFromUrl() {
    try {
      const params = new URL(window.location.href).searchParams;
      return params.get("curso") || null;
    } catch {
      return null;
    }
  }

  window.Isis2.SchoolMode = {
    isActive,
    isSchoolPage,
    flagsEnabled,
    currentSlugFromUrl,
    isRefinementActive,
    refinementFlagEnabled,
  };
})();
