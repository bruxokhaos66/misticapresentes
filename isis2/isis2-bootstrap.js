// Isis 2.0 — bootstrap.
//
// Monta o widget flutuante após o catálogo estar pronto, e só quando a
// feature flag pública MISTICA_ISIS2_ENABLED (window.misticaSiteConfig
// .isis2.enabled) está explicitamente true — default é false, então por
// padrão o site continua exatamente como antes (só a Isis 1 legada).
//
// A flag:
//  - nunca é lida de query string;
//  - nunca é lida/gravada em localStorage/sessionStorage;
//  - vem de um único arquivo estático público (site-config.js), sem
//    segredo nenhum — só um booleano de apresentação;
//  - é determinística: mesmo valor em todo carregamento da página,
//    não muda em runtime por ação do usuário.
//
// Convivência com a Isis 1 (isis-guided.js): quando a flag está ligada
// e a Isis 2.0 monta com sucesso (catálogo disponível), a conversa da
// Isis 1 embutida na seção #isis é escondida em runtime — via
// JavaScript, não CSS estático — e substituída por uma chamada para o
// widget flutuante. Se a Isis 2.0 falhar ao montar por qualquer motivo
// (catálogo não carregou, erro de script), a Isis 1 permanece visível e
// funcional: é sempre o fallback, nunca é removida do DOM.
(() => {
  if (window.__MISTICA_ISIS2__) return;
  window.__MISTICA_ISIS2__ = true;

  function enabled() {
    return window.misticaSiteConfig?.isis2?.enabled === true;
  }

  function deactivateLegacyChat() {
    const panel = document.querySelector(".isis-chat-panel");
    if (!panel || panel.dataset.isis2Deactivated) return;
    const chat = panel.querySelector("#isisChat");
    const form = panel.querySelector("#isisForm");
    const quickActions = panel.querySelector(".quick-actions");
    if (!chat && !form) return;
    panel.dataset.isis2Deactivated = "true";
    [chat, form, quickActions].forEach(el => {
      if (el) el.hidden = true;
    });
    const notice = document.createElement("div");
    notice.className = "isis2-legacy-notice";
    notice.innerHTML = `
      <p>Agora você fala com a Isis pelo assistente no canto da tela.</p>
      <button type="button" class="btn" id="isis2-open-from-legacy">Abrir conversa com a Isis</button>
    `;
    panel.appendChild(notice);
    const openButton = notice.querySelector("#isis2-open-from-legacy");
    openButton?.addEventListener("click", () => window.Isis2.Widget.open());
  }

  function mount() {
    if (!enabled()) return;
    if (!window.Isis2 || !window.Isis2.Widget) return;
    const mounted = window.Isis2.Widget.mount();
    if (mounted) deactivateLegacyChat();
  }

  function schedule() {
    mount();
    // O catálogo (products/getStock) chega via mobile-sync.js de forma
    // assíncrona; remonta algumas vezes como isis-guided.js já faz, sem
    // custo (mount() é idempotente e só desativa a Isis 1 na primeira
    // vez que realmente monta com sucesso).
    window.setTimeout(mount, 250);
    window.setTimeout(mount, 900);
    window.setTimeout(mount, 1600);
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", schedule, { once: true });
  else schedule();
})();
