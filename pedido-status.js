(() => {
  const PEDIDO_STATUS = [
    "Aguardando pagamento",
    "Pagamento confirmado",
    "Separando pedido",
    "Pronto para retirada",
    "Entregue",
    "Cancelado",
  ];

  const cfg = window.misticaSiteConfig || {};
  const API_BASE = (cfg.apiBaseUrl || "https://api.misticaesotericos.com.br").replace(/\/$/, "");
  const SITE_API_KEY = String(cfg.siteApiKey || "").trim();
  let pedidosApi = [];
  let apiOnline = false;

  function money(value) {
    try { return currency.format(Number(value || 0)); } catch { return `R$ ${Number(value || 0).toFixed(2)}`; }
  }

  function datePt(value) {
    try { return new Date(value).toLocaleString("pt-BR"); } catch { return String(value || ""); }
  }

  function headers() {
    return {
      "Content-Type": "application/json",
      ...(SITE_API_KEY ? { "X-Mistica-Api-Key": SITE_API_KEY } : {}),
    };
  }

  async function api(path, options = {}) {
    const response = await fetch(`${API_BASE}${path}`, {
      ...options,
      headers: { ...headers(), ...(options.headers || {}) },
    });
    if (!response.ok) {
      let detail = `API ${response.status}`;
      try {
        const body = await response.json();
        detail = body.detail || detail;
      } catch {}
      throw new Error(detail);
    }
    return response.json();
  }

  function normalizarPedidoApi(pedido) {
    return {
      id: String(pedido.id),
      date: pedido.data_iso || pedido.data_venda || new Date().toISOString(),
      total: Number(pedido.total_final || pedido.subtotal || 0),
      status: pedido.status || "Aguardando pagamento",
      formaPagamento: pedido.forma_pagamento || "",
      vendedor: pedido.vendedor || "",
      cliente: pedido.cliente || "Cliente não informado",
      observacao: pedido.observacao_pedido || "",
      origem: pedido.origem_sync || "api",
      items: Array.isArray(pedido.itens) && pedido.itens.length
        ? pedido.itens.map(item => ({
            qty: Number(item.quantidade || 1),
            name: item.nome_p || item.nome || "Item",
            price: Number(item.valor_unitario || 0),
          }))
        : [{ qty: 1, name: pedido.cliente || "Pedido", price: Number(pedido.total_final || 0) }],
      timeline: Array.isArray(pedido.historico_status)
        ? pedido.historico_status.map(item => ({ status: item.status, at: item.data_hora, user: item.usuario, note: item.observacao }))
        : [],
    };
  }

  async function carregarPedidosApi() {
    const lista = await api("/api/pedidos?limite=100");
    pedidosApi = lista.map(normalizarPedidoApi);
    apiOnline = true;
    renderPedidosAdmin();
    return pedidosApi;
  }

  function pedidosAtuais() {
    if (apiOnline && pedidosApi.length) return pedidosApi;
    ensurePedidoFields();
    return typeof sales !== "undefined" ? sales : [];
  }

  async function setPedidoStatus(saleId, status) {
    if (!PEDIDO_STATUS.includes(status)) return;
    try {
      await api(`/api/pedidos/${Number(saleId)}/status`, {
        method: "POST",
        body: JSON.stringify({ status, usuario: "Admin", observacao: "Alterado pelo painel do site" }),
      });
      await carregarPedidosApi();
    } catch (error) {
      const sale = typeof sales !== "undefined" ? sales.find(item => String(item.id) === String(saleId)) : null;
      if (sale) localStatusUpdate(sale, status, `API offline: ${error.message}`);
      else alert(`Não foi possível atualizar na API: ${error.message}`);
    }
  }

  async function salvarObservacaoPedido(saleId) {
    const field = document.querySelector(`[data-pedido-observacao="${saleId}"]`);
    if (!field) return;
    try {
      await api(`/api/pedidos/${Number(saleId)}/observacao`, {
        method: "POST",
        body: JSON.stringify({ observacao: field.value, usuario: "Admin" }),
      });
      await carregarPedidosApi();
    } catch (error) {
      alert(`Falha ao salvar observação: ${error.message}`);
    }
  }

  async function cancelarPedidoApi(saleId) {
    if (!confirm("Cancelar este pedido?")) return;
    try {
      await api(`/api/pedidos/${Number(saleId)}`, { method: "DELETE" });
      await carregarPedidosApi();
    } catch (error) {
      await setPedidoStatus(saleId, "Cancelado");
    }
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

  function localStatusUpdate(sale, status, user = "Admin") {
    sale.status = status;
    sale.timeline = Array.isArray(sale.timeline) ? sale.timeline : [];
    sale.timeline.unshift({ status, at: new Date().toISOString(), user });
    if (typeof saveState === "function") saveState();
    if (typeof renderAll === "function") renderAll();
    renderPedidosAdmin();
  }

  function buildPedidoMessage(sale) {
    const items = (sale.items || []).map(item => `• ${item.qty}x ${item.name} - ${money(Number(item.price || 0) * Number(item.qty || 0))}`).join("\n");
    return `Pedido ${sale.id} - Mística Presentes\n\nStatus: ${sale.status}\nCliente: ${sale.cliente || "Pedido site/celular"}\nData: ${datePt(sale.date)}\n\n${items}\n\nTotal: ${money(sale.total)}\n\nQualquer dúvida, estamos à disposição.`;
  }

  function sendPedidoWhatsapp(saleId) {
    const sale = pedidosAtuais().find(item => String(item.id) === String(saleId));
    if (!sale) return;
    const number = (window.misticaSiteConfig?.whatsappNumber || storeConfig.whatsappNumber || "554999172137");
    window.open(`https://wa.me/${number}?text=${encodeURIComponent(buildPedidoMessage(sale))}`, "_blank", "noopener");
  }

  function renderTimeline(sale) {
    const timeline = Array.isArray(sale.timeline) ? sale.timeline.slice(0, 5) : [];
    if (!timeline.length) return "";
    return `<div class="pedido-timeline">${timeline.map(item => `<span>${item.status}${item.note ? " • " + item.note : ""} • ${datePt(item.at)}</span>`).join("")}</div>`;
  }

  function renderPedidosAdmin() {
    const root = document.getElementById("pedidosAdminList");
    if (!root) return;
    const lista = pedidosAtuais();
    if (!lista.length) {
      root.innerHTML = `<div class="history-item"><span>Nenhum pedido registrado ainda.</span></div>`;
      return;
    }

    root.innerHTML = `
      <div class="pedido-toolbar">
        <span>${apiOnline ? "Pedidos carregados da API" : "Modo offline: pedidos locais"}</span>
        <button class="btn btn-ghost" type="button" data-reload-pedidos>Recarregar API</button>
      </div>
      ${lista.slice(0, 60).map(sale => {
        const items = (sale.items || []).map(item => `${item.qty}x ${item.name}`).join(" | ");
        const options = PEDIDO_STATUS.map(status => `<option value="${status}" ${sale.status === status ? "selected" : ""}>${status}</option>`).join("");
        return `
          <article class="pedido-card" data-sale-id="${sale.id}">
            <div class="pedido-card-head">
              <div>
                <strong>Pedido ${sale.id}</strong>
                <span>${sale.cliente || "Pedido site/celular"}</span>
                <span>${datePt(sale.date)}</span>
              </div>
              <span class="${statusClass(sale.status)}">${sale.status}</span>
            </div>
            <p>${items}</p>
            <strong>${money(sale.total)}</strong>
            <label class="pedido-status-select">Status do pedido
              <select data-pedido-status="${sale.id}">${options}</select>
            </label>
            <label class="pedido-status-select">Observação interna
              <textarea data-pedido-observacao="${sale.id}" placeholder="Ex.: cliente retirará amanhã">${sale.observacao || ""}</textarea>
            </label>
            <div class="pedido-actions">
              <button class="btn" type="button" data-confirm-pix="${sale.id}">Confirmar Pix</button>
              <button class="btn btn-ghost" type="button" data-ready-order="${sale.id}">Pronto retirada</button>
              <button class="btn btn-ghost" type="button" data-save-note="${sale.id}">Salvar obs.</button>
              <button class="btn btn-ghost" type="button" data-send-pedido="${sale.id}">WhatsApp</button>
              <button class="btn btn-ghost" type="button" data-print-pedido="${sale.id}">Imprimir</button>
              <button class="btn btn-ghost" type="button" data-cancel-pedido="${sale.id}">Cancelar</button>
            </div>
            ${renderTimeline(sale)}
          </article>
        `;
      }).join("")}
    `;
  }

  function mountPedidosAdmin() {
    const admin = document.getElementById("adminContent");
    if (!admin || document.getElementById("pedidosAdminPanel")) return;
    const panel = document.createElement("section");
    panel.id = "pedidosAdminPanel";
    panel.className = "form-panel pedidos-admin-panel";
    panel.innerHTML = `
      <p class="eyebrow">Pedidos</p>
      <h2>Painel conectado ao backend</h2>
      <p class="privacy-note">Pedidos, status, observações e histórico são carregados da API quando ela está online.</p>
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
      if (target.dataset.reloadPedidos !== undefined) carregarPedidosApi().catch(() => { apiOnline = false; renderPedidosAdmin(); });
      if (target.dataset.confirmPix) setPedidoStatus(target.dataset.confirmPix, "Pagamento confirmado");
      if (target.dataset.readyOrder) setPedidoStatus(target.dataset.readyOrder, "Pronto para retirada");
      if (target.dataset.cancelPedido) cancelarPedidoApi(target.dataset.cancelPedido);
      if (target.dataset.saveNote) salvarObservacaoPedido(target.dataset.saveNote);
      if (target.dataset.sendPedido) sendPedidoWhatsapp(target.dataset.sendPedido);
      if (target.dataset.printPedido) {
        const sale = pedidosAtuais().find(item => String(item.id) === String(target.dataset.printPedido));
        if (sale && typeof printReceipt === "function") printReceipt(sale);
      }
    });
  }

  window.misticaPedidos = {
    statuses: PEDIDO_STATUS,
    render: renderPedidosAdmin,
    setStatus: setPedidoStatus,
    reload: carregarPedidosApi,
  };

  window.addEventListener("load", () => {
    ensurePedidoFields();
    mountPedidosAdmin();
    installEvents();
    carregarPedidosApi().catch(() => { apiOnline = false; renderPedidosAdmin(); });
    setInterval(() => {
      mountPedidosAdmin();
      if (apiOnline) carregarPedidosApi().catch(() => { apiOnline = false; renderPedidosAdmin(); });
      else renderPedidosAdmin();
    }, 8000);
  });
})();
