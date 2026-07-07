document.addEventListener("DOMContentLoaded", () => {
  const cfg = window.misticaSiteConfig || {};
  const version = "20260707-single-ambient-controller-v1";
  const adminAccess = new URLSearchParams(window.location.search).get("admin") === "mistica" || window.location.hash === "#admin-mistica";

  function loadScriptOnce(id, src) {
    if (document.getElementById(id)) return;
    const script = document.createElement("script");
    script.id = id;
    script.src = `${src}?v=${version}`;
    script.defer = true;
    document.head.appendChild(script);
  }

  function setText(selector, text) {
    const el = document.querySelector(selector);
    if (el) el.textContent = text;
  }

  function setHtml(selector, html) {
    const el = document.querySelector(selector);
    if (el) el.innerHTML = html;
  }

  function configureWhatsApp() {
    const whatsapp = cfg.whatsappNumber || "554999172137";
    document.querySelectorAll("[data-whatsapp-link]").forEach(link => {
      link.href = `https://wa.me/${whatsapp}?text=${encodeURIComponent("Olá, vim pelo site da Mística Presentes e gostaria de atendimento.")}`;
      if (!link.dataset.keepText) link.textContent = "Chamar no WhatsApp";
    });
  }

  function configureAdminVisibility() {
    const adminPanel = document.getElementById("admin");
    if (!adminPanel) return;
    adminPanel.hidden = !adminAccess;
    if (adminAccess) setTimeout(() => adminPanel.scrollIntoView({ behavior: "smooth" }), 250);
    document.querySelectorAll(".internal-section").forEach(section => { section.hidden = true; });
  }

  function applyCommercialText() {
    setText(".hero-copy h1", "Presentes místicos fáceis de escolher, comprar e enviar pelo WhatsApp");
    setText(".hero-text", "Cristais, incensos, velas, aromas, banhos e kits especiais organizados para o cliente entender rápido, escolher com segurança e finalizar o pedido em poucos cliques.");
    setText(".hero-copy .eyebrow", "Mística Presentes • Atendimento espiritual e comercial em Pinhalzinho-SC");
    setHtml(".trust-row span:nth-child(1)", "<strong>Escolha simples</strong> produtos separados por intenção, presente e energia.");
    setHtml(".trust-row span:nth-child(2)", "<strong>Pix e WhatsApp</strong> carrinho claro, QR Code e envio do pedido em poucos cliques.");
    setHtml(".trust-row span:nth-child(3)", "<strong>Atendimento local</strong> dúvidas respondidas antes da retirada ou entrega combinada.");
    setText("#categorias .section-title h2", "Categorias claras para o cliente encontrar rápido");
    setText("#categorias .section-title p:last-child", "A vitrine destaca os grupos mais procurados e ajuda o cliente a comprar sem confusão.");
    setText("#produtos .section-title h2", "Produtos organizados por intenção e presente");
    setText("#produtos .section-title p:last-child", "Adicione ao carrinho, confira o total, gere Pix e envie o pedido pelo WhatsApp da loja.");
    setText("#checkout .form-panel h2", "Carrinho claro para finalizar o pedido");
    setText(".isis-chat-panel h2", "Isis ajuda o cliente a escolher");
    setText(".isis-chat-panel .privacy-note", "Assistente preparada para orientar presentes, produtos xamânicos, aromas, estoque e sugestões de compra de forma simples.");
  }

  function applyLogoAndIsis() {
    const logoAsset = `assets/logo-mistica-modern.svg?v=${version}`;
    const heroAsset = `assets/isis-humana-xamanica-02-publicitaria.png?v=${version}`;
    const sectionAsset = `assets/isis-humana-xamanica-03-produtos.png?v=${version}`;

    document.querySelectorAll(".brand-mark").forEach(mark => {
      if (mark.dataset.logoApplied === "true") return;
      mark.dataset.logoApplied = "true";
      mark.innerHTML = `<img src="${logoAsset}" alt="Logo Mística Presentes" class="brand-logo-img brand-logo-modern" loading="eager" decoding="async">`;
    });

    const heroCard = document.querySelector(".mystic-logo-card");
    if (heroCard && heroCard.dataset.isisApplied !== "true") {
      heroCard.dataset.isisApplied = "true";
      heroCard.classList.add("hero-card-isis", "hero-card-isis-publicitaria");
      heroCard.innerHTML = `<img class="hero-isis-img hero-isis-publicitaria" src="${heroAsset}" alt="Isis da Mística Presentes" width="720" height="900" loading="eager" decoding="async"><strong>Isis</strong><small>Guia de presentes, proteção e boas energias</small>`;
    }

    const isisPanel = document.querySelector(".isis-panel-image");
    if (isisPanel && isisPanel.dataset.isisProductsPanel !== "true") {
      isisPanel.dataset.isisProductsPanel = "true";
      isisPanel.innerHTML = `<img class="isis-human-img isis-human-produtos" src="${sectionAsset}" alt="Isis da Mística Presentes apresentando produtos xamânicos" width="720" height="900" loading="lazy" decoding="async"><p>Isis apresenta produtos xamânicos, aromas, banhos, velas e presentes com orientação clara para a escolha do cliente.</p>`;
    }
  }

  configureWhatsApp();
  configureAdminVisibility();
  applyCommercialText();
  applyLogoAndIsis();

  loadScriptOnce("ambientExperienceScript", "ambient-experience.js");
  loadScriptOnce("ambientPlayerUnifyScript", "ambient-player-unify.js");
  loadScriptOnce("ambientStartOffGuardScript", "ambient-start-off-guard.js");
  loadScriptOnce("formFieldAccessibilityFixScript", "form-field-accessibility-fix.js");
  loadScriptOnce("layoutWideFixScript", "layout-wide-fix.js");
  loadScriptOnce("heroIsisPositionFixScript", "hero-isis-position-fix.js");
  loadScriptOnce("cardSystemFixScript", "card-system-fix.js");
  loadScriptOnce("sectionSpacingFixScript", "section-spacing-fix.js");
});