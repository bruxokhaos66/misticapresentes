(() => {
  function loadOrderSummary() {
    if (document.getElementById("orderSummaryScript")) return;
    const script = document.createElement("script");
    script.id = "orderSummaryScript";
    script.src = "order-summary.js";
    script.defer = true;
    document.head.appendChild(script);
  }

  function normalizar(value) {
    return String(value || "").normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase();
  }

  function aplicarFiltroStatus() {
    const select = document.getElementById("orderStatusQuickFilter");
    const painel = document.getElementById("specialOrdersContent");
    if (!select || !painel) return;
    const filtro = normalizar(select.value);
    const cards = Array.from(painel.querySelectorAll(".history-item"));
    cards.forEach(card => {
      const texto = normalizar(card.textContent);
      card.hidden = filtro !== "todos" && !texto.includes(filtro);
    });
  }

  function montarFiltroStatus() {
    const painel = document.getElementById("specialOrdersPanel");
    const lista = document.getElementById("specialOrdersContent");
    if (!painel || !lista || document.getElementById("orderStatusQuickFilter")) return;
    const bloco = document.createElement("div");
    bloco.className = "report-filters";
    bloco.innerHTML = `
      <label>Status da encomenda
        <select id="orderStatusQuickFilter">
          <option value="todos">Todos</option>
          <option value="Pendente">Pendente</option>
          <option value="Solicitado">Solicitado</option>
          <option value="Disponivel">Disponivel</option>
        </select>
      </label>
    `;
    lista.parentNode.insertBefore(bloco, lista);
    bloco.querySelector("select").addEventListener("change", aplicarFiltroStatus);
  }

  function instalar() {
    montarFiltroStatus();
    const originalRender = window.misticaSpecialOrders?.render;
    if (typeof originalRender === "function" && !window.__misticaOrderStatusFilterInstalled) {
      window.__misticaOrderStatusFilterInstalled = true;
      window.misticaSpecialOrders.render = function renderComFiltroStatus() {
        originalRender();
        montarFiltroStatus();
        aplicarFiltroStatus();
      };
    }
    loadOrderSummary();
  }

  window.misticaOrderStatusFilter = { install: instalar, apply: aplicarFiltroStatus };
  window.addEventListener("load", () => setTimeout(instalar, 200));
})();
