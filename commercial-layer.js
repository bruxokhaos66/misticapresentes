(() => {
  if (window.__MISTICA_COMMERCIAL_LAYER_LOADED__) return;
  window.__MISTICA_COMMERCIAL_LAYER_LOADED__ = true;

  function restoreHero() {
    const hero = document.querySelector("#inicio.hero-section");
    if (!hero) return;
    hero.classList.add("legacy-premium-hero");
    const title = hero.querySelector(".hero-copy h1");
    if (title) title.textContent = "Presentes místicos fáceis de escolher, comprar e enviar pelo WhatsApp";
    const text = hero.querySelector(".hero-text");
    if (text) text.textContent = "Cristais, incensos, velas, aromas, banhos de ervas e presentes com significado para proteção, energia, beleza e bem-estar.";
    const visual = hero.querySelector(".hero-visual");
    if (visual && !visual.querySelector(".legacy-isis-card")) {
      visual.replaceChildren();
      const card = document.createElement("div");
      card.className = "legacy-isis-card";
      const orb = document.createElement("div");
      orb.className = "legacy-isis-orb";
      const symbol = document.createElement("div");
      symbol.className = "legacy-isis-symbol";
      symbol.textContent = "☾";
      const caption = document.createElement("div");
      caption.className = "legacy-isis-caption";
      const strong = document.createElement("strong");
      strong.textContent = "Curadoria Mística";
      const span = document.createElement("span");
      span.textContent = "Produtos escolhidos para intenção, beleza, proteção e presentes com significado.";
      caption.append(strong, span);
      card.append(orb, symbol, caption);
      visual.appendChild(card);
    }
  }

  function init() {
    document.body.classList.add("mistica-home-premium");
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
    restoreHero();
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init, { once: true });
  else init();
})();
