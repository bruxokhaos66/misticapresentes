(() => {
  const KEY = "misticaSpecialOrders";
  const LIMIT_DAYS = 7;

  function loadOrders() {
    try { return JSON.parse(localStorage.getItem(KEY) || "[]"); } catch { return []; }
  }

  function daysSince(value) {
    const date = value ? new Date(value) : null;
    if (!date || Number.isNaN(date.getTime())) return null;
    const dayMs = 24 * 60 * 60 * 1000;
    return Math.floor((Date.now() - date.getTime()) / dayMs);
  }

  function whatsappNumber() {
    const siteNumber = window.misticaSiteConfig?.whatsappNumber;
    const configNumber = typeof storeConfig !== "undefined" ? storeConfig.whatsappNumber : "";
    return String(siteNumber || configNumber || "554999172137").replace(/\D/g, "");
  }

  function lateOrders() {
    return loadOrders()
      .map(order => ({ ...order, days: daysSince(order.createdAt) }))
      .filter(order => order.days !== null && order.days >= LIMIT_DAYS && order.status !== "Disponivel");
  }

  function lateMessage() {
    const list = lateOrders();
    if (!list.length) return "Encomendas atrasadas - Mistica Presentes\n\nNenhuma encomenda atrasada.";
    return `Encomendas atrasadas - Mistica Presentes\n\n${list.map(order => `• ${order.name} | ${order.item} | ${order.status} | ${order.days} dia(s) | ${order.whatsapp || "sem WhatsApp"}`).join("\n")}`;
  }

  async function copyLateOrders() {
    const text = lateMessage();
    try {
      await navigator.clipboard.writeText(text);
      alert("Lista de encomendas atrasadas copiada.");
    } catch {
      prompt("Copie a lista de encomendas atrasadas:", text);
    }
  }

  function sendLateOrdersWhatsapp() {
    window.open(`https://wa.me/${whatsappNumber()}?text=${encodeURIComponent(lateMessage())}`, "_blank", "noopener");
  }

  function mountLateButton() {
    const panel = document.getElementById("specialOrdersPanel");
    const actions = panel?.querySelector(".report-export-actions");
    if (!actions) return;
    if (!document.getElementById("copyLateOrdersButton")) {
      const copyButton = document.createElement("button");
      copyButton.id = "copyLateOrdersButton";
      copyButton.className = "btn btn-ghost";
      copyButton.type = "button";
      copyButton.textContent = "Copiar atrasadas";
      copyButton.addEventListener("click", copyLateOrders);
      actions.appendChild(copyButton);
    }
    if (!document.getElementById("whatsappLateOrdersButton")) {
      const whatsappButton = document.createElement("button");
      whatsappButton.id = "whatsappLateOrdersButton";
      whatsappButton.className = "btn btn-ghost";
      whatsappButton.type = "button";
      whatsappButton.textContent = "WhatsApp atrasadas";
      whatsappButton.addEventListener("click", sendLateOrdersWhatsapp);
      actions.appendChild(whatsappButton);
    }
  }

  function decorate() {
    const content = document.getElementById("specialOrdersContent");
    if (!content) return;
    const orders = loadOrders();
    const cards = Array.from(content.querySelectorAll(".history-item"));
    cards.forEach(card => {
      const text = card.textContent || "";
      const order = orders.find(item => text.includes(item.name) && text.includes(item.item));
      if (!order || order.status === "Disponivel") return;
      const days = daysSince(order.createdAt);
      if (days === null) return;
      if (!card.querySelector("[data-order-age]")) {
        const badge = document.createElement("span");
        badge.dataset.orderAge = "true";
        badge.textContent = days >= LIMIT_DAYS ? `Atenção: ${days} dia(s) em aberto` : `${days} dia(s) em aberto`;
        card.insertBefore(badge, card.querySelector(".pedido-actions"));
      }
      if (days >= LIMIT_DAYS) card.classList.add("order-age-warning");
    });
  }

  function install() {
    mountLateButton();
    decorate();
    const originalRender = window.misticaSpecialOrders?.render;
    if (typeof originalRender === "function" && !window.__misticaOrderAgeAlertInstalled) {
      window.__misticaOrderAgeAlertInstalled = true;
      window.misticaSpecialOrders.render = function renderWithAgeAlert() {
        originalRender();
        mountLateButton();
        decorate();
      };
    }
  }

  window.misticaOrderAgeAlert = { install, decorate, lateOrders, lateMessage, copyLateOrders, sendWhatsapp: sendLateOrdersWhatsapp };
  window.addEventListener("load", () => setTimeout(install, 400));
})();
