// Isis 2.0 — Course Recommendation Engine (Fase 2 — Especialista da
// Mística Escola).
//
// Ranqueia cursos do catálogo real (School Knowledge) por tema de
// interesse e nível, evita recomendar de novo um curso já adquirido ou
// concluído (quando o aluno está autenticado) e sempre explica o motivo
// da escolha. Nunca inventa duração, certificado, preço ou pré-requisito
// que não esteja no catálogo.
(() => {
  window.Isis2 = window.Isis2 || {};
  if (window.Isis2.CourseRecommendationEngine) return;

  function knowledge() {
    return window.Isis2.SchoolKnowledge;
  }

  // Cursos "iniciante" são identificados pela própria tag do catálogo
  // real (["Iniciante"]) — nunca por suposição.
  function isBeginnerFriendly(curso) {
    return (curso.tags || []).some(tag => knowledge().normalize(tag) === "iniciante");
  }

  function ownedSlugs(myCoursesBody) {
    if (!Array.isArray(myCoursesBody)) return new Set();
    return new Set(myCoursesBody.map(item => item.slug));
  }

  function completedSlugs(myCoursesBody) {
    if (!Array.isArray(myCoursesBody)) return new Set();
    return new Set(myCoursesBody.filter(item => Number(item.percentual) >= 100).map(item => item.slug));
  }

  function isAdvanced(curso) {
    return (curso.tags || []).some(tag => knowledge().normalize(tag) === "avancado" || knowledge().normalize(tag) === "avançado");
  }

  function matchesExcludedTopic(curso, excludeTopics) {
    if (!excludeTopics || !excludeTopics.length) return false;
    const haystack = knowledge().normalize(`${curso.titulo} ${(curso.tags || []).join(" ")} ${curso.resumo || ""}`);
    return excludeTopics.some(term => haystack.includes(knowledge().normalize(term)));
  }

  // detection vem do School Intent Engine: { themeTerms, wantsBeginner }.
  // studentCourses (opcional) vem de StudentContext.myCourses() quando o
  // aluno está autenticado — usado só para não repetir curso já
  // adquirido/concluído, nunca para "adivinhar" progresso.
  //
  // preferences (Fase 2.1, opcional): estrutura do negation-parser.js —
  // { includeTopics, excludeTopics, includeLevels, excludeLevels,
  // excludeCourseIds, completedCourseIds }. Nunca é ignorada "para sempre
  // apresentar alguma recomendação": se toda opção do tema pedido também
  // bate com uma exclusão, o resultado correto é "nenhuma opção",
  // igual ao caso em que não existe curso do tema (note: "no_match").
  function recommend(detection, { studentCourses = null, limit = 3, preferences = null } = {}) {
    const kn = knowledge();
    if (!kn || !kn.hasCatalog()) return { courses: [], reasons: {}, note: "catalog_unavailable" };

    const owned = ownedSlugs(studentCourses);
    const completed = completedSlugs(studentCourses);
    const prefExcludeSlugs = new Set([...(preferences?.excludeCourseIds || []), ...(preferences?.completedCourseIds || [])]);

    const themeTerms = [
      ...(detection.themeTerms || []),
      ...(preferences?.includeTopics || []),
    ];
    const excludeTopics = preferences?.excludeTopics || [];
    const excludeLevels = preferences?.excludeLevels || [];
    const includeLevels = [...(preferences?.includeLevels || [])];
    if (detection.wantsBeginner) includeLevels.push("iniciante");

    let candidates = themeTerms.length
      ? kn.searchByTerms(themeTerms, { limit: limit + owned.size + completed.size + prefExcludeSlugs.size + 5 })
      : kn.listCourses();

    // Exclusões explícitas (tema recusado) sempre vencem — removidas antes
    // de qualquer outro filtro, para nunca "escapar" na lógica de
    // fallback de nível abaixo.
    candidates = candidates.filter(curso => !matchesExcludedTopic(curso, excludeTopics));

    if (excludeLevels.includes("iniciante")) candidates = candidates.filter(curso => !isBeginnerFriendly(curso));
    if (excludeLevels.includes("avancado")) candidates = candidates.filter(curso => !isAdvanced(curso));

    if (includeLevels.includes("iniciante")) {
      const beginner = candidates.filter(isBeginnerFriendly);
      if (beginner.length) candidates = beginner;
    } else if (includeLevels.includes("avancado")) {
      const advanced = candidates.filter(isAdvanced);
      if (advanced.length) candidates = advanced;
    }

    // Não recomenda de novo o que o aluno já concluiu, já adquiriu, ou
    // excluiu explicitamente ("já fiz esse", "menos esse"). Ao contrário
    // do filtro de nível acima, aqui NÃO cai de volta para a lista sem
    // filtro: se o único curso do tema já foi concluído/adquirido/
    // excluído, a resposta correta é "nenhuma novidade encontrada", nunca
    // sugerir de novo o que o aluno já tem ou pediu para não ver.
    const chosen = candidates
      .filter(curso => !owned.has(curso.slug) && !completed.has(curso.slug) && !prefExcludeSlugs.has(curso.slug))
      .slice(0, limit);

    const reasons = {};
    chosen.forEach((curso, index) => {
      const parts = [];
      if (themeTerms.length) {
        parts.push(`ele é o que mais se aproxima do tema que você mencionou`);
      }
      if (isBeginnerFriendly(curso)) parts.push("apresenta os fundamentos antes de temas mais avançados");
      if (index === 0 && chosen.length > 1) parts.push("é o ponto de partida mais indicado entre as opções encontradas");
      reasons[curso.slug] = parts.length ? parts.join(" e ") : "corresponde ao catálogo disponível para o que você procura";
    });

    return { courses: chosen, reasons, note: chosen.length ? null : "no_match" };
  }

  window.Isis2.CourseRecommendationEngine = { recommend };
})();
