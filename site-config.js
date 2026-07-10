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

  const params = new URLSearchParams(window.location.search);
  const adminRoute = window.location.hash === "#admin" || window.location.hash === "#adminbruxo" || params.get("admin") === "mistica";

  // O app.js legado é carregado depois deste arquivo e tentava instalar um
  // submit local no mesmo formulário. Na rota administrativa, bloqueamos
  // somente esse primeiro listener legado antes que ele seja registrado.
  let restoreAdminListenerGuard = null;
  if (adminRoute && !window.__misticaAdminLegacySubmitGuardInstalled) {
    window.__misticaAdminLegacySubmitGuardInstalled = true;
    const originalAddEventListener = HTMLFormElement.prototype.addEventListener;
    let legacySubmitBlocked = false;

    HTMLFormElement.prototype.addEventListener = function(type, listener, options) {
      if (!legacySubmitBlocked && type === "submit" && this.id === "adminLoginForm") {
        legacySubmitBlocked = true;
        return;
      }
      return originalAddEventListener.call(this, type, listener, options);
    };

    restoreAdminListenerGuard = () => {
      HTMLFormElement.prototype.addEventListener = originalAddEventListener;
    };
  }

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

  const loadProductionScripts = () => {
    if (restoreAdminListenerGuard) restoreAdminListenerGuard();
    loadScript("misticaProductionGuardScript", "site-production-guard.js?v=20260710-no-browser-secret");
    if (adminRoute) {
      loadScript("misticaAdminApiBootstrapScript", "admin-api-login-bootstrap.js?v=20260710-admin-separated-final");
    }
  };

  if (document.readyState === "loading") {
    window.addEventListener("DOMContentLoaded", loadProductionScripts, { once: true });
  } else {
    loadProductionScripts();
  }
})();