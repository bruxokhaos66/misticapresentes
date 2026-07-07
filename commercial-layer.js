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

  function restoreProductsIntent() {
    const section = document.querySelector("#produtos.products-section");
    if (!section) return;
    section.classList.add("legacy-products-intent");
    const eyebrow = section.querySelector(".section-title .eyebrow");
    if (eyebrow) eyebrow.textContent = "Escolha por intenção";
    const title = section.querySelector(".section-title h2");
    if (title) title.textContent = "Escolha produtos por intenção, presente e energia";
    const text = section.querySelector(".section-title p:not(.eyebrow)");
    if (text) text.textContent = "Encontre rapidamente produtos para proteção, limpeza energética, aromas, fé, decoração e presentes especiais.";
    const grid = section.querySelector("[data-product-grid]");
    if (!grid || section.querySelector(".intent-legacy-strip")) return;
    const strip = document.createElement("div");
    strip.className = "container intent-legacy-strip";
    const items = [["🌿", "Limpeza e proteção", "Incensos, banhos de ervas e itens para renovar a energia do ambiente."], ["💎", "Presentes com significado", "Cristais, kits e lembranças para surpreender com propósito."], ["🕯️", "Fé e intenção", "Velas, artigos de oração e produtos para momentos especiais."], ["✨", "Casa perfumada", "Aromas, essências e Via Aroma para deixar o lar mais acolhedor."]];
    items.forEach(([icon, name, desc]) => {
      const card = document.createElement("article");
      card.className = "intent-legacy-card";
      const span = document.createElement("span"); span.textContent = icon;
      const strong = document.createElement("strong"); strong.textContent = name;
      const small = document.createElement("small"); small.textContent = desc;
      card.append(span, strong, small);
      strip.appendChild(card);
    });
    section.insertBefore(strip, grid);
  }

  function restoreIsisCommerce() {
    const section = document.querySelector("#isis.isis-section");
    if (!section) return;
    section.classList.add("legacy-isis-commerce");
    const panelText = section.querySelector(".isis-panel-image p");
    if (panelText) panelText.textContent = "A Isis guia o cliente por produtos, intenções, presentes e sugestões rápidas para facilitar a compra.";
    const eyebrow = section.querySelector(".isis-chat-panel .eyebrow");
    if (eyebrow) eyebrow.textContent = "Isis a Bruxinha";
    const title = section.querySelector(".isis-chat-panel h2");
    if (title) title.textContent = "Atendimento místico, comercial e inteligente";
    const note = section.querySelector(".isis-chat-panel .privacy-note");
    if (note) note.textContent = "Peça sugestões de produtos, kits para presente, itens por intenção ou apoio para encontrar o que combina com cada momento.";
    const chatPanel = section.querySelector(".isis-chat-panel");
    if (!chatPanel || chatPanel.querySelector(".legacy-isis-cards")) return;
    const cards = document.createElement("div");
    cards.className = "legacy-isis-cards";
    const items = [["🔮", "Produtos combinados", "Sugestões de kits com incensos, cristais, velas, banhos e aromas."], ["🎁", "Presentes humanos", "Ideias com significado para datas especiais, carinho e proteção."], ["⚡", "Atendimento rápido", "Comandos prontos para encontrar produtos e enviar o pedido pelo WhatsApp."], ["📈", "Apoio nas vendas", "Ajuda para consultar vendas, estoque baixo e oportunidades de reposição."]];
    items.forEach(([icon, name, desc]) => {
      const card = document.createElement("article");
      card.className = "legacy-isis-card";
      const span = document.createElement("span"); span.textContent = icon;
      const strong = document.createElement("strong"); strong.textContent = name;
      const small = document.createElement("small"); small.textContent = desc;
      card.append(span, strong, small);
      cards.appendChild(card);
    });
    const form = chatPanel.querySelector("#isisForm");
    if (form) chatPanel.insertBefore(cards, form);
    else chatPanel.appendChild(cards);
  }

  function restoreContactFooter() {
    const contact = document.querySelector("#contato.contact-section");
    if (contact) {
      contact.classList.add("legacy-contact-premium");
      const title = contact.querySelector("h2");
      if (title) title.textContent = "Atendimento próximo, rápido e com significado";
      const desc = contact.querySelector(".split > div:first-child p:not(.eyebrow)");
      if (desc) desc.textContent = "Fale com a Mística Presentes pelo WhatsApp para escolher produtos, montar kits e tirar dúvidas antes da compra.";
      const first = contact.querySelector(".split > div:first-child");
      if (first && !first.querySelector(".legacy-contact-highlights")) {
        const highlights = document.createElement("div");
        highlights.className = "legacy-contact-highlights";
        [["Compra guiada", "Ajudamos você a escolher por intenção."], ["Retirada local", "Atendimento em Pinhalzinho-SC."], ["WhatsApp rápido", "Pedido direto e humanizado."]].forEach(([a, b]) => {
          const item = document.createElement("span");
          const strong = document.createElement("strong"); strong.textContent = a;
          const small = document.createElement("small"); small.textContent = b;
          item.append(strong, small);
          highlights.appendChild(item);
        });
        first.appendChild(highlights);
      }
      const card = contact.querySelector(".contact-card");
      if (card) card.classList.add("legacy-contact-card");
    }

    const footer = document.querySelector(".footer");
    if (footer) {
      footer.classList.add("legacy-footer-premium");
      const grid = footer.querySelector(".footer-grid");
      if (grid && !grid.querySelector(".footer-trust-line")) {
        const trust = document.createElement("div");
        trust.className = "footer-trust-line";
        ["Cristais", "Incensos", "Velas", "Aromas", "Presentes com significado", "Pinhalzinho-SC"].forEach(text => {
          const span = document.createElement("span");
          span.textContent = text;
          trust.appendChild(span);
        });
        grid.appendChild(trust);
      }
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
    restoreProductsIntent();
    restoreIsisCommerce();
    restoreContactFooter();
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init, { once: true });
  else init();
})();
