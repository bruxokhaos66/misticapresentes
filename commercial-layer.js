document.addEventListener("DOMContentLoaded", () => {
  const cfg = window.misticaSiteConfig || {};

  const whatsapp = cfg.whatsappNumber || "554999172137";
  const whatsappDisplay = cfg.whatsappDisplay || "(49) 99917-2137";
  const instagram = cfg.instagram || "@misticaprodutos";
  const domain = cfg.domain || "misticaesotericos.com.br";
  const params = new URLSearchParams(window.location.search);
  const adminAccess = params.get("admin") === "mistica" || window.location.hash === "#admin-mistica";
  const assetVersion = "20260706-etapa2-card-system";
  const logoAsset = `assets/logo-mistica-modern.svg?v=${assetVersion}`;
  const finalSectionPath = "isis-humana-xamanica-03-produtos.png";
  const finalSectionSrc = `assets/${finalSectionPath}?v=${assetVersion}`;
  const heroIsisPath = "isis-humana-xamanica-02-publicitaria.png";
  const heroIsisSources = [
    `assets/${heroIsisPath}?v=${assetVersion}`,
    `./assets/${heroIsisPath}?v=${assetVersion}`,
    `/assets/${heroIsisPath}?v=${assetVersion}`,
    `assets/isis-humana-xamanica-02-publicitaria.webp?v=${assetVersion}`
  ];
  const sectionIsisSources = [
    finalSectionSrc,
    `./assets/${finalSectionPath}?v=${assetVersion}`,
    `/assets/${finalSectionPath}?v=${assetVersion}`
  ];
  const heroIsisAsset = heroIsisSources[0];
  const sectionIsisAsset = sectionIsisSources[0];

  function installIsisHardLockStyle() {
    if (document.getElementById("isis-png-hardlock-style")) return;
    const style = document.createElement("style");
    style.id = "isis-png-hardlock-style";
    style.textContent = `
      .isis-panel-image .isis-symbol { display: none !important; }
      .isis-panel-image img:not([src*="${finalSectionPath}"]) {
        opacity: 0 !important;
        visibility: hidden !important;
        position: absolute !important;
        pointer-events: none !important;
      }
      .isis-panel-image img[src*="${finalSectionPath}"],
      .isis-panel-image .isis-human-produtos {
        opacity: 1 !important;
        visibility: visible !important;
        display: block !important;
      }
    `;
    document.head.appendChild(style);
  }

  function lockAssistantIsisPanel() {
    installIsisHardLockStyle();
    const panel = document.querySelector(".isis-panel-image");
    if (!panel) return;

    panel.dataset.isisProductsPanel = "true";
    panel.classList.remove("asset-failed");

    let img = panel.querySelector(`img[src*="${finalSectionPath}"]`) || panel.querySelector("img.isis-human-produtos") || panel.querySelector("img");
    if (!img) {
      img = document.createElement("img");
      panel.prepend(img);
    }

    img.className = "isis-human-img isis-human-produtos";
    img.alt = "Isis da Mística Presentes apresentando produtos xamânicos";
    img.width = 720;
    img.height = 900;
    img.loading = "eager";
    img.decoding = "async";

    if (!img.getAttribute("src") || !img.src.includes(finalSectionPath)) {
      img.src = sectionIsisAsset;
    }

    let text = panel.querySelector("p");
    if (!text) {
      text = document.createElement("p");
      panel.appendChild(text);
    }
    text.textContent = "Isis apresenta produtos xamânicos, aromas, banhos, velas e presentes com orientação clara para a escolha do cliente.";
  }

  document.querySelectorAll('link[rel~="icon"]').forEach(link => link.remove());
  const favicon = document.createElement("link");
  favicon.rel = "icon";
  favicon.type = "image/svg+xml";
  favicon.href = logoAsset;
  document.head.appendChild(favicon);

  function loadScriptOnce(id, src) {
    if (document.getElementById(id)) return;
    const script = document.createElement("script");
    script.id = id;
    script.src = `${src}?v=${assetVersion}`;
    script.defer = true;
    document.head.appendChild(script);
  }

  loadScriptOnce("modernIconFixScript", "modern-icon-fix.js");
  loadScriptOnce("seoSiteScript", "seo-site.js");
  loadScriptOnce("adminAccessScript", "admin-access.js");
  loadScriptOnce("productExtrasScript", "product-extras.js");
  loadScriptOnce("pedidoStatusScript", "pedido-status.js");
  loadScriptOnce("adminAlertsScript", "admin-alerts.js");
  loadScriptOnce("adminActivityScript", "admin-activity.js");
  loadScriptOnce("painelAuthScript", "painel-auth.js");
  loadScriptOnce("siteReadinessScript", "site-readiness.js");
  loadScriptOnce("isisCommerceScript", "isis-commerce.js");
  loadScriptOnce("isisCommandsScript", "isis-commands.js");
  loadScriptOnce("isisSectionProductsLockFinalScript", "isis-section-products-fix.js");
  loadScriptOnce("commercialPremiumScript", "commercial-premium.js");
  loadScriptOnce("ambientExperienceScript", "ambient-experience.js");
  loadScriptOnce("wideLayoutFixScript", "layout-wide-fix.js");
  loadScriptOnce("heroIsisPositionFixScript", "hero-isis-position-fix.js");
  loadScriptOnce("cardSystemFixScript", "card-system-fix.js");

  const adminPanel = document.getElementById("admin");
  if (adminPanel) {
    adminPanel.hidden = !adminAccess;
    if (adminAccess) setTimeout(() => adminPanel.scrollIntoView({ behavior: "smooth" }), 250);
  }
  document.querySelectorAll(".internal-section").forEach(section => { section.hidden = true; });

  function injectImage(target, src, alt, className, fallbackText) {
    if (!target) return;
    const img = document.createElement("img");
    img.src = src;
    img.alt = alt;
    img.className = className;
    img.loading = "lazy";
    img.decoding = "async";
    img.onerror = () => {
      target.classList.add("asset-failed");
      target.innerHTML = fallbackText;
    };
    target.replaceChildren(img);
  }

  document.querySelectorAll(".brand-mark").forEach(mark => {
    injectImage(mark, logoAsset, "Logo Mística Presentes", "brand-logo-img brand-logo-modern", "<span>☾</span>");
  });

  const heroCard = document.querySelector(".mystic-logo-card");
  if (heroCard) {
    heroCard.classList.add("hero-card-isis", "hero-card-isis-publicitaria");
    heroCard.innerHTML = `<img class="hero-isis-img hero-isis-publicitaria" src="${heroIsisAsset}" alt="Isis da Mística Presentes em destaque publicitário" width="720" height="900" loading="eager" decoding="async"><strong>Isis</strong><small>Guia de presentes, proteção e boas energias</small>`;
    const heroIsis = heroCard.querySelector("img");
    let heroAttempt = 0;
    heroIsis.onload = () => {
      heroCard.classList.remove("asset-failed");
    };
    heroIsis.onerror = () => {
      heroAttempt += 1;
      if (heroIsisSources[heroAttempt]) {
        heroIsis.src = heroIsisSources[heroAttempt];
        return;
      }
      heroCard.classList.add("asset-failed");
      heroCard.innerHTML = `<span class="sigil" aria-hidden="true">☾</span><strong>Mística Presentes</strong><small>Proteção • Energia • Bem-estar</small>`;
    };
  }

  lockAssistantIsisPanel();
  setTimeout(lockAssistantIsisPanel, 100);
  setTimeout(lockAssistantIsisPanel, 700);
  setTimeout(lockAssistantIsisPanel, 1600);
  setTimeout(lockAssistantIsisPanel, 3200);

  const lockedPanel = document.querySelector(".isis-panel-image");
  if (lockedPanel && lockedPanel.dataset.hardLockObserver !== "true") {
    lockedPanel.dataset.hardLockObserver = "true";
    const observer = new MutationObserver(() => {
      const current = lockedPanel.querySelector("img");
      if (!current || !current.src.includes(finalSectionPath)) {
        requestAnimationFrame(lockAssistantIsisPanel);
      }
    });
    observer.observe(lockedPanel, { childList: true, subtree: true, attributes: true, attributeFilter: ["src", "class"] });
  }

  document.querySelectorAll("[data-whatsapp-link]").forEach(link => {
    link.href = `https://wa.me/${whatsapp}?text=${encodeURIComponent("Olá, vim pelo site da Mística Presentes e gostaria de atendimento.")}`;
    if (!link.dataset.keepText) link.textContent = "Chamar no WhatsApp";
  });

  const heroTitle = document.querySelector(".hero-copy h1");
  if (heroTitle) heroTitle.textContent = "Presentes místicos fáceis de escolher, comprar e enviar pelo WhatsApp";

  const heroText = document.querySelector(".hero-text");
  if (heroText) heroText.textContent = "Cristais, incensos, velas, aromas, banhos e kits especiais organizados para o cliente entender rápido, escolher com segurança e finalizar o pedido em poucos cliques.";

  const heroEyebrow = document.querySelector(".hero-copy .eyebrow");
  if (heroEyebrow) heroEyebrow.textContent = "Mística Presentes • Atendimento espiritual e comercial em Pinhalzinho-SC";

  const trustItems = document.querySelectorAll(".trust-row span");
  const trustTexts = [
    "<strong>Escolha simples</strong> produtos separados por intenção, presente e energia.",
    "<strong>Pix e WhatsApp</strong> carrinho claro, QR Code e envio do pedido em poucos cliques.",
    "<strong>Atendimento local</strong> dúvidas respondidas antes da retirada ou entrega combinada."
  ];
  trustItems.forEach((item, index) => {
    if (trustTexts[index]) item.innerHTML = trustTexts[index];
  });

  const categoryTitle = document.querySelector("#categorias .section-title h2");
  if (categoryTitle) categoryTitle.textContent = "Categorias claras para o cliente encontrar rápido";

  const categoryText = document.querySelector("#categorias .section-title p:last-child");
  if (categoryText) categoryText.textContent = "A vitrine destaca os grupos mais procurados e ajuda o cliente a comprar sem confusão.";

  const productTitle = document.querySelector("#produtos .section-title h2");
  if (productTitle) productTitle.textContent = "Produtos organizados por intenção e presente";

  const productText = document.querySelector("#produtos .section-title p:last-child");
  if (productText) productText.textContent = "Adicione ao carrinho, confira o total, gere Pix e envie o pedido pelo WhatsApp da loja.";

  const checkoutTitle = document.querySelector("#checkout .form-panel h2");
  if (checkoutTitle) checkoutTitle.textContent = "Carrinho claro para finalizar o pedido";

  const isisTitle = document.querySelector(".isis-chat-panel h2");
  if (isisTitle) isisTitle.textContent = "Isis ajuda o cliente a escolher";

  const isisNote = document.querySelector(".isis-chat-panel .privacy-note");
  if (isisNote) isisNote.textContent = "Assistente preparada para orientar presentes, produtos xamânicos, aromas, estoque e sugestões de compra de forma simples.";

  const footerContact = document.querySelector(".footer-grid div:nth-child(2)");
  if (footerContact) {
    footerContact.innerHTML = `<h3>Contato</h3><p>WhatsApp: ${whatsappDisplay}</p><p>Instagram: ${instagram}</p><p>Site: ${domain}</p>`;
  }

  const footerPublish = document.querySelector(".footer-grid div:nth-child(3)");
  if (footerPublish) {
    footerPublish.innerHTML = `<h3>Experiência</h3><p>Visual xamânico premium, textos mais claros e opção de música ambiente ativada pelo visitante.</p><p>${domain}</p>`;
  }
});
