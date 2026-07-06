(() => {
  function injectWideLayoutFix() {
    if (document.getElementById("misticaWideLayoutFix")) return;

    const style = document.createElement("style");
    style.id = "misticaWideLayoutFix";
    style.textContent = `
      :root {
        --site-max-wide: 1420px;
        --site-side-space: clamp(18px, 4vw, 72px);
        --section-space: clamp(52px, 6vw, 86px);
        --grid-gap: clamp(18px, 1.8vw, 28px);
        --card-pad: clamp(18px, 1.65vw, 26px);
        --card-radius: 28px;
      }

      .container {
        width: min(var(--site-max-wide), calc(100% - (var(--site-side-space) * 2))) !important;
      }

      .section {
        padding-top: var(--section-space) !important;
        padding-bottom: var(--section-space) !important;
      }

      .section-title {
        margin-bottom: clamp(24px, 3vw, 42px) !important;
      }

      .section-title.centered {
        max-width: 880px !important;
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
        padding-top: clamp(38px, 4.4vw, 64px) !important;
        padding-bottom: clamp(34px, 4.2vw, 62px) !important;
      }

      .hero-grid {
        display: grid !important;
        grid-template-columns: minmax(0, 1.04fr) minmax(360px, .74fr) !important;
        gap: clamp(42px, 5.4vw, 92px) !important;
        align-items: start !important;
      }

      .hero-copy {
        justify-self: start !important;
        width: 100% !important;
        gap: clamp(16px, 1.4vw, 22px) !important;
      }

      .hero-copy h1 {
        max-width: 820px !important;
        font-size: clamp(2.72rem, 3.75vw, 4.45rem) !important;
        line-height: 1.07 !important;
        text-wrap: balance;
      }

      .hero-text {
        max-width: 680px !important;
        font-size: clamp(1rem, 1.02vw, 1.15rem) !important;
      }

      .hero-actions {
        margin-top: 4px !important;
      }

      .hero-visual {
        justify-self: center !important;
        align-self: start !important;
        width: min(100%, 470px) !important;
        min-height: 0 !important;
        height: auto !important;
        margin-top: clamp(8px, 1.1vw, 18px) !important;
        padding: clamp(14px, 1.45vw, 22px) !important;
        border-radius: 34px !important;
        background:
          radial-gradient(circle at 50% 16%, rgba(240,197,106,.14), transparent 34%),
          radial-gradient(circle at 70% 72%, rgba(83,107,55,.18), transparent 36%),
          linear-gradient(145deg, rgba(7,9,7,.96), rgba(38,21,48,.82)) !important;
      }

      .hero-visual::before {
        width: 72% !important;
        opacity: .55 !important;
        top: 7% !important;
      }

      .visual-orbit.one {
        width: 74% !important;
        opacity: .65 !important;
      }

      .visual-orbit.two {
        width: 60% !important;
        opacity: .6 !important;
      }

      .mystic-logo-card.hero-card-isis,
      .mystic-logo-card.hero-card-isis-publicitaria {
        width: 100% !important;
        max-width: 398px !important;
        min-height: 0 !important;
        height: auto !important;
        padding: 14px 14px 16px !important;
        align-self: start !important;
        justify-self: center !important;
        justify-content: end !important;
        gap: 6px !important;
        border-radius: 28px !important;
        background:
          linear-gradient(180deg, rgba(255,248,230,.055), rgba(3,3,5,.38)),
          rgba(3,3,5,.42) !important;
        box-shadow: 0 24px 70px rgba(0,0,0,.38) !important;
      }

      .hero-isis-publicitaria {
        width: min(100%, 382px) !important;
        max-height: clamp(350px, 29vw, 455px) !important;
        object-fit: contain !important;
        object-position: center top !important;
        margin: 0 auto !important;
        filter: drop-shadow(0 24px 46px rgba(0,0,0,.42)) !important;
      }

      .mystic-logo-card.hero-card-isis strong {
        font-size: clamp(1.32rem, 1.7vw, 1.9rem) !important;
        line-height: 1.1 !important;
      }

      .mystic-logo-card.hero-card-isis small {
        max-width: 300px !important;
        font-size: .66rem !important;
        line-height: 1.32 !important;
        letter-spacing: .08em !important;
      }

      .floating-card {
        left: 18px !important;
        right: 18px !important;
        bottom: 18px !important;
      }

      .trust-row {
        max-width: 820px !important;
        gap: 14px !important;
      }

      .category-grid,
      .confidence-grid,
      .product-grid,
      .checkout-grid,
      .split,
      .isis-layout,
      .dashboard-grid,
      .footer-grid,
      .how-to-buy-grid,
      .trust-footer-grid,
      .intent-grid {
        width: 100% !important;
        gap: var(--grid-gap) !important;
        align-items: stretch !important;
      }

      .category-grid article,
      .confidence-grid article,
      .trust-row span,
      .product-card,
      .form-panel,
      .metric-card,
      .contact-card,
      .client-item,
      .history-item,
      .stock-item,
      .cart-item,
      .how-to-buy-grid article,
      .trust-footer-grid article,
      .intent-grid a {
        box-sizing: border-box !important;
        height: auto !important;
        border-radius: var(--card-radius) !important;
        padding: var(--card-pad) !important;
        background-clip: padding-box !important;
      }

      .category-grid article,
      .confidence-grid article,
      .product-card,
      .how-to-buy-grid article,
      .trust-footer-grid article,
      .intent-grid a {
        min-height: clamp(170px, 14vw, 220px) !important;
      }

      .category-grid article,
      .confidence-grid article,
      .trust-row span,
      .product-card,
      .how-to-buy-grid article,
      .trust-footer-grid article,
      .intent-grid a {
        display: grid !important;
        align-content: start !important;
      }

      .trust-row span {
        min-height: 118px !important;
      }

      .metric-card {
        min-height: 120px !important;
        display: grid !important;
        align-content: center !important;
      }

      .product-grid {
        grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)) !important;
      }

      .product-card {
        gap: 14px !important;
        grid-template-rows: auto auto auto auto auto !important;
      }

      .product-card h3 {
        line-height: 1.18 !important;
      }

      .product-card p {
        line-height: 1.52 !important;
      }

      .product-image {
        min-height: 128px !important;
        border-radius: 22px !important;
      }

      .product-photo {
        aspect-ratio: 4 / 3 !important;
        max-height: 210px !important;
        object-fit: cover !important;
      }

      .qty-row {
        margin-top: auto !important;
      }

      .checkout-grid,
      .split {
        align-items: start !important;
      }

      .form-panel {
        min-height: 0 !important;
      }

      .isis-layout {
        grid-template-columns: minmax(320px, .78fr) minmax(0, 1.05fr) !important;
        align-items: center !important;
      }

      .isis-panel-image,
      .isis-panel-image:has(.isis-human-img) {
        min-height: 0 !important;
        height: auto !important;
        align-self: center !important;
        padding: clamp(18px, 1.8vw, 26px) !important;
        border-radius: 32px !important;
      }

      .isis-human-img,
      .isis-human-produtos {
        width: min(100%, 430px) !important;
        max-height: clamp(390px, 32vw, 560px) !important;
        object-fit: contain !important;
      }

      .isis-panel-image:has(.isis-human-img) p {
        position: relative !important;
        left: auto !important;
        right: auto !important;
        bottom: auto !important;
        margin-top: 14px !important;
        width: 100% !important;
        max-width: 430px !important;
      }

      .isis-chat-panel {
        align-self: center !important;
      }

      @media (min-width: 1500px) {
        .category-grid {
          grid-template-columns: repeat(6, minmax(0, 1fr)) !important;
        }

        .product-grid {
          grid-template-columns: repeat(4, minmax(0, 1fr)) !important;
        }

        .dashboard-grid {
          grid-template-columns: repeat(4, minmax(0, 1fr)) !important;
        }
      }

      @media (max-width: 1280px) {
        :root {
          --site-side-space: clamp(18px, 3.5vw, 44px);
          --site-max-wide: 1180px;
        }

        .hero-grid {
          grid-template-columns: minmax(0, 1fr) minmax(330px, .8fr) !important;
          gap: clamp(30px, 4vw, 58px) !important;
        }

        .hero-copy h1 {
          font-size: clamp(2.35rem, 4vw, 3.85rem) !important;
        }

        .hero-visual {
          width: min(100%, 440px) !important;
          margin-top: 6px !important;
        }

        .hero-isis-publicitaria {
          max-height: 390px !important;
        }
      }

      @media (max-width: 980px) {
        .container {
          width: min(100% - 28px, 780px) !important;
        }

        .hero-grid,
        .isis-layout,
        .checkout-grid,
        .split {
          grid-template-columns: 1fr !important;
        }

        .hero-copy {
          justify-self: center !important;
          text-align: center !important;
        }

        .hero-copy h1,
        .hero-text,
        .trust-row {
          margin-left: auto !important;
          margin-right: auto !important;
        }

        .hero-actions {
          justify-content: center !important;
        }

        .hero-visual {
          max-width: 500px !important;
          margin: 0 auto !important;
        }

        .hero-isis-publicitaria {
          max-height: 380px !important;
        }

        .isis-panel-image {
          max-width: 520px !important;
          margin: 0 auto !important;
        }

        .category-grid,
        .confidence-grid,
        .dashboard-grid,
        .trust-footer-grid,
        .how-to-buy-grid,
        .intent-grid {
          grid-template-columns: repeat(2, minmax(0, 1fr)) !important;
        }
      }

      @media (max-width: 680px) {
        :root {
          --grid-gap: 16px;
          --card-pad: 18px;
          --card-radius: 24px;
        }

        .container {
          width: min(100% - 24px, 100%) !important;
        }

        .section {
          padding-top: 42px !important;
          padding-bottom: 42px !important;
        }

        .hero-section {
          padding-top: 34px !important;
        }

        .hero-copy h1 {
          font-size: clamp(2rem, 10vw, 3rem) !important;
        }

        .hero-visual {
          width: 100% !important;
          padding: 14px !important;
        }

        .mystic-logo-card.hero-card-isis,
        .mystic-logo-card.hero-card-isis-publicitaria {
          max-width: 100% !important;
          padding: 14px !important;
        }

        .hero-isis-publicitaria {
          max-height: 330px !important;
        }

        .category-grid,
        .confidence-grid,
        .dashboard-grid,
        .footer-grid,
        .trust-row,
        .trust-footer-grid,
        .how-to-buy-grid,
        .intent-grid {
          grid-template-columns: 1fr !important;
        }

        .category-grid article,
        .confidence-grid article,
        .product-card,
        .how-to-buy-grid article,
        .trust-footer-grid article,
        .intent-grid a {
          min-height: 0 !important;
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
