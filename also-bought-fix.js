(() => {
  const styleId = "misticaAlsoBoughtStyle";
  const panelId = "alsoBoughtPanel";

  function installStyle() {
    if (document.getElementById(styleId)) return;

    const style = document.createElement("style");
    style.id = styleId;
    style.textContent = `
      .also-bought-panel {
        position: relative;
        overflow: hidden;
        margin-top: clamp(18px, 2.4vw, 28px);
        border: 1px solid rgba(240,197,106,.24);
        border-radius: 28px;
        padding: clamp(18px, 2.4vw, 24px);
        background:
          radial-gradient(circle at 12% 10%, rgba(240,197,106,.13), transparent 32%),
          linear-gradient(145deg, rgba(255,248,230,.07), rgba(83,107,55,.07));
        box-shadow: 0 22px 70px rgba(0,0,0,.22);
      }

      .also-bought-panel::before {
        content: "";
        position: absolute;
        inset: 0;
        pointer-events: none;
        background: linear-gradient(120deg, rgba(255,248,230,.08), transparent 38%, rgba(184,201,119,.06));
      }

      .also-bought-panel > * {
        position: relative;
        z-index: 1;
      }

      .also-bought-panel h3 {
        margin: 4px 0 8px;
        font-family: Cinzel, Georgia, serif;
        letter-spacing: .05em;
      }

      .also-bought-panel .privacy-note {
        margin-bottom: 15px;
        color: #efe1c5;
        font-weight: 650;
      }

      .also-bought-grid {
        display: grid;
        grid-template-columns: repeat(3, minmax(0, 1fr));
        gap: 12px;
      }

      .also-bought-item {
        display: grid;
        gap: 10px;
        border: 1px solid rgba(240,197,106,.18);
        border-radius: 22px;
        padding: 14px;
        background: rgba(3,3,5,.26);
      }

      .also-bought-item strong {
        color: #fff6dc;
        line-height: 1.2;
      }

      .also-bought-item span {
        color: #f0c56a;
        font-weight: 900;
      }

      .also-bought-item button {
        min-height: 40px;
        border: 1px solid rgba(240,197,106,.38);
        border-radius: 999px;
        background: rgba(240,197,106,.08);
        color: #ffd987;
        cursor: pointer;
        font-weight: 900;
      }

      .also-bought-item button:hover {
        background: rgba(240,197,106,.14);
      }

      @media (max-width: 860px) {
        .also-bought-grid {
          grid-template-columns: 1fr;
        }
      }
    `;

    document.head.appendChild(style);
  }

  function productInfoFromCard(card, index) {
    const title = card.querySelector("h3")?.textContent?.trim() || `Produto ${index + 1}`;
    const price = card.querySelector(".product-price")?.textContent?.trim() || "Ver preço";
    return { title, price, index };
  }

  function selectedCartText() {
    return document.getElementById("cartList")?.textContent?.toLowerCase() || "";
  }

  function recommendedProducts() {
    const cards = Array.from(document.querySelectorAll("[data-product-grid] .product-card"));
    const cartText = selectedCartText();

    const available = cards
      .map(productInfoFromCard)
      .filter(item => item.title && !cartText.includes(item.title.toLowerCase()));

    const start = cartText.trim() ? 0 : 3;
    return available.slice(start, start + 3).length ? available.slice(start, start + 3) : available.slice(0, 3);
  }

  function scrollToProduct(index) {
    const cards = Array.from(document.querySelectorAll("[data-product-grid] .product-card"));
    const card = cards[index];
    if (!card) return;
    card.scrollIntoView({ behavior: "smooth", block: "center" });
    card.classList.add("product-card-featured");
    setTimeout(() => card.classList.remove("product-card-featured"), 1600);
  }

  function mountPanel() {
    const checkout = document.getElementById("checkout");
    const checkoutGrid = checkout?.querySelector(".checkout-grid");
    if (!checkout || !checkoutGrid) return;

    let panel = document.getElementById(panelId);
    if (!panel) {
      panel = document.createElement("section");
      panel.id = panelId;
      panel.className = "also-bought-panel";
      checkoutGrid.insertAdjacentElement("afterend", panel);
    }

    const items = recommendedProducts();
    if (!items.length) {
      panel.hidden = true;
      return;
    }

    panel.hidden = false;
    panel.innerHTML = `
      <p class="eyebrow">Sugestões</p>
      <h3>Clientes também costumam levar</h3>
      <p class="privacy-note">Complemente o pedido com itens que combinam com presentes, limpeza energética e aromas para ambiente.</p>
      <div class="also-bought-grid">
        ${items.map(item => `
          <article class="also-bought-item">
            <strong>${item.title}</strong>
            <span>${item.price}</span>
            <button type="button" data-also-bought-index="${item.index}">Ver produto</button>
          </article>
        `).join("")}
      </div>
    `;
  }

  function installEvents() {
    if (document.body?.dataset.alsoBoughtEvents === "true") return;
    if (!document.body) return;
    document.body.dataset.alsoBoughtEvents = "true";

    document.addEventListener("click", event => {
      const button = event.target?.closest?.("[data-also-bought-index]");
      if (!button) return;
      scrollToProduct(Number(button.dataset.alsoBoughtIndex));
    });
  }

  function installObservers() {
    const grid = document.querySelector("[data-product-grid]");
    const cart = document.getElementById("cartList");

    if (grid && grid.dataset.alsoBoughtObserver !== "true") {
      grid.dataset.alsoBoughtObserver = "true";
      new MutationObserver(() => requestAnimationFrame(mountPanel)).observe(grid, { childList: true, subtree: true });
    }

    if (cart && cart.dataset.alsoBoughtObserver !== "true") {
      cart.dataset.alsoBoughtObserver = "true";
      new MutationObserver(() => requestAnimationFrame(mountPanel)).observe(cart, { childList: true, subtree: true, characterData: true });
    }
  }

  function apply() {
    installStyle();
    installEvents();
    mountPanel();
    installObservers();
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

  window.misticaAlsoBought = { apply: mountPanel };
})();
