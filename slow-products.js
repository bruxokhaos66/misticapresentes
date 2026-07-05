(() => {
  const LIMIT = 20;
  const DAYS_LIMIT = 30;

  function loadCustomerMissing() {
    if (document.getElementById("customerMissingScript")) return;
    const script = document.createElement("script");
    script.id = "customerMissingScript";
    script.src = "customer-missing.js";
    script.defer = true;
    document.head.appendChild(script);
  }

  function normalize(value) {
    return String(value || "").normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase().trim();
  }

  function money(value) {
    return typeof currency !== "undefined" ? currency.format(Number(value || 0)) : `R$ ${Number(value || 0).toFixed(2).replace(".", ",")}`;
  }

  function stockList() {
    const source = typeof stock !== "undefined" && Array.isArray(stock) ? stock : [];
    return source.map(item => ({
      name: item.name || item.nome || item.product || "Produto",
      qty: Number(item.qty ?? item.quantity ?? item.quantidade ?? item.stock ?? item.estoque ?? 0),
      price: Number(String(item.price ?? item.preco ?? item.valor ?? 0).replace(",", ".")) || 0,
      category: item.category || item.categoria || "Sem categoria",
    })).filter(item => item.qty > 0);
  }

  function validSale(sale) {
    const status = normalize(sale?.status || sale?.situacao || "");
    return !status.includes("cancel");
  }

  function saleDate(sale) {
    const raw = sale?.date || sale?.data || sale?.createdAt || sale?.created_at || sale?.vendido_em;
    const date = raw ? new Date(raw) : null;
    return date && !Number.isNaN(date.getTime()) ? date : null;
  }

  function saleItems(sale) {
    return sale?.items || sale?.itens || sale?.produtos || [];
  }

  function soldMap() {
    const map = new Map();
    const source = typeof sales !== "undefined" && Array.isArray(sales) ? sales : [];
    source.filter(validSale).forEach(sale => {
      const date = saleDate(sale);
      saleItems(sale).forEach(item => {
        const name = item.name || item.nome || item.product || item.produto || "";
        const key = normalize(name);
        if (!key) return;
        const qty = Number(item.qty || item.quantity || item.quantidade || item.qtd || 1);
        const current = map.get(key) || { qty: 0, last: null };
        current.qty += qty;
        if (date && (!current.last || date > current.last)) current.last = date;
        map.set(key, current);
      });
    });
    return map;
  }

  function daysSince(date) {
    if (!date) return null;
    return Math.floor((Date.now() - date.getTime()) / (24 * 60 * 60 * 1000));
  }

  function slowProducts() {
    const sold = soldMap();
    return stockList().map(product => {
      const info = sold.get(normalize(product.name));
      const days = daysSince(info?.last);
      return { ...product, soldQty: info?.qty || 0, last: info?.last || null, days };
    }).filter(product => product.soldQty === 0 || product.days === null || product.days >= DAYS_LIMIT)
      .sort((a, b) => (b.days ?? 9999) - (a.days ?? 9999) || b.qty - a.qty)
      .slice(0, LIMIT);
  }

  function lastText(product) {
    if (!product.last) return "Nunca vendido";
    return `Última venda há ${product.days} dia(s)`;
  }

  function message() {
    const list = slowProducts();
    if (!list.length) return "Produtos encalhados - Mística Presentes\n\nNenhum produto parado encontrado.";
    return `Produtos encalhados - Mística Presentes\n\n${list.map((item, index) => `${index + 1}. ${item.name} - estoque ${item.qty} - ${lastText(item)}`).join("\n")}`;
  }

  async function copyList() {
    const text = message();
    try {
      await navigator.clipboard.writeText(text);
      alert("Lista de produtos encalhados copiada.");
    } catch {
      prompt("Copie a lista de produtos encalhados:", text);
    }
  }

  function render() {
    const content = document.getElementById("slowProductsContent");
    if (!content) return;
    const list = slowProducts();
    if (!list.length) {
      content.innerHTML = `<div class="history-item"><span>Nenhum produto encalhado encontrado.</span></div>`;
      return;
    }
    content.innerHTML = list.map(item => `
      <div class="history-item">
        <strong>${item.name}</strong>
        <span>${item.category} • Estoque: ${item.qty} • ${money(item.price)}</span>
        <span>${lastText(item)} • Vendido: ${item.soldQty} un.</span>
      </div>
    `).join("");
  }

  function mount() {
    const admin = document.getElementById("adminContent");
    if (!admin || document.getElementById("slowProductsPanel")) return;
    const panel = document.createElement("section");
    panel.id = "slowProductsPanel";
    panel.className = "form-panel admin-report-panel";
    panel.innerHTML = `
      <p class="eyebrow">Estoque</p>
      <h2>Produtos encalhados</h2>
      <p class="privacy-note">Produtos com estoque parado há ${DAYS_LIMIT} dias ou sem venda registrada.</p>
      <div class="report-export-actions">
        <button class="btn btn-ghost" type="button" data-refresh-slow>Atualizar encalhados</button>
        <button class="btn" type="button" data-copy-slow>Copiar lista</button>
      </div>
      <div id="slowProductsContent" class="history-list"></div>
    `;
    const restock = document.getElementById("restockListPanel");
    if (restock?.nextSibling) admin.insertBefore(panel, restock.nextSibling);
    else admin.appendChild(panel);
    panel.querySelector("[data-refresh-slow]").addEventListener("click", render);
    panel.querySelector("[data-copy-slow]").addEventListener("click", copyList);
    render();
  }

  window.misticaSlowProducts = { render, list: slowProducts, message, copyList };
  window.addEventListener("load", () => {
    mount();
    loadCustomerMissing();
  });
})();
