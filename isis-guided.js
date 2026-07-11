(() => {
  if (window.__MISTICA_ISIS_GUIDED__) return;
  window.__MISTICA_ISIS_GUIDED__ = true;

  const INTENTS = [
    { id: "protecao", label: "Proteção", keywords: ["protec", "proteg", "energia ruim", "mau olhado", "mau-olhado", "descarrego", "olho gordo"], terms: ["protec", "proteg", "limpeza", "descarrego"] },
    { id: "amor", label: "Amor", keywords: ["amor", "paix", "relacionamento", "atrair amor"], terms: ["amor", "paix"] },
    { id: "prosperidade", label: "Prosperidade", keywords: ["prosperidade", "dinheiro", "abund", "trabalho", "sorte", "riqueza"], terms: ["prosperidade", "abund", "sorte", "fe e bencao"] },
    { id: "calma", label: "Calma e sono", keywords: ["ansiedade", "calma", "dormir", "relax", "estresse", "stress", "sono"], terms: ["calma", "relax", "banho", "erva"] },
    { id: "fe", label: "Fé e oração", keywords: ["fe ", "fé", "oracao", "oração", "benc", "espiritual"], terms: ["fe", "benc", "oracao", "vela"] },
    { id: "presente", label: "Presente", keywords: ["presente", "presentear", "aniversario", "aniversário", "kit", "surpresa"], terms: ["presente", "kit"] },
    { id: "aromas", label: "Aromas", keywords: ["aroma", "perfume", "incenso", "cheiro"], terms: ["aroma", "incenso", "perfume"] },
  ];

  function normalize(value) {
    return String(value || "").normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase();
  }

  function detectIntent(text) {
    const norm = normalize(text);
    return INTENTS.find(intent => intent.keywords.some(keyword => norm.includes(normalize(keyword)))) || null;
  }

  function availableQty(product) {
    try { return typeof getStock === "function" ? getStock(product.id) : Number(product.stock || 0); } catch { return Number(product.stock || 0); }
  }

  function money(value) {
    try { return currency.format(Number(value || 0)); } catch { return `R$ ${Number(value || 0).toFixed(2)}`; }
  }

  function searchProducts(terms) {
    if (typeof products === "undefined" || !Array.isArray(products)) return [];
    const normTerms = terms.map(normalize).filter(Boolean);
    if (!normTerms.length) return [];
    return products
      .filter(product => availableQty(product) > 0)
      .map(product => {
        const text = normalize(`${product.name} ${product.description} ${product.category}`);
        const score = normTerms.filter(term => text.includes(term)).length;
        return { product, score };
      })
      .filter(row => row.score > 0)
      .sort((a, b) => b.score - a.score)
      .slice(0, 3)
      .map(row => row.product);
  }

  function productLink(product) {
    return `produto.html?id=${encodeURIComponent(product.id)}`;
  }

  function chat() {
    return document.querySelector("#isisChat");
  }

  function appendUser(text) {
    const box = document.createElement("div");
    box.className = "isis-message user";
    box.textContent = text;
    chat()?.appendChild(box);
    scrollChat();
  }

  function appendBotHtml(html) {
    const box = document.createElement("div");
    box.className = "isis-message bot";
    box.innerHTML = html;
    chat()?.appendChild(box);
    scrollChat();
    return box;
  }

  function scrollChat() {
    const el = chat();
    if (el) el.scrollTop = el.scrollHeight;
  }

  function escapeHtml(value) {
    return String(value || "").replace(/[&<>"']/g, char => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[char]));
  }

  function renderRecommendations(found) {
    if (!found.length) {
      return `<p>Ainda não encontrei um produto certeiro para isso. Me conte um pouco mais (ex.: "quero algo para proteção" ou "presente para minha mãe") ou escolha uma intenção abaixo.</p>${renderFollowupChips()}`;
    }
    const items = found.map(product => `
      <li class="isis-recommend-item">
        <strong>${escapeHtml(product.name)}</strong>
        <span>${money(product.price)}</span>
        <div class="isis-recommend-actions">
          <a class="btn btn-small" href="${productLink(product)}">Ver produto</a>
          <button class="btn btn-ghost btn-small" type="button" data-isis-add="${escapeHtml(product.id)}">Adicionar ao carrinho</button>
        </div>
      </li>
    `).join("");
    return `<p>Encontrei estas opções para você:</p><ul class="isis-recommend-list">${items}</ul>${renderFollowupChips()}`;
  }

  function renderFollowupChips() {
    const chips = INTENTS.map(intent => `<button type="button" class="v2-chip" data-isis-followup="${intent.id}">${intent.label}</button>`).join("");
    return `<p class="isis-followup-label">Buscar por outra intenção:</p><div class="isis-followup-chips">${chips}</div>`;
  }

  function handleMessage(text) {
    if (!text || !text.trim()) return;
    appendUser(text);
    const intent = detectIntent(text);
    const terms = intent ? intent.terms : normalize(text).split(/\s+/).filter(word => word.length > 2);
    const found = searchProducts(terms);
    appendBotHtml(renderRecommendations(found));
  }

  function handleIntent(intentId) {
    const intent = INTENTS.find(item => item.id === intentId);
    if (!intent) return;
    appendUser(intent.label);
    const found = searchProducts(intent.terms);
    appendBotHtml(renderRecommendations(found));
  }

  function installChatDelegation() {
    const el = chat();
    if (!el || el.dataset.isisGuidedReady) return;
    el.dataset.isisGuidedReady = "true";
    el.addEventListener("click", event => {
      const addButton = event.target.closest("[data-isis-add]");
      if (addButton && typeof addToCart === "function") {
        addToCart(addButton.dataset.isisAdd);
        return;
      }
      const followupButton = event.target.closest("[data-isis-followup]");
      if (followupButton) {
        handleIntent(followupButton.dataset.isisFollowup);
      }
    });
  }

  function installForm() {
    const form = document.querySelector("#isisForm");
    const input = document.querySelector("#isisInput");
    if (!form || !input || form.dataset.isisGuidedReady) return;
    form.dataset.isisGuidedReady = "true";
    form.dataset.isisCommerce = "1";
    form.addEventListener("submit", event => {
      event.preventDefault();
      const value = input.value;
      handleMessage(value);
      form.reset();
    });
  }

  function installQuickActions() {
    document.querySelectorAll("[data-isis-command]").forEach(button => {
      if (button.dataset.isisGuidedReady) return;
      button.dataset.isisGuidedReady = "true";
      button.addEventListener("click", () => handleMessage(button.dataset.isisCommand || button.textContent));
    });
  }

  function welcomeMessage() {
    const el = chat();
    if (!el || el.dataset.isisWelcomeShown) return;
    el.dataset.isisWelcomeShown = "true";
    appendBotHtml(`<p>Olá! Eu sou a Isis. Me conte o que você procura (ex.: "presente para minha mãe", "algo para proteção") ou escolha uma intenção abaixo.</p>${renderFollowupChips()}`);
  }

  function apply() {
    installChatDelegation();
    installForm();
    installQuickActions();
    welcomeMessage();
  }

  function schedule() {
    apply();
    window.setTimeout(apply, 250);
    window.setTimeout(apply, 900);
    window.setTimeout(apply, 1600);
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", schedule, { once: true });
  else schedule();
})();
