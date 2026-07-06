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

  function getProducts() {
    try { return Array.isArray(products) ? products : []; } catch { return []; }
  }

  function getCartItems() {
    try { return Array.isArray(cart) ? cart.map(item => ({ ...item })) : []; } catch { return []; }
  }

  function produtoDoCarrinho(item) {
    return getProducts().find(p => p.id === item.id) || null;
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
    try { if (typeof setStatus === "function") setStatus(msg); } catch {}
  }

  function guardarPendente(venda) {
    try {
      const key = "misticaPendingOrders";
      const lista = JSON.parse(localStorage.getItem(key) || "[]");
      lista.unshift({ ...venda, pendingAt: new Date().toISOString() });
      localStorage.setItem(key, JSON.stringify(lista.slice(0, 20)));
    } catch {}
  }

  function atualizarTelaDepoisVenda(saved, venda) {
    const id = saved?.id || venda.id;
    try {
      if (Array.isArray(sales)) {
        sales.unshift({ ...venda, id: String(id), apiId: id });
        sales = sales.slice(0, 50);
      }
    } catch {}
    try { cart = []; } catch {}
    try { if (typeof saveState === "function") saveState(); } catch {}
    try { if (typeof renderAll === "function") renderAll(); } catch {}
    avisar("Pedido confirmado pela API. Estoque sincronizado pelo sistema.");
    try { if (window.misticaMobileSync?.syncNow) window.misticaMobileSync.syncNow(); } catch {}
  }

  function instalar() {
    try {
      if (window.__misticaSaleApiFirstMinimalInstalled || typeof saveSale !== "function") return;
      window.__misticaSaleApiFirstMinimalInstalled = true;
      saveSale = function saveSaleApiFirst(pixPayload, saleId) {
        const items = getCartItems();
        const total = typeof getTotal === "function" ? getTotal() : items.reduce((s, i) => s + Number(i.price || 0) * Number(i.qty || 0), 0);
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
          atualizarTelaDepoisVenda(saved, venda);
        }).catch(err => {
          guardarPendente(venda);
          avisar(`API não confirmou. Carrinho preservado e estoque não foi baixado: ${String(err.message || err).slice(0, 100)}`);
        });
      };
    } catch {}
  }

  window.addEventListener("load", () => {
    instalar();
    setTimeout(instalar, 500);
    setTimeout(instalar, 1500);
  });
})();
