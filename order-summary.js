(() => {
  const KEY = "misticaSpecialOrders";

  function loadOrderAgeAlert() {
    if (document.getElementById("orderAgeAlertScript")) return;
    const script = document.createElement("script");
    script.id = "orderAgeAlertScript";
    script.src = "order-age-alert.js";
    script.defer = true;
    document.head.appendChild(script);
  }

  function loadOrders() {
    try { return JSON.parse(localStorage.getItem(KEY) || "[]"); } catch { return []; }
  }

  function countByStatus() {
    const list = loadOrders();
    return list.reduce((acc, order) => {
      const status = order.status || "Sem status";
      acc.total += 1;
      acc[status] = (acc[status] || 0) + 1;
      return acc;
    }, { total: 0 });
  }

  function renderSummary() {
    const panel = document.getElementById("specialOrdersPanel");
    const list = document.getElementById("specialOrdersContent");
    if (!panel || !list) return;
    let summary = document.getElementById("orderSummaryCards");
    if (!summary) {
      summary = document.createElement("div");
      summary.id = "orderSummaryCards";
      summary.className = "report-grid";
      list.parentNode.insertBefore(summary, list);
    }
    const counts = countByStatus();
    summary.innerHTML = `
      <div class="report-card"><span>Total</span><strong>${counts.total || 0}</strong><small>Encomendas</small></div>
      <div class="report-card"><span>Pendentes</span><strong>${counts.Pendente || 0}</strong><small>Aguardando acao</small></div>
      <div class="report-card"><span>Solicitadas</span><strong>${counts.Solicitado || 0}</strong><small>Com fornecedor</small></div>
      <div class="report-card"><span>Disponiveis</span><strong>${counts.Disponivel || 0}</strong><small>Prontas</small></div>
    `;
  }

  function install() {
    renderSummary();
    const originalRender = window.misticaSpecialOrders?.render;
    if (typeof originalRender === "function" && !window.__misticaOrderSummaryInstalled) {
      window.__misticaOrderSummaryInstalled = true;
      window.misticaSpecialOrders.render = function renderWithSummary() {
        originalRender();
        renderSummary();
      };
    }
    loadOrderAgeAlert();
  }

  window.misticaOrderSummary = { render: renderSummary, counts: countByStatus };
  window.addEventListener("load", () => setTimeout(install, 300));
})();
