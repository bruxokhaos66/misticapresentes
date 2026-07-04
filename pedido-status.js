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
  let filtroOrigem = "todos";

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

  function origemDoPedido(pedido) {
    const origem = String(pedido.origem || pedido.origem_sync || pedido.origemSync || "api").toLowerCase();
    const vendedor = String(pedido.vendedor || "").toLowerCase();
    const cliente = String(pedido.cliente || "").toLowerCase();
    if (origem.includes("isis") || vendedor.includes("isis") || cliente.includes("isis")) return "isis";
    if (origem.includes("site") || origem.includes("api") || vendedor.includes("site")) return "site";
    return "manual";
  }

  function origemLabel(origem) {
    if (origem === "isis") return "Isis";
    if (origem === "site") return "Site/API";
    return "Manual";
  }

  function normalizarPedidoApi(pedido) {
    const origem = origemDoPedido(pedido);
    return {
      id: String(pedido.id),
      date: pedido.data_iso || pedido.data_venda || new Date().toISOString(),
      total: Number(pedido.total_final || pedido.subtotal || 0),
      status: pedido.status || "Aguardando pagamento",
      formaPagamento: pedido.forma_pagamento || "",
      vendedor: pedido.vendedor || "",
      cliente: pedido.cliente || "Cliente não informado",
      observacao: pedido.observacao_pedido || "",
      origem,
      origemRaw: pedido.origem || pedido.origem_sync || "api",
      estoqueBaixado: Number(pedido.estoque_baixado || 0) === 1,
      estoqueBaixadoEm: pedido.estoque_baixado_em || "",
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
    return typeof sales !== "undefined"
      ? sales.map(sale => ({ ...sale, origem: origemDoPedido(sale), estoqueBaixado: Boolean(sale.estoqueBaixado || sale.estoque_baixado) }))
      : [];
  }

  function aplicarFiltro(lista) {
    if (filtroOrigem === "todos") return lista;
    return lista.filter(pedido => pedido.origem === filtroOrigem);
  }

  function resumoPedidos(lista) {
    return {
      todos: lista.length,
      isis: lista.filter(p => p.origem === "isis").length,
      site: lista.filter(p => p.origem === "site").length,
      manual: lista.filter(p => p.origem === "manual").length,
      pendentes: lista.filter(p => p.status === "Aguardando pagamento").length,
      estoqueBaixado: lista.filter(p => p.estoqueBaixado).length,
    };
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

  async function baixarEstoqueManual(saleId) {
    const sale = pedidosAtuais().find(item => String(item.id) === String(saleId));
    if (!sale) return;
    if (sale.estoqueBaixado) return alert("O estoque deste pedido já foi baixado.");
    if (!confirm(`Baixar estoque do pedido ${saleId}? Esta ação não deve ser repetida.`)) return;
    try {
      await api(`/api/pedidos/${Number(saleId)}/baixar-estoque`, { method: "POST" });
      await carregarPedidosApi();
      alert("Estoque baixado com sucesso.");
    } catch (error) {
      alert(`Falha ao baixar estoque: ${error.message}`);
    }
  }

  async function registrarPagamentoPix(saleId) {
    const sale = pedidosAtuais().find(item => String(item.id) === String(saleId));
    if (!sale) return;
    const comprovante = window.prompt("Identificação do comprovante Pix, se houver:", "") || "";
    try {
      await api("/api/pagamentos", {
        method: "POST",
        body: JSON.stringify({
          venda_id: Number(saleId),
          forma: "Pix",
          valor: Number(sale.total || 0),
          status: "Confirmado",
          comprovante,
          observacao: "Pix confirmado manualmente pelo Admin",
          usuario: "Admin",
        }),
      });
      await carregarPedidosApi();
      alert("Pix registrado e pedido marcado como pagamento confirmado.");
    } catch (error) {
      alert(`Falha ao registrar Pix: ${error.message}`);
      await setPedidoStatus(saleId, "Pagamento confirmado");
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
    const estoque = sale.estoqueBaixado ? "Estoque já baixado" : "Estoque ainda pendente";
    return `Pedido ${sale.id} - Mística Presentes\n\nStatus: ${sale.status}\nOrigem: ${origemLabel(sale.origem)}\n${estoque}\nCliente: ${sale.cliente || "Pedido site/celular"}\nData: ${datePt(sale.date)}\n\n${items}\n\nTotal: ${money(sale.total)}\n\nQualquer dúvida, estamos à disposição.`;
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

  function filtroButton(key, label, count) {
    return `<button class="btn btn-ghost ${filtroOrigem === key ? "active" : ""}" type="button" data-filter-origem="${key}">${label}: ${count}</button>`;
  }

  function estoqueBadge(sale) {
    if (sale.estoqueBaixado) {
      const quando = sale.estoqueBaixadoEm ? ` em ${datePt(sale.estoqueBaixadoEm)}` : "";
      return `<small class="pedido-stock pedido-stock-ok">Estoque baixado${quando}</small>`;
    }
    return `<small class="pedido-stock pedido-stock-pending">Estoque pendente</small>`;
  }

  function renderPedidosAdmin() {
    const root = document.getElementById("pedidosAdminList");
    if (!root) return;
    const base = pedidosAtuais();
    const resumo = resumoPedidos(base);
    const lista = aplicarFiltro(base);
    if (!base.length) {
      root.innerHTML = `<div class="history-item"><span>Nenhum pedido registrado ainda.</span></div>`;
      return;
    }

    root.innerHTML = `
      <div class="pedido-toolbar">
        <span>${apiOnline ? "Pedidos carregados da API" : "Modo offline: pedidos locais"}</span>
        <strong>Pendentes: ${resumo.pendentes}</strong>
        <strong>Estoque baixado: ${resumo.estoqueBaixado}</strong>
        <button class="btn btn-ghost" type="button" data-reload-pedidos>Recarregar API</button>
      </div>
      <div class="pedido-toolbar pedido-filter-bar">
        ${filtroButton("todos", "Todos", resumo.todos)}
        ${filtroButton("isis", "Isis", resumo.isis)}
        ${filtroButton("site", "Site/API", resumo.site)}
        ${filtroButton("manual", "Manual", resumo.manual)}
      </div>
      ${!lista.length ? `<div class="history-item"><span>Nenhum pedido neste filtro.</span></div>` : ""}
      ${lista.slice(0, 60).map(sale => {
        const items = (sale.items || []).map(item => `${item.qty}x ${item.name}`).join(" | ");
        const options = PEDIDO_STATUS.map(status => `<option value="${status}" ${sale.status === status ? "selected" : ""}>${status}</option>`).join("");
        const stockButton = !sale.estoqueBaixado ? `<button class="btn btn-ghost" type="button" data-stock-down="${sale.id}">Baixar estoque</button>` : "";
        return `
          <article class="pedido-card pedido-origem-${sale.origem}" data-sale-id="${sale.id}">
            <div class="pedido-card-head">
              <div>
                <strong>Pedido ${sale.id}</strong>
                <span>${sale.cliente || "Pedido site/celular"}</span>
                <span>${datePt(sale.date)}</span>
                <small class="pedido-origin">Origem: ${origemLabel(sale.origem)}</small>
                ${estoqueBadge(sale)}
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
              <button class="btn" type="button" data-confirm-pix="${sale.id}">Registrar Pix</button>
              ${stockButton}
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
      <p class="privacy-note">Pedidos, status, observações, histórico, Pix, origem e baixa de estoque são carregados da API quando ela está online.</p>
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
      if (target.dataset.filterOrigem) {
        filtroOrigem = target.dataset.filterOrigem;
        renderPedidosAdmin();
      }
      if (target.dataset.reloadPedidos !== undefined) carregarPedidosApi().catch(() => { apiOnline = false; renderPedidosAdmin(); });
      if (target.dataset.confirmPix) registrarPagamentoPix(target.dataset.confirmPix);
      if (target.dataset.stockDown) baixarEstoqueManual(target.dataset.stockDown);
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
    registerPix: registrarPagamentoPix,
    stockDown: baixarEstoqueManual,
    setFilter: value => { filtroOrigem = value || "todos"; renderPedidosAdmin(); },
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
