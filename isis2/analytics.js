// Isis 2.0 — Analytics.
//
// Métricas de uso da assistente, sem dados pessoais: apenas contadores
// agregados por sessão (conversas iniciadas, recomendações, cliques,
// adições ao carrinho, conversão, abandono). Encaminha para
// window.misticaTrack quando disponível (GA/Meta Pixel, já com
// gate de consentimento em analytics.js) e mantém uma cópia local em
// sessionStorage só para depuração/QA.
(() => {
  window.Isis2 = window.Isis2 || {};
  if (window.Isis2.Analytics) return;

  const STORAGE_KEY = "isis2_metrics";

  function safeStorage() {
    try {
      return window.sessionStorage;
    } catch {
      return null;
    }
  }

  function load() {
    const storage = safeStorage();
    if (!storage) return {};
    try {
      return JSON.parse(storage.getItem(STORAGE_KEY) || "{}");
    } catch {
      return {};
    }
  }

  function save(data) {
    const storage = safeStorage();
    if (!storage) return;
    try {
      storage.setItem(STORAGE_KEY, JSON.stringify(data));
    } catch {
      /* ignora falha de storage */
    }
  }

  function track(eventName, payload = {}) {
    const data = load();
    data[eventName] = (data[eventName] || 0) + 1;
    save(data);
    try {
      window.misticaTrack?.(`isis2_${eventName}`, payload);
    } catch {
      /* nunca deixa telemetria quebrar a conversa */
    }
  }

  function getMetrics() {
    return { ...load() };
  }

  window.Isis2.Analytics = { track, getMetrics };
})();
