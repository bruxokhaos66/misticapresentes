(() => {
  function money(value) {
    return typeof currency !== "undefined" ? currency.format(Number(value || 0)) : `R$ ${Number(value || 0).toFixed(2).replace(".", ",")}`;
  }

  function normalizeStatus(value) {
    return String(value || "").normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase();
  }

  function validSale(sale) {
    return !normalizeStatus(sale?.status).includes("cancel");
  }

  function buildRanking() {
    if (typeof sales === "undefined" || !Array.isArray(sales)) return [];
    const map = new Map();
    sales.filter(validSale).forEach(sale => {
      (sale.items || []).forEach(item => {
        const name = item.name || "Item";
        const qty = Number(item.qty || item.quantidade || 1);
        const revenue = Number(item.price || 0) * qty;
        const current = map.get(name) || { name, qty: 0, revenue: 0 };
        current.qty += qty;
        current.revenue += revenue;
        map.set(name, current);
      });
    });
    return Array.from(map.values()).sort((a, b) => b.qty - a.qty || b.revenue - a.revenue).slice(0, 15);
  }

  function renderTopProducts() {
    const content = document.getElementById("topProductsContent");
    if (!content) return;
    const ranking = buildRanking();
    if (!ranking.length) {
      content.innerHTML = `<div class="history-item"><span>Nenhum produto vendido ainda.</span></div>`;
      return;
    }
    content.innerHTML = ranking.map((item, index) => `
      <div class="report-row">
        <span>${index + 1}. ${item.name}</span>
        <strong>${item.qty} un. • ${money(item.revenue)}</strong>
      </div>
    `).join("");
  }

  function message() {
    const ranking = buildRanking();
    if (!ranking.length) return "Produtos mais vendidos - Mística Presentes\n\nNenhuma venda registrada ainda.";
    return `Produtos mais vendidos - Mística Presentes\n\n${ranking.slice(0, 10).map((item, index) => `${index + 1}. ${item.name} - ${item.qty} un. - ${money(item.revenue)}`).join("\n")}`;
  }

  async function copyRanking() {
    const text = message();
    try {
      await navigator.clipboard.writeText(text);
      alert("Ranking de produtos copiado.");
    } catch {
      prompt("Copie o ranking:", text);
    }
  }

  function mountTopProducts() {
    const admin = document.getElementById("adminContent");
    if (!admin || document.getElementById("topProductsPanel")) return;
    const panel = document.createElement("section");
    panel.id = "topProductsPanel";
    panel.className = "form-panel admin-report-panel";
    panel.innerHTML = `
      <p class="eyebrow">Produtos</p>
      <h2>Produtos mais vendidos</h2>
      <p class="privacy-note">Ranking baseado nas vendas registradas, ignorando pedidos cancelados.</p>
      <div class="report-export-actions">
        <button class="btn btn-ghost" type="button" data-refresh-top-products>Atualizar ranking</button>
        <button class="btn" type="button" data-copy-top-products>Copiar ranking</button>
      </div>
      <div id="topProductsContent" class="report-list"></div>
    `;
    const restock = document.getElementById("restockListPanel");
    if (restock?.nextSibling) admin.insertBefore(panel, restock.nextSibling);
    else admin.appendChild(panel);
    panel.querySelector("[data-refresh-top-products]").addEventListener("click", renderTopProducts);
    panel.querySelector("[data-copy-top-products]").addEventListener("click", copyRanking);
    renderTopProducts();
  }

  window.misticaTopProducts = {
    render: renderTopProducts,
    ranking: buildRanking,
    message,
  };

  window.addEventListener("load", mountTopProducts);
})();
