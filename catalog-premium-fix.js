(() => {
  const styleId = "misticaCatalogPremiumStyle";

  function installStyle() {
    if (document.getElementById(styleId)) return;

    const style = document.createElement("style");
    style.id = styleId;
    style.textContent = `
      .products-section {
        position: relative;
        overflow: hidden;
        background:
          radial-gradient(circle at 18% 12%, rgba(240,197,106,.10), transparent 26rem),
          radial-gradient(circle at 88% 38%, rgba(184,201,119,.10), transparent 28rem),
          linear-gradient(180deg, rgba(255,255,255,.018), rgba(83,107,55,.075)) !important;
      }

      .products-section::before {
        content: "";
        position: absolute;
        inset: 0;
        pointer-events: none;
        background: linear-gradient(90deg, transparent, rgba(240,197,106,.035), transparent);
      }

      .products-section .section-title {
        position: relative;
        z-index: 1;
      }

      .products-section .section-title h2 {
        max-width: 860px;
        margin-left: auto;
        margin-right: auto;
      }

      .products-section .section-title p:last-child {
        max-width: 720px;
        margin-left: auto;
        margin-right: auto;
        color: #efe1c5;
        font-weight: 700;
      }

      .catalog-tools {
        position: relative;
        z-index: 2;
        display: grid;
        grid-template-columns: minmax(260px, 1.2fr) minmax(180px, .7fr) minmax(180px, .7fr);
        gap: 12px;
        margin-bottom: clamp(20px, 2.6vw, 34px);
        border: 1px solid rgba(240,197,106,.20);
        border-radius: 28px;
        padding: clamp(14px, 2vw, 20px);
        background:
          radial-gradient(circle at 8% 0, rgba(240,197,106,.12), transparent 32%),
          linear-gradient(145deg, rgba(255,248,230,.07), rgba(3,3,5,.28));
        box-shadow: 0 24px 70px rgba(0,0,0,.22);
        backdrop-filter: blur(10px);
      }

      .catalog-tools input,
      .catalog-tools select {
        min-height: 52px;
        border: 1px solid rgba(240,197,106,.26);
        border-radius: 999px;
        padding: 0 16px;
        background: rgba(3,3,5,.42);
        color: #fff8ea;
        font-weight: 800;
        box-shadow: inset 0 0 22px rgba(0,0,0,.18);
      }

      .catalog-tools input::placeholder {
        color: rgba(239,225,197,.72);
      }

      .product-grid {
        position: relative;
        z-index: 1;
        grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)) !important;
        gap: clamp(18px, 2.2vw, 28px) !important;
      }

      .product-card {
        border-radius: 30px !important;
        padding: clamp(18px, 2.4vw, 24px) !important;
        gap: 15px !important;
        background:
          radial-gradient(circle at 18% 8%, rgba(240,197,106,.12), transparent 30%),
          linear-gradient(145deg, rgba(255,248,230,.085), rgba(83,107,55,.075)) !important;
        border-color: rgba(240,197,106,.22) !important;
      }

      .product-card h3 {
        font-size: clamp(1.12rem, 1.5vw, 1.38rem);
        line-height: 1.15;
      }

      .product-card p:not(.eyebrow) {
        color: #e1d4bb;
        font-weight: 650;
      }

      .product-image,
      .product-photo {
        min-height: 150px !important;
        border-radius: 24px !important;
      }

      .product-photo {
        aspect-ratio: 4 / 3.25 !important;
      }

      .product-tag,
      .premium-product-badge {
        border-radius: 999px !important;
        padding: 7px 11px !important;
        font-size: .70rem !important;
        letter-spacing: .12em !important;
      }

      .product-price {
        width: fit-content;
        border: 1px solid rgba(240,197,106,.24);
        border-radius: 999px;
        padding: 8px 12px;
        background: rgba(240,197,106,.08);
        box-shadow: inset 0 0 20px rgba(240,197,106,.04);
      }

      .stock-badge {
        border-radius: 999px !important;
        padding: 7px 11px !important;
        background: rgba(184,201,119,.08) !important;
      }

      .qty-row {
        display: grid !important;
        grid-template-columns: 86px 1fr !important;
        gap: 10px !important;
      }

      .qty-row input {
        text-align: center;
        border-radius: 999px !important;
      }

      .product-card .btn,
      .product-card .btn-ghost {
        min-height: 48px;
      }

      .empty-catalog {
        grid-column: 1 / -1;
        border: 1px solid rgba(240,197,106,.22);
        border-radius: 28px;
        padding: 26px;
        background: rgba(255,248,230,.06);
        color: #efe1c5;
        font-weight: 800;
        text-align: center;
      }

      @media (max-width: 840px) {
        .catalog-tools {
          grid-template-columns: 1fr;
          border-radius: 24px;
        }

        .product-grid {
          grid-template-columns: repeat(auto-fit, minmax(230px, 1fr)) !important;
        }
      }

      @media (max-width: 520px) {
        .product-grid {
          grid-template-columns: 1fr !important;
        }

        .product-card {
          border-radius: 26px !important;
        }
      }
    `;

    document.head.appendChild(style);
  }

  function applyCopy() {
    const title = document.querySelector("#produtos .section-title h2");
    const text = document.querySelector("#produtos .section-title p:last-child");

    if (title) title.textContent = "Escolha produtos por intenção, presente e energia";
    if (text) text.textContent = "Use a busca e os filtros para encontrar rápido incensos, cristais, velas, aromas, banhos e presentes com significado.";
  }

  function apply() {
    installStyle();
    applyCopy();
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
