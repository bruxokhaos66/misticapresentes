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

  function init() {
    const contact = document.querySelector("#contato");
    if (contact) contact.dataset.singleContact = "true";
    const footer = document.querySelector(".footer");
    if (footer) footer.dataset.singleStoreFooter = "true";

    loadScriptOnce("commercialBadgesFixScript", "commercial-badges-fix.js?v=20260707-safe-badges");
    loadScriptOnce("ambientExperienceScript", "ambient-experience.js?v=20260707-safe-ambient");
    loadScriptOnce("ambientPlayerUnifyScript", "ambient-player-unify.js?v=20260707-safe-player");
    loadScriptOnce("ambientPlayerClickFixScript", "ambient-player-click-fix.js?v=20260707-click-bridge");

    const params = new URLSearchParams(window.location.search);
    const adminMode = params.get("admin") === "mistica" || window.location.hash === "#admin-mistica";
    if (adminMode) loadScriptOnce("adminApiLoginFixScript", "admin-api-login-fix.js?v=20260707-api-login");
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init, { once: true });
  else init();
})();
