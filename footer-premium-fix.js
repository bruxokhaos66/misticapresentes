(() => {
  const styleId = "mistica-footer-premium-style";

  function installFooterStyle() {
    if (document.getElementById(styleId)) return;

    const style = document.createElement("style");
    style.id = styleId;
    style.textContent = `
      .footer {
        position: relative;
        overflow: hidden;
        padding: clamp(42px, 6vw, 74px) 0 36px;
        border-top: 1px solid rgba(240,197,106,.28);
        background:
          radial-gradient(circle at 14% 18%, rgba(240,197,106,.14), transparent 28rem),
          radial-gradient(circle at 84% 8%, rgba(184,201,119,.12), transparent 24rem),
          linear-gradient(180deg, rgba(8,7,13,.92), rgba(3,3,5,.98));
        box-shadow: inset 0 1px 0 rgba(255,248,230,.06);
      }

      .footer::before {
        content: "";
        position: absolute;
        inset: 0;
        pointer-events: none;
        background:
          linear-gradient(90deg, transparent, rgba(240,197,106,.10), transparent),
          radial-gradient(circle at 50% 0, rgba(240,197,106,.12), transparent 34rem);
        opacity: .82;
      }

      .footer::after {
        content: "☾";
        position: absolute;
        right: clamp(18px, 6vw, 92px);
        bottom: -34px;
        color: rgba(240,197,106,.07);
        font-family: Cinzel, Georgia, serif;
        font-size: clamp(8rem, 18vw, 18rem);
        line-height: 1;
        pointer-events: none;
      }

      .footer-grid {
        position: relative;
        z-index: 1;
        gap: clamp(18px, 3vw, 32px);
      }

      .footer-grid > div {
        min-height: 100%;
        border: 1px solid rgba(240,197,106,.18);
        border-radius: 28px;
        padding: clamp(20px, 3vw, 30px);
        background:
          linear-gradient(145deg, rgba(255,248,230,.07), rgba(83,107,55,.055)),
          rgba(3,3,5,.24);
        box-shadow: 0 22px 70px rgba(0,0,0,.22);
        backdrop-filter: blur(10px);
      }

      .footer-grid > div:first-child {
        border-color: rgba(240,197,106,.30);
        background:
          radial-gradient(circle at 18% 10%, rgba(240,197,106,.16), transparent 34%),
          linear-gradient(145deg, rgba(255,248,230,.09), rgba(54,32,68,.12));
      }

      .footer-mark {
        margin-bottom: 16px;
        box-shadow: 0 0 0 7px rgba(240,197,106,.055), 0 18px 42px rgba(0,0,0,.32);
      }

      .footer strong {
        margin-bottom: 9px;
        font-size: clamp(1.18rem, 2vw, 1.56rem);
        letter-spacing: .08em;
        text-transform: uppercase;
      }

      .footer h3 {
        margin-bottom: 12px;
        font-family: Cinzel, Georgia, serif;
        letter-spacing: .08em;
        text-transform: uppercase;
      }

      .footer p {
        margin-bottom: 9px;
        color: #e5d8bf;
        font-weight: 650;
      }

      .footer a,
      .footer p:last-child {
        color: #b8c977;
      }

      .footer-premium-signature {
        position: relative;
        z-index: 1;
        width: min(1180px, calc(100% - 32px));
        margin: 22px auto 0;
        display: flex;
        flex-wrap: wrap;
        gap: 10px 16px;
        align-items: center;
        justify-content: space-between;
        border: 1px solid rgba(240,197,106,.16);
        border-radius: 999px;
        padding: 12px 16px;
        background: rgba(255,248,230,.045);
        color: #d8cbb6;
        font-size: .82rem;
        font-weight: 800;
      }

      .footer-premium-signature span:first-child {
        color: #f0c56a;
        letter-spacing: .08em;
        text-transform: uppercase;
      }

      @media (max-width: 680px) {
        .footer {
          padding-bottom: 86px;
        }

        .footer-grid > div {
          border-radius: 24px;
        }

        .footer-premium-signature {
          border-radius: 24px;
          align-items: flex-start;
          justify-content: flex-start;
        }
      }
    `;

    document.head.appendChild(style);
  }

  function enhanceFooter() {
    const footer = document.querySelector(".footer");
    if (!footer || footer.dataset.premiumFooter === "true") return;

    footer.dataset.premiumFooter = "true";

    const signature = document.createElement("div");
    signature.className = "footer-premium-signature";
    signature.innerHTML = `
      <span>Mística Presentes</span>
      <span>Produtos com significado • Atendimento local • Compra pelo WhatsApp</span>
    `;
    footer.appendChild(signature);
  }

  function loadScriptOnce(id, src) {
    if (document.getElementById(id)) return;
    const script = document.createElement("script");
    script.id = id;
    script.defer = true;
    script.src = src;
    document.head.appendChild(script);
  }

  function loadCatalogPremiumFix() { loadScriptOnce("catalogPremiumFixScript", "catalog-premium-fix.js?v=20260706-catalogo-premium"); }
  function loadAmbientPremiumFix() { loadScriptOnce("ambientPremiumFixScript", "ambient-premium-fix.js?v=20260706-ambient-premium"); }
  function loadCommercialBadgesFix() { loadScriptOnce("commercialBadgesFixScript", "commercial-badges-fix.js?v=20260706-commercial-badges"); }
  function loadAlsoBoughtFix() { loadScriptOnce("alsoBoughtFixScript", "also-bought-fix.js?v=20260706-also-bought"); }
  function loadCartCtaFix() { loadScriptOnce("cartCtaFixScript", "cart-cta-fix.js?v=20260706-cart-cta"); }
  function loadIsisRecommendationsFix() { loadScriptOnce("isisRecommendationsFixScript", "isis-recommendations-fix.js?v=20260706-isis-recommendations"); }
  function loadAdminDashboardPremiumFix() { loadScriptOnce("adminDashboardPremiumFixScript", "admin-dashboard-premium-fix.js?v=20260706-admin-dashboard"); }
  function loadPerformanceImagesFix() { loadScriptOnce("performanceImagesFixScript", "performance-images-fix.js?v=20260706-performance-images"); }
  function loadPerformanceSectionsFix() { loadScriptOnce("performanceSectionsFixScript", "performance-sections-fix.js?v=20260706-performance-sections"); }
  function loadAccessibilityStatusFix() { loadScriptOnce("accessibilityStatusFixScript", "accessibility-status-fix.js?v=20260706-accessibility-status"); }
  function loadAmbientPlaylistAdmin() { loadScriptOnce("ambientPlaylistAdminScript", "ambient-playlist-admin.js?v=20260706-playlist-ambiente-v3"); }
  function loadAmbientPlayerUnify() { loadScriptOnce("ambientPlayerUnifyScript", "ambient-player-unify.js?v=20260706-fallback"); }
  function loadAdminAmbientMusic() { loadScriptOnce("adminAmbientMusicScript", "admin-ambient-music.js?v=20260706-audio-timeout"); }
  function loadSinglePlayerGuard() { loadScriptOnce("ambientSinglePlayerGuardScript", "ambient-single-player-guard.js?v=20260706-single-player"); }
  function loadSaleApiFirstFix() { loadScriptOnce("misticaSaleApiFirstScript", "mobile-sale-api-first.js?v=20260706-api-first-sale"); }

  function applyFooterPremiumFix() {
    installFooterStyle();
    enhanceFooter();
    loadCatalogPremiumFix();
    loadAmbientPremiumFix();
    loadCommercialBadgesFix();
    loadAlsoBoughtFix();
    loadCartCtaFix();
    loadIsisRecommendationsFix();
    loadAdminDashboardPremiumFix();
    loadPerformanceImagesFix();
    loadPerformanceSectionsFix();
    loadAccessibilityStatusFix();
    loadAmbientPlaylistAdmin();
    loadAmbientPlayerUnify();
    loadAdminAmbientMusic();
    loadSinglePlayerGuard();
    loadSaleApiFirstFix();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", applyFooterPremiumFix, { once: true });
  } else {
    applyFooterPremiumFix();
  }

  window.addEventListener("load", () => {
    applyFooterPremiumFix();
    setTimeout(applyFooterPremiumFix, 600);
  });
})();
