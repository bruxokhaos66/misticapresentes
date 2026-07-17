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

  function emptyState() {
    return {
      startedAt: new Date().toISOString(),
      messageCount: 0,
      lastIntentId: null,
      categoryOfInterest: null,
      budget: null,
      viewedProductIds: [],
      cartAddedIds: [],
    };
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

  window.Isis2.ContextMemory = {
    get,
    update,
    addViewedProduct,
    addCartAdd,
    registerMessage,
    reset,
  };
})();
