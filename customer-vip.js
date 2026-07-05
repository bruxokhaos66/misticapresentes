(() => {
  const LIMIT = 12;

  function money(value) {
    return typeof currency !== "undefined" ? currency.format(Number(value || 0)) : `R$ ${Number(value || 0).toFixed(2).replace(".", ",")}`;
  }

  function normalize(value) {
    return String(value || "").normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase().trim();
  }

  function phone(value) {
    return String(value || "").replace(/\D/g, "");
  }

  function saleStatus(sale) {
    return normalize(sale?.status || sale?.situacao || "");
  }

  function validSale(sale) {
    return !saleStatus(sale).includes("cancel");
  }

  function saleName(sale) {
    const client = sale?.client || sale?.customer || {};
    return sale?.clientName || sale?.customerName || sale?.cliente || sale?.customer || client.name || client.nome || "Cliente não informado";
  }

  function salePhone(sale) {
    const client = sale?.client || sale?.customer || {};
    return phone(sale?.clientPhone || sale?.customerPhone || sale?.whatsapp || sale?.telefone || sale?.phone || client.whatsapp || client.telefone || client.phone);
  }

  function saleTotal(sale) {
    const direct = sale?.total ?? sale?.totalAmount ?? sale?.valorTotal ?? sale?.valor_total ?? sale?.amount;
    if (direct !== undefined && direct !== null && direct !== "") return Number(String(direct).replace(",", ".")) || 0;
    return (sale?.items || sale?.itens || sale?.produtos || []).reduce((sum, item) => {
      const qty = Number(item.qty || item.quantity || item.quantidade || item.qtd || 1);
      const price = Number(String(item.price || item.preco || item.valor || 0).replace(",", ".")) || 0;
      return sum + qty * price;
    }, 0);
  }

  function saleDate(sale) {
    const raw = sale?.date || sale?.data || sale?.createdAt || sale?.created_at || sale?.vendido_em;
    const date = raw ? new Date(raw) : null;
    return date && !Number.isNaN(date.getTime()) ? date : null;
  }

  function buildRanking() {
    if (typeof sales === "undefined" || !Array.isArray(sales)) return [];
    const map = new Map();
    sales.filter(validSale).forEach(sale => {
      const name = saleName(sale);
      const whatsapp = salePhone(sale);
      const key = whatsapp || normalize(name);
      const current = map.get(key) || { name, whatsapp, total: 0, count: 0, last: null };
      const total = saleTotal(sale);
      const date = saleDate(sale);
      current.total += total;
      current.count += 1;
      if (whatsapp && !current.whatsapp) current.whatsapp = whatsapp;
      if (date && (!current.last || date > current.last)) current.last = date;
      map.set(key, current);
    });
    return Array.from(map.values())
      .sort((a, b) => b.total - a.total || b.count - a.count)
      .slice(0, LIMIT);
  }

  function lastText(date) {
    if (!date) return "Sem data registrada";
    return `Última compra: ${date.toLocaleDateString("pt-BR")}`;
  }

  function message() {
    const ranking = buildRanking();
    if (!ranking.length) return "Clientes VIP - Mística Presentes\n\nNenhuma venda registrada ainda.";
    return `Clientes VIP - Mística Presentes\n\n${ranking.map((item, index) => `${index + 1}. ${item.name} - ${item.count} compra(s) - ${money(item.total)}`).join("\n")}`;
  }

  async function copyRanking() {
    const text = message();
    try {
      await navigator.clipboard.writeText(text);
      alert("Ranking de clientes VIP copiado.");
    } catch {
      prompt("Copie o ranking de clientes VIP:", text);
    }
  }

  function vipWhatsapp(index) {
    const item = buildRanking()[index];
    if (!item) return alert("Cliente VIP não encontrado.");
    if (!item.whatsapp) return alert("Cliente VIP sem WhatsApp cadastrado.");
    const firstName = String(item.name || "cliente").split(" ")[0];
    const text = `Olá, ${firstName}! Aqui é da Mística Presentes. Você está entre nossos clientes especiais e separamos novidades em produtos místicos, incensos, velas e presentes. Gratidão pela preferência!`;
    window.open(`https://wa.me/${item.whatsapp}?text=${encodeURIComponent(text)}`, "_blank", "noopener");
  }

  function render() {
    const content = document.getElementById("customerVipContent");
    if (!content) return;
    const ranking = buildRanking();
    if (!ranking.length) {
      content.innerHTML = `<div class="history-item"><span>Nenhum cliente VIP encontrado ainda.</span></div>`;
      return;
    }
    content.innerHTML = ranking.map((item, index) => `
      <div class="history-item">
        <strong>${index + 1}. ${item.name}</strong>
        <span>${item.count} compra(s) • ${money(item.total)}</span>
        <span>${lastText(item.last)} • WhatsApp: ${item.whatsapp || "não cadastrado"}</span>
        <button class="btn btn-ghost btn-full" type="button" onclick="misticaCustomerVip.whatsapp(${index})">Enviar mensagem VIP</button>
      </div>
    `).join("");
  }

  function mount() {
    const admin = document.getElementById("adminContent");
    if (!admin || document.getElementById("customerVipPanel")) return;
    const panel = document.createElement("section");
    panel.id = "customerVipPanel";
    panel.className = "form-panel admin-report-panel";
    panel.innerHTML = `
      <p class="eyebrow">Clientes</p>
      <h2>Clientes VIP</h2>
      <p class="privacy-note">Ranking dos melhores compradores, ignorando vendas canceladas.</p>
      <div class="report-export-actions">
        <button class="btn btn-ghost" type="button" data-refresh-vip>Atualizar VIP</button>
        <button class="btn" type="button" data-copy-vip>Copiar ranking</button>
      </div>
      <div id="customerVipContent" class="history-list"></div>
    `;
    const followup = document.getElementById("customerFollowupPanel");
    if (followup?.nextSibling) admin.insertBefore(panel, followup.nextSibling);
    else admin.appendChild(panel);
    panel.querySelector("[data-refresh-vip]").addEventListener("click", render);
    panel.querySelector("[data-copy-vip]").addEventListener("click", copyRanking);
    render();
  }

  window.misticaCustomerVip = { render, ranking: buildRanking, message, copyRanking, whatsapp: vipWhatsapp };
  window.addEventListener("load", mount);
})();
