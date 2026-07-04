(() => {
  const PEDIDO_STATUS = [
    "Aguardando pagamento",
    "Pagamento confirmado",
    "Separando pedido",
    "Pronto para retirada",
    "Entregue",
    "Cancelado",
  ];

  function money(value) {
    try { return currency.format(Number(value || 0)); } catch { return `R$ ${Number(value || 0).toFixed(2)}`; }
  }

  function datePt(value) {
    try { return new Date(value).toLocaleString("pt-BR"); } catch { return String(value || ""); }
  }

  function ensurePedidoFields() {
    if (typeof sales === "undefined") return;
    let changed = false;
    sales.forEach(sale => {
      if (!sale.status || sale.status === "Aguardando conferência do pagamento") {
        sale.status = "Aguardando pagamento";
        changed = true;
      }
      if (!sale.timeline) {
        sale.timeline = [{ status: sale.status, at: sale.date || new Date().toISOString(), user: "Sistema" }];
        changed = true;
      }
    });
    if (changed && typeof saveState === "function") saveState();
  }

  function statusClass(status) {
    return `pedido-status status-${String(status || "").normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase().replace(/[^a-z0-9]+/g, "-")}`;
  }

  function setPedidoStatus(saleId, status) {
    const sale = sales.find(item => String(item.id) === String(saleId));
    if (!sale || !PEDIDO_STATUS.includes(status)) return;
    sale.status = status;
    sale.timeline = Array.isArray(sale.timeline) ? sale.timeline : [];
    sale.timeline.unshift({ status, at: new Date().toISOString(), user: "Admin" });
    if (typeof saveState === "function") saveState();
    if (typeof renderAll === "function") renderAll();
    renderPedidosAdmin();
  }

  function buildPedidoMessage(sale) {
    const items = (sale.items || []).map(item => `• ${item.qty}x ${item.name} - ${money(Number(item.price || 0) * Number(item.qty || 0))}`).join("\n");
    return `Pedido ${sale.id} - Mística Presentes\n\nStatus: ${sale.status}\nData: ${datePt(sale.date)}\n\n${items}\n\nTotal: ${money(sale.total)}\n\nQualquer dúvida, estamos à disposição.`;
  }

  function sendPedidoWhatsapp(saleId) {
    const sale = sales.find(item => String(item.id) === String(saleId));
    if (!sale) return;
    const number = (window.misticaSiteConfig?.whatsappNumber || storeConfig.whatsappNumber || "554999172137");
    window.open(`https://wa.me/${number}?text=${encodeURIComponent(buildPedidoMessage(sale))}`, "_blank", "noopener");
  }

  function renderTimeline(sale) {
    const timeline = Array.isArray(sale.timeline) ? sale.timeline.slice(0, 4) : [];
    if (!timeline.length) return "";
    return `<div class="pedido-timeline">${timeline.map(item => `<span>${item.status} • ${datePt(item.at)}</span>`).join("")}</div>`;
  }

  function renderPedidosAdmin() {
    const root = document.getElementById("pedidosAdminList");
    if (!root || typeof sales === "undefined") return;
    ensurePedidoFields();
    if (!sales.length) {
      root.innerHTML = `<div class="history-item"><span>Nenhum pedido registrado ainda.</span></div>`;
      return;
    }

    root.innerHTML = sales.slice(0, 30).map(sale => {
      const items = (sale.items || []).map(item => `${item.qty}x ${item.name}`).join(" | ");
      const options = PEDIDO_STATUS.map(status => `<option value="${status}" ${sale.status === status ? "selected" : ""}>${status}</option>`).join("");
      return `
        <article class="pedido-card" data-sale-id="${sale.id}">
          <div class="pedido-card-head">
            <div>
              <strong>Pedido ${sale.id}</strong>
              <span>${datePt(sale.date)}</span>
            </div>
            <span class="${statusClass(sale.status)}">${sale.status}</span>
          </div>
          <p>${items}</p>
          <strong>${money(sale.total)}</strong>
          <label class="pedido-status-select">Status do pedido
            <select data-pedido-status="${sale.id}">${options}</select>
          </label>
          <div class="pedido-actions">
            <button class="btn" type="button" data-confirm-pix="${sale.id}">Confirmar Pix</button>
            <button class="btn btn-ghost" type="button" data-ready-order="${sale.id}">Pronto retirada</button>
            <button class="btn btn-ghost" type="button" data-send-pedido="${sale.id}">WhatsApp</button>
            <button class="btn btn-ghost" type="button" data-print-pedido="${sale.id}">Imprimir</button>
            <button class="btn btn-ghost" type="button" data-cancel-pedido="${sale.id}">Cancelar</button>
          </div>
          ${renderTimeline(sale)}
        </article>
      `;
    }).join("");
  }

  function mountPedidosAdmin() {
    const admin = document.getElementById("adminContent");
    if (!admin || document.getElementById("pedidosAdminPanel")) return;
    const panel = document.createElement("section");
    panel.id = "pedidosAdminPanel";
    panel.className = "form-panel pedidos-admin-panel";
    panel.innerHTML = `
      <p class="eyebrow">Pedidos</p>
      <h2>Confirmação de Pix e status</h2>
      <p class="privacy-note">Use este painel para confirmar pagamento, separar pedido, marcar como pronto, entregue ou cancelado.</p>
      <div id="pedidosAdminList" class="pedidos-admin-list"></div>
    `;
    admin.insertBefore(panel, admin.firstChild);
    renderPedidosAdmin();
  }

  function installEvents() {
    document.addEventListener("change", event => {
      const saleId = event.target?.dataset?.pedidoStatus;
      if (saleId) setPedidoStatus(saleId, event.target.value);
    });
    document.addEventListener("click", event => {
      const target = event.target;
      if (!target?.dataset) return;
      if (target.dataset.confirmPix) setPedidoStatus(target.dataset.confirmPix, "Pagamento confirmado");
      if (target.dataset.readyOrder) setPedidoStatus(target.dataset.readyOrder, "Pronto para retirada");
      if (target.dataset.cancelPedido) setPedidoStatus(target.dataset.cancelPedido, "Cancelado");
      if (target.dataset.sendPedido) sendPedidoWhatsapp(target.dataset.sendPedido);
      if (target.dataset.printPedido) {
        const sale = sales.find(item => String(item.id) === String(target.dataset.printPedido));
        if (sale && typeof printReceipt === "function") printReceipt(sale);
      }
    });
  }

  window.misticaPedidos = {
    statuses: PEDIDO_STATUS,
    render: renderPedidosAdmin,
    setStatus: setPedidoStatus,
  };

  window.addEventListener("load", () => {
    ensurePedidoFields();
    mountPedidosAdmin();
    installEvents();
    setInterval(() => {
      mountPedidosAdmin();
      renderPedidosAdmin();
    }, 2500);
  });
})();
