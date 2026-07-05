(() => {
  function money(value) {
    return typeof currency !== "undefined" ? currency.format(Number(value || 0)) : `R$ ${Number(value || 0).toFixed(2).replace(".", ",")}`;
  }

  function saleTotal(sale) {
    const direct = sale?.total ?? sale?.totalAmount ?? sale?.valorTotal ?? sale?.valor_total ?? sale?.amount;
    return Number(String(direct || 0).replace(",", ".")) || 0;
  }

  function list() {
    if (window.misticaSalesReport?.getFilteredSales) return window.misticaSalesReport.getFilteredSales();
    return typeof sales !== "undefined" && Array.isArray(sales) ? sales : [];
  }

  function totals() {
    const items = list();
    const total = items.reduce((sum, sale) => sum + saleTotal(sale), 0);
    const count = items.length;
    return { total, count, average: count ? total / count : 0 };
  }

  function paymentLines() {
    return window.misticaPaymentReport?.rows?.() || [];
  }

  function message() {
    const data = totals();
    const payments = paymentLines();
    return `Fechamento de caixa - Mística Presentes\n\nTotal: ${money(data.total)}\nVendas: ${data.count}\nTicket médio: ${money(data.average)}\n\nPor pagamento:\n${payments.length ? payments.map(item => `- ${item.label}: ${money(item.total)} (${item.count})`).join("\n") : "Nenhum pagamento encontrado."}`;
  }

  async function copy() {
    const text = message();
    try {
      await navigator.clipboard.writeText(text);
      alert("Fechamento de caixa copiado.");
    } catch {
      prompt("Copie o fechamento:", text);
    }
  }

  function render() {
    const content = document.getElementById("cashClosingContent");
    if (!content) return;
    const data = totals();
    const payments = paymentLines();
    content.innerHTML = `
      <div class="report-grid">
        <div class="report-card"><span>Total do caixa</span><strong>${money(data.total)}</strong><small>Conforme filtro atual</small></div>
        <div class="report-card"><span>Vendas</span><strong>${data.count}</strong><small>Pedidos no período</small></div>
        <div class="report-card"><span>Ticket médio</span><strong>${money(data.average)}</strong><small>Média por venda</small></div>
      </div>
      <div class="report-list">
        ${payments.length ? payments.map(item => `<div class="report-row"><span>${item.label} • ${item.count}</span><strong>${money(item.total)}</strong></div>`).join("") : `<div class="report-row"><span>Sem pagamentos</span><strong>${money(0)}</strong></div>`}
      </div>
    `;
  }

  function mount() {
    const admin = document.getElementById("adminContent");
    if (!admin || document.getElementById("cashClosingPanel")) return;
    const panel = document.createElement("section");
    panel.id = "cashClosingPanel";
    panel.className = "form-panel admin-report-panel";
    panel.innerHTML = `
      <p class="eyebrow">Financeiro</p>
      <h2>Fechamento de caixa</h2>
      <p class="privacy-note">Resumo pronto para conferir o caixa com base no filtro atual.</p>
      <div class="report-export-actions">
        <button class="btn btn-ghost" type="button" data-refresh-cash>Atualizar caixa</button>
        <button class="btn" type="button" data-copy-cash>Copiar fechamento</button>
      </div>
      <div id="cashClosingContent" class="admin-report-content"></div>
    `;
    const payment = document.getElementById("paymentReportPanel");
    if (payment?.nextSibling) admin.insertBefore(panel, payment.nextSibling);
    else admin.prepend(panel);
    panel.querySelector("[data-refresh-cash]").addEventListener("click", render);
    panel.querySelector("[data-copy-cash]").addEventListener("click", copy);
    document.getElementById("reportStart")?.addEventListener("change", render);
    document.getElementById("reportEnd")?.addEventListener("change", render);
    document.getElementById("reportStatus")?.addEventListener("change", render);
    render();
  }

  window.misticaCashClosing = { render, totals, message, copy };
  window.addEventListener("load", mount);
})();
