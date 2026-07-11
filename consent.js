(() => {
  const STORAGE_KEY = "mistica_consent_analytics";

  function lerConsentimento() {
    try {
      return window.localStorage.getItem(STORAGE_KEY);
    } catch {
      return null;
    }
  }

  function salvarConsentimento(valor) {
    try {
      window.localStorage.setItem(STORAGE_KEY, valor);
    } catch {}
  }

  window.misticaConsent = {
    STORAGE_KEY,
    status() {
      return lerConsentimento();
    },
    granted() {
      return lerConsentimento() === "granted";
    },
    set(valor) {
      salvarConsentimento(valor);
      document.dispatchEvent(new CustomEvent("mistica:consent-changed", { detail: { status: valor } }));
    },
  };

  function montarBanner() {
    if (document.getElementById("consentBanner")) return;
    const banner = document.createElement("div");
    banner.id = "consentBanner";
    banner.className = "consent-banner";
    banner.setAttribute("role", "dialog");
    banner.setAttribute("aria-label", "Consentimento de cookies e analytics");
    banner.innerHTML = `
      <div class="consent-banner-copy">
        <strong>Usamos cookies para melhorar sua experiência.</strong>
        <span>Analytics nos ajuda a entender como o site é usado. Você pode aceitar ou recusar a qualquer momento. Veja nossa <a href="politica-de-privacidade.html">política de privacidade</a>.</span>
      </div>
      <div class="consent-banner-actions">
        <button type="button" class="btn btn-ghost" data-consent-decline>Recusar</button>
        <button type="button" class="btn" data-consent-accept>Aceitar</button>
      </div>`;
    document.body.appendChild(banner);
    banner.querySelector("[data-consent-accept]").addEventListener("click", () => {
      window.misticaConsent.set("granted");
      banner.remove();
    });
    banner.querySelector("[data-consent-decline]").addEventListener("click", () => {
      window.misticaConsent.set("denied");
      banner.remove();
    });
  }

  if (!lerConsentimento()) {
    if (document.readyState === "loading") {
      document.addEventListener("DOMContentLoaded", montarBanner);
    } else {
      montarBanner();
    }
  }
})();
