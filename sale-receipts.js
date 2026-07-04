(() => {
  function textoSeguro(value) {
    return String(value ?? "");
  }

  function escapeInline(value) {
    return textoSeguro(value).replace(/\\/g, "\\\\").replace(/'/g, "\\'");
  }

  function carregarFiltrosHistorico() {
    if (document.getElementById("salesHistoryFiltersScript")) return;
    const script = document.createElement("script");
    script.id = "salesHistoryFiltersScript";
    script.src = "sales-history-filters.js";
    script.defer = true;
    document.head.appendChild(script);
  }

  function vendaPorId(vendaId) {
    if (typeof sales === "undefined" || !Array.isArray(sales)) return null;
    return sales.find(item => String(item.id) === String(vendaId));
  }

  function itensVenda(venda) {
    return Array.isArray(venda?.items) ? venda.items : [];
  }

  function mensagemComprovante(venda) {
    const nomeLoja = typeof storeConfig !== "undefined" ? storeConfig.name : "Mística Presentes";
    const total = typeof currency !== "undefined"
      ? currency.format(Number(venda.total || 0))
      : `R$ ${Number(venda.total || 0).toFixed(2).replace(".", ",")}`;
    const data = venda.date ? new Date(venda.date).toLocaleString("pt-BR") : new Date().toLocaleString("pt-BR");
    const itens = itensVenda(venda)
      .map(item => `• ${item.qty || 1}x ${item.name || "Item"} - ${typeof currency !== "undefined" ? currency.format(Number(item.price || 0) * Number(item.qty || 1)) : ""}`)
      .join("\n");

    return `Comprovante/Pedido - ${nomeLoja}\n\nPedido: ${venda.id || ""}\nData: ${data}\nStatus: ${venda.status || "Atualização"}\n\n${itens}\n\nTotal: ${total}\n\nGratidão pela preferência.`;
  }

  function numeroWhatsappLoja() {
    const siteNumber = window.misticaSiteConfig?.whatsappNumber;
    const configNumber = typeof storeConfig !== "undefined" ? storeConfig.whatsappNumber : "";
    return textoSeguro(siteNumber || configNumber || "554999172137").replace(/\D/g, "");
  }

  function abrirComprovanteWhatsapp(vendaId) {
    const venda = vendaPorId(vendaId);
    if (!venda) return alert("Venda não encontrada para enviar comprovante.");
    const url = `https://wa.me/${numeroWhatsappLoja()}?text=${encodeURIComponent(mensagemComprovante(venda))}`;
    window.open(url, "_blank", "noopener");
  }

  function imprimirComprovanteVenda(vendaId) {
    const venda = vendaPorId(vendaId);
    if (!venda) return alert("Venda não encontrada para imprimir comprovante.");
    if (typeof printReceipt === "function") return printReceipt(venda);
    window.print();
  }

  function inserirAcoesComprovante() {
    if (typeof renderHistory !== "function" || window.__misticaReceiptHistoryInstalled) return;
    window.__misticaReceiptHistoryInstalled = true;
    const renderOriginal = renderHistory;

    renderHistory = function renderHistoryWithReceipts() {
      renderOriginal();
      const historico = document.getElementById("salesHistory");
      if (!historico || typeof sales === "undefined" || !Array.isArray(sales)) return;
      const cards = Array.from(historico.querySelectorAll(".history-item"));
      sales.slice(0, 10).forEach((sale, index) => {
        const card = cards[index];
        if (!card || card.querySelector("[data-sale-receipt-actions]")) return;
        const vendaId = escapeInline(sale.id);
        const actions = document.createElement("div");
        actions.className = "pedido-actions";
        actions.dataset.saleReceiptActions = "true";
        actions.innerHTML = `
          <button class="btn btn-ghost" type="button" onclick="sendSaleReceiptWhatsapp('${vendaId}')">Comprovante WhatsApp</button>
          <button class="btn btn-ghost" type="button" onclick="printSaleReceipt('${vendaId}')">Imprimir cupom</button>
        `;
        card.appendChild(actions);
      });
    };

    renderHistory();
  }

  window.sendSaleReceiptWhatsapp = abrirComprovanteWhatsapp;
  window.printSaleReceipt = imprimirComprovanteVenda;
  window.misticaSaleReceipts = {
    sendWhatsapp: abrirComprovanteWhatsapp,
    print: imprimirComprovanteVenda,
    message: mensagemComprovante,
  };

  window.addEventListener("load", () => {
    inserirAcoesComprovante();
    carregarFiltrosHistorico();
  });
})();
