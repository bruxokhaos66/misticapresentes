// Isis 2.0 — Chat Inteligente (homologação controlada).
//
// Único script sempre baixado pelas páginas públicas para este módulo.
// Não confia em nenhuma flag lida só no navegador: consulta
// GET /api/isis2/chat/config com o cookie de sessão HttpOnly já existente
// (admin ou aluno) e só injeta o restante do widget se o servidor
// confirmar {enabled:true, authorized:true} -- ver backend/isis_chat_routes.py
// e backend/isis_chat_auth.py. Sem essa confirmação, nenhum outro arquivo
// deste módulo é baixado (nenhum script, nenhum CSS, nenhuma requisição
// extra) -- mesmo padrão de isis2/isis2-homolog-gate.js.
(() => {
  if (window.__MISTICA_ISIS_CHAT_GATE__) return;
  window.__MISTICA_ISIS_CHAT_GATE__ = true;

  const VERSION = "20260717-isis-chat-homolog";
  const cfg = window.misticaSiteConfig || {};
  const apiBase = String(cfg.apiBaseUrl || "").replace(/\/$/, "");
  if (!apiBase) return;

  function injetarWidget() {
    if (document.getElementById("misticaIsisChatWidgetScript")) return;
    const link = document.createElement("link");
    link.rel = "stylesheet";
    link.href = `isis2/chat-widget.css?v=${VERSION}`;
    document.head.appendChild(link);

    const script = document.createElement("script");
    script.id = "misticaIsisChatWidgetScript";
    script.src = `isis2/chat-widget.js?v=${VERSION}`;
    script.defer = true;
    script.dataset.apiBase = apiBase;
    document.head.appendChild(script);
  }

  fetch(`${apiBase}/api/isis2/chat/config`, {
    method: "GET",
    credentials: "include",
    cache: "no-store",
  })
    .then((resposta) => (resposta.ok ? resposta.json() : null))
    .then((dados) => {
      const autorizado = dados && dados.enabled === true && dados.authorized === true;
      if (autorizado) injetarWidget();
    })
    .catch(() => {
      // Fail-safe: qualquer erro de rede/parse mantém o chat desativado.
    });
})();
