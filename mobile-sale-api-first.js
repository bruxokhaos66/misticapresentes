(() => {
  const cfg = window.misticaSiteConfig || {};
  const productionMode = cfg.serverMode === "production" || cfg.storageMode === "api_first" || cfg.usePublicDomainAccess === true;
  if (!productionMode) return;

  const API_BASE = String(cfg.apiBaseUrl || "https://api.misticaesotericos.com.br").replace(/\/$/, "");
  const SITE_API_KEY = String(cfg.siteApiKey || "").trim();

  function headers() {
    return {
      "Content-Type": "application/json",
      ...(SITE_API_KEY ? { "X-Mistica-Api-Key": SITE_API_KEY } : {}),
    };
  }

  async function postVenda(payload) {
    const res = await fetch(`${API_BASE}/api/vendas`, {
      method: "POST",
      headers: headers(),
      body: JSON.stringify(payload),
    });
    if (!res.ok) throw new Error(`API ${res.status}`);
    return res.json();
  }

  function produtoDoCarrinho(item) {
    return Array.isArray(window.products) ? window.products.find(p => p.id === item.id) : null;
  }

  function montarItens(items) {
    return items.map(item => {
      const produto = produtoDoCarrinho(item);
      if (!produto?.apiId && !produto?.codigo) throw new Error("Produto sem código da API. Sincronize o catálogo antes da venda.");
      return {
        produto_id: produto?.apiId || null,
        codigo_p: produto?.codigo || item.id,
        nome_p: item.name,
        quantidade: Number(item.qty || 0),
        custo_unitario: 0,
        valor_unitario: Number(item.price || 0),
        valor_total: Number(item.price || 0) * Number(item.qty || 0),
      };
    });
  }

  function avisar(msg) {
    const el = document.getElementById("mobileSyncStatus") || document.getElementById("pixStatus");
    if (el) el.textContent = msg;
    if (typeof window.setStatus === "function") {
      try { window.setStatus(msg); } catch {}
    }
  }

  function guardarPendente(venda) {
    try {
      const key = "misticaPendingOrders";
      const lista = JSON.parse(localStorage.getItem(key) || "[]");
      lista.unshift({ ...venda, pendingAt: new Date().toISOString() });
      localStorage.setItem(key, JSON.stringify(lista.slice(0, 20)));
    } catch {}
  }

  function instalar() {
    if (window.__misticaSaleApiFirstMinimalInstalled || typeof window.saveSale !== "function") return;
    window.__misticaSaleApiFirstMinimalInstalled = true;
    window.saveSale = function saveSaleApiFirst(pixPayload, saleId) {
      const items = Array.isArray(window.cart) ? window.cart.map(item => ({ ...item })) : [];
      const total = typeof window.getTotal === "function" ? window.getTotal() : items.reduce((s, i) => s + Number(i.price || 0) * Number(i.qty || 0), 0);
      const venda = { id: saleId, date: new Date().toISOString(), total, items, pixPayload, status: "Aguardando pagamento" };
      let apiItems;
      try {
        apiItems = montarItens(items);
      } catch (err) {
        guardarPendente(venda);
        avisar(String(err.message || err));
        return;
      }
      avisar("Enviando pedido para a API antes de limpar carrinho ou baixar estoque...");
      postVenda({
        origem: "site",
        cliente: "Pedido site/celular",
        subtotal: total,
        desconto: 0,
        taxa: 0,
        total_final: total,
        forma_pagamento: "Pix site/celular",
        vendedor: "Site/Celular",
        status: "Aguardando pagamento",
        data_venda: new Date(venda.date).toLocaleString("pt-BR"),
        data_iso: venda.date,
        dia_operacional: venda.date.slice(0, 10),
        baixa_estoque: true,
        itens: apiItems,
      }).then(saved => {
        const id = saved?.id || saleId;
        if (Array.isArray(window.sales)) window.sales.unshift({ ...venda, id: String(id), apiId: id });
        if (Array.isArray(window.sales)) window.sales = window.sales.slice(0, 50);
        window.cart = [];
        if (typeof window.saveState === "function") window.saveState();
        if (typeof window.renderAll === "function") window.renderAll();
        avisar("Pedido confirmado pela API. Estoque sincronizado pelo sistema.");
        if (window.misticaMobileSync?.syncNow) window.misticaMobileSync.syncNow();
      }).catch(err => {
        guardarPendente(venda);
        avisar(`API não confirmou. Carrinho preservado e estoque não foi baixado: ${String(err.message || err).slice(0, 100)}`);
      });
    };
  }

  window.addEventListener("load", () => {
    instalar();
    setTimeout(instalar, 500);
    setTimeout(instalar, 1500);
  });
})();
