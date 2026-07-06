(() => {
  function injectCardSystemFix() {
    const old = document.getElementById("misticaCardSystemFix");
    if (old) old.remove();

    const style = document.createElement("style");
    style.id = "misticaCardSystemFix";
    style.textContent = `
      /* Etapa 2: sistema visual dos cards, sem mexer na posição da Isis no hero */
      :root {
        --mistica-card-radius: 22px;
        --mistica-card-radius-lg: 30px;
        --mistica-card-pad-sm: clamp(14px, 1.2vw, 18px);
        --mistica-card-pad: clamp(16px, 1.45vw, 22px);
        --mistica-card-pad-lg: clamp(20px, 1.8vw, 28px);
        --mistica-card-gap: clamp(14px, 1.5vw, 22px);
        --mistica-card-border: rgba(240,197,106,.22);
        --mistica-card-bg: linear-gradient(145deg, rgba(255,248,230,.075), rgba(83,107,55,.055));
        --mistica-card-bg-strong: linear-gradient(145deg, rgba(255,248,230,.105), rgba(83,107,55,.08));
      }

      .category-grid,
      .confidence-grid,
      .product-grid,
      .dashboard-grid,
      .checkout-grid,
      .split,
      .isis-layout,
      .footer-grid,
      .trust-row,
      .premium-hero-selling-bar,
      .intent-grid,
      .trust-footer-grid,
      .how-to-buy-grid {
        gap: var(--mistica-card-gap) !important;
      }

      .trust-row span,
      .premium-hero-selling-bar span,
      .category-grid article,
      .confidence-grid article,
      .product-card,
      .form-panel,
      .metric-card,
      .contact-card,
      .client-item,
      .history-item,
      .stock-item,
      .cart-item,
      .total-box,
      .warning-box,
      .saved-box,
      .intent-grid a,
      .trust-footer-grid article,
      .how-to-buy-grid article,
      .campaign-card,
      .ambient-card {
        box-sizing: border-box !important;
        border-radius: var(--mistica-card-radius) !important;
        border: 1px solid var(--mistica-card-border) !important;
        background: var(--mistica-card-bg) !important;
        box-shadow: 0 16px 42px rgba(0,0,0,.18) !important;
        height: auto !important;
        transition: transform .18s ease, border-color .18s ease, background .18s ease, box-shadow .18s ease !important;
      }

      .category-grid article:hover,
      .confidence-grid article:hover,
      .product-card:hover,
      .intent-grid a:hover,
      .trust-footer-grid article:hover,
      .how-to-buy-grid article:hover {
        transform: translateY(-2px) !important;
        border-color: rgba(240,197,106,.38) !important;
        background: var(--mistica-card-bg-strong) !important;
        box-shadow: 0 22px 58px rgba(0,0,0,.24) !important;
      }

      .trust-row,
      .premium-hero-selling-bar {
        display: grid !important;
        grid-template-columns: repeat(3, minmax(0, 1fr)) !important;
        align-items: stretch !important;
        max-width: 820px !important;
      }

      .trust-row span,
      .premium-hero-selling-bar span {
        min-height: 92px !important;
        padding: var(--mistica-card-pad-sm) !important;
        display: grid !important;
        align-content: center !important;
        gap: 5px !important;
      }

      .trust-row strong,
      .premium-hero-selling-bar strong {
        font-size: .72rem !important;
        letter-spacing: .12em !important;
        line-height: 1.25 !important;
      }

      .category-grid {
        align-items: stretch !important;
      }

      .category-grid article,
      .intent-grid a {
        min-height: 154px !important;
        padding: var(--mistica-card-pad) !important;
        display: grid !important;
        align-content: start !important;
        gap: 8px !important;
      }

      .category-grid span,
      .intent-grid span {
        font-size: clamp(1.55rem, 2vw, 2.05rem) !important;
        line-height: 1 !important;
      }

      .category-grid strong,
      .intent-grid strong {
        font-size: clamp(.98rem, 1.1vw, 1.12rem) !important;
        line-height: 1.22 !important;
      }

      .category-grid p,
      .intent-grid small,
      .confidence-grid span,
      .trust-footer-grid span,
      .how-to-buy-grid span {
        font-size: .94rem !important;
        line-height: 1.48 !important;
      }

      .confidence-grid article,
      .trust-footer-grid article,
      .how-to-buy-grid article {
        min-height: 132px !important;
        padding: var(--mistica-card-pad) !important;
        display: grid !important;
        align-content: start !important;
        gap: 8px !important;
      }

      .product-grid {
        grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)) !important;
        align-items: stretch !important;
      }

      .product-card {
        min-height: 0 !important;
        padding: var(--mistica-card-pad) !important;
        display: grid !important;
        grid-template-rows: auto auto auto auto 1fr auto auto !important;
        align-content: start !important;
        gap: 12px !important;
      }

      .premium-product-badge {
        width: fit-content !important;
        border-radius: 999px !important;
        padding: 6px 10px !important;
        font-size: .68rem !important;
        font-weight: 900 !important;
        letter-spacing: .08em !important;
        text-transform: uppercase !important;
        color: #171007 !important;
        background: linear-gradient(135deg, #fff0b2, #d8a846 62%, #fff1bd) !important;
      }

      .product-image,
      .product-photo {
        border-radius: 18px !important;
      }

      .product-image {
        min-height: 118px !important;
        display: grid !important;
        place-items: center !important;
        font-size: clamp(2.2rem, 3vw, 3rem) !important;
      }

      .product-photo {
        width: 100% !important;
        aspect-ratio: 4 / 3 !important;
        max-height: 190px !important;
        object-fit: cover !important;
      }

      .product-card h3 {
        margin: 0 !important;
        line-height: 1.18 !important;
        font-size: clamp(1.1rem, 1.35vw, 1.35rem) !important;
      }

      .product-card p {
        margin: 0 !important;
        line-height: 1.5 !important;
        font-size: .95rem !important;
      }

      .product-price {
        margin-top: 2px !important;
        font-size: 1.18rem !important;
      }

      .premium-product-note {
        display: block !important;
        color: rgba(239,225,197,.82) !important;
        line-height: 1.35 !important;
      }

      .qty-row {
        margin-top: 4px !important;
        align-self: end !important;
      }

      .form-panel,
      .contact-card,
      .campaign-card,
      .ambient-card {
        border-radius: var(--mistica-card-radius-lg) !important;
        padding: var(--mistica-card-pad-lg) !important;
      }

      .checkout-grid,
      .split,
      .isis-layout {
        align-items: start !important;
      }

      .dashboard-grid {
        align-items: stretch !important;
      }

      .metric-card {
        min-height: 112px !important;
        padding: var(--mistica-card-pad) !important;
        display: grid !important;
        align-content: center !important;
        gap: 8px !important;
      }

      .client-item,
      .history-item,
      .stock-item,
      .cart-item {
        padding: var(--mistica-card-pad-sm) !important;
      }

      .cart-item,
      .stock-item {
        display: flex !important;
        align-items: center !important;
        justify-content: space-between !important;
        gap: 12px !important;
      }

      .total-box {
        padding: var(--mistica-card-pad-sm) !important;
      }

      .isis-panel-image,
      .isis-chat-panel {
        border-radius: var(--mistica-card-radius-lg) !important;
      }

      .isis-panel-image {
        padding: var(--mistica-card-pad-lg) !important;
      }

      .campaign-card {
        display: grid !important;
        grid-template-columns: minmax(0, 1fr) auto !important;
        align-items: center !important;
        gap: var(--mistica-card-gap) !important;
      }

      @media (min-width: 1500px) {
        .product-grid {
          grid-template-columns: repeat(4, minmax(0, 1fr)) !important;
        }
      }

      @media (max-width: 980px) {
        .trust-row,
        .premium-hero-selling-bar,
        .campaign-card {
          grid-template-columns: 1fr !important;
        }

        .category-grid,
        .confidence-grid,
        .trust-footer-grid,
        .how-to-buy-grid,
        .intent-grid,
        .dashboard-grid {
          grid-template-columns: repeat(2, minmax(0, 1fr)) !important;
        }
      }

      @media (max-width: 680px) {
        .category-grid,
        .confidence-grid,
        .trust-footer-grid,
        .how-to-buy-grid,
        .intent-grid,
        .dashboard-grid,
        .product-grid {
          grid-template-columns: 1fr !important;
        }

        .trust-row span,
        .premium-hero-selling-bar span,
        .category-grid article,
        .confidence-grid article,
        .product-card,
        .intent-grid a,
        .trust-footer-grid article,
        .how-to-buy-grid article {
          min-height: 0 !important;
        }

        .cart-item,
        .stock-item {
          align-items: flex-start !important;
          flex-direction: column !important;
        }
      }
    `;

    document.head.appendChild(style);
  }

  function applyCardSystemMarkers() {
    document.querySelectorAll(".product-card, .category-grid article, .confidence-grid article, .trust-row span, .premium-hero-selling-bar span, .form-panel, .metric-card").forEach(card => {
      card.dataset.cardSystemReady = "true";
    });
  }

  function apply() {
    injectCardSystemFix();
    applyCardSystemMarkers();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", apply, { once: true });
  } else {
    apply();
  }

  window.addEventListener("load", () => {
    apply();
    setTimeout(apply, 600);
    setTimeout(apply, 1600);
  });
})();
