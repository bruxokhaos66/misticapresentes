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

  // Guarda de-dupe em memória (não em storage — só precisa durar o tempo
  // de um remount/clique duplo dentro da mesma execução da página).
  const recentDedupeKeys = new Set();

  // Eventos da Escola (Fase 2) usam nomes fixos do briefing
  // ("isis_school_opened" etc., sem o "2" do prefixo comercial
  // "isis2_*") — trackSchoolEvent envia o nome exato, sem prefixo
  // automático, mas reaproveita a mesma infraestrutura (contador local +
  // misticaTrack + gate de consentimento já existente). dedupeKey opcional
  // evita contar duas vezes o mesmo evento em remontagem/clique duplo
  // (ex.: "isis_school_opened:<slug>" só dispara uma vez por essa chave).
  function trackSchoolEvent(eventName, payload = {}, { dedupeKey = null } = {}) {
    if (dedupeKey) {
      const key = `${eventName}:${dedupeKey}`;
      if (recentDedupeKeys.has(key)) return;
      recentDedupeKeys.add(key);
    }
    const data = load();
    data[eventName] = (data[eventName] || 0) + 1;
    save(data);
    try {
      window.misticaTrack?.(eventName, payload);
    } catch {
      /* nunca deixa telemetria quebrar a conversa */
    }
  }

  function getMetrics() {
    return { ...load() };
  }

  window.Isis2.Analytics = { track, trackSchoolEvent, getMetrics };
})();
