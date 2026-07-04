(() => {
  const filtrosHistorico = {
    busca: "",
    status: "todos",
  };

  function normalizar(value) {
    return String(value || "").normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase();
  }

  function textoVenda(venda) {
    const itens = Array.isArray(venda?.items) ? venda.items.map(item => `${item.qty || 1}x ${item.name || "Item"}`).join(" ") : "";
    return normalizar(`${venda?.id || ""} ${venda?.status || ""} ${itens} ${venda?.formaPagamento || ""} ${venda?.vendedor || ""}`);
  }

  function listaFiltrada() {
    if (typeof sales === "undefined" || !Array.isArray(sales)) return [];
    const termo = normalizar(filtrosHistorico.busca);
    const status = normalizar(filtrosHistorico.status);
    return sales.filter(venda => {
      const matchBusca = !termo || textoVenda(venda).includes(termo);
      const matchStatus = status === "todos" || normalizar(venda.status).includes(status);
      return matchBusca && matchStatus;
    });
  }

  function montarFerramentas() {
    const history = document.getElementById("salesHistory");
    if (!history || document.getElementById("salesHistoryTools")) return;

    const panel = document.createElement("div");
    panel.id = "salesHistoryTools";
    panel.className = "admin-activity-tools";
    panel.innerHTML = `
      <input type="search" placeholder="Buscar por pedido, produto ou status" data-sales-history-search>
      <select data-sales-history-status aria-label="Filtrar status">
        <option value="todos">Todos os status</option>
        <option value="aguardando pagamento">Aguardando pagamento</option>
        <option value="pago">Pago</option>
        <option value="em separacao">Em separação</option>
        <option value="pronto para retirada">Pronto para retirada</option>
        <option value="entregue">Entregue</option>
        <option value="cancelado">Cancelado</option>
      </select>
    `;
    history.parentNode.insertBefore(panel, history);

    const summary = document.createElement("div");
    summary.id = "salesHistorySummary";
    summary.className = "privacy-note";
    history.parentNode.insertBefore(summary, history);
  }

  function atualizarResumo(lista) {
    const summary = document.getElementById("salesHistorySummary");
    if (!summary) return;
    const total = lista.reduce((sum, venda) => sum + Number(venda.total || 0), 0);
    const moeda = typeof currency !== "undefined" ? currency.format(total) : `R$ ${total.toFixed(2).replace(".", ",")}`;
    summary.textContent = `${lista.length} venda(s) encontrada(s) • Total filtrado: ${moeda}`;
  }

  function aplicarFiltroVisual(lista) {
    const history = document.getElementById("salesHistory");
    if (!history) return;
    const idsPermitidos = new Set(lista.slice(0, 10).map(venda => String(venda.id)));
    Array.from(history.querySelectorAll(".history-item")).forEach((card, index) => {
      const venda = sales[index];
      card.hidden = venda ? !idsPermitidos.has(String(venda.id)) : false;
    });
    if (!lista.length) {
      history.innerHTML = `<div class="history-item"><span>Nenhuma venda encontrada para este filtro.</span></div>`;
    }
  }

  function aplicarFiltros() {
    montarFerramentas();
    const lista = listaFiltrada();
    atualizarResumo(lista);
    aplicarFiltroVisual(lista);
  }

  function instalarFiltrosHistorico() {
    if (typeof renderHistory !== "function" || window.__misticaSalesHistoryFiltersInstalled) return;
    window.__misticaSalesHistoryFiltersInstalled = true;
    const renderOriginal = renderHistory;

    renderHistory = function renderHistoryWithFilters() {
      renderOriginal();
      aplicarFiltros();
    };

    document.addEventListener("input", event => {
      if (event.target?.dataset?.salesHistorySearch === undefined) return;
      filtrosHistorico.busca = event.target.value;
      renderHistory();
    });

    document.addEventListener("change", event => {
      if (event.target?.dataset?.salesHistoryStatus === undefined) return;
      filtrosHistorico.status = event.target.value;
      renderHistory();
    });

    renderHistory();
  }

  window.misticaSalesHistoryFilters = {
    apply: aplicarFiltros,
    getFiltered: listaFiltrada,
  };

  window.addEventListener("load", instalarFiltrosHistorico);
})();
