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

  // detection vem do School Intent Engine: { themeTerms, wantsBeginner }.
  // studentCourses (opcional) vem de StudentContext.myCourses() quando o
  // aluno está autenticado — usado só para não repetir curso já
  // adquirido/concluído, nunca para "adivinhar" progresso.
  function recommend(detection, { studentCourses = null, limit = 3 } = {}) {
    const kn = knowledge();
    if (!kn || !kn.hasCatalog()) return { courses: [], reasons: {}, note: "catalog_unavailable" };

    const owned = ownedSlugs(studentCourses);
    const completed = completedSlugs(studentCourses);

    let candidates = detection.themeTerms && detection.themeTerms.length
      ? kn.searchByTerms(detection.themeTerms, { limit: limit + owned.size + completed.size })
      : kn.listCourses();

    if (detection.wantsBeginner) {
      const beginner = candidates.filter(isBeginnerFriendly);
      if (beginner.length) candidates = beginner;
    }

    // Não recomenda de novo o que o aluno já concluiu; um curso já
    // adquirido mas não concluído ainda pode ser sugerido (ex.: "continue
    // esse"), mas com motivo diferente — aqui priorizamos descoberta de
    // curso novo, então também deduplicamos o que já foi adquirido. Ao
    // contrário do filtro de "iniciante" acima, aqui NÃO cai de volta
    // para a lista sem filtro: se o único curso do tema já foi
    // concluído/adquirido, a resposta correta é "nenhuma novidade
    // encontrada", nunca sugerir de novo o que o aluno já tem.
    const chosen = candidates.filter(curso => !owned.has(curso.slug) && !completed.has(curso.slug)).slice(0, limit);

    const reasons = {};
    chosen.forEach((curso, index) => {
      const parts = [];
      if (detection.themeTerms && detection.themeTerms.length) {
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
