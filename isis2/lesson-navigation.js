// Isis 2.0 — Lesson Navigation (Fase 2 — Especialista da Mística Escola).
//
// Único módulo que constrói URLs de navegação sugeridas pela Isis. Toda
// URL vem de rotas fixas e autorizadas (escola.html, escola-curso.html)
// combinadas com um slug validado contra o catálogo real — nunca aceita
// URL arbitrária vinda do usuário, nunca gera "javascript:" e nunca
// insere HTML não sanitizado no DOM (a Widget usa estes valores em
// atributos href escapados).
(() => {
  window.Isis2 = window.Isis2 || {};
  if (window.Isis2.LessonNavigation) return;

  const SLUG_PATTERN = /^[a-z0-9-]{1,80}$/;

  function isValidSlug(slug) {
    return typeof slug === "string" && SLUG_PATTERN.test(slug);
  }

  // Só aceita um slug que exista de fato no catálogo real (School
  // Knowledge) — impede que qualquer entrada do usuário vire URL sem
  // corresponder a um curso real.
  function isKnownCourse(slug) {
    const knowledge = window.Isis2.SchoolKnowledge;
    return Boolean(knowledge && isValidSlug(slug) && knowledge.bySlug(slug));
  }

  function catalogUrl() {
    return "escola.html";
  }

  function myCoursesUrl() {
    return "escola-curso.html";
  }

  function courseUrl(slug) {
    if (!isKnownCourse(slug)) return null;
    return `escola-curso.html?curso=${encodeURIComponent(slug)}`;
  }

  // Hoje a plataforma (escola-curso.js) sempre abre a primeira aula
  // pendente do curso automaticamente — não existe rota própria para
  // "aula X" ou "módulo Y" com parâmetro na URL, então "continuar",
  // "próxima aula" e "abrir módulo" apontam todos para a mesma URL do
  // curso (o player decide a aula certa a partir do progresso real do
  // backend). Documentado para não fingir granularidade que a rota atual
  // não tem.
  function resumeCourseUrl(slug) {
    return courseUrl(slug);
  }

  function assessmentUrl(slug) {
    return courseUrl(slug);
  }

  window.Isis2.LessonNavigation = {
    isValidSlug,
    isKnownCourse,
    catalogUrl,
    myCoursesUrl,
    courseUrl,
    resumeCourseUrl,
    assessmentUrl,
  };
})();
