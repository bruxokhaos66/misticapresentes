(() => {
  function money(value) {
    return typeof currency !== "undefined" ? currency.format(Number(value || 0)) : `R$ ${Number(value || 0).toFixed(2).replace(".", ",")}`;
  }

  function normalize(value) {
    return String(value || "").normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase().trim();
  }

  function salePayment(sale) {
    return sale?.payment || sale?.paymentMethod || sale?.formaPagamento || sale?.forma_pagamento || sale?.pagamento || "Não informado";
  }

  function saleTotal(sale) {
    const direct = sale?.total ?? sale?.totalAmount ?? sale?.valorTotal ?? sale?.valor_total ?? sale?.amount;
    return Number(String(direct || 0).replace(",", ".")) || 0;
  }

  function filteredSales() {
    if (window.misticaSalesReport?.getFilteredSales) return window.misticaSalesReport.getFilteredSales();
    return typeof sales !== "undefined" && Array.isArray(sales) ? sales : [];
  }

  function rows() {
    const map = new Map();
    filteredSales().forEach(sale => {
      const label = String(salePayment(sale) || "Não informado").trim() || "Não informado";
      const key = normalize(label) || "nao informado";
      const current = map.get(key) || { label, total: 0, count: 0 };
      current.total += saleTotal(sale);
      current.count += 1;
      map.set(key, current);
    });
    return Array.from(map.values()).sort((a, b) => b.total - a.total || b.count - a.count);
  }

  function message() {
    const list = rows();
    if (!list.length) return "Relatório por pagamento - Mística Presentes\n\nNenhuma venda encontrada.";
    return `Relatório por pagamento - Mística Presentes\n\n${list.map(item => `${item.label}: ${item.count} venda(s) - ${money(item.total)}`).join("\n")}`;
  }

  async function copy() {
    const text = message();
    try {
      await navigator.clipboard.writeText(text);
      alert("Relatório por pagamento copiado.");
    } catch {
      prompt("Copie o relatório:", text);
    }
  }

  function render() {
    const content = document.getElementById("paymentReportContent");
    if (!content) return;
    const list = rows();
    if (!list.length) {
      content.innerHTML = `<div class="report-row"><span>Nenhuma forma de pagamento encontrada</span><strong>${money(0)}</strong></div>`;
      return;
    }
    content.innerHTML = list.map(item => `
      <div class="report-row">
        <span>${item.label} • ${item.count} venda(s)</span>
        <strong>${money(item.total)}</strong>
      </div>
    `).join("");
  }

  function mount() {
    const admin = document.getElementById("adminContent");
    if (!admin || document.getElementById("paymentReportPanel")) return;
    const panel = document.createElement("section");
    panel.id = "paymentReportPanel";
    panel.className = "form-panel admin-report-panel";
    panel.innerHTML = `
      <p class="eyebrow">Financeiro</p>
      <h2>Relatório por pagamento</h2>
      <p class="privacy-note">Resumo por forma de pagamento usando o mesmo filtro do relatório de vendas.</p>
      <div class="report-export-actions">
        <button class="btn btn-ghost" type="button" data-refresh-payment>Atualizar pagamentos</button>
        <button class="btn" type="button" data-copy-payment>Copiar relatório</button>
      </div>
      <div id="paymentReportContent" class="report-list"></div>
    `;
    const report = document.getElementById("salesReportPanel");
    if (report?.nextSibling) admin.insertBefore(panel, report.nextSibling);
    else admin.prepend(panel);
    panel.querySelector("[data-refresh-payment]").addEventListener("click", render);
    panel.querySelector("[data-copy-payment]").addEventListener("click", copy);
    document.getElementById("reportStart")?.addEventListener("change", render);
    document.getElementById("reportEnd")?.addEventListener("change", render);
    document.getElementById("reportStatus")?.addEventListener("change", render);
    render();
  }

  window.misticaPaymentReport = { render, rows, message, copy };
  window.addEventListener("load", mount);
})();
