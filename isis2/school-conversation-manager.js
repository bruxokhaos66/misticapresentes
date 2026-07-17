// Isis 2.0 — School Conversation Manager (Fase 2 — Especialista da
// Mística Escola).
//
// Orquestra School Intent Engine + School Knowledge + Course
// Recommendation Engine + Student Context + Progress Assistant + Lesson
// Navigation + Assessment Safety + Safety Guardrails (reaproveitado da
// Fase 1) + Context Memory + Analytics. Mesmo contrato de entrada/saída
// do Conversation Manager comercial (handleUserMessage/handleIntentShortcut
// /startConversation) para que conversation-manager.js só precise
// delegar, sem duplicar a Widget nem o loop de conversa. Só é chamado
// quando window.Isis2.SchoolMode.isActive() é verdadeiro.
//
// Regras de segurança acadêmica (não decorativas — testadas):
//  - nunca responde avaliação pelo aluno, nunca resolve pergunta colada
//    da prova, nunca indica a alternativa correta (assessment-safety.js);
//  - nunca marca aula concluída, libera módulo, altera nota, reseta
//    tentativa ou confirma aprovação — isso é sempre o backend, pelos
//    botões reais da plataforma;
//  - nunca finge saber progresso de visitante não autenticado, nunca diz
//    que ele está matriculado, nunca expõe dado de outro aluno (toda
//    consulta de progresso é feita com a sessão do próprio navegador,
//    autorizada pelo backend).
(() => {
  window.Isis2 = window.Isis2 || {};
  if (window.Isis2.SchoolConversationManager) return;

  const ERROR_PROGRESS = 'Não consegui consultar seu progresso agora. Tente novamente em alguns instantes ou abra "Meus cursos".';
  const ERROR_GENERIC = "Não consegui completar essa consulta agora. Tente novamente em alguns instantes.";
  const ERROR_NOT_LOGGED_IN = "Essa informação só existe depois de entrar na sua conta de aluno — o progresso não pode ser adivinhado. Você pode entrar na página do curso ou em \"Meus cursos\".";
  // Fase 2.1 — mensagem exata do briefing para falha do endpoint público
  // de detalhe (nunca inventa detalhe quando a consulta falha).
  const ERROR_PUBLIC_DETAIL = "Não consegui consultar os detalhes completos desse curso agora. Posso mostrar as informações básicas disponíveis ou você pode tentar novamente mais tarde.";
  const FIELD_UNAVAILABLE = "Essa informação não está disponível no catálogo atual.";

  function nav() { return window.Isis2.LessonNavigation; }
  function knowledge() { return window.Isis2.SchoolKnowledge; }
  function student() { return window.Isis2.StudentContext; }
  function progressAssistant() { return window.Isis2.ProgressAssistant; }
  function memory() { return window.Isis2.ContextMemory; }
  function analytics() { return window.Isis2.Analytics; }
  function refinementActive() { return Boolean(window.Isis2.SchoolMode?.isRefinementActive?.()); }

  const QUICK_REPLIES = [
    { id: "school_meus_cursos", label: "Ver meus cursos" },
    { id: "school_continuar", label: "Continuar estudando" },
    { id: "school_comecar", label: "Qual curso começar?" },
    { id: "school_modulos", label: "Como funcionam os módulos?" },
    { id: "school_bloqueio", label: "Por que minha aula está bloqueada?" },
  ];

  function baseReply(overrides) {
    return {
      text: "",
      courses: [],
      reasons: {},
      actions: [],
      quickReplies: QUICK_REPLIES,
      ...overrides,
    };
  }

  function catalogUnavailableReply() {
    return baseReply({
      kind: "school_unavailable",
      text: "No momento não consigo consultar o catálogo de cursos desta página. Você pode ver todos os cursos na página da Escola, ou tentar novamente em instantes.",
      quickReplies: [],
    });
  }

  function greetingReply() {
    return baseReply({
      kind: "school_greeting",
      text: "Olá! Eu sou a Isis, agora também especialista da Mística Escola — uma assistente baseada em regras e no conteúdo real dos cursos (ainda não sou uma IA generativa nesta fase). Posso apresentar os cursos, explicar módulos e aulas, recomendar uma trilha, ou — se você estiver logado — consultar seu progresso. O que você quer saber?",
    });
  }

  function thanksReply() {
    return baseReply({ kind: "school_thanks", text: "Por nada! Se precisar de mais alguma coisa sobre os cursos, é só chamar. 🌿" });
  }

  function courseListText(courses) {
    return courses.map(c => `${c.icone || "📘"} ${c.titulo}${c.tipo === "gratuito" ? " (gratuito)" : ` (${knowledge().formatPrice(c.preco)})`}`).join("\n");
  }

  function courseActions(courses) {
    return courses
      .map(curso => ({ label: `Ver "${curso.titulo}"`, url: nav().courseUrl(curso.slug) }))
      .filter(action => Boolean(action.url));
  }

  function registerPresented(courses) {
    courses.forEach(curso => memory().addPresentedCourse(curso.slug));
  }

  function catalogReply() {
    const courses = knowledge().listCourses();
    if (!courses.length) return catalogUnavailableReply();
    registerPresented(courses);
    return baseReply({
      kind: "school_catalog",
      text: `Estes são os cursos disponíveis na Mística Escola:\n${courseListText(courses)}`,
      courses,
      actions: courseActions(courses),
    });
  }

  function noMatchReply({ hadPreferences = false } = {}) {
    return baseReply({
      kind: "school_no_match",
      text: hadPreferences
        ? "Não encontrei no catálogo atual um curso que combine com todas essas preferências."
        : "Ainda não encontrei um curso certeiro para isso no catálogo atual. Pode me contar um pouco mais sobre o tema de interesse? Também posso te mostrar todos os cursos disponíveis.",
    });
  }

  async function currentStudentCourses() {
    try {
      const authed = await student().isAuthenticated();
      if (!authed) return null;
      const r = await student().myCourses();
      return r.ok ? r.body : null;
    } catch {
      return null;
    }
  }

  async function recommendationReply(detection, { introWhenBeginner, preferences = null } = {}) {
    const kn = knowledge();
    if (!kn.hasCatalog()) return catalogUnavailableReply();
    const studentCourses = await currentStudentCourses();
    const { courses, reasons, note } = window.Isis2.CourseRecommendationEngine.recommend(detection, { studentCourses, preferences });
    const hadPreferences = Boolean(preferences && (
      preferences.excludeTopics?.length || preferences.excludeLevels?.length ||
      preferences.excludeCourseIds?.length || preferences.completedCourseIds?.length
    ));
    if (note === "catalog_unavailable") return catalogUnavailableReply();
    if (!courses.length) return noMatchReply({ hadPreferences });

    if (hadPreferences && refinementActive()) {
      analytics().trackSchoolEvent("isis_course_exclusion_applied", {
        excludedCount: (preferences.excludeTopics?.length || 0) + (preferences.excludeLevels?.length || 0) +
          (preferences.excludeCourseIds?.length || 0) + (preferences.completedCourseIds?.length || 0),
      });
    }

    registerPresented(courses);
    if (courses[0]) memory().updateSchool({ courseOfInterest: courses[0].slug, lastRecommendedCourseIds: courses.map(c => c.slug) });
    analytics().trackSchoolEvent("isis_course_recommended", { count: courses.length });

    const intro = introWhenBeginner && detection.wantsBeginner
      ? `Recomendo começar por "${courses[0].titulo}" porque ${reasons[courses[0].slug]}.`
      : `Encontrei estas opções para você:`;

    return baseReply({
      kind: "school_recommendation",
      text: intro,
      courses,
      reasons,
      actions: courseActions(courses),
    });
  }

  function myCoursesUnavailableUrl() {
    return nav().myCoursesUrl();
  }

  async function myCoursesReply() {
    const r = await student().myCourses();
    if (r.networkError) return baseReply({ kind: "school_error", text: ERROR_GENERIC });
    if (r.status === 401) {
      return baseReply({
        kind: "school_not_authenticated",
        text: "Você ainda não está logado. Entre com o e-mail e senha do curso para eu poder mostrar seus cursos e progresso — ou acesse \"Meus cursos\" para entrar por lá.",
        actions: [{ label: "Abrir Meus cursos", url: myCoursesUnavailableUrl() }],
      });
    }
    if (!r.ok) return baseReply({ kind: "school_error", text: ERROR_GENERIC });

    const cursos = Array.isArray(r.body) ? r.body : [];
    if (!cursos.length) {
      return baseReply({
        kind: "school_my_courses_empty",
        text: "Você ainda não tem cursos liberados na plataforma de estudo. Assim que sua matrícula for confirmada, ele aparece em \"Meus cursos\".",
        actions: [{ label: "Ver catálogo de cursos", url: nav().catalogUrl() }],
      });
    }
    analytics().trackSchoolEvent("isis_progress_consulted", { count: cursos.length });
    const text = cursos.map(c => `${c.titulo}: ${c.percentual}% concluído (${c.aulas_concluidas}/${c.total_aulas} aulas)`).join("\n");
    return baseReply({
      kind: "school_my_courses",
      text: `Seus cursos:\n${text}`,
      actions: cursos.map(c => ({ label: `Continuar "${c.titulo}"`, url: nav().resumeCourseUrl(c.slug) })).filter(a => a.url),
    });
  }

  // Resolve de qual curso o aluno está falando: contexto explícito da URL
  // (escola-curso.html?curso=slug), ou o último curso de interesse
  // guardado na sessão. Nunca adivinha um curso ao acaso.
  function resolveSlugInFocus() {
    const fromUrl = window.Isis2.SchoolMode?.currentSlugFromUrl();
    if (fromUrl && nav().isKnownCourse(fromUrl)) return fromUrl;
    const school = memory().getSchool();
    if (school.viewedCourseSlug && nav().isKnownCourse(school.viewedCourseSlug)) return school.viewedCourseSlug;
    if (school.courseOfInterest && nav().isKnownCourse(school.courseOfInterest)) return school.courseOfInterest;
    return null;
  }

  function askWhichCourseReply() {
    return baseReply({
      kind: "school_need_course_context",
      text: "De qual curso você está falando? Você pode me dizer o nome, ou abrir o curso e perguntar de novo por lá.",
      actions: [{ label: "Ver catálogo de cursos", url: nav().catalogUrl() }],
    });
  }

  async function fetchCourseForStudent(slug) {
    const r = await student().courseDetail(slug);
    return r;
  }

  async function progressReply() {
    const slug = resolveSlugInFocus();
    if (!slug) return askWhichCourseReply();
    const r = await fetchCourseForStudent(slug);
    if (r.networkError) return baseReply({ kind: "school_error", text: ERROR_PROGRESS });
    if (r.status === 401) return baseReply({ kind: "school_not_authenticated", text: ERROR_NOT_LOGGED_IN, actions: [{ label: "Abrir curso", url: nav().courseUrl(slug) }] });
    if (r.status === 403) {
      return baseReply({
        kind: "school_enrollment_blocked",
        text: r.body?.detail || "Sua matrícula neste curso não está liberada no momento (pagamento pendente ou suspenso). Fale com o suporte para regularizar o acesso.",
      });
    }
    if (!r.ok) return baseReply({ kind: "school_error", text: ERROR_PROGRESS });

    const summary = progressAssistant().progressSummary(r.body);
    if (!summary) return baseReply({ kind: "school_error", text: ERROR_PROGRESS });
    analytics().trackSchoolEvent("isis_progress_consulted", { course: 1 });
    memory().updateSchool({ viewedCourseSlug: slug });
    const texto = summary.concluido
      ? `Você já concluiu "${r.body.titulo}" (100%, ${summary.aulasConcluidas}/${summary.totalAulas} aulas). Isso é da sua conta, direto da plataforma.`
      : `No curso "${r.body.titulo}" você já concluiu ${summary.percentual}% (${summary.aulasConcluidas}/${summary.totalAulas} aulas) — informação da sua conta, consultada agora.`;
    return baseReply({ kind: "school_progress", text: texto, actions: [{ label: "Continuar estudando", url: nav().resumeCourseUrl(slug) }] });
  }

  async function nextLessonReply() {
    const slug = resolveSlugInFocus();
    if (!slug) return askWhichCourseReply();
    const r = await fetchCourseForStudent(slug);
    if (r.networkError) return baseReply({ kind: "school_error", text: ERROR_PROGRESS });
    if (r.status === 401) return baseReply({ kind: "school_not_authenticated", text: ERROR_NOT_LOGGED_IN, actions: [{ label: "Abrir curso", url: nav().courseUrl(slug) }] });
    if (r.status === 403) return baseReply({ kind: "school_enrollment_blocked", text: r.body?.detail || "Sua matrícula neste curso não está liberada no momento." });
    if (!r.ok) return baseReply({ kind: "school_error", text: ERROR_PROGRESS });

    const next = progressAssistant().nextLesson(r.body);
    memory().updateSchool({ viewedCourseSlug: slug });
    if (!next) {
      return baseReply({
        kind: "school_no_pending_lesson",
        text: `Parece que não há aula pendente liberada agora em "${r.body.titulo}" — pode já ter concluído tudo que está disponível, ou o próximo módulo ainda está bloqueado.`,
        actions: [{ label: "Abrir curso", url: nav().courseUrl(slug) }],
      });
    }
    analytics().trackSchoolEvent("isis_resume_course_clicked", {}, { dedupeKey: slug });
    return baseReply({
      kind: "school_next_lesson",
      text: `Sua próxima aula em "${r.body.titulo}" é "${next.aula.titulo}", no módulo "${next.modulo.titulo}".`,
      actions: [{ label: "Abrir próxima aula", url: nav().resumeCourseUrl(slug) }],
    });
  }

  async function blockedModuleReply() {
    const slug = resolveSlugInFocus();
    if (!slug) return askWhichCourseReply();
    const r = await fetchCourseForStudent(slug);
    if (r.networkError) return baseReply({ kind: "school_error", text: ERROR_PROGRESS });
    if (r.status === 401) return baseReply({ kind: "school_not_authenticated", text: ERROR_NOT_LOGGED_IN, actions: [{ label: "Abrir curso", url: nav().courseUrl(slug) }] });
    if (r.status === 403) return baseReply({ kind: "school_enrollment_blocked", text: r.body?.detail || "Sua matrícula neste curso não está liberada no momento." });
    if (!r.ok) return baseReply({ kind: "school_error", text: ERROR_PROGRESS });

    const blocked = progressAssistant().explainBlockedModule(r.body);
    if (!blocked) {
      return baseReply({ kind: "school_no_blocked_module", text: `Não encontrei módulo bloqueado em "${r.body.titulo}" agora — todos os módulos liberados até aqui estão disponíveis.` });
    }
    return baseReply({
      kind: "school_blocked_module",
      text: `O módulo "${blocked.moduloTitulo}" está bloqueado porque ${blocked.motivo}.`,
      actions: [{ label: "Continuar estudando", url: nav().resumeCourseUrl(slug) }],
    });
  }

  function gradeReply() {
    return baseReply({
      kind: "school_grade_info",
      text: "A nota mínima de cada avaliação aparece assim que você abre a avaliação do módulo — não tenho esse número aqui na conversa para não arriscar te passar um valor errado. Abra a avaliação disponível para conferir.",
    });
  }

  function attemptsReply() {
    return baseReply({
      kind: "school_attempts_info",
      text: "Não consigo confirmar o número exato de tentativas restantes por aqui. Abra a avaliação do módulo para ver essa informação atualizada.",
    });
  }

  function assessmentHelpReply() {
    analytics().trackSchoolEvent("isis_assessment_help_blocked", {});
    return baseReply({
      kind: "school_assessment_help_blocked",
      text: "Não posso te dar a resposta de uma avaliação nem resolver a questão por você — isso não seria justo com seu aprendizado, e eu não faço isso. Posso, sim, explicar o conteúdo da aula de novo, revisar os conceitos principais ou te propor perguntas de estudo parecidas (mas não iguais à avaliação) para você treinar antes de responder.",
    });
  }

  function safetyReply(classification) {
    if (classification === "crisis") {
      // Reaproveita o mesmo evento de guardrail já existente na Fase 1
      // (isis2_safety_crisis_detected via Analytics.track), em vez de
      // inventar um nome novo fora da lista de eventos da Fase 2.
      analytics().track("safety_crisis_detected", {});
      return baseReply({
        kind: "school_safety_crisis",
        text: "Sinto muito que você esteja passando por isso — o que você sente é sério e importa. Eu sou só uma assistente educacional da Escola, não tenho preparo para isso: por favor, fale agora com alguém de confiança e busque ajuda especializada. No Brasil, o CVV acolhe de graça pelo 188, 24h por dia. Em risco imediato, ligue 190 ou 192, ou vá a um pronto atendimento.",
        quickReplies: [],
      });
    }
    if (classification === "medical_claim") {
      return baseReply({
        kind: "school_safety_medical_claim",
        text: "Não posso diagnosticar, prometer cura, nem indicar que o conteúdo do curso substitui tratamento médico — isso é sempre trabalho de um profissional de saúde, e nunca recomendo interromper um tratamento em curso. O conteúdo da Escola é educacional, histórico e cultural, não clínico.",
      });
    }
    if (classification === "substance_risk") {
      return baseReply({
        kind: "school_safety_substance_risk",
        text: "Sobre rapé, ayahuasca e medicinas da floresta eu só trago conteúdo educativo, histórico e cultural do curso — não indico dose, preparo ou combinação com remédios, e não são temas apropriados para menores de idade nem apresentados como tratamento. Decisões de uso pessoal exigem orientação de um facilitador ou profissional qualificado, respeitando a legislação local.",
        quickReplies: [],
      });
    }
    if (classification === "substance_education") {
      return baseReply({
        kind: "school_safety_substance_education",
        text: "Posso explicar a origem, a tradição e o contexto cultural desse tema a partir do conteúdo do curso — sem indicar dose, preparo nem uso medicinal.",
      });
    }
    return null;
  }

  function howModulesWorkReply() {
    return baseReply({
      kind: "school_how_modules_work",
      text: "Cada curso é dividido em módulos, e cada módulo tem aulas. Você libera o próximo módulo concluindo as aulas obrigatórias (e a avaliação, quando o módulo tiver uma) do módulo atual — sempre confirmado pelo sistema, não por mim. Se um módulo aparece bloqueado, é porque o anterior ainda não foi concluído.",
    });
  }

  // ---- Fase 2.1 — Refinamento -------------------------------------------
  // Tudo nesta seção só é chamado quando refinementActive() é verdadeiro
  // (window.Isis2.SchoolMode.isRefinementActive()). Com a flag desligada,
  // handleUserMessage nunca entra aqui — o comportamento é idêntico à
  // Fase 2 (ver handleRefinedIntent, primeira linha).

  function dedupeMerge(a, b) {
    return Array.from(new Set([...(a || []), ...(b || [])])).slice(0, 10);
  }

  // Interpreta negações/exclusões da mensagem atual (negation-parser.js) e
  // acumula com o que já estava salvo na memória da sessão (TTL de 45min,
  // ver context-memory.js), para que "não quero cristais" dito uma vez
  // continue valendo nas próximas recomendações da mesma sessão. Exclusão
  // sempre vence conflito com inclusão do mesmo termo.
  function buildPreferences(text) {
    const parser = window.Isis2.NegationParser;
    if (!parser) return null;
    const parsed = parser.parse(text);
    const kn = knowledge();
    const completedCourseIds = parser.resolveCompletedCourseIds(text, kn ? kn.listCourses() : []);
    const school = memory().getSchool();

    const excludeTopics = dedupeMerge(school.excludeTopics, parsed.excludeTopics);
    const excludeLevels = dedupeMerge(school.excludeLevels, parsed.excludeLevels);
    const includeTopics = dedupeMerge(school.includeTopics, parsed.includeTopics).filter(t => !excludeTopics.includes(t));
    const includeLevels = dedupeMerge(school.includeLevels, parsed.includeLevels).filter(l => !excludeLevels.includes(l));

    memory().updateSchool({ includeTopics, excludeTopics, includeLevels, excludeLevels });

    return { includeTopics, excludeTopics, includeLevels, excludeLevels, excludeCourseIds: [], completedCourseIds };
  }

  function resolveComparisonCandidates(detection) {
    const kn = knowledge();
    const catalog = kn.listCourses();
    const titleMatches = catalog.filter(c => detection.normalized.includes(kn.normalize(c.titulo)));
    let candidates = titleMatches;
    if (candidates.length < 2 && detection.themeTerms.length) {
      const themeCandidates = detection.themeTerms
        .map(term => kn.searchByTerms([term], { limit: 1 })[0])
        .filter(Boolean);
      candidates = [...candidates, ...themeCandidates];
    }
    const bySlug = new Map();
    candidates.forEach(c => bySlug.set(c.slug, c));
    return Array.from(bySlug.values()).slice(0, window.Isis2.CourseComparisonEngine.MAX_COURSES);
  }

  function comparisonRowText(row) {
    const tema = row.tema || FIELD_UNAVAILABLE;
    const nivel = row.nivel || FIELD_UNAVAILABLE;
    const resumo = row.resumo ? ` — ${row.resumo}` : "";
    return `"${row.titulo}": tema ${tema}, nível ${nivel}${resumo}`;
  }

  async function comparisonReply(detection) {
    const candidates = resolveComparisonCandidates(detection);
    if (candidates.length < 2) {
      return baseReply({
        kind: "school_need_comparison_context",
        text: "Me diga os nomes de até três cursos que você quer comparar (por exemplo, pelo tema de cada um).",
        actions: [{ label: "Ver catálogo de cursos", url: nav().catalogUrl() }],
      });
    }
    const { rows, guidance } = window.Isis2.CourseComparisonEngine.compare(candidates.map(curso => ({ curso })));
    memory().updateSchool({ lastComparedCourseIds: candidates.map(c => c.slug) });
    analytics().trackSchoolEvent("isis_course_comparison", { count: candidates.length });
    return baseReply({
      kind: "school_comparison",
      text: `Comparando ${candidates.length} cursos:\n${rows.map(comparisonRowText).join("\n")}\n\n${guidance.join(" ")}`,
      courses: candidates,
      actions: courseActions(candidates),
    });
  }

  function resolveDetailSlug(detection) {
    const fromFocus = resolveSlugInFocus();
    if (fromFocus) return fromFocus;
    if (detection.themeTerms.length) {
      const match = knowledge().searchByTerms(detection.themeTerms, { limit: 1 })[0];
      if (match) return match.slug;
    }
    return null;
  }

  async function courseDetailReply(detection) {
    const slug = resolveDetailSlug(detection);
    if (!slug) return askWhichCourseReply();
    if (!window.Isis2.SchoolPublicDetail) return catalogUnavailableReply();

    const result = await window.Isis2.SchoolPublicDetail.fetchDetail(slug);
    if (!result.ok) {
      analytics().trackSchoolEvent("isis_school_api_unavailable", { reason: result.reason });
      return baseReply({
        kind: "school_detail_unavailable",
        text: ERROR_PUBLIC_DETAIL,
        actions: nav().courseUrl(slug) ? [{ label: "Ver informações básicas", url: nav().courseUrl(slug) }] : [],
      });
    }

    memory().updateSchool({ lastPublicCourseSlug: slug });
    analytics().trackSchoolEvent("isis_course_detail_consulted", { cached: Boolean(result.fromCache) });

    const curso = result.curso;
    const modulosText = curso.modulos.length
      ? curso.modulos.map(m => `${m.titulo} (${m.totalAulas} aula${m.totalAulas === 1 ? "" : "s"})`).join("; ")
      : "Estrutura de módulos não informada no momento.";
    const partes = [`"${curso.titulo}"`];
    if (curso.resumo) partes.push(curso.resumo);
    if (curso.paraQuemE) partes.push(`Para quem é: ${curso.paraQuemE}`);
    partes.push(`Módulos: ${modulosText}`);

    return baseReply({
      kind: "school_course_detail",
      text: partes.join("\n"),
      actions: [{ label: `Ver "${curso.titulo}"`, url: nav().courseUrl(slug) }],
    });
  }

  function accessHelpReply() {
    const slug = resolveSlugInFocus();
    const curso = slug ? knowledge().bySlug(slug) : null;
    return baseReply({
      kind: "school_access_help",
      text: curso
        ? `Para acessar "${curso.titulo}", entre na sua conta e abra o curso em "Meus cursos". Se ele aparecer bloqueado, o motivo aparece direto na tela do curso.`
        : "Para acessar um curso, entre na sua conta e abra \"Meus cursos\". Se quiser, me diga qual curso para eu te ajudar a encontrar o link certo.",
      actions: [{ label: "Abrir Meus cursos", url: nav().myCoursesUrl() }],
    });
  }

  function levelInfoReply(detection) {
    const slug = resolveDetailSlug(detection);
    const curso = slug ? knowledge().bySlug(slug) : null;
    if (!curso) {
      return baseReply({ kind: "school_level_info", text: "Para eu indicar o nível de um curso específico, me diga qual curso você quer saber." });
    }
    const nivel = (curso.tags || []).find(tag => ["iniciante", "avancado", "avançado"].includes(knowledge().normalize(tag)));
    return baseReply({
      kind: "school_level_info",
      text: nivel ? `"${curso.titulo}" está marcado no catálogo como ${nivel}.` : `${FIELD_UNAVAILABLE} para o nível de "${curso.titulo}".`,
      actions: [{ label: `Ver "${curso.titulo}"`, url: nav().courseUrl(curso.slug) }],
    });
  }

  function reviewContentReply() {
    analytics().trackSchoolEvent("isis_study_path_suggested", { kind: "review" });
    return baseReply({
      kind: "school_review_content",
      text: "Posso ajudar a revisar: me diga o tema ou módulo que você quer relembrar, que eu explico os conceitos principais de novo — sem repetir a avaliação, só o conteúdo da aula.",
    });
  }

  async function resumeStudiesReply() {
    const authed = await student().isAuthenticated();
    if (!authed) {
      analytics().trackSchoolEvent("isis_study_path_suggested", { kind: "resume_not_authenticated" });
      return baseReply({
        kind: "school_resume_not_authenticated",
        text: "Para eu retomar exatamente de onde você parou, preciso que você esteja logado — entre na sua conta ou abra \"Meus cursos\". Enquanto isso, posso te mostrar o catálogo ou recomendar por onde começar.",
        actions: [{ label: "Abrir Meus cursos", url: nav().myCoursesUrl() }],
      });
    }
    analytics().trackSchoolEvent("isis_study_path_suggested", { kind: "resume" });
    return nextLessonReply();
  }

  function unavailabilityAckReply() {
    return baseReply({
      kind: "school_unavailability_ack",
      text: "Se a plataforma estiver fora do ar ou não carregando para você, tente novamente em alguns minutos. Se persistir, entre em contato com o suporte da Mística Escola.",
    });
  }

  async function courseCompletedInfoReply(detection, preferences) {
    const slug = resolveSlugInFocus();
    const curso = slug ? knowledge().bySlug(slug) : null;
    const rec = await recommendationReply(detection, { preferences });
    const prefix = curso ? `Parabéns por concluir "${curso.titulo}"! ` : "Parabéns por concluir o curso! ";
    return { ...rec, text: `${prefix}${rec.text}` };
  }

  // Dispatcher das intenções novas da Fase 2.1. Retorna null (nunca lança)
  // quando a intenção não é nova — quem chama cai de volta no dispatch
  // original da Fase 2, preservado sem alteração logo abaixo. Só é
  // chamado quando refinementActive() já foi confirmado por
  // handleUserMessage (ver ali).
  async function dispatchRefinedIntent(detection, preferences) {
    switch (detection.primaryIntent) {
      case "comparison":
        return comparisonReply(detection);
      case "course_detail":
      case "course_structure":
      case "lesson_count":
        return courseDetailReply(detection);
      case "access":
        return accessHelpReply();
      case "difficulty":
      case "level":
        return levelInfoReply(detection);
      case "review_content":
        return reviewContentReply();
      case "resume_studies":
        return resumeStudiesReply();
      case "unavailability":
        return unavailabilityAckReply();
      case "course_completed":
        return courseCompletedInfoReply(detection, preferences);
      default:
        return null;
    }
  }

  function detectionToEventBucket(detection) {
    if (detection.isCatalogQuery) return "catalog";
    if (detection.isBestStartQuery) return "best_start";
    if (detection.isMyCoursesQuery) return "my_courses";
    if (detection.isNextModuleQuery || detection.isNextLessonQuery) return "next_lesson";
    if (detection.isProgressQuery) return "progress";
    if (detection.isBlockedModuleQuery) return "blocked_module";
    if (detection.isGradeQuery) return "grade";
    if (detection.isAttemptsQuery) return "attempts";
    if (detection.isSuspendedQuery) return "suspended";
    if (detection.themeTerms.length) return "theme";
    return "unknown";
  }

  async function handleUserMessage(text) {
    const detection = window.Isis2.SchoolIntentEngine.detect(text);
    analytics().trackSchoolEvent("isis_school_intent", { intent: detectionToEventBucket(detection) });

    if (!knowledge() || !knowledge().hasCatalog()) return catalogUnavailableReply();
    if (detection.isGreeting) return greetingReply();
    if (detection.isThanks) return thanksReply();

    const assessment = window.Isis2.AssessmentSafety ? window.Isis2.AssessmentSafety.classify(text) : null;
    if (assessment === "direct_answer_request") {
      // Fase 2.1: evento dedicado de contorno de avaliação, além do
      // evento "isis_assessment_help_blocked" já existente da Fase 2
      // (mantido sem alteração) — só disparado com a flag de refinamento
      // ligada, nunca carrega texto da pergunta/resposta.
      if (refinementActive()) analytics().trackSchoolEvent("isis_assessment_bypass_blocked", {});
      return assessmentHelpReply();
    }

    const classification = window.Isis2.SafetyGuardrails ? window.Isis2.SafetyGuardrails.classify(text) : null;
    if (classification) {
      const safety = safetyReply(classification);
      if (safety) return safety;
    }

    // Fase 2.1 — intenções novas (comparação, detalhe público, acesso,
    // nível, revisão, retomada, indisponibilidade, curso concluído) e
    // negações/exclusões (negation-parser.js). Só roda com a flag de
    // refinamento ligada; com ela desligada, `preferences` fica null e o
    // dispatch abaixo (Fase 2) é idêntico ao anterior.
    const refinement = refinementActive();
    const preferences = refinement ? buildPreferences(text) : null;
    if (refinement) {
      analytics().trackSchoolEvent("isis_school_refinement_intent", { intent: detection.primaryIntent });
      const refinedReply = await dispatchRefinedIntent(detection, preferences);
      if (refinedReply) return refinedReply;
    }

    if (detection.isSuspendedQuery) {
      return baseReply({ kind: "school_suspended_info", text: "Se sua matrícula estiver suspensa, o motivo e como regularizar aparecem ao abrir o curso — posso te levar até lá.", actions: resolveSlugInFocus() ? [{ label: "Abrir curso", url: nav().courseUrl(resolveSlugInFocus()) }] : [] });
    }
    if (detection.isMyCoursesQuery) return myCoursesReply();
    if (detection.isBlockedModuleQuery) return blockedModuleReply();
    if (detection.isNextModuleQuery || detection.isNextLessonQuery) return nextLessonReply();
    if (detection.isProgressQuery) return progressReply();
    if (detection.isGradeQuery) return gradeReply();
    if (detection.isAttemptsQuery) return attemptsReply();
    if (/modulo|módulo/.test(detection.normalized) && /como funciona|o que e|o que é/.test(detection.normalized)) return howModulesWorkReply();
    if (detection.isCatalogQuery) return catalogReply();
    if (detection.isBestStartQuery) return recommendationReply(detection, { introWhenBeginner: true, preferences });
    if (detection.themeTerms.length) return recommendationReply(detection, { preferences });

    return baseReply({
      kind: "school_fallback",
      text: "Ainda não entendi exatamente o que você precisa sobre os cursos. Posso mostrar o catálogo, recomendar por onde começar, ou (se você estiver logado) consultar seu progresso.",
    });
  }

  function handleIntentShortcut(intentId) {
    const shortcuts = {
      school_meus_cursos: () => myCoursesReply(),
      school_continuar: () => nextLessonReply(),
      school_comecar: () => recommendationReply({ themeTerms: [], wantsBeginner: true }, { introWhenBeginner: true }),
      school_modulos: () => Promise.resolve(howModulesWorkReply()),
      school_bloqueio: () => blockedModuleReply(),
    };
    const handler = shortcuts[intentId];
    return handler ? handler() : Promise.resolve(catalogReply());
  }

  function startConversation() {
    analytics().trackSchoolEvent("isis_school_opened", {}, { dedupeKey: "session" });
    return Promise.resolve(greetingReply());
  }

  window.Isis2.SchoolConversationManager = {
    handleUserMessage,
    handleIntentShortcut,
    startConversation,
    QUICK_REPLIES,
  };
})();
