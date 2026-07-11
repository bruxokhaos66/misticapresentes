(() => {
  const cfg = window.misticaSiteConfig || {};
  const gaId = String(cfg.gaMeasurementId || "").trim();
  const pixelId = String(cfg.metaPixelId || "").trim();
  let iniciado = false;

  function loadScript(src) {
    const script = document.createElement("script");
    script.async = true;
    script.src = src;
    document.head.appendChild(script);
  }

  function iniciarAnalytics() {
    if (iniciado) return;
    iniciado = true;

    if (gaId) {
      window.dataLayer = window.dataLayer || [];
      window.gtag = function gtag() { window.dataLayer.push(arguments); };
      window.gtag("js", new Date());
      window.gtag("config", gaId, { anonymize_ip: true });
      loadScript(`https://www.googletagmanager.com/gtag/js?id=${encodeURIComponent(gaId)}`);
    }

    if (pixelId) {
      window.fbq = window.fbq || function fbq() {
        (window.fbq.queue = window.fbq.queue || []).push(arguments);
      };
      window.fbq.loaded = true;
      window.fbq("init", pixelId);
      window.fbq("track", "PageView");
      loadScript("https://connect.facebook.net/en_US/fbevents.js");
    }
  }

  const FB_EVENT_MAP = {
    view_item: "ViewContent",
    add_to_cart: "AddToCart",
    begin_checkout: "InitiateCheckout",
    contact_whatsapp: "Contact",
  };

  window.misticaTrack = function misticaTrack(name, params) {
    if (!iniciado) return;
    const data = params || {};
    try {
      if (window.gtag) window.gtag("event", name, data);
    } catch {}
    try {
      if (window.fbq) {
        const fbEvent = FB_EVENT_MAP[name];
        if (fbEvent) window.fbq("track", fbEvent, data);
        else window.fbq("trackCustom", name, data);
      }
    } catch {}
  };

  // Analytics só carrega depois de consentimento explícito (LGPD): ver
  // consent.js, que grava a escolha em localStorage e dispara o evento
  // abaixo assim que o usuário decide no banner de cookies.
  const consentApi = window.misticaConsent;
  if (consentApi && consentApi.granted()) {
    iniciarAnalytics();
  } else {
    document.addEventListener("mistica:consent-changed", (evento) => {
      if (evento.detail && evento.detail.status === "granted") iniciarAnalytics();
    });
  }
})();
