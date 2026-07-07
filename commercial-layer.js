(() => {
  if (window.__MISTICA_COMMERCIAL_LAYER_LOADED__) return;
  window.__MISTICA_COMMERCIAL_LAYER_LOADED__ = true;

  function init() {
    const params = new URLSearchParams(window.location.search);
    const adminAccess = params.get("admin") === "mistica" || window.location.hash === "#admin-mistica";
    const adminPanel = document.getElementById("admin");
    if (adminPanel) adminPanel.hidden = !adminAccess;
    document.querySelectorAll(".internal-section").forEach(section => { section.hidden = true; });

    const cfg = window.misticaSiteConfig || {};
    const whatsapp = cfg.whatsappNumber || "554999172137";
    document.querySelectorAll("[data-whatsapp-link]").forEach(link => {
      link.href = `https://wa.me/${whatsapp}?text=${encodeURIComponent("Olá, vim pelo site da Mística Presentes e gostaria de atendimento.")}`;
    });
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init, { once: true });
  else init();
})();
