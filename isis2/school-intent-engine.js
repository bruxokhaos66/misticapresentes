// Isis 2.0 — School Intent Engine (Fase 2 — Especialista da Mística
// Escola).
//
// Mesmo estilo do intent-engine.js (regras + heurísticas em PT-BR, sem
// rede), mas para o domínio da Escola: catálogo de cursos, recomendação,
// progresso, módulos/aulas e avaliações. É um módulo irmão, não uma
// extensão do intent-engine.js comercial — o domínio (cursos, módulos,
// avaliações) e o vocabulário são bem diferentes de produtos/orçamento, e
// mantê-los separados evita risco de regressão na Isis comercial da
// Fase 1. Tolera erros de digitação simples (variações de grafia comuns
// listadas nas keywords de cada tema/intenção).
(() => {
  window.Isis2 = window.Isis2 || {};
  if (window.Isis2.SchoolIntentEngine) return;

  function normalize(value) {
    return String(value || "")
      .normalize("NFD")
      .replace(/[̀-ͯ]/g, "")
      .toLowerCase()
      .trim();
  }

  const GREETINGS = ["ola", "oi", "bom dia", "boa tarde", "boa noite", "oii", "opa"];
  const THANKS = ["obrigad", "valeu", "gratidao", "gratidão"];

  // Temas de curso reconhecidos, com variações informais/erros de
  // digitação comuns — usados para pontuar School Knowledge#searchByTerms
  // contra título/tags/resumo do catálogo real.
  const THEMES = [
    { terms: ["xamanismo", "xama", "xamanico", "xamânico"], keywords: ["xamanismo", "xamanica", "xamânica", "xamanismos", "xamanizmo", "xamanisco", "xaman"] },
    { terms: ["cristais", "cristal", "pedras"], keywords: ["cristais", "cristal", "cristalzinho", "pedras", "kristais", "cristias", "crista"] },
    { terms: ["aromaterapia", "aromas", "oleos"], keywords: ["aromaterapia", "aromaterapa", "aromoterapia", "aromoterapa", "óleos essenciais", "oleos essenciais", "aromater"] },
    { terms: ["rape", "tradicao"], keywords: ["rape", "rapé", "rapes"] },
    { terms: ["ayahuasca", "ritual"], keywords: ["ayahuasca", "aiuasca", "daime"] },
    { terms: ["cosmologia", "universo", "historia"], keywords: ["universo", "cosmologia", "origem do universo", "big bang"] },
  ];

  const CATALOG_PATTERNS = [/quais\s+cursos/, /que\s+cursos/, /cursos\s+(voces|vocês)\s+tem/, /catalogo\s+de\s+cursos/, /o\s+que\s+(voces|vocês)\s+ensinam/];
  const BEST_START_PATTERNS = [/melhor\s+(curso\s+)?para\s+comecar/, /por\s+onde\s+comeco/, /qual\s+curso\s+comecar/, /sou\s+iniciante/, /quero\s+comecar/, /nunca\s+estudei/];
  const MY_COURSES_PATTERNS = [/meus\s+cursos/, /onde\s+(encontro|estao|ficam)\s+meus\s+cursos/, /onde\s+vejo\s+meus\s+cursos/, /cursos\s+que\s+comprei/, /cursos\s+que\s+eu\s+tenho/];
  const NEXT_MODULE_PATTERNS = [/proximo\s+modulo/, /próximo\s+módulo/, /qual\s+(e\s+|é\s+)?o\s+modulo\s+seguinte/];
  const NEXT_LESSON_PATTERNS = [/proxima\s+aula/, /próxima\s+aula/, /qual\s+aula\s+vem\s+agora/, /terminei\s+a\s+aula/, /acabei\s+a\s+aula/, /o\s+que\s+faco\s+agora/];
  const PROGRESS_PATTERNS = [/quanto\s+(do\s+curso\s+)?(eu\s+)?ja\s+conclui/, /meu\s+progresso/, /quanto\s+falta/, /quantos?\s+por\s?cento/];
  const BLOCKED_MODULE_PATTERNS = [/por\s?que\s+(o\s+)?(proximo\s+)?modulo\s+esta\s+bloqueado/, /modulo\s+bloqueado/, /nao\s+consigo\s+abrir\s+o\s+modulo/, /não\s+consigo\s+abrir\s+o\s+módulo/];
  const GRADE_PATTERNS = [/qual\s+nota\s+preciso/, /nota\s+minima/, /nota\s+mínima/, /preciso\s+tirar\s+quanto/];
  const ATTEMPTS_PATTERNS = [/quantas\s+tentativas/, /tentativas\s+(ainda\s+)?tenho/, /tentativas\s+restantes/];
  const SUSPENDED_PATTERNS = [/matricula\s+suspensa/, /matrícula\s+suspensa/, /acesso\s+suspenso/, /minha\s+matricula\s+esta\s+bloqueada/];

  function matchAny(patterns, norm) {
    return patterns.some(pattern => pattern.test(norm));
  }

  function detectThemes(norm) {
    return THEMES.filter(theme => theme.keywords.some(keyword => norm.includes(normalize(keyword))))
      .flatMap(theme => theme.terms);
  }

  function detectGreeting(norm) {
    return GREETINGS.some(word => norm === word || norm.startsWith(`${word} `));
  }

  function detectThanks(norm) {
    return THANKS.some(word => norm.includes(word));
  }

  function detect(text) {
    const norm = normalize(text);
    const wantsBeginner = /iniciante|comec|começ|nunca\s+estudei|do\s+zero/.test(norm);
    return {
      raw: text,
      normalized: norm,
      isGreeting: detectGreeting(norm),
      isThanks: detectThanks(norm),
      themeTerms: detectThemes(norm),
      wantsBeginner,
      isCatalogQuery: matchAny(CATALOG_PATTERNS, norm),
      isBestStartQuery: matchAny(BEST_START_PATTERNS, norm),
      isMyCoursesQuery: matchAny(MY_COURSES_PATTERNS, norm),
      isNextModuleQuery: matchAny(NEXT_MODULE_PATTERNS, norm),
      isNextLessonQuery: matchAny(NEXT_LESSON_PATTERNS, norm),
      isProgressQuery: matchAny(PROGRESS_PATTERNS, norm),
      isBlockedModuleQuery: matchAny(BLOCKED_MODULE_PATTERNS, norm),
      isGradeQuery: matchAny(GRADE_PATTERNS, norm),
      isAttemptsQuery: matchAny(ATTEMPTS_PATTERNS, norm),
      isSuspendedQuery: matchAny(SUSPENDED_PATTERNS, norm),
    };
  }

  window.Isis2.SchoolIntentEngine = { normalize, detect, THEMES };
})();
