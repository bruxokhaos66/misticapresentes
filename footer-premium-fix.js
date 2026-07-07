(() => {
  if (window.__MISTICA_FOOTER_PREMIUM_FIX_LOADED__) return;
  window.__MISTICA_FOOTER_PREMIUM_FIX_LOADED__ = true;

  function init() {
    const contact = document.querySelector("#contato");
    if (contact) contact.dataset.singleContact = "true";
    const footer = document.querySelector(".footer");
    if (footer) footer.dataset.singleStoreFooter = "true";
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init, { once: true });
  else init();
})();
