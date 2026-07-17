// Isis 2.0 — Course Comparison Engine (Fase 2.1 — Refinamento da
// Especialista da Mística Escola).
//
// Compara até 3 cursos usando só atributos disponíveis no catálogo real
// ou no detalhe público normalizado (course-payload-normalizer.js).
// Quando um campo não está disponível para um curso, o resultado marca
// isso explicitamente em vez de omitir ou inventar. Nunca elege um
// "vencedor absoluto" — a recomendação final é sempre contextual (ex.:
// "para quem está começando" vs. "para quem já tem base").
(() => {
  window.Isis2 = window.Isis2 || {};
  if (window.Isis2.CourseComparisonEngine) return;

  const MAX_COURSES = 3;
  const UNAVAILABLE = null; // sinaliza "não disponível" — o chamador converte para o texto padrão

  function isBeginnerFriendly(curso) {
    return (curso.tags || []).some(tag => String(tag).toLowerCase() === "iniciante");
  }

  function attributesFor(curso, detail) {
    return {
      slug: curso.slug,
      titulo: curso.titulo,
      tema: (curso.tags || [])[0] || UNAVAILABLE,
      nivel: isBeginnerFriendly(curso) ? "Iniciante" : UNAVAILABLE,
      resumo: curso.resumo || UNAVAILABLE,
      descricao: detail?.descricao || UNAVAILABLE,
      paraQuemE: detail?.paraQuemE || UNAVAILABLE,
      totalModulos: detail ? detail.totalModulos : UNAVAILABLE,
      totalAulas: detail ? detail.totalAulas : UNAVAILABLE,
    };
  }

  // courses: array de { curso, detail? } (detail é opcional, vem de
  // SchoolPublicDetail já normalizado). Limita a MAX_COURSES — comparação
  // de mais de 3 cursos não é suportada nesta fase (limite deliberado de
  // clareza da resposta, não uma restrição técnica).
  function compare(entries) {
    const limited = (entries || []).slice(0, MAX_COURSES);
    const rows = limited.map(entry => attributesFor(entry.curso, entry.detail));

    const beginnerRow = rows.find(r => r.nivel === "Iniciante");
    const advancedRow = rows.find(r => r.nivel !== "Iniciante");

    const guidance = [];
    if (beginnerRow) guidance.push(`Para quem está começando, "${beginnerRow.titulo}" parece mais adequado.`);
    if (advancedRow && rows.length > 1) guidance.push(`Para quem já possui alguma base, "${advancedRow.titulo}" pode fazer mais sentido.`);
    if (!guidance.length) guidance.push("O catálogo atual não indica nível para diferenciar estes cursos com segurança — vale ler o resumo de cada um antes de decidir.");

    return { rows, guidance, count: rows.length };
  }

  window.Isis2.CourseComparisonEngine = { compare, MAX_COURSES };
})();
