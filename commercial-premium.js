(() => {
  const cfg = window.misticaSiteConfig || {};
  const whatsapp = cfg.whatsappNumber || "554999172137";
  const whatsappMsg = "Olá, vim pelo site da Mística Presentes e gostaria de atendimento.";
  const whatsUrl = `https://wa.me/${whatsapp}?text=${encodeURIComponent(whatsappMsg)}`;

  function el(tag, className, html) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (html !== undefined) node.innerHTML = html;
    return node;
  }

  function updateCopy() {
    const title = document.querySelector(".hero-copy h1");
    if (title) title.textContent = "Presentes místicos que encantam, protegem e transformam ambientes";

    const text = document.querySelector(".hero-text");
    if (text) text.textContent = "Cristais, incensos, velas, aromas, banhos e kits especiais para quem busca beleza, significado e boas energias em cada detalhe.";

    const eyebrow = document.querySelector(".hero-copy .eyebrow");
    if (eyebrow) eyebrow.textContent = "Mística Presentes • Curadoria espiritual em Pinhalzinho-SC";

    const productsTitle = document.querySelector("#produtos .section-title h2");
    if (productsTitle) productsTitle.textContent = "Escolha por energia, intenção ou presente";

    const productsText = document.querySelector("#produtos .section-title p:last-child");
    if (productsText) productsText.textContent = "Produtos organizados para facilitar a compra: escolha, coloque no carrinho e finalize pelo WhatsApp.";
  }

  function mountHeroSellingBar() {
    const hero = document.querySelector(".hero-copy");
    if (!hero || document.querySelector(".premium-hero-selling-bar")) return;
    const bar = el("div", "premium-hero-selling-bar", `
      <span><strong>Retirada local</strong> Pinhalzinho-SC</span>
      <span><strong>Pedido rápido</strong> pelo WhatsApp</span>
      <span><strong>Curadoria</strong> produtos com intenção</span>
    `);
    const actions = hero.querySelector(".hero-actions");
    if (actions) actions.after(bar);
    else hero.appendChild(bar);
  }

  function mountIntentSection() {
    if (document.getElementById("comprar-por-intencao")) return;
    const categories = document.getElementById("categorias");
    if (!categories) return;

    const section = el("section", "section intent-section", `
      <div class="container section-title centered">
        <p class="eyebrow">Comprar por intenção</p>
        <h2>Encontre o produto certo para cada momento</h2>
        <p>Uma vitrine pensada para o cliente escolher rápido, pelo significado e pela energia que procura.</p>
      </div>
      <div class="container intent-grid">
        <a href="#produtos" data-intent-query="proteção"><span>🛡️</span><strong>Proteção</strong><small>cristais, velas e incensos</small></a>
        <a href="#produtos" data-intent-query="limpeza"><span>🌿</span><strong>Limpeza energética</strong><small>banhos, ervas e defumações</small></a>
        <a href="#produtos" data-intent-query="presente"><span>🎁</span><strong>Presentes</strong><small>kits bonitos e simbólicos</small></a>
        <a href="#produtos" data-intent-query="relaxamento"><span>✨</span><strong>Relaxamento</strong><small>aromas e bem-estar</small></a>
      </div>
    `);
    section.id = "comprar-por-intencao";
    categories.parentNode.insertBefore(section, categories.nextSibling);
  }

  function mountCampaignBand() {
    if (document.querySelector(".premium-campaign-band")) return;
    const products = document.getElementById("produtos");
    if (!products) return;
    const band = el("section", "premium-campaign-band", `
      <div class="container campaign-card">
        <div>
          <p class="eyebrow">Atendimento personalizado</p>
          <h2>Não sabe o que escolher?</h2>
          <p>A Isis e a equipe ajudam a montar kits por intenção: proteção, limpeza, prosperidade, amor, relaxamento ou presente.</p>
        </div>
        <div class="campaign-actions">
          <a class="btn" href="#isis">Pedir sugestão da Isis</a>
          <a class="btn btn-ghost" href="${whatsUrl}" target="_blank" rel="noopener">Falar no WhatsApp</a>
        </div>
      </div>
    `);
    products.parentNode.insertBefore(band, products);
  }

  function improveProductCards() {
    document.querySelectorAll(".product-card").forEach((card, index) => {
      if (card.dataset.premiumReady === "true") return;
      card.dataset.premiumReady = "true";
      const badges = ["Mais pedido", "Energia especial", "Ótimo presente", "Boa escolha"];
      const badge = el("span", "premium-product-badge", badges[index % badges.length]);
      card.prepend(badge);
      const price = card.querySelector(".product-price");
      if (price && !card.querySelector(".premium-product-note")) {
        price.insertAdjacentHTML("afterend", `<small class="premium-product-note">Finalize pelo WhatsApp e confirme disponibilidade.</small>`);
      }
    });
  }

  function improveCheckout() {
    const checkout = document.getElementById("checkout");
    if (!checkout || checkout.dataset.premiumReady === "true") return;
    checkout.dataset.premiumReady = "true";
    const title = checkout.querySelector(".form-panel h2");
    if (title) title.textContent = "Seu pedido místico";
    const pixTitle = checkout.querySelector(".pix-panel h2");
    if (pixTitle) pixTitle.textContent = "Pagamento Pix";
  }

  function mountTrustFooter() {
    if (document.querySelector(".premium-trust-footer")) return;
    const contact = document.getElementById("contato");
    if (!contact) return;
    const section = el("section", "section premium-trust-footer", `
      <div class="container trust-footer-grid">
        <article><strong>Compra simples</strong><span>Você escolhe no site e finaliza no WhatsApp.</span></article>
        <article><strong>Pagamento conferido</strong><span>Confira recebedor e valor antes do Pix.</span></article>
        <article><strong>Atendimento local</strong><span>Retirada e entrega combinadas diretamente com a loja.</span></article>
      </div>
    `);
    contact.parentNode.insertBefore(section, contact);
  }

  function fixLinksAndA11y() {
    document.querySelectorAll("[data-whatsapp-link], .floating-whatsapp").forEach(link => {
      link.href = whatsUrl;
      link.target = "_blank";
      link.rel = "noopener";
      if (!link.getAttribute("aria-label")) link.setAttribute("aria-label", "Chamar a Mística Presentes no WhatsApp");
    });

    const menu = document.querySelector("[data-menu-toggle]");
    const nav = document.querySelector("[data-nav-links]");
    if (menu && nav) {
      if (!nav.id) nav.id = "menu-principal";
      menu.setAttribute("aria-controls", nav.id);
      menu.setAttribute("aria-expanded", String(nav.classList.contains("open") || nav.classList.contains("is-open")));
    }
  }

  function bindIntentActions() {
    document.addEventListener("click", event => {
      const link = event.target.closest("[data-intent-query]");
      if (!link) return;
      const query = link.dataset.intentQuery;
      setTimeout(() => {
        const isisInput = document.getElementById("isisInput");
        const isisForm = document.getElementById("isisForm");
        if (isisInput && isisForm && typeof window.misticaIsisCommerce?.ask === "function") {
          window.misticaIsisCommerce.ask(`quero produtos para ${query}`);
        }
      }, 350);
    });
  }

  function apply() {
    updateCopy();
    mountHeroSellingBar();
    mountIntentSection();
    mountCampaignBand();
    improveProductCards();
    improveCheckout();
    mountTrustFooter();
    fixLinksAndA11y();
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", apply, { once: true });
  else apply();

  window.addEventListener("load", () => {
    apply();
    setTimeout(apply, 800);
    setTimeout(improveProductCards, 2200);
  });

  bindIntentActions();
})();
