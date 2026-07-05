(() => {
  const KEY = "misticaSpecialOrders";
  const LIMIT_DAYS = 7;
  let lateOnly = false;

  function installActiveStyle() {
    if (document.getElementById("lateOrdersActiveStyle")) return;
    const style = document.createElement("style");
    style.id = "lateOrdersActiveStyle";
    style.textContent = `
      #filterLateOrdersButton.active {
        background: rgba(240, 197, 106, 0.24);
        border-color: rgba(240, 197, 106, 0.62);
        color: #fff8e7;
        box-shadow: 0 0 0 1px rgba(240, 197, 106, 0.16);
      }
      #lateOrdersSummary {
        cursor: pointer;
      }
      #lateOrdersSummary:hover {
        border-color: rgba(240, 197, 106, 0.42);
        background: rgba(240, 197, 106, 0.08);
      }
    `;
    document.head.appendChild(style);
  }

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

  function lateCountText() {
    const count = lateOrders().length;
    return count ? `${count} atrasada(s)` : "sem atrasadas";
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

  function updateLateButtons() {
    const countText = lateCountText();
    const copyButton = document.getElementById("copyLateOrdersButton");
    const whatsappButton = document.getElementById("whatsappLateOrdersButton");
    const filterButton = document.getElementById("filterLateOrdersButton");
    if (copyButton) copyButton.textContent = `Copiar atrasadas (${countText})`;
    if (whatsappButton) whatsappButton.textContent = `WhatsApp atrasadas (${countText})`;
    if (filterButton) {
      filterButton.textContent = lateOnly ? "Mostrar todas" : `Ver atrasadas (${countText})`;
      filterButton.classList.toggle("active", lateOnly);
    }
  }

  function renderLateSummary() {
    const panel = document.getElementById("specialOrdersPanel");
    const content = document.getElementById("specialOrdersContent");
    if (!panel || !content) return;
    let summary = document.getElementById("lateOrdersSummary");
    if (!summary) {
      summary = document.createElement("div");
      summary.id = "lateOrdersSummary";
      summary.className = "report-card";
      summary.title = "Clique para filtrar encomendas atrasadas";
      summary.addEventListener("click", toggleLateOnly);
      content.parentNode.insertBefore(summary, content);
    }
    const list = lateOrders();
    const oldest = list.reduce((max, order) => Math.max(max, order.days || 0), 0);
    summary.innerHTML = `<span>Encomendas atrasadas</span><strong>${list.length}</strong><small>${oldest ? `Mais antiga: ${oldest} dia(s)` : "Nenhuma acima do prazo"}</small>`;
  }

  function updateEmptyNotice(visible) {
    const content = document.getElementById("specialOrdersContent");
    if (!content) return;
    let notice = document.getElementById("lateOrdersEmptyNotice");
    if (!notice) {
      notice = document.createElement("div");
      notice.id = "lateOrdersEmptyNotice";
      notice.className = "history-item";
      notice.innerHTML = "<span>Nenhuma encomenda atrasada encontrada.</span>";
      content.appendChild(notice);
    }
    notice.hidden = !visible;
  }

  function applyLateFilter() {
    const content = document.getElementById("specialOrdersContent");
    if (!content) return;
    const late = lateOrders();
    const cards = Array.from(content.querySelectorAll(".history-item:not(#lateOrdersEmptyNotice)"));
    let visibleCount = 0;
    cards.forEach(card => {
      if (!lateOnly) {
        card.hidden = false;
        return;
      }
      const text = card.textContent || "";
      const match = late.some(order => text.includes(order.name) && text.includes(order.item));
      card.hidden = !match;
      if (match) visibleCount += 1;
    });
    updateEmptyNotice(lateOnly && visibleCount === 0);
    updateLateButtons();
  }

  function toggleLateOnly() {
    lateOnly = !lateOnly;
    applyLateFilter();
  }

  function mountLateButton() {
    const panel = document.getElementById("specialOrdersPanel");
    const actions = panel?.querySelector(".report-export-actions");
    if (!actions) return;
    if (!document.getElementById("filterLateOrdersButton")) {
      const filterButton = document.createElement("button");
      filterButton.id = "filterLateOrdersButton";
      filterButton.className = "btn btn-ghost";
      filterButton.type = "button";
      filterButton.addEventListener("click", toggleLateOnly);
      actions.appendChild(filterButton);
    }
    if (!document.getElementById("copyLateOrdersButton")) {
      const copyButton = document.createElement("button");
      copyButton.id = "copyLateOrdersButton";
      copyButton.className = "btn btn-ghost";
      copyButton.type = "button";
      copyButton.addEventListener("click", copyLateOrders);
      actions.appendChild(copyButton);
    }
    if (!document.getElementById("whatsappLateOrdersButton")) {
      const whatsappButton = document.createElement("button");
      whatsappButton.id = "whatsappLateOrdersButton";
      whatsappButton.className = "btn btn-ghost";
      whatsappButton.type = "button";
      whatsappButton.addEventListener("click", sendLateOrdersWhatsapp);
      actions.appendChild(whatsappButton);
    }
    updateLateButtons();
  }

  function orderLateFirst() {
    const content = document.getElementById("specialOrdersContent");
    if (!content) return;
    const late = lateOrders();
    const cards = Array.from(content.querySelectorAll(".history-item:not(#lateOrdersEmptyNotice)"));
    cards
      .sort((a, b) => {
        const aText = a.textContent || "";
        const bText = b.textContent || "";
        const aLate = late.find(order => aText.includes(order.name) && aText.includes(order.item));
        const bLate = late.find(order => bText.includes(order.name) && bText.includes(order.item));
        return (bLate?.days || 0) - (aLate?.days || 0);
      })
      .forEach(card => content.appendChild(card));
  }

  function decorate() {
    const content = document.getElementById("specialOrdersContent");
    if (!content) return;
    const orders = loadOrders();
    const cards = Array.from(content.querySelectorAll(".history-item:not(#lateOrdersEmptyNotice)"));
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
    renderLateSummary();
    orderLateFirst();
    applyLateFilter();
    updateLateButtons();
  }

  function install() {
    installActiveStyle();
    mountLateButton();
    decorate();
    const originalRender = window.misticaSpecialOrders?.render;
    if (typeof originalRender === "function" && !window.__misticaOrderAgeAlertInstalled) {
      window.__misticaOrderAgeAlertInstalled = true;
      window.misticaSpecialOrders.render = function renderWithAgeAlert() {
        originalRender();
        installActiveStyle();
        mountLateButton();
        decorate();
      };
    }
  }

  window.misticaOrderAgeAlert = { install, decorate, lateOrders, lateMessage, copyLateOrders, sendWhatsapp: sendLateOrdersWhatsapp, updateButtons: updateLateButtons, toggleLateOnly, orderLateFirst, renderLateSummary };
  window.addEventListener("load", () => setTimeout(install, 400));
})();
