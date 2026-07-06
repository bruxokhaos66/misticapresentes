(() => {
  function injectWideLayoutFix() {
    if (document.getElementById("misticaWideLayoutFix")) return;

    const style = document.createElement("style");
    style.id = "misticaWideLayoutFix";
    style.textContent = `
      :root {
        --site-max-wide: 1560px;
        --site-side-space: clamp(20px, 4.8vw, 92px);
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
        padding-top: clamp(42px, 5vw, 72px) !important;
      }

      .hero-grid {
        grid-template-columns: minmax(0, 0.98fr) minmax(420px, 0.92fr) !important;
        gap: clamp(34px, 5.4vw, 96px) !important;
        align-items: center !important;
      }

      .hero-copy {
        justify-self: start;
        width: 100%;
      }

      .hero-copy h1 {
        max-width: 760px !important;
        font-size: clamp(3rem, 4.05vw, 4.85rem) !important;
        line-height: 1.08 !important;
      }

      .hero-text {
        max-width: 720px !important;
        font-size: clamp(1.02rem, 1.04vw, 1.2rem) !important;
      }

      .hero-visual {
        justify-self: stretch;
        width: 100%;
        min-height: clamp(520px, 43vw, 670px) !important;
        padding: clamp(22px, 2.7vw, 42px) !important;
      }

      .mystic-logo-card.hero-card-isis,
      .mystic-logo-card.hero-card-isis-publicitaria {
        width: min(100%, 470px) !important;
        min-height: clamp(500px, 38vw, 610px) !important;
        align-self: center !important;
        justify-self: center !important;
        justify-content: end !important;
      }

      .hero-isis-publicitaria {
        width: min(100%, 455px) !important;
        max-height: 520px !important;
        object-fit: contain !important;
        margin: 0 auto 0 !important;
      }

      .trust-row {
        max-width: 820px;
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
          grid-template-columns: minmax(0, 1fr) minmax(360px, .9fr) !important;
          gap: clamp(28px, 4vw, 56px) !important;
        }

        .hero-copy h1 {
          font-size: clamp(2.5rem, 4.4vw, 4.05rem) !important;
        }
      }

      @media (max-width: 980px) {
        .container {
          width: min(100% - 28px, 780px) !important;
        }

        .hero-grid {
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
          min-height: 520px !important;
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
          min-height: 470px !important;
          padding: 16px !important;
        }

        .mystic-logo-card.hero-card-isis,
        .mystic-logo-card.hero-card-isis-publicitaria {
          min-height: 450px !important;
        }

        .hero-isis-publicitaria {
          max-height: 390px !important;
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
