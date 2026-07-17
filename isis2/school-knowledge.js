// Isis 2.0 — School Knowledge (Fase 2 — Especialista da Mística Escola).
//
// Única fonte de leitura sobre cursos: catálogo público real
// (window.MISTICA_ESCOLA_CURSOS, exposto por escola.js) + APIs reais da
// Mística Escola (endpoints /api/escola/*). Nunca inventa curso, preço,
// duração, certificado ou pré-requisito que não esteja nessas fontes.
// Como product-knowledge.js na Fase 1, retorna null/undefined quando a
// informação não existe, e quem consome decide como admitir a lacuna.
(() => {
  window.Isis2 = window.Isis2 || {};
  if (window.Isis2.SchoolKnowledge) return;

  function normalize(value) {
    return String(value || "")
      .normalize("NFD")
      .replace(/[̀-ͯ]/g, "")
      .toLowerCase()
      .trim();
  }

  function apiBase() {
    return String((window.misticaSiteConfig || {}).apiBaseUrl || "https://api.misticaesotericos.com.br").replace(/\/$/, "");
  }

  function catalog() {
    return typeof window !== "undefined" && Array.isArray(window.MISTICA_ESCOLA_CURSOS)
      ? window.MISTICA_ESCOLA_CURSOS
      : [];
  }

  function hasCatalog() {
    return catalog().length > 0;
  }

  function listCourses() {
    return catalog().slice();
  }

  function bySlug(slug) {
    return catalog().find(curso => curso.slug === slug) || null;
  }

  function formatPrice(value) {
    try {
      return new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" }).format(Number(value || 0));
    } catch {
      return `R$ ${Number(value || 0).toFixed(2).replace(".", ",")}`;
    }
  }

  // Pontuação simples por frequência de termos em título/tags/resumo —
  // mesma técnica leve do product-knowledge.js#searchByTerms.
  function searchByTerms(terms, { limit = 3 } = {}) {
    const normTerms = (terms || []).map(normalize).filter(Boolean);
    if (!normTerms.length) return [];
    return catalog()
      .map(curso => {
        const haystack = normalize(`${curso.titulo} ${(curso.tags || []).join(" ")} ${curso.resumo || ""}`);
        const score = normTerms.reduce((acc, term) => acc + (haystack.includes(term) ? 1 : 0), 0);
        return { curso, score };
      })
      .filter(row => row.score > 0)
      .sort((a, b) => b.score - a.score)
      .slice(0, limit)
      .map(row => row.curso);
  }

  async function apiJson(path, options = {}) {
    try {
      const response = await fetch(`${apiBase()}${path}`, {
        credentials: "include",
        headers: { "Content-Type": "application/json", ...(options.headers || {}) },
        ...options,
      });
      const body = await response.json().catch(() => ({}));
      return { ok: response.ok, status: response.status, body, networkError: false };
    } catch {
      return { ok: false, status: 0, body: {}, networkError: true };
    }
  }

  // Detalhe público (sem sessão): usado para visitante não autenticado —
  // nunca contém progresso pessoal, o backend só devolve o que é público.
  function fetchPublicDetail(slug) {
    return apiJson(`/api/escola/publico/cursos/${encodeURIComponent(slug)}`);
  }

  // Detalhe autenticado (com progresso real do aluno) — 401 sem sessão,
  // 403 sem acesso à matrícula. A autorização é sempre decidida pelo
  // backend; este módulo só repassa o status recebido.
  function fetchAuthenticatedDetail(slug) {
    return apiJson(`/api/escola/cursos/${encodeURIComponent(slug)}`);
  }

  window.Isis2.SchoolKnowledge = {
    normalize,
    hasCatalog,
    listCourses,
    bySlug,
    searchByTerms,
    formatPrice,
    fetchPublicDetail,
    fetchAuthenticatedDetail,
  };
})();
