(() => {
  if (window.__MISTICA_SAFE_BADGES_LOADED__) return;
  window.__MISTICA_SAFE_BADGES_LOADED__ = true;

  const styleId = "mistica-safe-badges-style";

  function installStyle() {
    if (document.getElementById(styleId)) return;
    const style = document.createElement("style");
    style.id = styleId;
    style.textContent = `
      .product-card { position: relative; }
      .product-card-featured { border-color: rgba(240,197,106,.48) !important; box-shadow: 0 26px 80px rgba(240,197,106,.14), 0 24px 70px rgba(0,0,0,.26) !important; }
      .product-card-featured::before { content: ""; position: absolute; inset: 0; pointer-events: none; border-radius: inherit; background: radial-gradient(circle at 18% 0, rgba(240,197,106,.16), transparent 34%); opacity: .85; }
      .product-card-featured > * { position: relative; z-index: 1; }
      .product-commercial-badges { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; margin-bottom: 8px; }
      .product-commercial-badge { display: inline-flex; align-items: center; border-radius: 999px; padding: 7px 10px; font-size: .68rem; font-weight: 950; letter-spacing: .08em; line-height: 1; text-transform: uppercase; white-space: nowrap; }
      .badge-best-seller { border: 1px solid rgba(240,197,106,.62); background: linear-gradient(135deg, #fff0b2, #d8a846 62%, #fff1bd); color: #171007; }
      .badge-new { border: 1px solid rgba(184,201,119,.45); background: rgba(184,201,119,.10); color: #dfeab2; }
      @media (max-width: 520px) { .product-commercial-badges { gap: 6px; } .product-commercial-badge { font-size: .64rem; padding: 7px 9px; } }
    `;
    document.head.appendChild(style);
  }

  function makeBadge(className, text) {
    const badge = document.createElement("span");
    badge.className = `product-commercial-badge ${className}`;
    badge.textContent = text;
    return badge;
  }

  function ensureBox(card) {
    let box = card.querySelector(".product-commercial-badges");
    if (box) return box;
    box = document.createElement("div");
    box.className = "product-commercial-badges";
    const title = card.querySelector("h3");
    if (title && title.parentNode === card) card.insertBefore(box, title);
    else card.prepend(box);
    return box;
  }

  function applyBadgesOnce() {
    installStyle();
    const grid = document.querySelector("[data-product-grid]");
    if (!grid) return false;
    const cards = Array.from(grid.querySelectorAll(".product-card"));
    if (!cards.length) return false;

    cards.forEach((card, index) => {
      if (card.dataset.safeBadgesApplied === "true") return;
      card.dataset.safeBadgesApplied = "true";
      const box = ensureBox(card);
      box.replaceChildren();
      if (index < 3) {
        box.appendChild(makeBadge("badge-best-seller", "Mais Vendido"));
        card.classList.add("product-card-featured");
        card.style.order = String(-10 + index);
      } else if (index < 6) {
        box.appendChild(makeBadge("badge-new", "Novidade"));
        card.style.order = String(index);
      } else {
        box.hidden = true;
        card.style.order = String(index);
      }
    });
    return true;
  }

  function waitForCards(attempt = 0) {
    if (applyBadgesOnce()) return;
    if (attempt < 12) window.setTimeout(() => waitForCards(attempt + 1), 250);
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", () => waitForCards(), { once: true });
  else waitForCards();

  window.misticaCommercialBadges = { apply: applyBadgesOnce };
})();
