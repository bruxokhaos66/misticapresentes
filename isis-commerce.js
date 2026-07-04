(() => {
  const cfg = window.misticaSiteConfig || {};
  const API_BASE = (cfg.apiBaseUrl || "https://api.misticaesotericos.com.br").replace(/\/$/, "");

  const intents = [
    { key: "protecao", label: "Proteção", terms: ["prote", "defesa", "olho", "energia pesada", "arruda", "sálvia", "salvia", "limpeza"] },
    { key: "limpeza", label: "Limpeza energética", terms: ["limpeza", "limpar", "defum", "banho", "erva", "incenso", "sal"] },
    { key: "presente", label: "Presente", terms: ["presente", "lembrança", "lembranca", "kit", "especial", "aniversario", "aniversário"] },
    { key: "relaxar", label: "Relaxamento", terms: ["relax", "calma", "sono", "descanso", "aroma", "lavanda", "difusor"] },
    { key: "amor", label: "Amor e harmonia", terms: ["amor", "harmonia", "casal", "rosa", "autoestima"] },
    { key: "prosperidade", label: "Prosperidade", terms: ["prosper", "dinheiro", "abund", "sucesso", "canela"] },
    { key: "cristais", label: "Cristais", terms: ["cristal", "pedra", "quartzo", "ametista", "pirita"] },
    { key: "velas", label: "Velas", terms: ["vela", "ritual", "chama", "intenção", "intencao"] },
    { key: "incensos", label: "Incensos", terms: ["incenso", "aroma", "defumação", "defumacao"] },
  ];

  function clean(value) {
    return String(value || "").normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase();
  }

  function money(value) {
    try { return currency.format(Number(value || 0)); } catch { return `R$ ${Number(value || 0).toFixed(2)}`; }
  }

  async function fetchProducts() {
    try {
      const response = await fetch(`${API_BASE}/api/produtos?limite=500`);
      if (!response.ok) throw new Error(`API ${response.status}`);
      const data = await response.json();
      if (!Array.isArray(data)) return [];
      return data.map(item => ({
        id: `api-${item.id}`,
        apiId: item.id,
        codigo: item.codigo_p || String(item.id),
        name: item.nome || "Produto",
        category: item.categoria || "Produtos",
        description: item.descricao || "Produto da Mística Presentes.",
        price: Number(item.preco || 0),
        stock: Number(item.quantidade || 0),
        tag: item.selo || "",
        imageUrl: item.imagem_url || "",
        images: Array.isArray(item.imagens) ? item.imagens : [],
      }));
    } catch {
      return Array.isArray(window.products) ? window.products : [];
    }
  }

  function productText(product) {
    return clean(`${product.name} ${product.category} ${product.description} ${product.tag || ""}`);
  }

  function detectIntent(text) {
    const query = clean(text);
    return intents.find(intent => intent.terms.some(term => query.includes(clean(term)))) || null;
  }

  function scoreProduct(product, intent, query) {
    const text = productText(product);
    let score = 0;
    if (intent) score += intent.terms.filter(term => text.includes(clean(term))).length * 4;
    clean(query).split(/\s+/).filter(word => word.length > 2).forEach(word => {
      if (text.includes(word)) score += 1;
    });
    if (Number(product.stock || 0) > 0) score += 2;
    if (product.tag) score += 1;
    return score;
  }

  function suggestProducts(list, query) {
    const intent = detectIntent(query);
    return [...list]
      .map(product => ({ product, score: scoreProduct(product, intent, query) }))
      .filter(row => row.score > 0)
      .sort((a, b) => b.score - a.score)
      .slice(0, 5)
      .map(row => row.product);
  }

  function addIsisMessage(role, html) {
    const chat = document.getElementById("isisChat");
    if (!chat) return;
    const div = document.createElement("div");
    div.className = `isis-message isis-${role}`;
    div.innerHTML = html;
    chat.appendChild(div);
    chat.scrollTop = chat.scrollHeight;
  }

  function addProductToCart(product) {
    if (typeof addToCart !== "function") return;
    const local = Array.isArray(products) ? products.find(item => String(item.id) === String(product.id) || String(item.apiId) === String(product.apiId)) : null;
    if (!local) return alert("Produto ainda não sincronizado na vitrine. Aguarde a sincronização e tente novamente.");
    const input = document.getElementById(`qty-${safeId(local.id)}`);
    if (input) input.value = "1";
    addToCart(local.id);
  }

  function renderSuggestions(query, suggestions) {
    if (!suggestions.length) {
      addIsisMessage("bot", "Não encontrei um produto exato agora. Posso te encaminhar pelo WhatsApp para a loja verificar opções disponíveis.");
      return;
    }

    const cards = suggestions.map(product => `
      <article class="isis-product-card">
        <strong>${product.name}</strong>
        <span>${product.category || "Produto"} • ${money(product.price)}</span>
        <small>${Number(product.stock || 0) > 0 ? "Disponível" : "Sob consulta"}${product.tag ? " • " + product.tag : ""}</small>
        <p>${product.description || "Produto selecionado pela Mística Presentes."}</p>
        <div class="isis-product-actions">
          <button class="btn btn-small" type="button" data-isis-add="${product.id}">Adicionar</button>
          <a class="btn btn-small btn-ghost" href="produto.html?id=${encodeURIComponent(product.id)}">Ver página</a>
        </div>
      </article>
    `).join("");

    const intent = detectIntent(query);
    const intro = intent
      ? `Encontrei sugestões para <strong>${intent.label}</strong>:`
      : "Encontrei estes produtos que combinam com sua busca:";
    addIsisMessage("bot", `${intro}<div class="isis-product-grid">${cards}</div>`);
  }

  async function handleQuestion(text) {
    addIsisMessage("user", text);
    const list = await fetchProducts();
    const suggestions = suggestProducts(list, text);
    renderSuggestions(text, suggestions);
  }

  function installForm() {
    const form = document.getElementById("isisForm");
    const input = document.getElementById("isisInput");
    if (!form || !input || form.dataset.isisCommerce === "1") return;
    form.dataset.isisCommerce = "1";
    form.addEventListener("submit", event => {
      event.preventDefault();
      const text = input.value.trim();
      if (!text) return;
      input.value = "";
      handleQuestion(text);
    });
  }

  function installQuickActions() {
    const area = document.querySelector(".quick-actions");
    if (!area || document.getElementById("isisCommerceActions")) return;
    const wrap = document.createElement("div");
    wrap.id = "isisCommerceActions";
    wrap.className = "quick-actions isis-commerce-actions";
    [
      "Quero proteção",
      "Quero limpar energias",
      "Quero um presente",
      "Quero algo para relaxar",
      "Cristais disponíveis",
      "Produtos em promoção",
    ].forEach(label => {
      const btn = document.createElement("button");
      btn.className = "btn btn-ghost";
      btn.type = "button";
      btn.textContent = label;
      btn.addEventListener("click", () => handleQuestion(label));
      wrap.appendChild(btn);
    });
    area.parentNode.appendChild(wrap);
  }

  function installAddButtons() {
    document.addEventListener("click", event => {
      const id = event.target?.dataset?.isisAdd;
      if (!id) return;
      const product = Array.isArray(products) ? products.find(item => String(item.id) === String(id)) : null;
      if (product) addProductToCart(product);
    });
  }

  window.misticaIsisCommerce = { ask: handleQuestion };

  window.addEventListener("load", () => {
    installForm();
    installQuickActions();
    installAddButtons();
    setTimeout(() => {
      addIsisMessage("bot", "Olá, eu sou a Isis. Posso sugerir produtos por intenção: proteção, limpeza energética, presente, relaxamento, cristais, velas ou incensos.");
    }, 900);
  });
})();
