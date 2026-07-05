(() => {
  const KEY = "misticaSpecialOrders";

  function loadOrders() {
    try { return JSON.parse(localStorage.getItem(KEY) || "[]"); } catch { return []; }
  }

  function saveOrders(list) {
    localStorage.setItem(KEY, JSON.stringify(list));
  }

  function phone(value) {
    return String(value || "").replace(/\D/g, "");
  }

  function addOrder(event) {
    event.preventDefault();
    const name = document.getElementById("specialOrderClient")?.value.trim();
    const item = document.getElementById("specialOrderItem")?.value.trim();
    const whatsapp = document.getElementById("specialOrderWhatsapp")?.value.trim();
    if (!name || !item) return alert("Informe cliente e item da encomenda.");
    const list = loadOrders();
    list.unshift({ id: Date.now(), name, item, whatsapp, status: "Pendente", createdAt: new Date().toISOString() });
    saveOrders(list.slice(0, 50));
    event.target.reset();
    renderOrders();
  }

  function updateStatus(id, status) {
    const list = loadOrders();
    const order = list.find(item => String(item.id) === String(id));
    if (!order) return;
    order.status = status;
    order.updatedAt = new Date().toISOString();
    saveOrders(list);
    renderOrders();
  }

  function removeOrder(id) {
    if (!confirm("Remover esta encomenda?")) return;
    saveOrders(loadOrders().filter(item => String(item.id) !== String(id)));
    renderOrders();
  }

  function message(order) {
    return `Ola, ${order.name}! Aqui e da Mistica Presentes. Sua encomenda (${order.item}) esta com status: ${order.status}. Gratidao!`;
  }

  function listMessage() {
    const list = loadOrders();
    if (!list.length) return "Encomendas - Mistica Presentes\n\nNenhuma encomenda registrada.";
    return `Encomendas - Mistica Presentes\n\n${list.map(order => `• ${order.name} | ${order.item} | ${order.status} | ${order.whatsapp || "sem WhatsApp"}`).join("\n")}`;
  }

  async function copyList() {
    const text = listMessage();
    try {
      await navigator.clipboard.writeText(text);
      alert("Lista de encomendas copiada.");
    } catch {
      prompt("Copie a lista de encomendas:", text);
    }
  }

  function openWhatsapp(id) {
    const order = loadOrders().find(item => String(item.id) === String(id));
    if (!order) return;
    const number = phone(order.whatsapp);
    if (!number) return alert("Encomenda sem WhatsApp cadastrado.");
    window.open(`https://wa.me/${number}?text=${encodeURIComponent(message(order))}`, "_blank", "noopener");
  }

  function renderOrders() {
    const content = document.getElementById("specialOrdersContent");
    if (!content) return;
    const list = loadOrders();
    if (!list.length) {
      content.innerHTML = `<div class="history-item"><span>Nenhuma encomenda registrada.</span></div>`;
      return;
    }
    content.innerHTML = list.map(order => `
      <div class="history-item">
        <strong>${order.name} • ${order.status}</strong>
        <span>${order.item}</span>
        <span>WhatsApp: ${order.whatsapp || "nao informado"}</span>
        <div class="pedido-actions">
          <button class="btn btn-ghost" type="button" onclick="misticaSpecialOrders.status(${order.id}, 'Pendente')">Pendente</button>
          <button class="btn btn-ghost" type="button" onclick="misticaSpecialOrders.status(${order.id}, 'Solicitado')">Solicitado</button>
          <button class="btn btn-ghost" type="button" onclick="misticaSpecialOrders.status(${order.id}, 'Disponivel')">Disponivel</button>
          <button class="btn btn-ghost" type="button" onclick="misticaSpecialOrders.whatsapp(${order.id})">WhatsApp</button>
          <button class="btn btn-ghost" type="button" onclick="misticaSpecialOrders.remove(${order.id})">Remover</button>
        </div>
      </div>
    `).join("");
  }

  function mountOrders() {
    const admin = document.getElementById("adminContent");
    if (!admin || document.getElementById("specialOrdersPanel")) return;
    const panel = document.createElement("section");
    panel.id = "specialOrdersPanel";
    panel.className = "form-panel admin-report-panel";
    panel.innerHTML = `
      <p class="eyebrow">Encomendas</p>
      <h2>Encomendas rapidas</h2>
      <form id="specialOrderForm" class="form">
        <label>Cliente<input id="specialOrderClient" type="text" placeholder="Nome do cliente" required></label>
        <label>Item solicitado<input id="specialOrderItem" type="text" placeholder="Produto, tamanho, aroma ou detalhe" required></label>
        <label>WhatsApp<input id="specialOrderWhatsapp" type="text" placeholder="(49) 99999-9999"></label>
        <button class="btn" type="submit">Salvar encomenda</button>
      </form>
      <div class="report-export-actions">
        <button class="btn btn-ghost" type="button" onclick="misticaSpecialOrders.copyList()">Copiar lista</button>
        <button class="btn btn-ghost" type="button" onclick="misticaSpecialOrders.render()">Atualizar</button>
      </div>
      <div id="specialOrdersContent" class="history-list"></div>
    `;
    const memo = document.getElementById("adminMemoPanel");
    if (memo?.nextSibling) admin.insertBefore(panel, memo.nextSibling);
    else admin.appendChild(panel);
    panel.querySelector("#specialOrderForm").addEventListener("submit", addOrder);
    renderOrders();
  }

  window.misticaSpecialOrders = { render: renderOrders, status: updateStatus, remove: removeOrder, whatsapp: openWhatsapp, copyList, listMessage };
  window.addEventListener("load", mountOrders);
})();
