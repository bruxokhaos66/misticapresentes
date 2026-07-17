// Isis 2.0 — Widget (camada de interface).
//
// Renderiza um assistente flutuante independente do chat legado
// (#isisChat/#isisForm, mantido intacto por isis-guided.js). Consome
// somente os módulos do namespace window.Isis2 — nenhuma regra de
// negócio mora aqui, só apresentação e eventos de UI.
(() => {
  window.Isis2 = window.Isis2 || {};
  if (window.Isis2.Widget) return;

  const OPEN_STORAGE_KEY = "isis2_ui_open";
  let els = {};
  let mounted = false;

  function escapeHtml(value) {
    return String(value || "").replace(/[&<>"']/g, char => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[char]));
  }

  function productLink(product) {
    return `produto.html?id=${encodeURIComponent(product.id)}`;
  }

  function buildDom() {
    const root = document.createElement("div");
    root.id = "isis2-root";
    root.innerHTML = `
      <button id="isis2-toggle" class="isis2-fab" type="button" aria-expanded="false" aria-controls="isis2-panel" aria-label="Abrir assistente Isis">
        <span class="isis2-fab-avatar" aria-hidden="true">🔮</span>
        <span class="isis2-fab-label">Fale com a Isis</span>
      </button>
      <section id="isis2-panel" class="isis2-panel" role="dialog" aria-label="Conversa com a Isis, consultora virtual" hidden>
        <header class="isis2-header">
          <span class="isis2-avatar" aria-hidden="true">🔮</span>
          <div class="isis2-header-copy">
            <strong>Isis</strong>
            <small>Consultora virtual da Mística</small>
          </div>
          <button type="button" class="isis2-minimize" aria-label="Minimizar conversa com a Isis">–</button>
        </header>
        <div id="isis2-messages" class="isis2-messages" role="log" aria-live="polite" aria-relevant="additions"></div>
        <div id="isis2-typing" class="isis2-typing" hidden aria-hidden="true">
          <span></span><span></span><span></span>
        </div>
        <div id="isis2-quick-replies" class="isis2-quick-replies" aria-label="Sugestões rápidas"></div>
        <form id="isis2-form" class="isis2-form">
          <label class="sr-only" for="isis2-input">Mensagem para a Isis</label>
          <input id="isis2-input" type="text" autocomplete="off" placeholder="Ex.: quero um incenso para relaxar" />
          <button type="submit" aria-label="Enviar mensagem">➤</button>
        </form>
      </section>
    `;
    document.body.appendChild(root);
    return {
      root,
      toggle: root.querySelector("#isis2-toggle"),
      panel: root.querySelector("#isis2-panel"),
      minimize: root.querySelector(".isis2-minimize"),
      messages: root.querySelector("#isis2-messages"),
      typing: root.querySelector("#isis2-typing"),
      quickReplies: root.querySelector("#isis2-quick-replies"),
      form: root.querySelector("#isis2-form"),
      input: root.querySelector("#isis2-input"),
    };
  }

  function scrollToBottom() {
    els.messages.scrollTop = els.messages.scrollHeight;
  }

  function appendMessage(role, html) {
    const bubble = document.createElement("div");
    bubble.className = `isis2-message isis2-message-${role}`;
    bubble.innerHTML = html;
    els.messages.appendChild(bubble);
    scrollToBottom();
    return bubble;
  }

  function renderProductCard(product, reason) {
    const knowledge = window.Isis2.ProductKnowledge;
    const rating = knowledge.ratingOf(product);
    const ratingHtml = rating ? `<span class="isis2-card-rating">★ ${rating.media.toFixed(1)} (${rating.total})</span>` : "";
    return `
      <li class="isis2-card">
        <div class="isis2-card-icon" aria-hidden="true">${escapeHtml(product.icon || "🔮")}</div>
        <div class="isis2-card-body">
          <strong>${escapeHtml(product.name)}</strong>
          <span class="isis2-card-price">${escapeHtml(knowledge.formatPrice(product.price))}</span>
          ${ratingHtml}
          ${reason ? `<p class="isis2-card-reason">Escolhi este produto porque ${escapeHtml(reason)}.</p>` : ""}
          <div class="isis2-card-actions">
            <a class="isis2-btn isis2-btn-ghost" href="${productLink(product)}" data-isis2-view="${escapeHtml(product.id)}">Ver produto</a>
            <button type="button" class="isis2-btn" data-isis2-add="${escapeHtml(product.id)}">Adicionar ao carrinho</button>
          </div>
        </div>
      </li>
    `;
  }

  function renderComplements(complements) {
    if (!complements || !complements.length) return "";
    const items = complements.map(row => `
      <li class="isis2-complement">
        <span>+ ${escapeHtml(row.product.name)} <em>(${escapeHtml(row.reason)})</em></span>
        <button type="button" class="isis2-btn isis2-btn-small" data-isis2-add="${escapeHtml(row.product.id)}">Adicionar</button>
      </li>
    `).join("");
    return `<p class="isis2-followup-label">Também combina com:</p><ul class="isis2-complements">${items}</ul>`;
  }

  function renderQuickReplies(quickReplies) {
    els.quickReplies.innerHTML = (quickReplies || []).map(item =>
      `<button type="button" class="isis2-chip" data-isis2-intent="${escapeHtml(item.id)}">${escapeHtml(item.label)}</button>`
    ).join("");
  }

  function renderCartHint() {
    const assistant = window.Isis2.CartAssistant;
    if (!assistant || !assistant.available() || assistant.itemCount() <= 0) return "";
    return `<p class="isis2-cart-hint">Seu carrinho está em ${escapeHtml(assistant.formattedSubtotal())}. <button type="button" class="isis2-link" id="isis2-checkout-suggest">Quer finalizar a compra?</button></p>`;
  }

  function renderReply(reply) {
    const productsHtml = reply.products?.length
      ? `<ul class="isis2-card-list">${reply.products.map(product => renderProductCard(product, reply.reasons?.[product.id])).join("")}</ul>`
      : "";
    const html = `<p>${escapeHtml(reply.text)}</p>${productsHtml}${renderComplements(reply.complements)}${renderCartHint()}`;
    appendMessage("bot", html);
    renderQuickReplies(reply.quickReplies);
  }

  function showTyping(show) {
    els.typing.hidden = !show;
    if (show) scrollToBottom();
  }

  function respondTo(replyFactory) {
    showTyping(true);
    window.setTimeout(() => {
      showTyping(false);
      const reply = replyFactory();
      if (reply) renderReply(reply);
    }, 450);
  }

  function handleSubmit(event) {
    event.preventDefault();
    const value = els.input.value.trim();
    if (!value) return;
    appendMessage("user", escapeHtml(value));
    els.form.reset();
    respondTo(() => window.Isis2.ConversationManager.handleUserMessage(value));
  }

  function handlePanelClick(event) {
    const addButton = event.target.closest("[data-isis2-add]");
    if (addButton) {
      const id = addButton.dataset.isis2Add;
      const result = window.Isis2.CartAssistant.add(id);
      window.Isis2.Analytics.track("recommendation_clicked", { item_id: id, action: "add_to_cart" });
      if (result.ok) {
        addButton.textContent = "Adicionado ✓";
        addButton.disabled = true;
      }
      return;
    }
    const viewLink = event.target.closest("[data-isis2-view]");
    if (viewLink) {
      window.Isis2.Analytics.track("recommendation_clicked", { item_id: viewLink.dataset.isis2View, action: "view_product" });
      return;
    }
    const intentChip = event.target.closest("[data-isis2-intent]");
    if (intentChip) {
      const intentId = intentChip.dataset.isis2Intent;
      const intent = window.Isis2.IntentEngine.INTENTS.find(item => item.id === intentId);
      if (intent) appendMessage("user", escapeHtml(intent.label));
      respondTo(() => window.Isis2.ConversationManager.handleIntentShortcut(intentId));
      return;
    }
    if (event.target.closest("#isis2-checkout-suggest")) {
      const suggestion = window.Isis2.CartAssistant.suggestCheckout();
      closePanel();
      suggestion.scrollTo();
    }
  }

  function persistOpenState(open) {
    try {
      window.sessionStorage.setItem(OPEN_STORAGE_KEY, open ? "1" : "0");
    } catch {
      /* ignora indisponibilidade de storage */
    }
  }

  function openPanel() {
    els.panel.hidden = false;
    els.toggle.setAttribute("aria-expanded", "true");
    els.root.classList.add("isis2-open");
    persistOpenState(true);
    window.setTimeout(() => els.input.focus(), 50);
    if (!els.messages.childElementCount) {
      respondTo(() => window.Isis2.ConversationManager.startConversation());
    }
  }

  function closePanel() {
    els.panel.hidden = true;
    els.toggle.setAttribute("aria-expanded", "false");
    els.root.classList.remove("isis2-open");
    persistOpenState(false);
  }

  function togglePanel() {
    if (els.panel.hidden) openPanel();
    else closePanel();
  }

  function handleKeydown(event) {
    if (event.key === "Escape" && !els.panel.hidden) closePanel();
  }

  function mount() {
    if (mounted) return;
    mounted = true;
    els = buildDom();
    els.toggle.addEventListener("click", togglePanel);
    els.minimize.addEventListener("click", closePanel);
    els.form.addEventListener("submit", handleSubmit);
    els.panel.addEventListener("click", handlePanelClick);
    document.addEventListener("keydown", handleKeydown);

    let startedOpen = false;
    try {
      startedOpen = window.sessionStorage.getItem(OPEN_STORAGE_KEY) === "1";
    } catch {
      /* ignora indisponibilidade de storage */
    }
    if (startedOpen) openPanel();
  }

  window.Isis2.Widget = { mount };
})();
