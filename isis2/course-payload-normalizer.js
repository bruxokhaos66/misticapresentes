// Isis 2.0 — Course Payload Normalizer (Fase 2.1 — Refinamento da
// Especialista da Mística Escola).
//
// Normaliza e valida com rigor o payload devolvido pelo endpoint público
// de detalhe de curso (GET /api/escola/publico/cursos/:slug). Nunca confia
// no retorno só por ter status 200: valida tipo, tamanho, formato de cada
// campo, ignora campos desconhecidos e nunca deixa passar um valor que
// possa ser usado como HTML confiável (a Widget sempre usa textContent
// para estes campos, nunca innerHTML — ver widget.js). Retorna null
// sempre que o payload não puder ser normalizado com segurança; quem
// chama trata isso como "detalhe indisponível", nunca inventa um valor.
(() => {
  window.Isis2 = window.Isis2 || {};
  if (window.Isis2.CoursePayloadNormalizer) return;

  const MAX_TITLE = 160;
  const MAX_SUMMARY = 2000;
  const MAX_LIST = 60;
  const SLUG_PATTERN = /^[a-z0-9-]{1,80}$/;

  function isNonEmptyString(value, max) {
    return typeof value === "string" && value.trim().length > 0 && value.length <= max;
  }

  function cleanString(value, max) {
    if (typeof value !== "string") return "";
    return value.trim().slice(0, max);
  }

  function normalizeAula(raw, index) {
    if (!raw || typeof raw !== "object") return null;
    if (!isNonEmptyString(raw.titulo, MAX_TITLE)) return null;
    return {
      id: isNonEmptyString(raw.id, 80) ? cleanString(raw.id, 80) : null,
      titulo: cleanString(raw.titulo, MAX_TITLE),
      ordem: Number.isFinite(raw.ordem) ? raw.ordem : index,
      disponivel: raw.disponivel !== false,
    };
  }

  function normalizeModulo(raw, index) {
    if (!raw || typeof raw !== "object") return null;
    if (!isNonEmptyString(raw.titulo, MAX_TITLE)) return null;
    const aulasRaw = Array.isArray(raw.aulas) ? raw.aulas.slice(0, MAX_LIST) : [];
    const aulas = aulasRaw.map(normalizeAula).filter(Boolean);
    return {
      id: isNonEmptyString(raw.id, 80) ? cleanString(raw.id, 80) : null,
      titulo: cleanString(raw.titulo, MAX_TITLE),
      ordem: Number.isFinite(raw.ordem) ? raw.ordem : index,
      aulas,
      totalAulas: aulas.length,
    };
  }

  // Retorna { ok: true, curso } com um objeto normalizado e seguro para
  // renderização (sempre via textContent/atributos escapados), ou
  // { ok: false, reason } quando o payload não é confiável — nunca lança.
  function normalizeCourseDetail(raw, { expectedSlug } = {}) {
    if (!raw || typeof raw !== "object" || Array.isArray(raw)) return { ok: false, reason: "invalid_payload" };
    if (!isNonEmptyString(raw.slug, 80) || !SLUG_PATTERN.test(raw.slug)) return { ok: false, reason: "invalid_payload" };
    if (expectedSlug && raw.slug !== expectedSlug) return { ok: false, reason: "invalid_payload" };
    if (!isNonEmptyString(raw.titulo, MAX_TITLE)) return { ok: false, reason: "invalid_payload" };

    const modulosRaw = Array.isArray(raw.modulos) ? raw.modulos.slice(0, MAX_LIST) : [];
    const modulos = modulosRaw.map(normalizeModulo).filter(Boolean);

    const curso = {
      slug: cleanString(raw.slug, 80),
      titulo: cleanString(raw.titulo, MAX_TITLE),
      resumo: isNonEmptyString(raw.resumo, MAX_SUMMARY) ? cleanString(raw.resumo, MAX_SUMMARY) : null,
      descricao: isNonEmptyString(raw.descricao, MAX_SUMMARY) ? cleanString(raw.descricao, MAX_SUMMARY) : null,
      paraQuemE: isNonEmptyString(raw.para_quem_e, MAX_SUMMARY) ? cleanString(raw.para_quem_e, MAX_SUMMARY) : null,
      nivel: isNonEmptyString(raw.nivel, 40) ? cleanString(raw.nivel, 40) : null,
      tags: Array.isArray(raw.tags) ? raw.tags.filter(t => typeof t === "string").map(t => cleanString(t, 40)).slice(0, 20) : [],
      modulos,
      totalModulos: modulos.length,
      totalAulas: modulos.reduce((acc, m) => acc + m.totalAulas, 0),
      disponivel: raw.disponivel !== false,
    };

    return { ok: true, curso };
  }

  window.Isis2.CoursePayloadNormalizer = { normalizeCourseDetail };
})();
