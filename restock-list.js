(() => {
  function money(value) {
    return typeof currency !== "undefined" ? currency.format(Number(value || 0)) : `R$ ${Number(value || 0).toFixed(2).replace(".", ",")}`;
  }

  function threshold() {
    return Number(typeof storeConfig !== "undefined" ? storeConfig.minStock : 3) || 3;
  }

  function currentStock(product) {
    if (typeof getStock === "function") return getStock(product.id);
    return Number(stock?.[product.id] || product.stock || 0);
  }

  function lowStockProducts() {
    if (typeof products === "undefined" || !Array.isArray(products)) return [];
    const min = threshold();
    return products
      .map(product => ({ ...product, currentStock: currentStock(product), suggestedQty: Math.max(min * 2 - currentStock(product), 1) }))
      .filter(product => product.currentStock <= min)
      .sort((a, b) => a.currentStock - b.currentStock || String(a.name).localeCompare(String(b.name), "pt-BR"));
  }

  function message(list = lowStockProducts()) {
    if (!list.length) return "Lista de reposição - Mística Presentes\n\nNenhum produto abaixo do mínimo no momento.";
    const lines = list.map(product => `• ${product.name} | estoque: ${product.currentStock} | sugerido comprar: ${product.suggestedQty} | venda: ${money(product.price)}`);
    return `Lista de reposição - Mística Presentes\n\n${lines.join("\n")}\n\nConferir fornecedores e prazos antes da compra.`;
  }

  function whatsappNumber() {
    const siteNumber = window.misticaSiteConfig?.whatsappNumber;
    const configNumber = typeof storeConfig !== "undefined" ? storeConfig.whatsappNumber : "";
    return String(siteNumber || configNumber || "554999172137").replace(/\D/g, "");
  }

  async function copyList() {
    const text = message();
    try {
      await navigator.clipboard.writeText(text);
      alert("Lista de reposição copiada.");
    } catch {
      prompt("Copie a lista de reposição:", text);
    }
  }

  function sendWhatsapp() {
    window.open(`https://wa.me/${whatsappNumber()}?text=${encodeURIComponent(message())}`, "_blank", "noopener");
  }

  function renderPanel() {
    const content = document.getElementById("restockListContent");
    if (!content) return;
    const list = lowStockProducts();
    if (!list.length) {
      content.innerHTML = `<div class="history-item"><span>Nenhum produto abaixo do mínimo.</span></div>`;
      return;
    }
    content.innerHTML = list.slice(0, 20).map(product => `
      <div class="history-item">
        <strong>${product.name}</strong>
        <span>${product.category || "Produto"} • estoque atual: ${product.currentStock} • comprar: ${product.suggestedQty}</span>
        <span>Preço de venda: ${money(product.price)}</span>
      </div>
    `).join("");
  }

  function mountPanel() {
    const admin = document.getElementById("adminContent");
    if (!admin || document.getElementById("restockListPanel")) return;
    const panel = document.createElement("section");
    panel.id = "restockListPanel";
    panel.className = "form-panel admin-report-panel";
    panel.innerHTML = `
      <p class="eyebrow">Reposição</p>
      <h2>Lista de compra por estoque baixo</h2>
      <p class="privacy-note">Sugestão automática baseada no estoque mínimo atual.</p>
      <div class="report-export-actions">
        <button class="btn btn-ghost" type="button" data-refresh-restock>Atualizar lista</button>
        <button class="btn btn-ghost" type="button" data-copy-restock>Copiar lista</button>
        <button class="btn" type="button" data-whatsapp-restock>Enviar pelo WhatsApp</button>
      </div>
      <div id="restockListContent" class="history-list"></div>
    `;
    const report = document.getElementById("salesReportPanel");
    if (report?.nextSibling) admin.insertBefore(panel, report.nextSibling);
    else admin.appendChild(panel);
    panel.querySelector("[data-refresh-restock]").addEventListener("click", renderPanel);
    panel.querySelector("[data-copy-restock]").addEventListener("click", copyList);
    panel.querySelector("[data-whatsapp-restock]").addEventListener("click", sendWhatsapp);
    renderPanel();
  }

  window.misticaRestockList = {
    render: renderPanel,
    products: lowStockProducts,
    message,
    copy: copyList,
    whatsapp: sendWhatsapp,
  };

  window.addEventListener("load", mountPanel);
})();
