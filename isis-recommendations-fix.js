(() => {
  const styleId = "misticaIsisRecommendationsStyle";
  const panelId = "isisRecommendationsPanel";

  function installStyle() {
    if (document.getElementById(styleId)) return;

    const style = document.createElement("style");
    style.id = styleId;
    style.textContent = `
      .isis-recommendations-panel {
        position: relative;
        overflow: hidden;
        margin-top: 18px;
        border: 1px solid rgba(240,197,106,.24);
        border-radius: 26px;
        padding: clamp(16px, 2.4vw, 22px);
        background:
          radial-gradient(circle at 14% 8%, rgba(240,197,106,.13), transparent 32%),
          radial-gradient(circle at 86% 0, rgba(184,201,119,.10), transparent 28%),
          rgba(3,3,5,.22);
        box-shadow: 0 20px 62px rgba(0,0,0,.20);
      }

      .isis-recommendations-panel::before {
        content: "";
        position: absolute;
        inset: 0;
        pointer-events: none;
        background: linear-gradient(135deg, rgba(255,248,230,.07), transparent 46%, rgba(184,201,119,.05));
      }

      .isis-recommendations-panel > * {
        position: relative;
        z-index: 1;
      }

      .isis-recommendations-panel h3 {
        margin: 5px 0 8px;
        font-family: Cinzel, Georgia, serif;
        letter-spacing: .05em;
      }

      .isis-recommendations-panel p {
        color: #e5d8bf;
      }

      .isis-recommendations-grid {
        display: grid;
        grid-template-columns: repeat(3, minmax(0, 1fr));
        gap: 10px;
        margin-top: 14px;
      }

      .isis-recommendation-card {
        display: grid;
        gap: 9px;
        border: 1px solid rgba(240,197,106,.18);
        border-radius: 20px;
        padding: 13px;
        background: rgba(255,248,230,.045);
      }

      .isis-recommendation-card strong {
        color: #fff4d6;
        line-height: 1.2;
      }

      .isis-recommendation-card span {
        color: #f0c56a;
        font-weight: 900;
      }

      .isis-recommendation-card small {
        color: #cfc2ad;
        line-height: 1.35;
        font-weight: 650;
      }

      .isis-recommendation-card button {
        min-height: 38px;
        border: 1px solid rgba(184,201,119,.42);
        border-radius: 999px;
        background: rgba(184,201,119,.08);
        color: #dfeab2;
        cursor: pointer;
        font-weight: 900;
      }

      @media (max-width: 880px) {
        .isis-recommendations-grid {
          grid-template-columns: 1fr;
        }
      }
    `;

    document.head.appendChild(style);
  }

  function productInfo(card, index) {
    const title = card.querySelector("h3")?.textContent?.trim() || `Produto ${index + 1}`;
    const price = card.querySelector(".product-price")?.textContent?.trim() || "Ver preço";
    const text = card.textContent.toLowerCase();
    let reason = "Boa opção para presentear com significado.";

    if (/incenso|aroma|essência|oleo|óleo|difusor/.test(text)) reason = "Indicado para aroma, ambiente e bem-estar.";
    else if (/cristal|pedra|quartzo|ametista/.test(text)) reason = "Indicado para energia, proteção e decoração.";
    else if (/vela|banho|erva|ritual/.test(text)) reason = "Indicado para intenção, limpeza e ritual.";

    return { title, price, reason, index };
  }

  function recommendations() {
    const cards = Array.from(document.querySelectorAll("[data-product-grid] .product-card"));
    if (!cards.length) return [];

    const preferred = cards.filter(card => /incenso|cristal|vela|aroma|banho|energia|proteção|presente/i.test(card.textContent));
    const source = preferred.length >= 3 ? preferred : cards;
    return source.slice(0, 3).map((card) => productInfo(card, cards.indexOf(card)));
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
    const isisPanel = document.querySelector("#isis .isis-chat-panel");
    if (!isisPanel) return;

    let panel = document.getElementById(panelId);
    if (!panel) {
      panel = document.createElement("section");
      panel.id = panelId;
      panel.className = "isis-recommendations-panel";
      const quickActions = isisPanel.querySelector(".quick-actions");
      if (quickActions) quickActions.insertAdjacentElement("afterend", panel);
      else isisPanel.appendChild(panel);
    }

    const items = recommendations();
    if (!items.length) {
      panel.hidden = true;
      return;
    }

    panel.hidden = false;
    panel.innerHTML = `
      <p class="eyebrow">Curadoria da Isis</p>
      <h3>Produtos recomendados para hoje</h3>
      <p>A Isis destaca opções da vitrine para ajudar o cliente a escolher com mais facilidade.</p>
      <div class="isis-recommendations-grid">
        ${items.map(item => `
          <article class="isis-recommendation-card">
            <strong>${item.title}</strong>
            <span>${item.price}</span>
            <small>${item.reason}</small>
            <button type="button" data-isis-product-index="${item.index}">Ver produto</button>
          </article>
        `).join("")}
      </div>
    `;
  }

  function installEvents() {
    if (document.body?.dataset.isisRecommendationsEvents === "true") return;
    if (!document.body) return;
    document.body.dataset.isisRecommendationsEvents = "true";

    document.addEventListener("click", event => {
      const button = event.target?.closest?.("[data-isis-product-index]");
      if (!button) return;
      scrollToProduct(Number(button.dataset.isisProductIndex));
    });
  }

  function installObserver() {
    const grid = document.querySelector("[data-product-grid]");
    if (!grid || grid.dataset.isisRecommendationsObserver === "true") return;

    grid.dataset.isisRecommendationsObserver = "true";
    new MutationObserver(() => requestAnimationFrame(mountPanel)).observe(grid, { childList: true, subtree: true });
  }

  function apply() {
    installStyle();
    installEvents();
    mountPanel();
    installObserver();
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

  window.misticaIsisRecommendations = { apply: mountPanel };
})();
