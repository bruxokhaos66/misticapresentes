(() => {
  const config = window.misticaSiteConfig || {};
  const API_BASE = (config.apiBaseUrl || "https://api.misticaesotericos.com.br").replace(/\/$/, "");
  const SYNC_INTERVAL_MS = 5000;

  let syncRunning = false;
  let lastSyncAt = null;

  function carregarPainelAuth() {
    if (document.getElementById("painelAuthScript")) return;
    const script = document.createElement("script");
    script.id = "painelAuthScript";
    script.src = "painel-auth.js";
    script.defer = true;
    document.head.appendChild(script);
  }

  function statusEl() {
    let el = document.getElementById("mobileSyncStatus");
    if (!el) {
      el = document.createElement("div");
      el.id = "mobileSyncStatus";
      el.setAttribute("aria-live", "polite");
      el.style.position = "fixed";
      el.style.right = "12px";
      el.style.bottom = "12px";
      el.style.zIndex = "9999";
      el.style.padding = "8px 10px";
      el.style.borderRadius = "999px";
      el.style.font = "600 12px Inter, Arial, sans-serif";
      el.style.boxShadow = "0 8px 24px rgba(0,0,0,.25)";
      el.style.background = "#162116";
      el.style.color = "#dff5d8";
      document.body.appendChild(el);
    }
    return el;
  }

  function setSyncStatus(text, ok = true) {
    const el = statusEl();
    el.textContent = text;
    el.style.background = ok ? "#162116" : "#3b1c1c";
    el.style.color = ok ? "#dff5d8" : "#ffd7d7";
  }

  async function api(path, options = {}) {
    const response = await fetch(`${API_BASE}${path}`, {
      ...options,
      headers: {
        "Content-Type": "application/json",
        ...(options.headers || {}),
      },
    });
    if (!response.ok) throw new Error(`API ${response.status}`);
    return response.json();
  }

  function normalizarProduto(item) {
    const codigo = item.codigo_p || item.codigo || String(item.id);
    const id = `api-${item.id}`;
    return {
      id,
      apiId: item.id,
      codigo,
      name: item.nome || item.nome_p || "Produto sem nome",
      category: item.categoria || "Produtos da loja",
      description: item.descricao || (item.categoria ? `Categoria: ${item.categoria}` : "Produto sincronizado da loja."),
      price: Number(item.preco || item.valor || 0),
      stock: Number(item.quantidade || item.estoque || 0),
      icon: item.icone || "✨",
      imageUrl: item.imagem || item.imageUrl || "",
      images: Array.isArray(item.imagens) ? item.imagens : [],
    };
  }

  function aplicarProdutos(lista) {
    if (!Array.isArray(lista) || !lista.length || typeof products === "undefined") return;
    const novos = lista.map(normalizarProduto);
    products.splice(0, products.length, ...novos);
    stock = novos.reduce((map, product) => {
      map[product.id] = product.stock;
      return map;
    }, {});
  }

  function aplicarClientes(lista) {
    if (!Array.isArray(lista) || typeof clients === "undefined") return;
    clients = lista.map(c => ({
      id: c.id,
      name: c.nome || "Cliente",
      cpf: c.cpf || "",
      address: c.endereco || "",
      whatsapp: c.telefone || "",
      createdAt: new Date().toISOString(),
    })).slice(0, 50);
  }

  function aplicarVendas(lista) {
    if (!Array.isArray(lista) || typeof sales === "undefined") return;
    sales = lista.map(v => {
      const total = Number(v.total_final || v.subtotal || 0);
      return {
        id: String(v.id),
        date: v.data_iso || v.data_venda || new Date().toISOString(),
        total,
        items: Array.isArray(v.itens) && v.itens.length
          ? v.itens.map(item => ({ qty: Number(item.quantidade || 1), name: item.nome_p || item.nome || "Item", price: Number(item.valor_unitario || 0) }))
          : [{ qty: 1, name: v.cliente || "Venda sincronizada", price: total }],
        status: v.status || "Concluído",
        formaPagamento: v.forma_pagamento || "",
        vendedor: v.vendedor || "",
      };
    }).slice(0, 50);
  }

  async function sincronizarAgora() {
    if (syncRunning) return;
    syncRunning = true;
    try {
      const [status, produtos, vendas, clientes] = await Promise.all([
        api("/api/status"),
        api("/api/produtos?limite=500"),
        api("/api/vendas?limite=50"),
        api("/api/clientes?limite=50"),
      ]);

      aplicarProdutos(produtos);
      aplicarVendas(vendas);
      aplicarClientes(clientes);
      lastSyncAt = new Date();

      try {
        saveState();
        renderAll();
      } catch {}

      setSyncStatus(`Online • estoque sincronizado • ${status.produtos || 0} produtos • ${lastSyncAt.toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" })}`, true);
    } catch (error) {
      setSyncStatus("Offline • usando dados locais", false);
    } finally {
      syncRunning = false;
    }
  }

  async function reservarEstoqueApi(itens, vendaId) {
    const payload = {
      origem: "site",
      venda_id: vendaId,
      itens: itens.map(item => {
        const produto = products.find(p => p.id === item.id);
        return {
          produto_id: produto?.apiId || null,
          codigo_p: produto?.codigo || item.id,
          nome_p: item.name,
          quantidade: Number(item.qty || 0),
        };
      }),
    };
    return api("/api/estoque/reservar", { method: "POST", body: JSON.stringify(payload) });
  }

  async function enviarVendaApi(venda, itens) {
    const payload = {
      origem: "site",
      cliente: "Pedido site/celular",
      subtotal: Number(venda.total || 0),
      desconto: 0,
      taxa: 0,
      total_final: Number(venda.total || 0),
      forma_pagamento: "Pix site/celular",
      vendedor: "Site/Celular",
      status: venda.status || "Aguardando conferência do pagamento",
      data_venda: new Date(venda.date).toLocaleString("pt-BR"),
      data_iso: venda.date,
      dia_operacional: new Date(venda.date).toISOString().slice(0, 10),
      baixa_estoque: true,
      itens: itens.map(item => {
        const produto = products.find(p => p.id === item.id);
        return {
          produto_id: produto?.apiId || null,
          codigo_p: produto?.codigo || item.id,
          nome_p: item.name,
          quantidade: Number(item.qty || 0),
          custo_unitario: 0,
          valor_unitario: Number(item.price || 0),
          valor_total: Number(item.price || 0) * Number(item.qty || 0),
        };
      }),
    };
    return api("/api/vendas", { method: "POST", body: JSON.stringify(payload) });
  }

  function instalarEnvioVendas() {
    if (typeof saveSale !== "function" || window.__misticaMobileSaveSaleInstalled) return;
    window.__misticaMobileSaveSaleInstalled = true;
    saveSale = function(payload, saleId) {
      const saleItems = cart.map(item => ({ ...item }));
      const total = getTotal();
      reduceStockFromCart();
      const venda = {
        date: new Date().toISOString(),
        id: saleId,
        total,
        items: saleItems,
        pixPayload: payload,
        status: "Aguardando conferência do pagamento",
      };
      sales.unshift(venda);
      sales = sales.slice(0, 50);
      cart = [];
      saveState();
      renderAll();

      reservarEstoqueApi(saleItems, saleId)
        .catch(() => null)
        .then(() => enviarVendaApi(venda, saleItems))
        .then(() => sincronizarAgora())
        .catch(() => setSyncStatus("Venda local salva • API offline", false));
    };
  }

  window.misticaMobileSync = {
    apiBase: API_BASE,
    syncNow: sincronizarAgora,
    sendSale: enviarVendaApi,
    reserveStock: reservarEstoqueApi,
  };

  window.addEventListener("load", () => {
    carregarPainelAuth();
    instalarEnvioVendas();
    sincronizarAgora();
    setInterval(sincronizarAgora, SYNC_INTERVAL_MS);
  });
})();
