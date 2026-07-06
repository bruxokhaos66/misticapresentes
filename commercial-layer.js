document.addEventListener("DOMContentLoaded", () => {
  const cfg = window.misticaSiteConfig || {};

  const whatsapp = cfg.whatsappNumber || "554999172137";
  const whatsappDisplay = cfg.whatsappDisplay || "(49) 99917-2137";
  const instagram = cfg.instagram || "@misticaprodutos";
  const domain = cfg.domain || "misticaesotericos.com.br";
  const params = new URLSearchParams(window.location.search);
  const adminAccess = params.get("admin") === "mistica" || window.location.hash === "#admin-mistica";
  const assetVersion = "20260706-commercial-premium";
  const logoAsset = `assets/logo-mistica-modern.svg?v=${assetVersion}`;
  const finalSectionPath = "isis-humana-xamanica-03-produtos.png";
  const finalSectionSrc = `assets/${finalSectionPath}?v=${assetVersion}`;
  const heroIsisSources = [
    `assets/isis-humana-xamanica-02-publicitaria.webp?v=${assetVersion}`,
    `./assets/isis-humana-xamanica-02-publicitaria.webp?v=${assetVersion}`,
    `/assets/isis-humana-xamanica-02-publicitaria.webp?v=${assetVersion}`,
    `assets/isis-humana-xamanica.webp?v=${assetVersion}`
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
    img.alt = "Isis da Mística Presentes apresentando produtos";
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
    text.textContent = "Isis, presença misteriosa e xamânica para guiar escolhas, produtos e atendimento da loja.";
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
    heroCard.innerHTML = `<img class="hero-isis-img hero-isis-publicitaria" src="${heroIsisAsset}" alt="Isis da Mística Presentes" width="720" height="900" loading="eager" decoding="async"><strong>Isis</strong><small>Sua guia espiritual para escolhas conscientes</small>`;
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
  if (heroTitle) heroTitle.textContent = "Presentes místicos que encantam, protegem e transformam ambientes";

  const heroText = document.querySelector(".hero-text");
  if (heroText) heroText.textContent = "Cristais, incensos, velas, aromas, banhos e kits especiais para quem busca beleza, significado e boas energias em cada detalhe.";

  const heroEyebrow = document.querySelector(".hero-copy .eyebrow");
  if (heroEyebrow) heroEyebrow.textContent = "Mística Presentes • Curadoria espiritual em Pinhalzinho-SC";

  const productTitle = document.querySelector("#produtos .section-title h2");
  if (productTitle) productTitle.textContent = "Escolha por energia, intenção ou presente";

  const productText = document.querySelector("#produtos .section-title p:last-child");
  if (productText) productText.textContent = "Produtos organizados para facilitar a compra: escolha, coloque no carrinho e finalize pelo WhatsApp.";

  const footerContact = document.querySelector(".footer-grid div:nth-child(2)");
  if (footerContact) {
    footerContact.innerHTML = `<h3>Contato</h3><p>WhatsApp: ${whatsappDisplay}</p><p>Instagram: ${instagram}</p><p>Site: ${domain}</p>`;
  }

  const footerPublish = document.querySelector(".footer-grid div:nth-child(3)");
  if (footerPublish) {
    footerPublish.innerHTML = `<h3>Divulgação</h3><p>Produtos para espiritualidade, bem-estar, proteção e energias positivas.</p><p>${domain}</p>`;
  }
});
