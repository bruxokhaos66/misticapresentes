window.misticaSiteConfig = {
  domain: "www.misticaesotericos.com.br",
  publicBaseUrl: "https://www.misticaesotericos.com.br",
  apiBaseUrl: "https://api.misticaesotericos.com.br",
  serverMode: "production",
  usePublicDomainAccess: true,
  storageMode: "api_first",
  instagram: "@misticaprodutos",
  whatsappNumber: "554999172137",
  whatsappDisplay: "(49) 99917-2137",
  headerTitle: "Mística Presentes",
  headerSubtitle: "Xamanismo • Cristais • Aromas",
  promoText: "Transforme sua energia. Eleve sua essência."
};

(() => {
  const cfg = window.misticaSiteConfig || {};
  const productionMode = cfg.serverMode === "production" || cfg.storageMode === "api_first" || cfg.usePublicDomainAccess === true;
  if (!productionMode) return;

  if (!window.__misticaSyncIntervalGuardInstalled) {
    window.__misticaSyncIntervalGuardInstalled = true;
    const originalSetInterval = window.setInterval.bind(window);
    window.setInterval = (handler, timeout, ...args) => {
      const handlerName = typeof handler === "function" ? handler.name : "";
      const looksLikeMobileSync = typeof handler === "function" && Number(timeout) === 5000 && handlerName === "sincronizarAgora";
      if (!looksLikeMobileSync) return originalSetInterval(handler, timeout, ...args);

      const guardedHandler = (...runArgs) => {
        if (document.hidden) return;
        return handler(...runArgs);
      };
      return originalSetInterval(guardedHandler, 15000, ...args);
    };
  }

  const loadGuard = () => {
    if (document.getElementById("misticaProductionGuardScript")) return;
    const script = document.createElement("script");
    script.id = "misticaProductionGuardScript";
    script.src = "site-production-guard.js?v=20260710-no-browser-secret";
    script.defer = true;
    document.head.appendChild(script);
  };

  if (document.readyState === "loading") {
    window.addEventListener("DOMContentLoaded", loadGuard, { once: true });
  } else {
    loadGuard();
  }
})();
