// Isis 2.0 — School Public Detail (Fase 2.1 — Refinamento da
// Especialista da Mística Escola).
//
// Consulta, sob demanda e só quando o cliente pede (nunca ao abrir o
// widget, nunca para todos os cursos de uma vez), o endpoint público:
//   GET /api/escola/publico/cursos/:slug
// Somente leitura. Cache curto por slug, timeout com AbortController,
// tratamento explícito de cada falha (401 inesperado, 403, 404, 429, 500,
// JSON inválido, HTML inesperado, corpo vazio, payload incompleto, curso
// removido, slug inválido, conexão lenta, offline). Nunca inventa detalhe
// quando a consulta falha — devolve { ok:false, reason } e quem chama usa
// a mensagem padrão de indisponibilidade (school-conversation-manager.js).
(() => {
  window.Isis2 = window.Isis2 || {};
  if (window.Isis2.SchoolPublicDetail) return;

  const SLUG_PATTERN = /^[a-z0-9-]{1,80}$/;
  const TIMEOUT_MS = 6000;
  const CACHE_TTL_MS = 3 * 60 * 1000; // cache curto: 3 minutos por slug

  const cache = new Map(); // slug -> { expiresAt, result }

  function apiBase() {
    return String((window.misticaSiteConfig || {}).apiBaseUrl || "https://api.misticaesotericos.com.br").replace(/\/$/, "");
  }

  function isValidSlug(slug) {
    return typeof slug === "string" && SLUG_PATTERN.test(slug);
  }

  function isOffline() {
    try {
      return typeof navigator !== "undefined" && navigator.onLine === false;
    } catch {
      return false;
    }
  }

  function fromCache(slug) {
    const entry = cache.get(slug);
    if (!entry) return null;
    if (Date.now() > entry.expiresAt) {
      cache.delete(slug);
      return null;
    }
    return entry.result;
  }

  function storeCache(slug, result) {
    if (!result.ok) return; // só cacheia sucesso — falha nunca fica "presa" em cache curto
    cache.set(slug, { expiresAt: Date.now() + CACHE_TTL_MS, result });
  }

  function clearCache() {
    cache.clear();
  }

  async function rawFetch(slug, timeoutMs) {
    const controller = typeof AbortController !== "undefined" ? new AbortController() : null;
    const timer = controller ? setTimeout(() => controller.abort(), timeoutMs) : null;
    try {
      const response = await fetch(`${apiBase()}/api/escola/publico/cursos/${encodeURIComponent(slug)}`, {
        method: "GET",
        headers: { Accept: "application/json" },
        signal: controller ? controller.signal : undefined,
      });
      return { response };
    } catch (err) {
      if (err && err.name === "AbortError") return { error: "timeout" };
      return { error: "network" };
    } finally {
      if (timer) clearTimeout(timer);
    }
  }

  function contentTypeIsJson(response) {
    try {
      const ct = response.headers?.get?.("content-type") || "";
      return ct.includes("application/json");
    } catch {
      return false;
    }
  }

  // Consulta o detalhe público de um curso. Sempre devolve um objeto com
  // "ok" e, em falha, "reason" de uma lista fechada de categorias (usada
  // também por analytics.js, nunca a mensagem bruta da API):
  //   timeout | offline | invalid_payload | not_found | rate_limited |
  //   server_error | unauthorized | forbidden | network
  async function fetchDetail(slug, { fresh = false, timeoutMs = TIMEOUT_MS } = {}) {
    if (!isValidSlug(slug)) return { ok: false, reason: "invalid_payload" };
    if (!fresh) {
      const cached = fromCache(slug);
      if (cached) return { ...cached, fromCache: true };
    }
    if (isOffline()) return { ok: false, reason: "offline" };

    const { response, error } = await rawFetch(slug, timeoutMs);
    if (error === "timeout") return { ok: false, reason: "timeout" };
    if (error) return { ok: false, reason: "network" };

    if (response.status === 401) return { ok: false, reason: "unauthorized" };
    if (response.status === 403) return { ok: false, reason: "forbidden" };
    if (response.status === 404) return { ok: false, reason: "not_found" };
    if (response.status === 429) return { ok: false, reason: "rate_limited" };
    if (response.status >= 500) return { ok: false, reason: "server_error" };
    if (!response.ok) return { ok: false, reason: "server_error" };

    if (!contentTypeIsJson(response)) return { ok: false, reason: "invalid_payload" };

    let body;
    try {
      const text = await response.text();
      if (!text || !text.trim()) return { ok: false, reason: "invalid_payload" };
      body = JSON.parse(text);
    } catch {
      return { ok: false, reason: "invalid_payload" };
    }

    const normalizer = window.Isis2.CoursePayloadNormalizer;
    const normalized = normalizer ? normalizer.normalizeCourseDetail(body, { expectedSlug: slug }) : { ok: false };
    if (!normalized.ok) return { ok: false, reason: "invalid_payload" };
    if (normalized.curso.disponivel === false) return { ok: false, reason: "not_found" };

    const result = { ok: true, curso: normalized.curso, fromCache: false };
    storeCache(slug, result);
    return result;
  }

  window.Isis2.SchoolPublicDetail = { fetchDetail, clearCache, isValidSlug };
})();
