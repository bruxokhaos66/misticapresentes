(() => {
  const styleId = "misticaCommercialBadgesStyle";
  const gridSelector = "[data-product-grid]";

  function installStyle() {
    if (document.getElementById(styleId)) return;

    const style = document.createElement("style");
    style.id = styleId;
    style.textContent = `
      .product-card {
        position: relative;
      }

      .product-commercial-badges {
        display: flex;
        flex-wrap: wrap;
        gap: 8px;
        align-items: center;
        margin-bottom: 2px;
      }

      .product-commercial-badge {
        display: inline-flex;
        align-items: center;
        gap: 5px;
        width: fit-content;
        border-radius: 999px;
        padding: 7px 10px;
        font-size: .68rem;
        font-weight: 950;
        letter-spacing: .10em;
        line-height: 1;
        text-transform: uppercase;
        white-space: nowrap;
        box-shadow: inset 0 1px 0 rgba(255,255,255,.12);
      }

      .badge-best-seller {
        border: 1px solid rgba(240,197,106,.62);
        background: linear-gradient(135deg, #fff0b2, #d8a846 62%, #fff1bd);
        color: #171007;
      }

      .badge-new {
        border: 1px solid rgba(184,201,119,.45);
        background: rgba(184,201,119,.10);
        color: #dfeab2;
      }

      .badge-low-stock {
        border: 1px solid rgba(255,160,90,.48);
        background: rgba(255,160,90,.10);
        color: #ffd7b0;
      }

      .product-card-featured {
        border-color: rgba(240,197,106,.48) !important;
        box-shadow: 0 26px 80px rgba(240,197,106,.14), 0 24px 70px rgba(0,0,0,.26) !important;
      }

      .product-card-featured::before {
        content: "";
        position: absolute;
        inset: 0;
        pointer-events: none;
        border-radius: inherit;
        background: radial-gradient(circle at 18% 0, rgba(240,197,106,.16), transparent 34%);
        opacity: .85;
      }

      .product-card-featured > * {
        position: relative;
        z-index: 1;
      }

      .product-card-featured .product-price {
        border-color: rgba(240,197,106,.44) !important;
        background: rgba(240,197,106,.12) !important;
      }

      @media (max-width: 520px) {
        .product-commercial-badges {
          gap: 6px;
        }

        .product-commercial-badge {
          font-size: .64rem;
          padding: 7px 9px;
        }
      }
    `;

    document.head.appendChild(style);
  }

  function numberFromText(text) {
    const match = String(text || "").match(/\d+/);
    return match ? Number(match[0]) : null;
  }

  function stockFromCard(card) {
    const candidates = [
      card.querySelector(".stock-badge")?.textContent,
      card.textContent,
    ];

    for (const text of candidates) {
      const normalized = String(text || "").toLowerCase();
      if (!/estoque|unidade|unidades|restam|dispon/i.test(normalized)) continue;
      const value = numberFromText(normalized);
      if (Number.isFinite(value)) return value;
    }

    return null;
  }

  function makeBadge(className, text) {
    const badge = document.createElement("span");
    badge.className = `product-commercial-badge ${className}`;
    badge.textContent = text;
    return badge;
  }

  function ensureBadgeContainer(card) {
    let box = card.querySelector(".product-commercial-badges");
    if (box) return box;

    box = document.createElement("div");
    box.className = "product-commercial-badges";

    const title = card.querySelector("h3");
    const target = title?.parentNode === card ? title : card.firstElementChild;
    if (target) card.insertBefore(box, target);
    else card.prepend(box);

    return box;
  }

  function applyCardBadges(card, index) {
    if (!card || card.dataset.commercialBadgesApplied === "true") return;

    const box = ensureBadgeContainer(card);
    box.innerHTML = "";

    const badges = [];

    if (index < 3) {
      badges.push(makeBadge("badge-best-seller", "🏆 Mais Vendido"));
      card.classList.add("product-card-featured");
      card.style.order = String(-10 + index);
    } else {
      card.classList.remove("product-card-featured");
      card.style.order = String(index);
    }

    if (index >= 3 && index < 6) {
      badges.push(makeBadge("badge-new", "✨ Novidade"));
    }

    const stock = stockFromCard(card);
    if (Number.isFinite(stock) && stock >= 1 && stock <= 3) {
      badges.push(makeBadge("badge-low-stock", "🔥 Últimas Unidades"));
    }

    badges.forEach(badge => box.appendChild(badge));
    box.hidden = badges.length === 0;
    card.dataset.commercialBadgesApplied = "true";
  }

  function resetAppliedFlags(grid) {
    grid.querySelectorAll(".product-card").forEach(card => {
      card.dataset.commercialBadgesApplied = "false";
    });
  }

  function applyCommercialBadges() {
    installStyle();
    const grid = document.querySelector(gridSelector);
    if (!grid) return;

    const cards = Array.from(grid.querySelectorAll(".product-card"));
    cards.forEach(applyCardBadges);
  }

  function installObserver() {
    const grid = document.querySelector(gridSelector);
    if (!grid || grid.dataset.commercialBadgesObserver === "true") return;

    grid.dataset.commercialBadgesObserver = "true";
    const observer = new MutationObserver(() => {
      resetAppliedFlags(grid);
      requestAnimationFrame(applyCommercialBadges);
    });

    observer.observe(grid, { childList: true, subtree: true });
    window.misticaCommercialBadgesObserver = observer;
  }

  function apply() {
    applyCommercialBadges();
    installObserver();
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

  window.misticaCommercialBadges = { apply: applyCommercialBadges };
})();
