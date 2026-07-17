"use strict";
// Carrega os módulos da Isis 2.0 — Especialista da Mística Escola (Fase 2)
// num ambiente Node mínimo, simulando `window`, `sessionStorage`, `fetch`,
// `location.pathname` e o catálogo real (window.MISTICA_ESCOLA_CURSOS,
// como escola.js expõe de verdade). Mesmo padrão de
// tests/isis2/helpers/load-isis2.js (Fase 1).

const { createMemoryStorage } = require("./load-isis2");

const MODULE_FILES = [
  "../../../isis2/product-knowledge.js",
  "../../../isis2/intent-engine.js",
  "../../../isis2/safety-guardrails.js",
  "../../../isis2/recommendation-engine.js",
  "../../../isis2/context-memory.js",
  "../../../isis2/analytics.js",
  "../../../isis2/cart-assistant.js",
  "../../../isis2/ai-providers.js",
  "../../../isis2/school-mode.js",
  "../../../isis2/school-knowledge.js",
  "../../../isis2/student-context.js",
  "../../../isis2/course-recommendation-engine.js",
  "../../../isis2/lesson-navigation.js",
  "../../../isis2/progress-assistant.js",
  "../../../isis2/assessment-safety.js",
  "../../../isis2/school-intent-engine.js",
  "../../../isis2/school-conversation-manager.js",
  "../../../isis2/conversation-manager.js",
];

const CURSOS_REAIS = [
  { slug: "xamanismo-introducao", titulo: "Xamanismo: Introdução", icone: "🌿", tipo: "gratuito", preco: 0, tags: ["Xamanismo", "Iniciante"], resumo: "Fundamentos do xamanismo: história, práticas, símbolos." },
  { slug: "rape-uso-tradicao", titulo: "Rapé: Uso e Tradição", icone: "🍃", tipo: "pago", preco: 97, tags: ["Rapé", "Ritual"], resumo: "A origem indígena do rapé, seus usos tradicionais e cuidados." },
  { slug: "ayahuasca-fundamentos", titulo: "Ayahuasca: Fundamentos", icone: "🌀", tipo: "pago", preco: 127, tags: ["Ayahuasca", "Ritual"], resumo: "História, preparo tradicional e contexto ritualístico." },
  { slug: "origem-universo-dias-atuais", titulo: "Origem do Universo até os Dias Atuais", icone: "✨", tipo: "pago", preco: 147, tags: ["Cosmologia", "História"], resumo: "Uma jornada pela origem do universo até os dias atuais." },
];

function loadIsis2Escola({
  pathname = "/escola.html",
  query = "",
  isis2Enabled = true,
  escolaEnabled = true,
  cursos = CURSOS_REAIS,
  fetchImpl = null,
} = {}) {
  MODULE_FILES.forEach(file => delete require.cache[require.resolve(file)]);

  global.window = global;
  global.window.Isis2 = undefined;
  global.window.sessionStorage = createMemoryStorage();
  global.window.misticaTrack = undefined;
  global.window.misticaSiteConfig = {
    apiBaseUrl: "https://api.misticaesotericos.com.br",
    isis2: { enabled: isis2Enabled, escola: { enabled: escolaEnabled } },
  };
  global.window.location = { pathname, href: `https://www.misticaesotericos.com.br${pathname}${query}`, search: query };
  function deepFreeze(value) {
    if (value === null || typeof value !== "object" || Object.isFrozen(value)) return value;
    Object.values(value).forEach(deepFreeze);
    return Object.freeze(value);
  }
  // Mesma técnica de congelamento profundo de escola.js (não só o array e
  // cada curso, mas também campos aninhados como "tags").
  global.window.MISTICA_ESCOLA_CURSOS = deepFreeze(cursos.map(c => ({ ...c })));
  global.document = { getElementById: () => null, querySelector: () => null };

  const calls = [];
  const impl = fetchImpl || (async () => ({ ok: false, status: 0, json: async () => ({}) }));
  global.fetch = (...args) => {
    calls.push(args);
    return impl(...args);
  };

  MODULE_FILES.forEach(file => require(file));

  return { Isis2: global.window.Isis2, calls };
}

// fetch mock helper: mapeia "METHOD path" (prefixo de path) para uma
// resposta { status, body }. Usado pelos testes para simular
// 200/401/403/500/timeout sem bater em rede real.
function mockFetch(routes) {
  return async (url, options = {}) => {
    const method = (options.method || "GET").toUpperCase();
    const path = String(url).replace("https://api.misticaesotericos.com.br", "");
    const key = Object.keys(routes).find(k => {
      const [routeMethod, routePath] = k.split(" ");
      return routeMethod === method && path.startsWith(routePath);
    });
    if (!key) return { ok: false, status: 404, json: async () => ({ detail: "not found" }) };
    const route = routes[key];
    if (route === "network_error") throw new Error("network down");
    const status = route.status ?? 200;
    return { ok: status >= 200 && status < 300, status, json: async () => route.body ?? {} };
  };
}

module.exports = { loadIsis2Escola, mockFetch, CURSOS_REAIS };
