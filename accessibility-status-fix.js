(() => {
  function setLiveRegion(el, politeness = "polite") {
    if (!el || el.dataset.accessibilityLiveRegion === "true") return;
    el.setAttribute("role", el.getAttribute("role") || "status");
    el.setAttribute("aria-live", politeness);
    el.setAttribute("aria-atomic", "true");
    el.dataset.accessibilityLiveRegion = "true";
  }

  function improveButtonLabels() {
    const whatsappButtons = document.querySelectorAll('[data-send-sale-whatsapp], [data-whatsapp-link]');
    whatsappButtons.forEach(button => {
      if (!button.getAttribute("aria-label")) {
        button.setAttribute("aria-label", "Enviar pedido ou chamar atendimento pelo WhatsApp da Mística Presentes");
      }
    });

    const pixButton = document.querySelector('[data-generate-pix]');
    if (pixButton && !pixButton.getAttribute("aria-label")) {
      pixButton.setAttribute("aria-label", "Gerar QR Code Pix para o pedido atual");
    }

    const copyPixButton = document.querySelector('[data-copy-pix]');
    if (copyPixButton && !copyPixButton.getAttribute("aria-label")) {
      copyPixButton.setAttribute("aria-label", "Copiar código Pix copia e cola");
    }
  }

  function apply() {
    setLiveRegion(document.getElementById("pixStatus"), "polite");
    setLiveRegion(document.getElementById("adminLoginStatus"), "assertive");
    setLiveRegion(document.getElementById("clientSaved"), "polite");
    setLiveRegion(document.getElementById("backupStatus"), "polite");
    setLiveRegion(document.getElementById("cartTotal"), "polite");
    improveButtonLabels();
  }

  function installObserver() {
    if (!document.body || document.body.dataset.accessibilityStatusObserver === "true") return;
    document.body.dataset.accessibilityStatusObserver = "true";

    new MutationObserver(() => requestAnimationFrame(apply)).observe(document.body, {
      childList: true,
      subtree: true,
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", () => {
      apply();
      installObserver();
    }, { once: true });
  } else {
    apply();
    installObserver();
  }

  window.addEventListener("load", () => {
    apply();
    setTimeout(apply, 900);
  });

  window.misticaAccessibilityStatus = { apply };
})();
