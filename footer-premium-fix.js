(() => {
  const styleId = "mistica-footer-premium-style";

  function installFooterStyle() {
    if (document.getElementById(styleId)) return;
    const style = document.createElement("style");
    style.id = styleId;
    style.textContent = `
      .contact-section { position: relative; overflow: hidden; border-top: 1px solid rgba(240,197,106,.18); border-bottom: 1px solid rgba(240,197,106,.16); background: radial-gradient(circle at 12% 18%, rgba(240,197,106,.14), transparent 30rem), radial-gradient(circle at 84% 78%, rgba(184,201,119,.12), transparent 28rem), linear-gradient(180deg, rgba(8,7,13,.94), rgba(3,3,5,.98)); }
      .contact-section .split { align-items: stretch; gap: clamp(18px, 3vw, 34px); }
      .contact-section .split > div:first-child, .contact-section .contact-card { border: 1px solid rgba(240,197,106,.24); border-radius: clamp(24px, 3vw, 36px); padding: clamp(24px, 4vw, 42px); background: radial-gradient(circle at 18% 12%, rgba(240,197,106,.14), transparent 34%), linear-gradient(145deg, rgba(255,248,230,.075), rgba(83,107,55,.075)), rgba(3,3,5,.32); box-shadow: 0 24px 80px rgba(0,0,0,.30); backdrop-filter: blur(10px); }
      .contact-section .contact-card { display: grid; gap: 14px; }
      .contact-section .contact-card p { margin: 0; padding: 12px 14px; border: 1px solid rgba(240,197,106,.16); border-radius: 18px; background: rgba(255,248,230,.045); color: #e5d8bf; font-weight: 750; }
      .contact-section .contact-card a { color: #b8c977; text-decoration: none; }
      .contact-section .contact-card a:hover { color: #f0c56a; }
      .contact-cta-row { display: flex; flex-wrap: wrap; gap: 10px; margin-top: 18px; }
      .footer { position: relative; overflow: hidden; padding: 28px 0 92px; border-top: 1px solid rgba(240,197,106,.20); background: radial-gradient(circle at 50% 0, rgba(240,197,106,.10), transparent 30rem), linear-gradient(180deg, rgba(8,7,13,.92), rgba(3,3,5,.98)); box-shadow: inset 0 1px 0 rgba(255,248,230,.06); }
      .footer::before { content: ""; position: absolute; inset: 0; pointer-events: none; background: linear-gradient(90deg, transparent, rgba(240,197,106,.08), transparent); opacity: .75; }
      .footer::after { content: "☾"; position: absolute; right: clamp(18px, 6vw, 92px); bottom: -34px; color: rgba(240,197,106,.07); font-family: Cinzel, Georgia, serif; font-size: clamp(8rem, 18vw, 18rem); line-height: 1; pointer-events: none; }
      .footer-grid { position: relative; z-index: 1; display: block; }
      .footer-grid > div:not(:first-child) { display: none !important; }
      .footer-grid > div:first-child { width: min(1180px, 100%); min-height: auto; border: 1px solid rgba(240,197,106,.22); border-radius: 999px; padding: 14px 18px; display: flex; flex-wrap: wrap; gap: 10px 16px; align-items: center; justify-content: space-between; background: rgba(255,248,230,.045); box-shadow: 0 18px 60px rgba(0,0,0,.20); backdrop-filter: blur(10px); }
      .footer-mark { margin: 0; box-shadow: 0 0 0 7px rgba(240,197,106,.055), 0 18px 42px rgba(0,0,0,.32); }
      .footer strong { color: #f0c56a; font-size: .88rem; letter-spacing: .10em; text-transform: uppercase; }
      .footer p { margin: 0; color: #e5d8bf; font-weight: 800; }
      .footer a { color: #b8c977; }
      .footer-premium-signature { display: none !important; }
      @media (max-width: 680px) { .footer { padding-bottom: 100px; } .footer-grid > div:first-child { border-radius: 24px; align-items: flex-start; justify-content: flex-start; } .contact-section .split > div:first-child, .contact-section .contact-card { border-radius: 24px; } }
    `;
    document.head.appendChild(style);
  }

  function enhanceContactSection() {
    const contact = document.querySelector("#contato");
    if (!contact || contact.dataset.singleContact === "true") return;
    contact.dataset.singleContact = "true";
    const intro = contact.querySelector(".split > div:first-child");
    const card = contact.querySelector(".contact-card");
    if (intro) {
      intro.innerHTML = `
        <p class="eyebrow">Contato oficial</p>
        <h2>Mística Presentes</h2>
        <p>Produtos místicos, presentes com significado e atendimento personalizado em Pinhalzinho-SC.</p>
        <div class="contact-cta-row">
          <a class="btn" href="https://wa.me/5549999172137?text=Ol%C3%A1%2C%20vim%20pelo%20site%20da%20M%C3%ADstica%20Presentes%20e%20gostaria%20de%20atendimento." target="_blank" rel="noopener">Chamar no WhatsApp</a>
          <a class="btn btn-ghost" href="#produtos">Ver produtos</a>
        </div>
      `;
    }
    if (card) {
      card.innerHTML = `
        <p><strong>Endereço:</strong> Galeria Ody - Av. Brasília, 2400 - Sala 07 - Centro, Pinhalzinho - SC</p>
        <p><strong>WhatsApp:</strong> <a href="https://wa.me/5549999172137" target="_blank" rel="noopener">(49) 99917-2137</a></p>
        <p><strong>Instagram:</strong> <a href="https://www.instagram.com/misticaprodutos" target="_blank" rel="noopener">@misticaprodutos</a></p>
        <p><strong>Site:</strong> <a href="https://misticaesotericos.com.br" target="_blank" rel="noopener">misticaesotericos.com.br</a></p>
      `;
    }
  }

  function enhanceFooter() {
    const footer = document.querySelector(".footer");
    if (!footer) return;
    const footerGrid = footer.querySelector(".footer-grid");
    if (footerGrid && footerGrid.dataset.singleStoreFooter !== "true") {
      footerGrid.dataset.singleStoreFooter = "true";
      footerGrid.innerHTML = `
        <div>
          <span class="brand-mark footer-mark" aria-hidden="true"><span>☾</span></span>
          <strong>Mística Presentes</strong>
          <p>Produtos com significado • Atendimento local • Compra pelo WhatsApp</p>
        </div>
      `;
    }
    footer.querySelectorAll(".footer-premium-signature").forEach(item => item.remove());
  }

  function loadScriptOnce(id, src) {
    if (document.getElementById(id)) return;
    const script = document.createElement("script");
    script.id = id;
    script.defer = true;
    script.src = src;
    document.head.appendChild(script);
  }

  function loadAdminApiLoginFix() { loadScriptOnce("adminApiLoginFixScript", "admin-api-login-fix.js?v=20260707-api-login"); }
  function loadCatalogPremiumFix() { loadScriptOnce("catalogPremiumFixScript", "catalog-premium-fix.js?v=20260706-catalogo-premium"); }
  function loadCommercialBadgesFix() { loadScriptOnce("commercialBadgesFixScript", "commercial-badges-fix.js?v=20260706-commercial-badges"); }
  function loadAlsoBoughtFix() { loadScriptOnce("alsoBoughtFixScript", "also-bought-fix.js?v=20260706-also-bought"); }
  function loadCartCtaFix() { loadScriptOnce("cartCtaFixScript", "cart-cta-fix.js?v=20260706-cart-cta"); }
  function loadIsisRecommendationsFix() { loadScriptOnce("isisRecommendationsFixScript", "isis-recommendations-fix.js?v=20260706-isis-recommendations"); }
  function loadAdminDashboardPremiumFix() { loadScriptOnce("adminDashboardPremiumFixScript", "admin-dashboard-premium-fix.js?v=20260706-admin-dashboard"); }
  function loadPerformanceImagesFix() { loadScriptOnce("performanceImagesFixScript", "performance-images-fix.js?v=20260706-performance-images"); }
  function loadPerformanceSectionsFix() { loadScriptOnce("performanceSectionsFixScript", "performance-sections-fix.js?v=20260706-performance-sections"); }
  function loadAccessibilityStatusFix() { loadScriptOnce("accessibilityStatusFixScript", "accessibility-status-fix.js?v=20260706-accessibility-status"); }
  function loadSaleApiFirstFix() { loadScriptOnce("misticaSaleApiFirstScript", "mobile-sale-api-first.js?v=20260706-api-first-sale"); }

  function applyFooterPremiumFix() {
    installFooterStyle();
    enhanceContactSection();
    enhanceFooter();
    loadAdminApiLoginFix();
    loadCatalogPremiumFix();
    loadCommercialBadgesFix();
    loadAlsoBoughtFix();
    loadCartCtaFix();
    loadIsisRecommendationsFix();
    loadAdminDashboardPremiumFix();
    loadPerformanceImagesFix();
    loadPerformanceSectionsFix();
    loadAccessibilityStatusFix();
    loadSaleApiFirstFix();
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", applyFooterPremiumFix, { once: true });
  else applyFooterPremiumFix();
  window.addEventListener("load", () => { applyFooterPremiumFix(); setTimeout(applyFooterPremiumFix, 600); });
})();