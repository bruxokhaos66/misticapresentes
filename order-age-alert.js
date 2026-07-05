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
    decorate();
    const originalRender = window.misticaSpecialOrders?.render;
    if (typeof originalRender === "function" && !window.__misticaOrderAgeAlertInstalled) {
      window.__misticaOrderAgeAlertInstalled = true;
      window.misticaSpecialOrders.render = function renderWithAgeAlert() {
        originalRender();
        decorate();
      };
    }
  }

  window.misticaOrderAgeAlert = { install, decorate };
  window.addEventListener("load", () => setTimeout(install, 400));
})();
