(() => {
  const CUSTOM_PRODUCTS_KEY = "misticaCustomProducts";
  const ENTRY_KEY = "misticaStockEntries";

  function money(value) {
    return typeof currency !== "undefined" ? currency.format(Number(value || 0)) : `R$ ${Number(value || 0).toFixed(2).replace(".", ",")}`;
  }

  function parseMoney(value) {
    return Number(String(value || "").replace(/\./g, "").replace(",", ".")) || 0;
  }

  function productList() {
    return typeof products !== "undefined" && Array.isArray(products) ? products : [];
  }

  function entries() {
    try { return JSON.parse(localStorage.getItem(ENTRY_KEY) || "[]"); } catch { return []; }
  }

  function saveEntries(list) {
    localStorage.setItem(ENTRY_KEY, JSON.stringify(list));
  }

  function updateCustomProduct(productId, patch) {
    try {
      const list = JSON.parse(localStorage.getItem(CUSTOM_PRODUCTS_KEY) || "[]");
      const next = list.map(item => item.id === productId ? { ...item, ...patch } : item);
      localStorage.setItem(CUSTOM_PRODUCTS_KEY, JSON.stringify(next));
    } catch {}
  }

  function selectOptions() {
    return productList().map(product => `<option value="${product.id}">${product.name}</option>`).join("");
  }

  function calculateMargin(cost, price) {
    if (!price) return 0;
    return ((price - cost) / price) * 100;
  }

  function applyEntry(event) {
    event.preventDefault();
    const productId = document.getElementById("stockEntryProduct")?.value;
    const qty = Number.parseInt(document.getElementById("stockEntryQty")?.value || "0", 10);
    const cost = parseMoney(document.getElementById("stockEntryCost")?.value);
    const price = parseMoney(document.getElementById("stockEntryPrice")?.value);
    const product = productList().find(item => item.id === productId);
    const status = document.getElementById("stockEntryStatus");

    if (!product || !qty || qty <= 0) {
      if (status) status.textContent = "Informe produto e quantidade validos.";
      return;
    }

    const current = Number(typeof getStock === "function" ? getStock(productId) : stock?.[productId] || product.stock || 0);
    const nextQty = current + qty;
    if (typeof stock !== "undefined") stock[productId] = nextQty;
    product.stock = nextQty;
    if (price > 0) product.price = price;
    if (cost > 0) product.cost = cost;
    product.margin = calculateMargin(cost, Number(product.price || price || 0));
    updateCustomProduct(productId, { stock: nextQty, price: product.price, cost: product.cost, margin: product.margin });

    const log = entries();
    log.unshift({ id: Date.now(), productId, name: product.name, qty, cost, price: product.price, margin: product.margin, date: new Date().toISOString() });
    saveEntries(log.slice(0, 80));

    if (typeof saveState === "function") saveState();
    if (typeof renderAll === "function") renderAll();
    if (typeof renderStock === "function") renderStock();
    renderHistory();
    if (status) status.textContent = `Entrada registrada: ${product.name} +${qty}. Estoque atual: ${nextQty}. Margem: ${product.margin.toFixed(1)}%`;
    event.target.reset();
    fillSelect();
  }

  function fillSelect() {
    const select = document.getElementById("stockEntryProduct");
    if (!select) return;
    const current = select.value;
    select.innerHTML = selectOptions();
    if ([...select.options].some(option => option.value === current)) select.value = current;
  }

  function renderHistory() {
    const content = document.getElementById("stockEntryHistory");
    if (!content) return;
    const list = entries().slice(0, 10);
    if (!list.length) {
      content.innerHTML = `<div class="history-item"><span>Nenhuma entrada registrada ainda.</span></div>`;
      return;
    }
    content.innerHTML = list.map(item => `
      <div class="history-item">
        <strong>${item.name}</strong>
        <span>Entrada: ${item.qty} un. • Custo: ${money(item.cost)} • Venda: ${money(item.price)}</span>
        <span>Margem: ${Number(item.margin || 0).toFixed(1)}% • ${new Date(item.date).toLocaleString("pt-BR")}</span>
      </div>
    `).join("");
  }

  function mount() {
    const admin = document.getElementById("adminContent");
    if (!admin || document.getElementById("stockEntryPanel")) return;
    const panel = document.createElement("section");
    panel.id = "stockEntryPanel";
    panel.className = "form-panel admin-report-panel";
    panel.innerHTML = `
      <p class="eyebrow">Estoque</p>
      <h2>Entrada de mercadoria</h2>
      <p class="privacy-note">Atualiza estoque, custo, preço de venda e margem estimada.</p>
      <form id="stockEntryForm" class="form">
        <label>Produto<select id="stockEntryProduct"></select></label>
        <label>Quantidade recebida<input id="stockEntryQty" type="number" min="1" step="1" placeholder="Ex.: 10" required></label>
        <label>Custo unitário<input id="stockEntryCost" type="text" placeholder="Ex.: 4,50"></label>
        <label>Preço de venda<input id="stockEntryPrice" type="text" placeholder="Ex.: 12,00"></label>
        <button class="btn" type="submit">Registrar entrada</button>
        <div id="stockEntryStatus" class="saved-box"></div>
      </form>
      <div id="stockEntryHistory" class="history-list"></div>
    `;
    const slow = document.getElementById("slowProductsPanel");
    if (slow?.nextSibling) admin.insertBefore(panel, slow.nextSibling);
    else admin.appendChild(panel);
    panel.querySelector("#stockEntryForm").addEventListener("submit", applyEntry);
    fillSelect();
    renderHistory();
  }

  window.misticaStockEntry = { mount, renderHistory, entries };
  window.addEventListener("load", mount);
})();
