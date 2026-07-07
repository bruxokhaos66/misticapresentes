(() => {
  const STORAGE_KEY = "misticaAmbientEnabled";
  let userClicked = false;

  function loadCss(id, href) {
    if (document.getElementById(id)) return;
    const link = document.createElement("link");
    link.id = id;
    link.rel = "stylesheet";
    link.href = href;
    document.head.appendChild(link);
  }

  function loadScript(id, src) {
    if (document.getElementById(id)) return;
    const script = document.createElement("script");
    script.id = id;
    script.defer = true;
    script.src = src;
    document.head.appendChild(script);
  }

  function loadVisualCss() {
    loadCss("homePremiumFinishCss", "home-premium-finish.css?v=20260707-final-premium");
    loadCss("mobilePolishCss", "mobile-polish.css?v=20260707-final-mobile");
    loadCss("heroLegacyPremiumCss", "hero-legacy-premium.css?v=20260707-hero-comercial-isis");
    loadCss("ambientLegacyCompleteCss", "ambient-legacy-complete.css?v=20260707-final-ambient");
    loadCss("productsIntentLegacyCss", "products-intent-legacy.css?v=20260707-final-products");
    loadCss("isisCommerceLegacyCss", "isis-commerce-legacy.css?v=20260707-final-isis");
    loadCss("footerContactLegacyCss", "footer-contact-legacy.css?v=20260707-final-footer");
    loadCss("heroAuthorityFinalCss", "hero-authority-final.css?v=20260707-authority-isis-final");
    loadCss("siteProportionalFinalCss", "site-proportional-final.css?v=20260707-site-proporcional-v2");
    loadScript("localBusinessSchemaScript", "local-business-schema.js?v=20260707-final-seo");
    loadScript("heroHardResetScript", "hero-hard-reset.js?v=20260707-layout-proporcional-final");
  }

  function pauseAllAmbientAudio() {
    document.querySelectorAll("audio").forEach(audio => {
      try { audio.pause(); } catch {}
    });
  }

  function forceOff() {
    if (userClicked) return;
    try { localStorage.removeItem(STORAGE_KEY); } catch {}
    pauseAllAmbientAudio();
    document.querySelectorAll("[data-ambient-toggle]").forEach(button => {
      button.setAttribute("aria-pressed", "false");
      button.textContent = "Ativar ambiente xamânico";
    });
    document.querySelectorAll("[data-ambient-status], [data-unified-status]").forEach(status => {
      status.textContent = "Aguardando ativação.";
    });
    document.querySelectorAll("[data-unified-player-panel]").forEach(panel => {
      panel.dataset.open = "false";
    });
  }

  document.addEventListener("click", event => {
    if (event.target?.closest?.("[data-ambient-toggle], [data-unified-next], [data-unified-volume]")) {
      userClicked = true;
    }
  }, true);

  loadVisualCss();
  forceOff();
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", () => { loadVisualCss(); forceOff(); }, { once: true });
  window.addEventListener("load", () => {
    loadVisualCss();
    forceOff();
    setTimeout(forceOff, 250);
    setTimeout(forceOff, 900);
    setTimeout(forceOff, 1800);
  });
})();