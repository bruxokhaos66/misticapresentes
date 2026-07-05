(() => {
  const DAYS_LIMIT = 30;

  function loadMessageTemplates() {
    if (document.getElementById("messageTemplatesScript")) return;
    const script = document.createElement("script");
    script.id = "messageTemplatesScript";
    script.src = "message-templates.js";
    script.defer = true;
    document.head.appendChild(script);
  }

  function loadCustomerVip() {
    if (document.getElementById("customerVipScript")) return;
    const script = document.createElement("script");
    script.id = "customerVipScript";
    script.src = "customer-vip.js";
    script.defer = true;
    document.head.appendChild(script);
  }

  function normalizePhone(value) {
    return String(value || "").replace(/\D/g, "");
  }

  function clientName(client) {
    return client?.name || client?.nome || "Cliente";
  }

  function clientPhone(client) {
    return normalizePhone(client?.whatsapp || client?.telefone || "");
  }

  function saleText(sale) {
    return `${sale?.cliente || ""} ${sale?.clientName || ""} ${sale?.customer || ""}`.toLowerCase();
  }

  function daysAgo(date) {
    const day = 24 * 60 * 60 * 1000;
    return Math.floor((Date.now() - date.getTime()) / day);
  }

  function lastPurchase(client) {
    if (typeof sales === "undefined" || !Array.isArray(sales)) return null;
    const name = clientName(client).toLowerCase();
    const phone = clientPhone(client);
    const matches = sales
      .filter(sale => !String(sale.status || "").toLowerCase().includes("cancel"))
      .filter(sale => saleText(sale).includes(name) || (phone && saleText(sale).includes(phone)))
      .map(sale => sale.date ? new Date(sale.date) : null)
      .filter(date => date && !Number.isNaN(date.getTime()))
      .sort((a, b) => b - a);
    return matches[0] || null;
  }

  function followupClients() {
    if (typeof clients === "undefined" || !Array.isArray(clients)) return [];
    return clients.map(client => {
      const last = lastPurchase(client);
      return { client, last, days: last ? daysAgo(last) : null };
    }).filter(item => !item.last || item.days >= DAYS_LIMIT).slice(0, 20);
  }

  function message(item) {
    const name = clientName(item.client).split(" ")[0] || "tudo bem";
    return `Olá, ${name}! Aqui é da Mística Presentes. Passando para saber se você precisa de algum produto místico, incenso, vela, cristal ou presente especial. Gratidão!`;
  }

  function openWhatsapp(index) {
    const item = followupClients()[index];
    if (!item) return alert("Cliente não encontrado para recontato.");
    const phone = clientPhone(item.client);
    if (!phone) return alert("Cliente sem WhatsApp cadastrado.");
    window.open(`https://wa.me/${phone}?text=${encodeURIComponent(message(item))}`, "_blank", "noopener");
  }

  function renderFollowup() {
    const content = document.getElementById("customerFollowupContent");
    if (!content) return;
    const list = followupClients();
    if (!list.length) {
      content.innerHTML = `<div class="history-item"><span>Nenhum cliente para recontato agora.</span></div>`;
      return;
    }
    content.innerHTML = list.map((item, index) => `
      <div class="history-item">
        <strong>${clientName(item.client)}</strong>
        <span>${item.last ? `Última compra há ${item.days} dia(s)` : "Sem compra registrada"}</span>
        <span>WhatsApp: ${clientPhone(item.client) || "não cadastrado"}</span>
        <button class="btn btn-ghost btn-full" type="button" onclick="misticaCustomerFollowup.openWhatsapp(${index})">Enviar recontato</button>
      </div>
    `).join("");
  }

  function mountFollowup() {
    const admin = document.getElementById("adminContent");
    if (!admin || document.getElementById("customerFollowupPanel")) return;
    const panel = document.createElement("section");
    panel.id = "customerFollowupPanel";
    panel.className = "form-panel admin-report-panel";
    panel.innerHTML = `
      <p class="eyebrow">Clientes</p>
      <h2>Recontato comercial</h2>
      <p class="privacy-note">Lista clientes sem compra recente ou sem compra registrada.</p>
      <div class="report-export-actions">
        <button class="btn btn-ghost" type="button" data-refresh-followup>Atualizar clientes</button>
      </div>
      <div id="customerFollowupContent" class="history-list"></div>
    `;
    const topProducts = document.getElementById("topProductsPanel");
    if (topProducts?.nextSibling) admin.insertBefore(panel, topProducts.nextSibling);
    else admin.appendChild(panel);
    panel.querySelector("[data-refresh-followup]").addEventListener("click", renderFollowup);
    renderFollowup();
  }

  window.misticaCustomerFollowup = {
    render: renderFollowup,
    list: followupClients,
    openWhatsapp,
  };

  window.addEventListener("load", () => {
    mountFollowup();
    loadCustomerVip();
    loadMessageTemplates();
  });
})();
