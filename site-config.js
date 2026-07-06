window.misticaSiteConfig = {
  domain: "misticaesotericos.com.br",
  publicBaseUrl: "https://misticaesotericos.com.br",
  apiBaseUrl: "https://api.misticaesotericos.com.br",
  siteApiKey: "c4e9012d72c6bb42f52457c6d6ba916a",
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

  const loadScript = (id, src) => {
    if (document.getElementById(id)) return;
    const script = document.createElement("script");
    script.id = id;
    script.src = src;
    script.defer = true;
    document.head.appendChild(script);
  };

  const loadGuard = () => {
    loadScript("misticaWriteKeyGuardScript", "site-write-key-guard.js?v=20260706-write-key");
    loadScript("misticaProductionGuardScript", "site-production-guard.js?v=20260706-api-guard");
  };

  if (document.readyState === "loading") {
    window.addEventListener("DOMContentLoaded", loadGuard, { once: true });
  } else {
    loadGuard();
  }
})();
