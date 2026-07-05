(() => {
  function phone(value) {
    return String(value || "").replace(/\D/g, "");
  }

  function nameOf(client) {
    return client?.name || client?.nome || client?.cliente || "Cliente";
  }

  function phoneOf(client) {
    return phone(client?.whatsapp || client?.telefone || client?.phone || client?.celular || "");
  }

  function emailOf(client) {
    return String(client?.email || client?.mail || "").trim();
  }

  function missingOf(client) {
    const missing = [];
    if (!nameOf(client) || nameOf(client) === "Cliente") missing.push("nome");
    if (!phoneOf(client)) missing.push("WhatsApp");
    if (!emailOf(client)) missing.push("email");
    return missing;
  }

  function items() {
    const source = typeof clients !== "undefined" && Array.isArray(clients) ? clients : [];
    return source.map(client => ({ client, missing: missingOf(client) })).filter(item => item.missing.length);
  }

  function text() {
    const list = items();
    if (!list.length) return "Cadastros incompletos - Mistica Presentes\n\nNenhum item encontrado.";
    return `Cadastros incompletos - Mistica Presentes\n\n${list.map((item, index) => `${index + 1}. ${nameOf(item.client)} - falta: ${item.missing.join(", ")}`).join("\n")}`;
  }

  async function copy() {
    const value = text();
    try {
      await navigator.clipboard.writeText(value);
      alert("Lista copiada.");
    } catch {
      prompt("Copie a lista:", value);
    }
  }

  function render() {
    const content = document.getElementById("customerMissingContent");
    if (!content) return;
    const list = items();
    if (!list.length) {
      content.innerHTML = `<div class="history-item"><span>Nenhum cadastro incompleto encontrado.</span></div>`;
      return;
    }
    content.innerHTML = list.map(item => `
      <div class="history-item">
        <strong>${nameOf(item.client)}</strong>
        <span>Falta: ${item.missing.join(", ")}</span>
        <span>WhatsApp: ${phoneOf(item.client) || "nao cadastrado"} • Email: ${emailOf(item.client) || "nao cadastrado"}</span>
      </div>
    `).join("");
  }

  function mount() {
    const admin = document.getElementById("adminContent");
    if (!admin || document.getElementById("customerMissingPanel")) return;
    const panel = document.createElement("section");
    panel.id = "customerMissingPanel";
    panel.className = "form-panel admin-report-panel";
    panel.innerHTML = `
      <p class="eyebrow">Clientes</p>
      <h2>Cadastros incompletos</h2>
      <p class="privacy-note">Clientes sem nome, WhatsApp ou email.</p>
      <div class="report-export-actions">
        <button class="btn btn-ghost" type="button" data-refresh-missing>Atualizar</button>
        <button class="btn" type="button" data-copy-missing>Copiar lista</button>
      </div>
      <div id="customerMissingContent" class="history-list"></div>
    `;
    const vip = document.getElementById("customerVipPanel");
    if (vip?.nextSibling) admin.insertBefore(panel, vip.nextSibling);
    else admin.appendChild(panel);
    panel.querySelector("[data-refresh-missing]").addEventListener("click", render);
    panel.querySelector("[data-copy-missing]").addEventListener("click", copy);
    render();
  }

  window.misticaCustomerMissing = { render, items, text, copy };
  window.addEventListener("load", mount);
})();
