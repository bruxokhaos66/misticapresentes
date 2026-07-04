(() => {
  function money(value) {
    return typeof currency !== "undefined" ? currency.format(Number(value || 0)) : `R$ ${Number(value || 0).toFixed(2).replace(".", ",")}`;
  }

  function normalize(value) {
    return String(value || "").normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase();
  }

  function dateValue(value) {
    const date = value ? new Date(value) : null;
    return date && !Number.isNaN(date.getTime()) ? date : null;
  }

  function inputDate(date) {
    return date.toISOString().slice(0, 10);
  }

  function filteredSales() {
    if (typeof sales === "undefined" || !Array.isArray(sales)) return [];
    const startValue = document.getElementById("reportStart")?.value;
    const endValue = document.getElementById("reportEnd")?.value;
    const statusValue = document.getElementById("reportStatus")?.value || "todos";
    const start = startValue ? new Date(`${startValue}T00:00:00`) : null;
    const end = endValue ? new Date(`${endValue}T23:59:59`) : null;
    const status = normalize(statusValue);

    return sales.filter(sale => {
      const date = dateValue(sale.date);
      if (!date) return false;
      if (start && date < start) return false;
      if (end && date > end) return false;
      if (status !== "todos" && !normalize(sale.status).includes(status)) return false;
      return true;
    });
  }

  function countByStatus(list) {
    return list.reduce((map, sale) => {
      const status = sale.status || "Sem status";
      map[status] = (map[status] || 0) + 1;
      return map;
    }, {});
  }

  function renderReport() {
    const content = document.getElementById("salesReportContent");
    if (!content) return;
    const list = filteredSales();
    const total = list.reduce((sum, sale) => sum + Number(sale.total || 0), 0);
    const average = list.length ? total / list.length : 0;
    const byStatus = countByStatus(list);
    const statusRows = Object.entries(byStatus).length
      ? Object.entries(byStatus).map(([status, count]) => `<div class="report-row"><span>${status}</span><strong>${count}</strong></div>`).join("")
      : `<div class="report-row"><span>Nenhum status encontrado</span><strong>0</strong></div>`;
    const saleRows = list.slice(0, 10).map(sale => `
      <div class="report-row">
        <span>${sale.id || "Pedido"} • ${sale.status || "Sem status"}</span>
        <strong>${money(sale.total)}</strong>
      </div>
    `).join("") || `<div class="report-row"><span>Nenhuma venda no período</span><strong>${money(0)}</strong></div>`;

    content.innerHTML = `
      <div class="report-grid">
        <div class="report-card"><span>Total vendido</span><strong>${money(total)}</strong><small>Dentro do período filtrado</small></div>
        <div class="report-card"><span>Pedidos</span><strong>${list.length}</strong><small>Quantidade de vendas</small></div>
        <div class="report-card"><span>Ticket médio</span><strong>${money(average)}</strong><small>Média por pedido</small></div>
        <div class="report-card"><span>Status</span><strong>${document.getElementById("reportStatus")?.selectedOptions?.[0]?.textContent || "Todos"}</strong><small>Filtro atual</small></div>
      </div>
      <div class="report-columns">
        <section><h3>Vendas por status</h3><div class="report-list">${statusRows}</div></section>
        <section><h3>Últimas vendas do filtro</h3><div class="report-list">${saleRows}</div></section>
      </div>
    `;
  }

  function mountReport() {
    const admin = document.getElementById("adminContent");
    if (!admin || document.getElementById("salesReportPanel")) return;
    const today = new Date();
    const monthStart = new Date(today.getFullYear(), today.getMonth(), 1);
    const panel = document.createElement("div");
    panel.id = "salesReportPanel";
    panel.className = "form-panel admin-report-panel";
    panel.innerHTML = `
      <p class="eyebrow">Relatórios</p>
      <h2>Vendas por período</h2>
      <div class="report-filters">
        <label>Data inicial<input id="reportStart" type="date" value="${inputDate(monthStart)}"></label>
        <label>Data final<input id="reportEnd" type="date" value="${inputDate(today)}"></label>
        <label>Status<select id="reportStatus">
          <option value="todos">Todos</option>
          <option value="aguardando pagamento">Aguardando pagamento</option>
          <option value="pago">Pago</option>
          <option value="em separacao">Em separação</option>
          <option value="pronto para retirada">Pronto para retirada</option>
          <option value="entregue">Entregue</option>
          <option value="cancelado">Cancelado</option>
        </select></label>
      </div>
      <div class="report-export-actions">
        <button class="btn" type="button" data-refresh-sales-report>Atualizar relatório</button>
      </div>
      <div id="salesReportContent" class="admin-report-content"></div>
    `;
    const dashboard = admin.querySelector(".dashboard-grid");
    if (dashboard?.nextSibling) admin.insertBefore(panel, dashboard.nextSibling);
    else admin.prepend(panel);
    panel.querySelectorAll("input, select").forEach(input => input.addEventListener("change", renderReport));
    panel.querySelector("[data-refresh-sales-report]").addEventListener("click", renderReport);
    renderReport();
  }

  window.misticaSalesReport = {
    render: renderReport,
    getFilteredSales: filteredSales,
  };

  window.addEventListener("load", mountReport);
})();
