(() => {
  if (window.__MISTICA_COMMERCIAL_LAYER_LOADED__) return;
  window.__MISTICA_COMMERCIAL_LAYER_LOADED__ = true;

  function injectAuditStyles() {
    if (document.getElementById("mistica-audit-polish")) return;
    const style = document.createElement("style");
    style.id = "mistica-audit-polish";
    style.textContent = `
      :root {
        --audit-cream: #fff6dd;
        --audit-gold: #f0c56a;
        --audit-sage: #b8c977;
        --audit-moss: #516832;
        --audit-ink: #050509;
        --audit-glass: rgba(255, 246, 221, .075);
        --audit-border: rgba(240, 197, 106, .24);
      }

      body.mistica-home-premium {
        background:
          radial-gradient(circle at 12% 18%, rgba(81,104,50,.22), transparent 31rem),
          radial-gradient(circle at 78% 20%, rgba(240,197,106,.14), transparent 28rem),
          radial-gradient(circle at 82% 72%, rgba(64,38,78,.22), transparent 34rem),
          linear-gradient(135deg, #050509 0%, #0b0c09 46%, #120b18 100%);
      }

      body.mistica-home-premium::before {
        content: "";
        position: fixed;
        inset: 0;
        z-index: -1;
        pointer-events: none;
        opacity: .42;
        background-image:
          radial-gradient(circle, rgba(240,197,106,.45) 0 1px, transparent 1.4px),
          linear-gradient(120deg, transparent 0 43%, rgba(184,201,119,.04) 44%, transparent 45% 100%);
        background-size: 92px 92px, 100% 100%;
      }

      .top-ribbon {
        background: linear-gradient(90deg, rgba(3,3,5,.88), rgba(20,17,11,.86), rgba(3,3,5,.88)) !important;
      }

      .site-header {
        background: rgba(5,5,9,.78) !important;
        box-shadow: 0 18px 52px rgba(0,0,0,.22);
      }

      .brand-mark {
        box-shadow: 0 0 0 5px rgba(240,197,106,.06), 0 0 36px rgba(240,197,106,.16), 0 16px 38px rgba(0,0,0,.34) !important;
      }

      .nav-links a:not(.btn) {
        position: relative;
      }

      .nav-links a:not(.btn)::after {
        content: "";
        position: absolute;
        left: 14px;
        right: 14px;
        bottom: 6px;
        height: 1px;
        transform: scaleX(0);
        transform-origin: center;
        background: linear-gradient(90deg, transparent, var(--audit-gold), transparent);
        transition: transform .2s ease;
      }

      .nav-links a:not(.btn):hover::after {
        transform: scaleX(1);
      }

      #inicio.hero-section.legacy-premium-hero,
      body.mistica-home-premium #inicio.hero-section.legacy-premium-hero {
        min-height: clamp(620px, 78vh, 820px) !important;
        display: grid;
        align-items: center;
        padding: clamp(46px, 6.2vw, 82px) 0 !important;
      }

      #inicio .hero-grid,
      body.mistica-home-premium #inicio.legacy-premium-hero .hero-grid {
        grid-template-columns: minmax(0, .95fr) minmax(330px, .72fr) !important;
      }

      #inicio .hero-copy h1,
      body.mistica-home-premium #inicio.legacy-premium-hero .hero-copy h1 {
        max-width: 700px !important;
        font-size: clamp(2.45rem, 4.65vw, 4.55rem) !important;
        line-height: .98 !important;
        letter-spacing: -.035em !important;
      }

      #inicio .hero-text,
      body.mistica-home-premium #inicio.legacy-premium-hero .hero-text {
        max-width: 680px !important;
        font-weight: 700 !important;
      }

      #inicio .eyebrow,
      .section-title .eyebrow,
      .form-panel .eyebrow {
        width: fit-content;
        border: 1px solid rgba(184,201,119,.26);
        border-radius: 999px;
        padding: 8px 13px;
        background: rgba(184,201,119,.08);
        color: #d9ed92 !important;
      }

      .section-title.centered .eyebrow {
        margin-inline: auto;
      }

      #inicio .legacy-isis-card {
        transform: translateZ(0);
      }

      #inicio .legacy-isis-card::after {
        content: "";
        position: absolute;
        inset: 0;
        pointer-events: none;
        background:
          linear-gradient(180deg, rgba(255,255,255,.05), transparent 30%),
          radial-gradient(circle at 70% 18%, rgba(240,197,106,.18), transparent 22rem);
      }

      .trust-row span,
      .confidence-grid article,
      .category-grid article,
      .product-card,
      .form-panel,
      .contact-card {
        border-color: var(--audit-border) !important;
        background:
          linear-gradient(180deg, rgba(255,246,221,.09), rgba(255,246,221,.045)),
          rgba(5,5,9,.52) !important;
        backdrop-filter: blur(14px);
      }

      .category-grid article,
      .product-card {
        position: relative;
        overflow: hidden;
      }

      .category-grid article::before,
      .product-card::before {
        content: "";
        position: absolute;
        inset: 0;
        pointer-events: none;
        opacity: .75;
        background: radial-gradient(circle at 80% 0%, rgba(240,197,106,.13), transparent 14rem);
      }

      .category-grid article > *,
      .product-card > * {
        position: relative;
        z-index: 1;
      }

      .category-grid {
        grid-template-columns: repeat(auto-fit, minmax(170px, 1fr)) !important;
      }

      .category-grid article {
        min-height: 168px !important;
      }

      .confidence-grid article {
        min-height: 116px;
      }

      .intent-legacy-strip {
        margin-bottom: 22px !important;
      }

      .intent-legacy-card {
        min-height: 142px;
      }

      .product-grid {
        grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)) !important;
        align-items: stretch;
      }

      .product-card {
        display: flex !important;
        flex-direction: column;
        min-height: 100%;
        transition: transform .2s ease, border-color .2s ease, box-shadow .2s ease;
      }

      .product-card:hover,
      .category-grid article:hover {
        transform: translateY(-4px);
        border-color: rgba(240,197,106,.5) !important;
        box-shadow: 0 22px 70px rgba(0,0,0,.34), 0 0 32px rgba(240,197,106,.08);
      }

      .product-image,
      .product-photo {
        min-height: 150px !important;
        border: 1px solid rgba(240,197,106,.18);
        background:
          radial-gradient(circle at 50% 35%, rgba(240,197,106,.24), transparent 36%),
          radial-gradient(circle at 50% 70%, rgba(184,201,119,.18), transparent 48%),
          linear-gradient(145deg, rgba(11,13,9,.92), rgba(30,18,37,.72)) !important;
      }

      .product-photo {
        width: 100%;
        aspect-ratio: 4 / 3;
        object-fit: cover;
      }

      .product-card .qty-row,
      .product-card .btn-full {
        margin-top: auto;
      }

      .checkout-section,
      .isis-section,
      .contact-section {
        isolation: isolate;
      }

      .checkout-section::before,
      .isis-section::before,
      .contact-section::before {
        content: "";
        position: absolute;
        inset: 0;
        z-index: -1;
        pointer-events: none;
        background: radial-gradient(circle at 16% 26%, rgba(184,201,119,.08), transparent 26rem);
      }

      .isis-layout {
        align-items: center;
      }

      .isis-panel-image {
        min-height: 520px !important;
        background:
          linear-gradient(180deg, rgba(3,3,5,.04), rgba(3,3,5,.76)),
          radial-gradient(circle at 50% 20%, rgba(240,197,106,.22), transparent 24rem),
          linear-gradient(145deg, rgba(8,10,7,.96), rgba(45,27,55,.82)) !important;
      }

      .legacy-isis-cards {
        display: grid;
        grid-template-columns: repeat(2, minmax(0, 1fr));
        gap: 12px;
        margin: 18px 0;
      }

      .legacy-isis-card {
        border: 1px solid rgba(240,197,106,.2);
        border-radius: 18px;
        padding: 14px;
        background: rgba(255,255,255,.045);
      }

      .legacy-isis-card span {
        font-size: 1.35rem;
      }

      .legacy-isis-card strong {
        display: block;
        color: var(--audit-gold);
      }

      .legacy-isis-card small {
        color: #d8cbb6;
      }

      .legacy-contact-highlights {
        display: grid;
        grid-template-columns: repeat(3, minmax(0, 1fr));
        gap: 12px;
        margin-top: 20px;
      }

      .legacy-contact-highlights span,
      .footer-trust-line span {
        border: 1px solid rgba(240,197,106,.2);
        border-radius: 16px;
        padding: 12px;
        background: rgba(255,255,255,.045);
      }

      .legacy-contact-highlights strong,
      .legacy-contact-highlights small {
        display: block;
      }

      .legacy-contact-highlights strong {
        color: var(--audit-gold);
      }

      .legacy-contact-highlights small {
        color: #d8cbb6;
      }

      .footer-trust-line {
        grid-column: 1 / -1;
        display: flex;
        flex-wrap: wrap;
        gap: 10px;
        padding-top: 10px;
      }

      .footer-trust-line span {
        color: #efe1c5;
        font-size: .86rem;
        font-weight: 800;
      }

      .floating-whatsapp {
        background: linear-gradient(135deg, #dcf9b9, #9bc969) !important;
        box-shadow: 0 20px 60px rgba(0,0,0,.42), 0 0 32px rgba(184,201,119,.22) !important;
      }

      @media (max-width: 980px) {
        #inicio .hero-grid,
        body.mistica-home-premium #inicio.legacy-premium-hero .hero-grid {
          grid-template-columns: 1fr !important;
        }
        #inicio .hero-copy,
        body.mistica-home-premium #inicio.legacy-premium-hero .hero-copy {
          text-align: center !important;
        }
        #inicio .eyebrow {
          margin-inline: auto;
        }
        #inicio .legacy-isis-card {
          width: min(420px, 100%) !important;
          min-height: 540px !important;
          margin-inline: auto;
        }
      }

      @media (max-width: 680px) {
        #inicio.hero-section.legacy-premium-hero,
        body.mistica-home-premium #inicio.hero-section.legacy-premium-hero {
          min-height: auto !important;
          padding-top: 32px !important;
        }
        #inicio .hero-copy h1,
        body.mistica-home-premium #inicio.legacy-premium-hero .hero-copy h1 {
          font-size: clamp(2rem, 10.5vw, 3.05rem) !important;
        }
        .trust-row,
        .legacy-isis-cards,
        .legacy-contact-highlights {
          grid-template-columns: 1fr !important;
        }
        #inicio .legacy-isis-card {
          min-height: 430px !important;
          border-radius: 26px !important;
        }
        .product-grid {
          grid-template-columns: 1fr !important;
        }
      }
    `;
    document.head.appendChild(style);
  }

  function restoreHero() {
    const hero = document.querySelector("#inicio.hero-section");
    if (!hero) return;
    hero.classList.add("legacy-premium-hero");
    const eyebrow = hero.querySelector(".hero-copy .eyebrow");
    if (eyebrow) eyebrow.textContent = "Mística Presentes • curadoria espiritual e comercial em Pinhalzinho-SC";
    const title = hero.querySelector(".hero-copy h1");
    if (title) title.textContent = "Produtos místicos com energia, beleza e compra fácil pelo WhatsApp";
    const text = hero.querySelector(".hero-text");
    if (text) text.textContent = "Cristais, incensos, velas, aromas, banhos e kits especiais organizados para o cliente entender rápido, escolher com segurança e finalizar o pedido em poucos cliques.";
    const actions = hero.querySelector(".hero-actions");
    if (actions && !actions.querySelector('[data-scroll-categorias]')) {
      const link = document.createElement("a");
      link.className = "btn btn-ghost";
      link.href = "#categorias";
      link.dataset.scrollCategorias = "true";
      link.textContent = "Escolher por intenção";
      actions.appendChild(link);
    }
    const trustItems = hero.querySelectorAll(".trust-row span");
    if (trustItems.length >= 3) {
      trustItems[0].innerHTML = "<strong>Escolha guiada</strong> categorias por intenção, energia e presente.";
      trustItems[1].innerHTML = "<strong>WhatsApp direto</strong> pedido pronto para atendimento humano.";
      trustItems[2].innerHTML = "<strong>Pix facilitado</strong> QR Code e copia e cola preservados.";
    }
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
      span.textContent = "Produtos escolhidos para intenção, beleza e significado.";
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
    if (title) title.textContent = "Produtos organizados para vender melhor";
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
    injectAuditStyles();
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