// Isis 2.0 — Student Context (Fase 2 — Especialista da Mística Escola).
//
// Único módulo que consulta o estado do aluno autenticado, sempre via as
// APIs reais (mesmas usadas por escola.js/escola-curso.js), nunca via
// localStorage/sessionStorage como fonte de autorização. A sessão em si
// (cookie httpOnly) é gerida pelo backend; este módulo não lê, grava nem
// expõe token nenhum. Cache só em variável de módulo (não persiste entre
// carregamentos de página, some ao navegar) para evitar chamadas
// repetidas dentro da mesma conversa.
(() => {
  window.Isis2 = window.Isis2 || {};
  if (window.Isis2.StudentContext) return;

  function apiBase() {
    return String((window.misticaSiteConfig || {}).apiBaseUrl || "https://api.misticaesotericos.com.br").replace(/\/$/, "");
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

  let cachedMe;

  // Consulta quem está logado (se alguém). Nunca decide autorização a
  // partir de estado local — só o que a API responde agora.
  async function me({ fresh = false } = {}) {
    if (!fresh && cachedMe !== undefined) return cachedMe;
    const r = await apiJson("/api/alunos/me");
    cachedMe = r.ok ? r.body : null;
    return cachedMe;
  }

  async function isAuthenticated() {
    return Boolean(await me());
  }

  // "Meus cursos": lista de matrículas reais do aluno (slug, título,
  // percentual, aulas concluídas/total). 401 = sem sessão.
  function myCourses() {
    return apiJson("/api/escola/meus-cursos");
  }

  // Curso completo com progresso real (módulos, bloqueio, quiz). 401 =
  // sem sessão (cai para conteúdo público); 403 = sem acesso à matrícula
  // (pagamento pendente/suspenso).
  function courseDetail(slug) {
    return apiJson(`/api/escola/cursos/${encodeURIComponent(slug)}`);
  }

  function resetCache() {
    cachedMe = undefined;
  }

  window.Isis2.StudentContext = {
    me,
    isAuthenticated,
    myCourses,
    courseDetail,
    resetCache,
  };
})();
