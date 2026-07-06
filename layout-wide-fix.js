(() => {
  function injectWideLayoutFix() {
    if (document.getElementById("misticaWideLayoutFix")) return;

    const style = document.createElement("style");
    style.id = "misticaWideLayoutFix";
    style.textContent = `
      :root {
        --site-max-wide: 1560px;
        --site-side-space: clamp(20px, 4.8vw, 92px);
        --card-gap: clamp(14px, 1.4vw, 22px);
      }

      .container {
        width: min(var(--site-max-wide), calc(100% - (var(--site-side-space) * 2))) !important;
      }

      .top-ribbon-grid,
      .nav,
      .hero-grid {
        max-width: var(--site-max-wide);
      }

      .nav {
        min-height: 84px;
      }

      .hero-section {
        padding-top: clamp(36px, 4.2vw, 62px) !important;
        padding-bottom: clamp(34px, 4.4vw, 58px) !important;
      }

      .hero-grid {
        grid-template-columns: minmax(0, 1fr) minmax(360px, .78fr) !important;
        gap: clamp(30px, 5vw, 82px) !important;
        align-items: center !important;
      }

      .hero-copy {
        justify-self: start;
        width: 100%;
      }

      .hero-copy h1 {
        max-width: 760px !important;
        font-size: clamp(2.75rem, 3.9vw, 4.65rem) !important;
        line-height: 1.08 !important;
      }

      .hero-text {
        max-width: 720px !important;
        font-size: clamp(1.02rem, 1.04vw, 1.2rem) !important;
      }

      .hero-visual {
        justify-self: stretch;
        width: 100%;
        min-height: auto !important;
        height: auto !important;
        padding: clamp(18px, 2vw, 30px) !important;
        align-self: center !important;
      }

      .hero-visual::before,
      .visual-orbit,
      .floating-card {
        pointer-events: none;
      }

      .mystic-logo-card.hero-card-isis,
      .mystic-logo-card.hero-card-isis-publicitaria {
        width: min(100%, 430px) !important;
        min-height: auto !important;
        height: auto !important;
        padding: clamp(14px, 1.6vw, 22px) !important;
        align-self: center !important;
        justify-self: center !important;
        justify-content: end !important;
        gap: 8px !important;
      }

      .hero-isis-publicitaria {
        width: min(100%, 405px) !important;
        max-height: clamp(330px, 29vw, 455px) !important;
        object-fit: contain !important;
        margin: 0 auto 0 !important;
      }

      .mystic-logo-card.hero-card-isis strong {
        font-size: clamp(1.45rem, 2.1vw, 2.2rem) !important;
      }

      .mystic-logo-card.hero-card-isis small {
        max-width: 320px !important;
        font-size: .72rem !important;
        line-height: 1.35 !important;
      }

      .trust-row {
        max-width: 820px;
      }

      .trust-row span,
      .confidence-grid article,
      .category-grid article,
      .product-card,
      .form-panel,
      .metric-card,
      .contact-card,
      .client-item,
      .history-item,
      .stock-item,
      .cart-item {
        height: auto !important;
        min-height: 0 !important;
      }

      .category-grid,
      .confidence-grid,
      .product-grid,
      .checkout-grid,
      .split,
      .isis-layout,
      .dashboard-grid,
      .footer-grid {
        width: 100%;
        gap: var(--card-gap) !important;
        align-items: start !important;
      }

      .category-grid article {
        align-content: start !important;
        padding: clamp(16px, 1.45vw, 22px) !important;
      }

      .confidence-grid article,
      .trust-row span {
        padding: clamp(13px, 1.15vw, 18px) !important;
      }

      .product-card {
        align-content: start !important;
        padding: clamp(16px, 1.4vw, 22px) !important;
      }

      .product-image {
        min-height: clamp(96px, 8vw, 130px) !important;
      }

      .product-photo {
        aspect-ratio: 4 / 3 !important;
        max-height: 190px !important;
      }

      .isis-layout {
        grid-template-columns: minmax(320px, .72fr) minmax(0, 1fr) !important;
      }

      .isis-panel-image,
      .isis-panel-image:has(.isis-human-img) {
        min-height: auto !important;
        height: fit-content !important;
        align-self: start !important;
        padding: clamp(16px, 1.8vw, 26px) !important;
      }

      .isis-human-img,
      .isis-human-produtos {
        width: min(100%, 430px) !important;
        max-height: clamp(380px, 32vw, 540px) !important;
        object-fit: contain !important;
      }

      .isis-panel-image:has(.isis-human-img) p {
        position: relative !important;
        left: auto !important;
        right: auto !important;
        bottom: auto !important;
        margin-top: 12px !important;
        width: 100% !important;
      }

      .section-title.centered {
        max-width: 920px;
      }

      @media (min-width: 1600px) {
        .product-grid {
          grid-template-columns: repeat(4, minmax(0, 1fr)) !important;
        }

        .category-grid {
          grid-template-columns: repeat(6, minmax(0, 1fr)) !important;
        }
      }

      @media (max-width: 1280px) {
        :root {
          --site-side-space: clamp(18px, 3.5vw, 44px);
        }

        .hero-grid {
          grid-template-columns: minmax(0, 1fr) minmax(330px, .82fr) !important;
          gap: clamp(28px, 4vw, 56px) !important;
        }

        .hero-copy h1 {
          font-size: clamp(2.45rem, 4.2vw, 3.95rem) !important;
        }

        .hero-isis-publicitaria {
          max-height: 405px !important;
        }
      }

      @media (max-width: 980px) {
        .container {
          width: min(100% - 28px, 780px) !important;
        }

        .hero-grid,
        .isis-layout {
          grid-template-columns: 1fr !important;
        }

        .hero-copy {
          justify-self: center;
          text-align: center;
        }

        .hero-copy h1,
        .hero-text,
        .trust-row {
          margin-left: auto;
          margin-right: auto;
        }

        .hero-visual {
          max-width: 540px !important;
          margin: 0 auto !important;
        }

        .hero-isis-publicitaria {
          max-height: 400px !important;
        }

        .isis-panel-image {
          max-width: 540px !important;
          margin: 0 auto !important;
        }
      }

      @media (max-width: 680px) {
        .container {
          width: min(100% - 24px, 100%) !important;
        }

        .hero-copy h1 {
          font-size: clamp(2rem, 10.2vw, 3rem) !important;
        }

        .hero-visual {
          padding: 14px !important;
        }

        .mystic-logo-card.hero-card-isis,
        .mystic-logo-card.hero-card-isis-publicitaria {
          width: 100% !important;
          padding: 14px !important;
        }

        .hero-isis-publicitaria {
          max-height: 330px !important;
        }

        .isis-human-img,
        .isis-human-produtos {
          max-height: 420px !important;
        }
      }
    `;

    document.head.appendChild(style);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", injectWideLayoutFix);
  } else {
    injectWideLayoutFix();
  }
})();
