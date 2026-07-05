document.addEventListener("DOMContentLoaded", () => {
  const cfg = window.misticaSiteConfig || {};

  const whatsapp = cfg.whatsappNumber || "554999172137";
  const whatsappDisplay = cfg.whatsappDisplay || "(49) 99917-2137";
  const instagram = cfg.instagram || "@misticaprodutos";
  const domain = cfg.domain || "misticaesotericos.com.br";
  const params = new URLSearchParams(window.location.search);
  const adminAccess = params.get("admin") === "mistica" || window.location.hash === "#admin-mistica";
  const assetVersion = "20260705-isis-reload";
  const logoAsset = `assets/logo-mistica-final.webp?v=${assetVersion}`;
  const isisSources = [
    `assets/isis-humana-xamanica.webp?v=${assetVersion}`,
    `assets/isis-humana-premium.webp?v=${assetVersion}`,
    `assets/isis-xamanica-nova.webp?v=${assetVersion}`,
    `assets/isis-premium.png?v=${assetVersion}`
  ];
  const isisAsset = isisSources[0];

  document.querySelectorAll('link[rel~="icon"]').forEach(link => link.remove());
  const favicon = document.createElement("link");
  favicon.rel = "icon";
  favicon.type = "image/webp";
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

  loadScriptOnce("seoSiteScript", "seo-site.js");
  loadScriptOnce("adminAccessScript", "admin-access.js");
  loadScriptOnce("productExtrasScript", "product-extras.js");
  loadScriptOnce("pedidoStatusScript", "pedido-status.js");
  loadScriptOnce("adminAlertsScript", "admin-alerts.js");
  loadScriptOnce("adminActivityScript", "admin-activity.js");
  loadScriptOnce("isisCommerceScript", "isis-commerce.js");
  loadScriptOnce("isisCommandsScript", "isis-commands.js");

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
    injectImage(mark, logoAsset, "Logo Mística Presentes", "brand-logo-img", "<span>☾</span>");
  });

  const heroCard = document.querySelector(".mystic-logo-card");
  if (heroCard) {
    heroCard.innerHTML = `<img class="hero-logo-img" src="${logoAsset}" alt="Logo Mística Presentes" width="320" height="320" loading="eager" decoding="async"><strong>Mística Presentes</strong><small>Proteção • Energia • Bem-estar</small>`;
    const heroLogo = heroCard.querySelector("img");
    heroLogo.onerror = () => {
      heroCard.innerHTML = `<span class="sigil" aria-hidden="true">☾</span><strong>Mística Presentes</strong><small>Proteção • Energia • Bem-estar</small>`;
    };
  }

  const isisPanel = document.querySelector(".isis-panel-image");
  if (isisPanel) {
    isisPanel.innerHTML = `<img class="isis-human-img" src="${isisAsset}" alt="Isis da Mística Presentes" width="720" height="900" loading="lazy" decoding="async"><p>Isis, presença misteriosa e xamânica para guiar escolhas e atendimento da loja.</p>`;
    const isisImg = isisPanel.querySelector("img");
    let isisAttempt = 0;
    isisImg.onerror = () => {
      isisAttempt += 1;
      if (isisSources[isisAttempt]) {
        isisImg.src = isisSources[isisAttempt];
        return;
      }
      isisPanel.classList.add("asset-failed");
      isisPanel.innerHTML = `<div class="isis-symbol" aria-hidden="true">ISIS</div><p>Isis, presença misteriosa e xamânica para guiar escolhas e atendimento da loja.</p>`;
    };
  }

  document.querySelectorAll("[data-whatsapp-link]").forEach(link => {
    link.href = `https://wa.me/${whatsapp}?text=${encodeURIComponent("Olá, vim pelo site da Mística Presentes e gostaria de atendimento.")}`;
    if (!link.dataset.keepText) link.textContent = "Chamar no WhatsApp";
  });

  const heroTitle = document.querySelector(".hero-copy h1");
  if (heroTitle) heroTitle.textContent = "Produtos místicos para proteção, energia e bem-estar";

  const heroText = document.querySelector(".hero-text");
  if (heroText) heroText.textContent = "Cristais, incensos, velas, aromas e presentes com significado para transformar ambientes, rituais e momentos especiais.";

  const heroEyebrow = document.querySelector(".hero-copy .eyebrow");
  if (heroEyebrow) heroEyebrow.textContent = "Mística Presentes • Pinhalzinho-SC";

  const productTitle = document.querySelector("#produtos .section-title h2");
  if (productTitle) productTitle.textContent = "Produtos em destaque";

  const productText = document.querySelector("#produtos .section-title p:last-child");
  if (productText) productText.textContent = "Escolha seus artigos favoritos, adicione ao carrinho e envie o pedido pelo WhatsApp.";

  const footerContact = document.querySelector(".footer-grid div:nth-child(2)");
  if (footerContact) {
    footerContact.innerHTML = `<h3>Contato</h3><p>WhatsApp: ${whatsappDisplay}</p><p>Instagram: ${instagram}</p><p>Site: ${domain}</p>`;
  }

  const footerPublish = document.querySelector(".footer-grid div:nth-child(3)");
  if (footerPublish) {
    footerPublish.innerHTML = `<h3>Divulgação</h3><p>Produtos para espiritualidade, bem-estar, proteção e energias positivas.</p><p>${domain}</p>`;
  }
});
