(() => {
  const STORAGE_KEY = "misticaDailyGoal";

  function loadTopProducts() {
    if (document.getElementById("topProductsScript")) return;
    const script = document.createElement("script");
    script.id = "topProductsScript";
    script.src = "top-products.js";
    script.defer = true;
    document.head.appendChild(script);
  }

  function money(value) {
    return typeof currency !== "undefined" ? currency.format(Number(value || 0)) : `R$ ${Number(value || 0).toFixed(2).replace(".", ",")}`;
  }

  function todayKey() {
    return new Date().toISOString().slice(0, 10);
  }

  function saleDateKey(sale) {
    const date = sale?.date ? new Date(sale.date) : null;
    return date && !Number.isNaN(date.getTime()) ? date.toISOString().slice(0, 10) : "";
  }

  function validSale(sale) {
    return !String(sale?.status || "").toLowerCase().includes("cancel");
  }

  function todaySales() {
    if (typeof sales === "undefined" || !Array.isArray(sales)) return [];
    const key = todayKey();
    return sales.filter(sale => saleDateKey(sale) === key && validSale(sale));
  }

  function goalValue() {
    return Number(localStorage.getItem(STORAGE_KEY) || 0);
  }

  function setGoal(value) {
    const parsed = Number(String(value || "0").replace(",", "."));
    localStorage.setItem(STORAGE_KEY, String(Math.max(parsed, 0)));
  }

  function summaryText() {
    const list = todaySales();
    const total = list.reduce((sum, sale) => sum + Number(sale.total || 0), 0);
    const goal = goalValue();
    const missing = Math.max(goal - total, 0);
    const percent = goal > 0 ? Math.min((total / goal) * 100, 100) : 0;
    return `Fechamento diário - Mística Presentes\n\nVendas de hoje: ${list.length}\nTotal vendido: ${money(total)}\nMeta diária: ${money(goal)}\nAtingido: ${percent.toFixed(0)}%\n${missing > 0 ? `Falta para meta: ${money(missing)}` : "Meta batida!"}`;
  }

  function whatsappNumber() {
    const siteNumber = window.misticaSiteConfig?.whatsappNumber;
    const configNumber = typeof storeConfig !== "undefined" ? storeConfig.whatsappNumber : "";
    return String(siteNumber || configNumber || "554999172137").replace(/\D/g, "");
  }

  async function copySummary() {
    const text = summaryText();
    try {
      await navigator.clipboard.writeText(text);
      alert("Resumo diário copiado.");
    } catch {
      prompt("Copie o resumo diário:", text);
    }
  }

  function sendWhatsapp() {
    window.open(`https://wa.me/${whatsappNumber()}?text=${encodeURIComponent(summaryText())}`, "_blank", "noopener");
  }

  function renderGoal() {
    const content = document.getElementById("dailyGoalContent");
    if (!content) return;
    const list = todaySales();
    const total = list.reduce((sum, sale) => sum + Number(sale.total || 0), 0);
    const goal = goalValue();
    const missing = Math.max(goal - total, 0);
    const average = list.length ? total / list.length : 0;
    const percent = goal > 0 ? Math.min((total / goal) * 100, 100) : 0;
    const status = goal <= 0 ? "Defina uma meta diária" : (missing > 0 ? `Faltam ${money(missing)}` : "Meta batida");

    content.innerHTML = `
      <div class="report-grid">
        <div class="report-card"><span>Total hoje</span><strong>${money(total)}</strong><small>${list.length} venda(s)</small></div>
        <div class="report-card"><span>Meta diária</span><strong>${money(goal)}</strong><small>${status}</small></div>
        <div class="report-card"><span>Atingido</span><strong>${percent.toFixed(0)}%</strong><small>Progresso da meta</small></div>
        <div class="report-card"><span>Ticket médio</span><strong>${money(average)}</strong><small>Média do dia</small></div>
      </div>
      <div class="report-list">
        ${list.slice(0, 8).map(sale => `<div class="report-row"><span>${sale.id || "Pedido"} • ${sale.status || "Sem status"}</span><strong>${money(sale.total)}</strong></div>`).join("") || `<div class="report-row"><span>Nenhuma venda hoje</span><strong>${money(0)}</strong></div>`}
      </div>
    `;
  }

  function mountGoal() {
    const admin = document.getElementById("adminContent");
    if (!admin || document.getElementById("dailyGoalPanel")) return;
    const panel = document.createElement("section");
    panel.id = "dailyGoalPanel";
    panel.className = "form-panel admin-report-panel";
    panel.innerHTML = `
      <p class="eyebrow">Fechamento</p>
      <h2>Meta e fechamento diário</h2>
      <div class="report-filters">
        <label>Meta diária<input id="dailyGoalInput" type="number" min="0" step="10" value="${goalValue()}"></label>
      </div>
      <div class="report-export-actions">
        <button class="btn btn-ghost" type="button" data-save-daily-goal>Salvar meta</button>
        <button class="btn btn-ghost" type="button" data-copy-daily-summary>Copiar resumo</button>
        <button class="btn" type="button" data-whatsapp-daily-summary>Enviar pelo WhatsApp</button>
      </div>
      <div id="dailyGoalContent" class="admin-report-content"></div>
    `;
    const report = document.getElementById("salesReportPanel");
    if (report) admin.insertBefore(panel, report);
    else admin.prepend(panel);
    panel.querySelector("[data-save-daily-goal]").addEventListener("click", () => {
      setGoal(document.getElementById("dailyGoalInput")?.value);
      renderGoal();
    });
    panel.querySelector("[data-copy-daily-summary]").addEventListener("click", copySummary);
    panel.querySelector("[data-whatsapp-daily-summary]").addEventListener("click", sendWhatsapp);
    renderGoal();
  }

  window.misticaDailyGoal = {
    render: renderGoal,
    summary: summaryText,
    setGoal,
  };

  window.addEventListener("load", () => {
    mountGoal();
    loadTopProducts();
  });
})();
