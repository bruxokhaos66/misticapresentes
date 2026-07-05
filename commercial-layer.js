document.addEventListener("DOMContentLoaded", () => {
  const cfg = window.misticaSiteConfig || {};

  const whatsapp = cfg.whatsappNumber || "554999172137";
  const whatsappDisplay = cfg.whatsappDisplay || "(49) 99917-2137";
  const instagram = cfg.instagram || "@misticaprodutos";
  const domain = cfg.domain || "misticaesotericos.com.br";
  const params = new URLSearchParams(window.location.search);
  const adminAccess = params.get("admin") === "mistica" || window.location.hash === "#admin-mistica";

  const adminPanel = document.getElementById("admin");
  if (adminPanel) {
    adminPanel.hidden = !adminAccess;
    if (adminAccess) setTimeout(() => adminPanel.scrollIntoView({ behavior: "smooth" }), 250);
  }
  document.querySelectorAll(".internal-section").forEach(section => { section.hidden = true; });

  if (!document.getElementById("seoSiteScript")) {
    const seo = document.createElement("script");
    seo.id = "seoSiteScript";
    seo.src = "seo-site.js?v=20260705-visual1";
    seo.defer = true;
    document.head.appendChild(seo);
  }

  if (!document.getElementById("adminAccessScript")) {
    const script = document.createElement("script");
    script.id = "adminAccessScript";
    script.src = "admin-access.js?v=20260705-visual1";
    script.defer = true;
    document.head.appendChild(script);
  }

  if (!document.getElementById("productExtrasScript")) {
    const extras = document.createElement("script");
    extras.id = "productExtrasScript";
    extras.src = "product-extras.js?v=20260705-visual1";
    extras.defer = true;
    document.head.appendChild(extras);
  }

  if (!document.getElementById("pedidoStatusScript")) {
    const pedidos = document.createElement("script");
    pedidos.id = "pedidoStatusScript";
    pedidos.src = "pedido-status.js?v=20260705-visual1";
    pedidos.defer = true;
    document.head.appendChild(pedidos);
  }

  if (!document.getElementById("adminAlertsScript")) {
    const alerts = document.createElement("script");
    alerts.id = "adminAlertsScript";
    alerts.src = "admin-alerts.js?v=20260705-visual1";
    alerts.defer = true;
    document.head.appendChild(alerts);
  }

  if (!document.getElementById("adminActivityScript")) {
    const activity = document.createElement("script");
    activity.id = "adminActivityScript";
    activity.src = "admin-activity.js?v=20260705-visual1";
    activity.defer = true;
    document.head.appendChild(activity);
  }

  if (!document.getElementById("isisCommerceScript")) {
    const isis = document.createElement("script");
    isis.id = "isisCommerceScript";
    isis.src = "isis-commerce.js?v=20260705-visual1";
    isis.defer = true;
    document.head.appendChild(isis);
  }

  if (!document.getElementById("isisCommandsScript")) {
    const isisCommands = document.createElement("script");
    isisCommands.id = "isisCommandsScript";
    isisCommands.src = "isis-commands.js?v=20260705-visual1";
    isisCommands.defer = true;
    document.head.appendChild(isisCommands);
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

  const isisPanelText = document.querySelector(".isis-panel-image p");
  if (isisPanelText) isisPanelText.textContent = "Imagem humana xamânica premium será aplicada quando o WebP final estiver aprovado.";

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
    footerPublish.innerHTML = `<h3>Divulgação</h3><p>Encontre produtos para espiritualidade, bem-estar, proteção e energias positivas.</p><p>${domain}</p>`;
  }
});
