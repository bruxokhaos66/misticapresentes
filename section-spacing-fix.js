(() => {
  function injectSectionSpacingFix() {
    const old = document.getElementById("misticaSectionSpacingFix");
    if (old) old.remove();

    const style = document.createElement("style");
    style.id = "misticaSectionSpacingFix";
    style.textContent = `
      /* Etapa 3: espaçamento entre seções, sem mexer na posição da Isis nem nos cards */
      :root {
        --mistica-section-gap: clamp(46px, 5.2vw, 78px);
        --mistica-section-gap-tight: clamp(30px, 3.6vw, 54px);
      }

      .hero-section {
        min-height: auto !important;
        padding-bottom: clamp(22px, 2.5vw, 38px) !important;
      }

      .hero-copy {
        gap: clamp(12px, 1.15vw, 18px) !important;
      }

      .hero-copy h1,
      .hero-text {
        margin-bottom: 0 !important;
      }

      .hero-actions {
        margin-top: clamp(8px, 1vw, 14px) !important;
        margin-bottom: 0 !important;
      }

      .trust-row,
      .premium-hero-selling-bar {
        margin-top: clamp(10px, 1.2vw, 18px) !important;
        margin-bottom: 0 !important;
      }

      .ambient-card {
        margin-top: clamp(18px, 1.9vw, 28px) !important;
        margin-bottom: 0 !important;
      }

      .section {
        padding-top: var(--mistica-section-gap) !important;
        padding-bottom: var(--mistica-section-gap) !important;
      }

      .premium-campaign-band,
      .premium-trust-footer {
        padding-top: var(--mistica-section-gap-tight) !important;
        padding-bottom: var(--mistica-section-gap-tight) !important;
      }

      .section-title {
        margin-bottom: clamp(22px, 2.5vw, 36px) !important;
      }

      .section-title h2 {
        margin-top: 0 !important;
        margin-bottom: clamp(8px, 1vw, 14px) !important;
      }

      .section-title p:last-child {
        margin-bottom: 0 !important;
      }

      #categorias,
      #produtos,
      #checkout,
      #isis,
      #contato,
      #admin,
      #comprar-por-intencao,
      .premium-trust-footer,
      .premium-campaign-band {
        scroll-margin-top: 140px !important;
      }

      .checkout-grid,
      .split,
      .isis-layout,
      .footer-grid,
      .product-grid,
      .category-grid,
      .confidence-grid,
      .intent-grid,
      .trust-footer-grid {
        margin-top: 0 !important;
      }

      .isis-layout {
        align-items: center !important;
      }

      .footer {
        padding-top: clamp(34px, 4vw, 58px) !important;
        padding-bottom: clamp(28px, 3.4vw, 46px) !important;
      }

      @media (min-width: 981px) {
        .hero-grid {
          align-items: start !important;
        }

        .hero-copy {
          padding-top: clamp(8px, 1vw, 16px) !important;
        }
      }

      @media (max-width: 980px) {
        :root {
          --mistica-section-gap: clamp(40px, 7vw, 62px);
          --mistica-section-gap-tight: clamp(30px, 5vw, 46px);
        }

        .hero-section {
          padding-bottom: 34px !important;
        }

        .ambient-card {
          margin-top: 22px !important;
        }
      }

      @media (max-width: 680px) {
        :root {
          --mistica-section-gap: 38px;
          --mistica-section-gap-tight: 30px;
        }

        .hero-section {
          padding-top: 28px !important;
          padding-bottom: 30px !important;
        }

        .hero-copy {
          gap: 12px !important;
        }

        .ambient-card {
          margin-top: 18px !important;
        }
      }
    `;

    document.head.appendChild(style);
  }

  function apply() {
    injectSectionSpacingFix();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", apply, { once: true });
  } else {
    apply();
  }

  window.addEventListener("load", () => {
    apply();
    setTimeout(apply, 700);
    setTimeout(apply, 1800);
  });
})();
