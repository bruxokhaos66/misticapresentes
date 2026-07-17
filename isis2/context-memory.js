// Isis 2.0 — Context Memory (memória de sessão).
//
// Guarda apenas sinais não sensíveis para melhorar a conversa dentro da
// mesma aba: intenção, categoria/orçamento de interesse, produtos vistos
// e adicionados ao carrinho. Nunca nome, telefone, endereço, CPF ou
// qualquer dado pessoal. Usa sessionStorage (limpa ao fechar a aba) em
// vez de localStorage, para reforçar que é memória de sessão, não
// persistência definitiva.
(() => {
  window.Isis2 = window.Isis2 || {};
  if (window.Isis2.ContextMemory) return;

  const STORAGE_KEY = "isis2_session";

  // Memória da Escola (Fase 2): expira sozinha depois de
  // SCHOOL_TTL_MS mesmo dentro da mesma aba/sessionStorage — mais estrito
  // que a memória comercial (que só "expira" ao fechar a aba). Nunca
  // guarda resposta de avaliação, nota completa, texto integral de
  // conversa, dado pessoal, token, cookie ou conteúdo médico.
  const SCHOOL_TTL_MS = 45 * 60 * 1000;
  const SCHOOL_LIST_MAX = 10;

  function emptyState() {
    return {
      startedAt: new Date().toISOString(),
      messageCount: 0,
      lastIntentId: null,
      categoryOfInterest: null,
      budget: null,
      viewedProductIds: [],
      cartAddedIds: [],
      school: emptySchoolState(),
    };
  }

  function emptySchoolState() {
    return {
      updatedAt: null,
      courseOfInterest: null,
      studentLevel: null,
      viewedCourseSlug: null,
      currentModuleId: null,
      currentLessonId: null,
      educationalIntent: null,
      presentedCourseIds: [],
      // Fase 2.1 — allowlist fechada, só termos normalizados de um
      // vocabulário fechado (negation-parser.js) ou slugs já validados
      // contra o catálogo real, nunca texto integral da conversa, nota,
      // e-mail, nome, ID de aluno, token ou cookie.
      includeTopics: [],
      excludeTopics: [],
      includeLevels: [],
      excludeLevels: [],
      lastRecommendedCourseIds: [],
      lastComparedCourseIds: [],
      lastPublicCourseSlug: null,
    };
  }

  // Fase 2.1 — allowlist fechada de campos aceitos em updateSchool()/
  // partial de school. Qualquer chave fora desta lista é ignorada
  // silenciosamente (nunca lança, nunca deixa passar um campo novo sem
  // revisão explícita deste arquivo) — reforça a regra de "nenhum dado de
  // avaliação, nota, e-mail, nome, ID de aluno, token ou cookie".
  const SCHOOL_FIELD_ALLOWLIST = [
    "courseOfInterest", "studentLevel", "viewedCourseSlug", "currentModuleId", "currentLessonId",
    "educationalIntent", "includeTopics", "excludeTopics", "includeLevels", "excludeLevels",
    "lastRecommendedCourseIds", "lastComparedCourseIds", "lastPublicCourseSlug",
  ];
  const SCHOOL_LIST_FIELDS = ["includeTopics", "excludeTopics", "includeLevels", "excludeLevels", "lastRecommendedCourseIds", "lastComparedCourseIds"];

  function sanitizeSchoolPartial(partial) {
    const clean = {};
    Object.keys(partial || {}).forEach(key => {
      if (!SCHOOL_FIELD_ALLOWLIST.includes(key)) return;
      const value = partial[key];
      if (SCHOOL_LIST_FIELDS.includes(key)) {
        clean[key] = Array.isArray(value) ? value.filter(v => typeof v === "string" && v.length <= 80).slice(0, SCHOOL_LIST_MAX) : [];
      } else if (value === null || (typeof value === "string" && value.length <= 200)) {
        clean[key] = value;
      }
    });
    return clean;
  }

  function safeStorage() {
    try {
      return window.sessionStorage;
    } catch {
      return null;
    }
  }

  let memoryState = null;

  function load() {
    if (memoryState) return memoryState;
    const storage = safeStorage();
    if (!storage) {
      memoryState = emptyState();
      return memoryState;
    }
    try {
      const raw = storage.getItem(STORAGE_KEY);
      memoryState = raw ? { ...emptyState(), ...JSON.parse(raw) } : emptyState();
    } catch {
      memoryState = emptyState();
    }
    return memoryState;
  }

  function persist() {
    const storage = safeStorage();
    if (!storage || !memoryState) return;
    try {
      storage.setItem(STORAGE_KEY, JSON.stringify(memoryState));
    } catch {
      /* sessionStorage indisponível (modo privado etc.) — segue só em memória */
    }
  }

  function get() {
    return { ...load() };
  }

  function update(partial) {
    const state = load();
    Object.assign(state, partial);
    persist();
    return get();
  }

  function addUnique(list, value, max = 10) {
    if (!value || list.includes(value)) return list;
    return [...list, value].slice(-max);
  }

  function addViewedProduct(id) {
    const state = load();
    state.viewedProductIds = addUnique(state.viewedProductIds, id);
    persist();
  }

  function addCartAdd(id) {
    const state = load();
    state.cartAddedIds = addUnique(state.cartAddedIds, id);
    persist();
  }

  function registerMessage(detection) {
    const state = load();
    state.messageCount += 1;
    if (detection.primaryIntent) state.lastIntentId = detection.primaryIntent.id;
    if (detection.budget) state.budget = detection.budget;
    if (detection.primaryIntent) state.categoryOfInterest = detection.primaryIntent.priorityCategory;
    persist();
    return get();
  }

  function reset() {
    memoryState = emptyState();
    persist();
    return get();
  }

  // ---- Memória da Escola (Fase 2) ----------------------------------------

  function schoolExpired(school) {
    if (!school || !school.updatedAt) return false;
    return Date.now() - new Date(school.updatedAt).getTime() > SCHOOL_TTL_MS;
  }

  // Devolve a memória da Escola, ou o estado vazio se ela expirou (sem
  // apagar o resto da sessão comercial).
  function getSchool() {
    const state = load();
    if (!state.school) state.school = emptySchoolState();
    if (schoolExpired(state.school)) {
      state.school = emptySchoolState();
      persist();
    }
    return { ...state.school };
  }

  function updateSchool(partial) {
    const state = load();
    if (!state.school || schoolExpired(state.school)) state.school = emptySchoolState();
    Object.assign(state.school, sanitizeSchoolPartial(partial), { updatedAt: new Date().toISOString() });
    persist();
    return getSchool();
  }

  function addPresentedCourse(slug) {
    if (!slug) return;
    const state = load();
    if (!state.school || schoolExpired(state.school)) state.school = emptySchoolState();
    state.school.presentedCourseIds = addUnique(state.school.presentedCourseIds, slug, SCHOOL_LIST_MAX);
    state.school.updatedAt = new Date().toISOString();
    persist();
  }

  function resetSchool() {
    const state = load();
    state.school = emptySchoolState();
    persist();
    return getSchool();
  }

  window.Isis2.ContextMemory = {
    get,
    update,
    addViewedProduct,
    addCartAdd,
    registerMessage,
    reset,
    getSchool,
    updateSchool,
    addPresentedCourse,
    resetSchool,
  };
})();
