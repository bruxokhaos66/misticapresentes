// Isis 2.0 — bootstrap.
//
// Monta o widget flutuante após o catálogo estar pronto. Aditivo: não
// remove nem substitui o chat legado (#isisChat/#isisForm, controlado
// por isis-guided.js). Pode ser desligado por configuração
// (window.misticaSiteConfig.isis2.enabled === false) sem alterar o
// restante do site.
(() => {
  if (window.__MISTICA_ISIS2__) return;
  window.__MISTICA_ISIS2__ = true;

  function enabled() {
    return window.misticaSiteConfig?.isis2?.enabled !== false;
  }

  function mount() {
    if (!enabled()) return;
    if (!window.Isis2 || !window.Isis2.Widget) return;
    window.Isis2.Widget.mount();
  }

  function schedule() {
    mount();
    // O catálogo (products/getStock) chega via mobile-sync.js de forma
    // assíncrona; remonta algumas vezes como isis-guided.js já faz, sem
    // custo (mount() é idempotente).
    window.setTimeout(mount, 250);
    window.setTimeout(mount, 900);
    window.setTimeout(mount, 1600);
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", schedule, { once: true });
  else schedule();
})();
