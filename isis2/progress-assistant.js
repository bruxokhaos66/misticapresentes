// Isis 2.0 — Progress Assistant (Fase 2 — Especialista da Mística
// Escola).
//
// Traduz o estado real devolvido pelo backend (curso com módulos,
// progresso, bloqueio, quiz) em explicações simples. Só leitura: nunca
// altera progresso, nunca marca aula como concluída, nunca libera módulo,
// nunca altera nota, nunca reseta tentativa — qualquer mudança de estado
// continua acontecendo exclusivamente pelos botões reais da plataforma
// (escola-curso.js), pelo backend.
(() => {
  window.Isis2 = window.Isis2 || {};
  if (window.Isis2.ProgressAssistant) return;

  // Acha o módulo "atual": o que contém a próxima aula pendente, ou o
  // primeiro módulo liberado ainda não concluído.
  function currentModule(curso) {
    if (!curso || !Array.isArray(curso.modulos)) return null;
    return curso.modulos.find(m => m.liberado && !m.concluido) || curso.modulos.find(m => m.liberado) || null;
  }

  function nextLesson(curso) {
    const modulo = currentModule(curso);
    if (!modulo || !Array.isArray(modulo.aulas)) return null;
    const aula = modulo.aulas.find(a => a.status !== "concluida");
    return aula ? { aula, modulo } : null;
  }

  function firstLockedModule(curso) {
    if (!curso || !Array.isArray(curso.modulos)) return null;
    return curso.modulos.find(m => !m.liberado) || null;
  }

  function pendingQuiz(curso) {
    if (!curso || !Array.isArray(curso.modulos)) return null;
    for (const modulo of curso.modulos) {
      if (modulo.quiz && modulo.quiz.disponivel && !modulo.quiz.aprovado) return { quiz: modulo.quiz, modulo };
    }
    return null;
  }

  // Só descreve o motivo de bloqueio com o que a API realmente informa.
  // Quando o payload traz um campo de motivo explícito (ex.: "motivo" ou
  // "motivo_bloqueio"), repassa exatamente esse texto (normalizado como
  // qualquer outro campo de API — nunca renderizado como HTML). Quando o
  // backend não informa nada além do próprio bloqueio, usa o texto
  // genérico documentado no briefing da Fase 2.1 em vez de presumir nota
  // mínima, tentativas, aula pendente, pagamento ou suspensão — nunca
  // deduz um motivo que a API não mandou (ver isis2/README.md, "Honestidade").
  function explainBlockedModule(curso) {
    const locked = firstLockedModule(curso);
    if (!locked) return null;
    const apiMotivo = typeof locked.motivo === "string" && locked.motivo.trim()
      ? locked.motivo.trim()
      : (typeof locked.motivo_bloqueio === "string" && locked.motivo_bloqueio.trim() ? locked.motivo_bloqueio.trim() : null);
    return {
      moduloTitulo: locked.titulo,
      motivo: apiMotivo || "o módulo anterior ainda não foi concluído (todas as aulas obrigatórias, e a avaliação quando existir, com a nota mínima)",
      motivoGenerico: !apiMotivo,
    };
  }

  function progressSummary(curso) {
    if (!curso || !curso.progresso) return null;
    const p = curso.progresso;
    return {
      percentual: p.percentual ?? 0,
      aulasConcluidas: p.aulas_concluidas ?? 0,
      totalAulas: p.total_aulas ?? 0,
      concluido: Boolean(p.concluido),
    };
  }

  // "Quantas tentativas ainda tenho?" — a API de quiz observada
  // (escola-curso.js#abrirQuiz/#enviar) não expõe hoje um contador de
  // tentativas restantes; quando o payload trouxer esse campo no futuro
  // ele é repassado, mas nunca inventado quando ausente.
  function attemptsInfo(quizPayload) {
    if (!quizPayload) return { known: false };
    const remaining = quizPayload.tentativas_restantes ?? quizPayload.tentativasRestantes;
    if (remaining == null) return { known: false };
    return { known: true, remaining: Number(remaining) };
  }

  function minGrade(quizPayload) {
    if (!quizPayload) return null;
    return quizPayload.nota_minima ?? null;
  }

  window.Isis2.ProgressAssistant = {
    currentModule,
    nextLesson,
    firstLockedModule,
    pendingQuiz,
    explainBlockedModule,
    progressSummary,
    attemptsInfo,
    minGrade,
  };
})();
