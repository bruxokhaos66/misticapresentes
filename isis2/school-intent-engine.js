// Isis 2.0 — School Intent Engine (Fase 2 — Especialista da Mística
// Escola, ampliado na Fase 2.1).
//
// Mesmo estilo do intent-engine.js (regras + heurísticas em PT-BR, sem
// rede), mas para o domínio da Escola: catálogo de cursos, recomendação,
// progresso, módulos/aulas e avaliações. É um módulo irmão, não uma
// extensão do intent-engine.js comercial — o domínio (cursos, módulos,
// avaliações) e o vocabulário são bem diferentes de produtos/orçamento, e
// mantê-los separados evita risco de regressão na Isis comercial da
// Fase 1. Tolera erros de digitação simples (variações de grafia comuns
// listadas nas keywords de cada tema/intenção).
//
// Fase 2.1 amplia o vocabulário reconhecido (comparação, detalhe/
// estrutura de curso, aulas, acesso, dificuldade/nível, revisão de
// conteúdo, retomada dos estudos) e resolve intenção primária por ordem
// de prioridade explícita (`PRIORITY_ORDER`) para evitar colisão entre
// intenções concorrentes na mesma frase — sem descartar as demais: todas
// as intenções detectadas ficam em `matchedIntents`, então uma frase como
// "Qual é a próxima aula e existe um curso avançado depois?" preserva as
// duas necessidades (`primaryIntent: "next_lesson"`,
// `matchedIntents: ["next_lesson", "best_start"]`).
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
  const NEXT_LESSON_PATTERNS = [/proxima\s+aula/, /próxima\s+aula/, /qual\s+aula\s+vem\s+agora/, /terminei\s+a\s+aula/, /acabei\s+a\s+aula/, /o\s+que\s+faco\s+agora/, /o\s+que\s+(eu\s+)?estudo\s+agora/];
  const PROGRESS_PATTERNS = [/quanto\s+(do\s+curso\s+)?(eu\s+)?ja\s+conclui/, /meu\s+progresso/, /quanto\s+falta/, /quantos?\s+por\s?cento/];
  const BLOCKED_MODULE_PATTERNS = [/por\s?que\s+(o\s+)?(proximo\s+)?modulo\s+esta\s+bloqueado/, /modulo\s+bloqueado/, /nao\s+consigo\s+abrir\s+o\s+modulo/, /não\s+consigo\s+abrir\s+o\s+módulo/];
  const GRADE_PATTERNS = [/qual\s+nota\s+preciso/, /nota\s+minima/, /nota\s+mínima/, /preciso\s+tirar\s+quanto/];
  const ATTEMPTS_PATTERNS = [/quantas\s+tentativas/, /tentativas\s+(ainda\s+)?tenho/, /tentativas\s+restantes/];
  const SUSPENDED_PATTERNS = [/matricula\s+suspensa/, /matrícula\s+suspensa/, /acesso\s+suspenso/, /minha\s+matricula\s+esta\s+bloqueada/];

  // Fase 2.1 — vocabulário adicional.
  const COMPARISON_PATTERNS = [/\bcompar[ae]r?\b/, /qual\s+(e\s+|é\s+)?melhor[,:]?\s+\S+\s+ou\s+\S+/, /diferenca\s+entre|diferença\s+entre/, /\bversus\b|\bvs\b/];
  const COURSE_DETAIL_PATTERNS = [/detalhes\s+d[oe]\s+curso/, /me\s+fala\s+(mais\s+)?sobre\s+o\s+curso/, /o\s+que\s+tem\s+no\s+curso/, /sobre\s+o\s+que\s+(e\s+|é\s+)?o\s+curso/, /descricao\s+d[oe]\s+curso|descrição\s+d[oe]\s+curso/, /para\s+quem\s+(e\s+|é\s+)?(esse\s+|este\s+)?curso/];
  const COURSE_STRUCTURE_PATTERNS = [
    /estrutura\s+d[oe]\s+curso/, /como\s+(e\s+|é\s+)?organizado\s+o\s+curso/, /sequencia\s+de\s+estudos|sequência\s+de\s+estudos/,
    /ordem\s+dos\s+modulos|ordem\s+dos\s+módulos/, /quais\s+(sao\s+|são\s+)?(os\s+)?modulos|módulos/, /o\s+que\s+tem\s+nos?\s+modulos|módulos/,
  ];
  const LESSON_COUNT_PATTERNS = [/quantas\s+aulas/, /quais\s+aulas/, /lista\s+de\s+aulas/];
  const COURSE_COMPLETED_PATTERNS = [/curso\s+conclu[ií]do/, /terminei\s+o\s+curso/, /finalizei\s+o\s+curso/, /completei\s+o\s+curso/];
  const ACCESS_PATTERNS = [/como\s+(eu\s+)?acesso\s+o\s+curso/, /nao\s+consigo\s+acessar|não\s+consigo\s+acessar/, /acesso\s+ao\s+curso/, /nao\s+encontro\s+o\s+curso|não\s+encontro\s+o\s+curso/];
  const DIFFICULTY_PATTERNS = [/(e\s+|é\s+)?dificil\s+(esse\s+|este\s+)?curso|difícil\s+(esse\s+|este\s+)?curso/, /dificuldade\s+d[oe]\s+curso/, /(e\s+|é\s+)?facil\s+(esse\s+|este\s+)?curso|fácil\s+(esse\s+|este\s+)?curso/];
  const LEVEL_PATTERNS = [/qual\s+o\s+nivel|qual\s+o\s+nível/, /nivel\s+d[oe]\s+curso|nível\s+d[oe]\s+curso/, /(e\s+|é\s+)?para\s+iniciante|(e\s+|é\s+)?para\s+avancado|para\s+avançado/];
  const REVIEW_CONTENT_PATTERNS = [/revisar\s+(o\s+)?conteudo|revisar\s+(o\s+)?conteúdo/, /revis[aã]o\s+d[oe]\s+conteudo|revisão\s+d[oe]\s+conteúdo/, /quero\s+revisar/];
  const UNAVAILABILITY_PATTERNS = [/fora\s+do\s+ar/, /sistema\s+(esta\s+|está\s+)?indisponivel|indisponível/, /plataforma\s+fora\s+do\s+ar/, /nao\s+esta\s+carregando|não\s+está\s+carregando/];
  const RESUME_STUDIES_PATTERNS = [/retomar\s+(os\s+)?estudos/, /voltar\s+a\s+estudar/, /estou\s+perdido\s+nos\s+estudos/, /quero\s+retomar\s+de\s+onde\s+parei/];

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

  // Ordem de prioridade para resolver `primaryIntent` quando várias
  // intenções batem na mesma frase. Segurança/proteção acadêmica NÃO
  // entra aqui de propósito: quem chama este módulo (school-conversation-
  // manager.js) já roda os guardrails de crise/saúde e a proteção
  // acadêmica ANTES de consultar o Intent Engine — este motor nunca decide
  // sozinho sobre conteúdo sensível (ver README, "Ordem de prioridade").
  const PRIORITY_ORDER = [
    "suspended", "blocked_module", "access", "next_lesson", "progress", "course_completed",
    "grade", "attempts", "resume_studies", "comparison", "course_detail", "course_structure",
    "lesson_count", "difficulty", "level", "review_content", "my_courses", "unavailability",
    "best_start", "theme", "catalog",
  ];

  function detect(text) {
    const norm = normalize(text);
    const wantsBeginner = /iniciante|comec|começ|nunca\s+estudei|do\s+zero/.test(norm);

    const flags = {
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
      isComparisonQuery: matchAny(COMPARISON_PATTERNS, norm),
      isCourseDetailQuery: matchAny(COURSE_DETAIL_PATTERNS, norm),
      isCourseStructureQuery: matchAny(COURSE_STRUCTURE_PATTERNS, norm),
      isLessonCountQuery: matchAny(LESSON_COUNT_PATTERNS, norm),
      isCourseCompletedQuery: matchAny(COURSE_COMPLETED_PATTERNS, norm),
      isAccessQuery: matchAny(ACCESS_PATTERNS, norm),
      isDifficultyQuery: matchAny(DIFFICULTY_PATTERNS, norm),
      isLevelQuery: matchAny(LEVEL_PATTERNS, norm),
      isReviewContentQuery: matchAny(REVIEW_CONTENT_PATTERNS, norm),
      isUnavailabilityMention: matchAny(UNAVAILABILITY_PATTERNS, norm),
      isResumeStudiesQuery: matchAny(RESUME_STUDIES_PATTERNS, norm),
    };

    const intentMap = {
      suspended: flags.isSuspendedQuery,
      blocked_module: flags.isBlockedModuleQuery,
      access: flags.isAccessQuery,
      next_lesson: flags.isNextModuleQuery || flags.isNextLessonQuery,
      progress: flags.isProgressQuery,
      course_completed: flags.isCourseCompletedQuery,
      grade: flags.isGradeQuery,
      attempts: flags.isAttemptsQuery,
      resume_studies: flags.isResumeStudiesQuery,
      comparison: flags.isComparisonQuery,
      course_detail: flags.isCourseDetailQuery,
      course_structure: flags.isCourseStructureQuery,
      lesson_count: flags.isLessonCountQuery,
      difficulty: flags.isDifficultyQuery,
      level: flags.isLevelQuery,
      review_content: flags.isReviewContentQuery,
      my_courses: flags.isMyCoursesQuery,
      unavailability: flags.isUnavailabilityMention,
      best_start: flags.isBestStartQuery,
      theme: false, // resolvido abaixo, depende de themeTerms
      catalog: flags.isCatalogQuery,
    };

    const themeTerms = detectThemes(norm);
    if (themeTerms.length) intentMap.theme = true;

    const matchedIntents = PRIORITY_ORDER.filter(id => intentMap[id]);
    const primaryIntent = matchedIntents[0] || (themeTerms.length ? "theme" : "undefined_intent");

    return {
      raw: text,
      normalized: norm,
      isGreeting: detectGreeting(norm),
      isThanks: detectThanks(norm),
      themeTerms,
      wantsBeginner,
      primaryIntent,
      matchedIntents,
      ...flags,
    };
  }

  window.Isis2.SchoolIntentEngine = { normalize, detect, THEMES, PRIORITY_ORDER };
})();
