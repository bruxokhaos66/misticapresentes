(() => {
  if (window.__MISTICA_FOOTER_PREMIUM_FIX_LOADED__) return;
  window.__MISTICA_FOOTER_PREMIUM_FIX_LOADED__ = true;

  function loadScriptOnce(id, src) {
    if (document.getElementById(id)) return;
    const script = document.createElement("script");
    script.id = id;
    script.defer = true;
    script.src = src;
    document.head.appendChild(script);
  }

  function loadStyleOnce(id, href) {
    if (document.getElementById(id)) return;
    const link = document.createElement("link");
    link.id = id;
    link.rel = "stylesheet";
    link.href = href;
    document.head.appendChild(link);
  }

  function cleanIsisImagePanel() {
    const panel = document.querySelector("#isis .isis-panel-image");
    if (!panel) return;
    panel.querySelectorAll(".isis-symbol").forEach(symbol => {
      symbol.setAttribute("aria-hidden", "true");
      symbol.hidden = true;
      symbol.style.setProperty("display", "none", "important");
      symbol.style.setProperty("visibility", "hidden", "important");
      symbol.style.setProperty("opacity", "0", "important");
    });
    panel.dataset.imageCleaned = "true";
  }

  function init() {
    const contact = document.querySelector("#contato");
    if (contact) contact.dataset.singleContact = "true";
    const footer = document.querySelector(".footer");
    if (footer) footer.dataset.singleStoreFooter = "true";

    loadStyleOnce("isisLowerImageStyle", "isis-lower-image.css?v=20260707-isis-lower-image");
    loadStyleOnce("isisLowerImageFixStyle", "isis-lower-image-fix.css?v=20260707-isis-fix-v2");
    loadStyleOnce("restoreVideoLayoutStyle", "restore-video-layout.css?v=20260707-layout-video-antigo");
    cleanIsisImagePanel();
    window.setTimeout(cleanIsisImagePanel, 150);
    window.setTimeout(cleanIsisImagePanel, 600);

    loadScriptOnce("publicHomeSafetyScript", "public-home-safety.js?v=20260707-public-safe");
    loadScriptOnce("commercialBadgesFixScript", "commercial-badges-fix.js?v=20260707-safe-badges");
    loadScriptOnce("ambientExperienceScript", "ambient-experience.js?v=20260707-safe-ambient");
    loadScriptOnce("ambientPlayerUnifyScript", "ambient-player-unify.js?v=20260707-safe-player");
    loadScriptOnce("ambientPlayerClickFixScript", "ambient-player-click-fix.js?v=20260707-click-bridge");
    loadScriptOnce("restoreVideoLayoutScript", "restore-video-layout.js?v=20260707-layout-video-antigo");

    const params = new URLSearchParams(window.location.search);
    const adminMode = params.get("admin") === "mistica" || window.location.hash === "#admin-mistica";
    if (adminMode) loadScriptOnce("adminApiLoginFixScript", "admin-api-login-fix.js?v=20260707-api-login");
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init, { once: true });
  else init();
})();