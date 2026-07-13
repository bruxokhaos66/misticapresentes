(() => {
  const config = window.misticaSiteConfig || {};
  const API_BASE = String(config.apiBaseUrl || "https://api.misticaesotericos.com.br").replace(/\/$/, "");
  const SYNC_INTERVAL_MS = 15000;

  let syncRunning = false;
  window.misticaCatalogState = "loading";

  function statusEl() {
    let el = document.getElementById("mobileSyncStatus");
    if (!el) {
      el = document.createElement("div");
      el.id = "mobileSyncStatus";
      el.setAttribute("aria-live", "polite");
      el.style.position = "fixed";
      el.style.right = "12px";
      el.style.bottom = "78px";
      el.style.zIndex = "89";
      el.style.padding = "8px 10px";
      el.style.borderRadius = "999px";
      el.style.font = "600 12px Inter, Arial, sans-serif";
      el.style.boxShadow = "0 8px 24px rgba(0,0,0,.25)";
      el.style.maxWidth = "min(92vw, 360px)";
      document.body.appendChild(el);
    }
    return el;
  }

  function setSyncStatus(message, ok = true) {
    const el = statusEl();
    el.textContent = message;
    el.style.background = ok ? "#162116" : "#3b1c1c";
    el.style.color = ok ? "#dff5d8" : "#ffd7d7";
  }

  function setCatalogState(state, message) {
    window.misticaCatalogState = state;
    document.documentElement.dataset.catalogState = state;
    const checkoutButton = document.querySelector("[data-generate-pix]");
    if (checkoutButton) {
      const blocked = state !== "ready";
      checkoutButton.disabled = blocked;
      checkoutButton.setAttribute("aria-disabled", blocked ? "true" : "false");
    }
    if (message) setSyncStatus(message, state === "ready");
    window.dispatchEvent(new CustomEvent("mistica:catalog-state", {
      detail: { state, message: message || "" },
    }));
  }

  function apiHeaders(extra = {}) {
    return { "Content-Type": "application/json", ...extra };
  }

  async function api(path, options = {}) {
    const response = await fetch(`${API_BASE}${path}`, {
      credentials: "include",
      cache: "no-store",
      ...options,
      headers: apiHeaders(options.headers || {}),
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data.detail || data.message || `API ${response.status}`);
    return data;
  }

  function fullUrl(path) {
    const value = String(path || "").trim();
    if (!value) return "";
    if (/^https?:\/\//i.test(value)) return value;
    return `${API_BASE}${value.startsWith("/") ? "" : "/"}${value}`;
  }

  function normalizarProduto(item) {
    const codigo = item.codigo_p || item.codigo || String(item.id || "");
    const imagens = Array.isArray(item.imagens) ? item.imagens.map(fullUrl).filter(Boolean) : [];
    const imagemPrincipal = fullUrl(item.imagem_url || item.imagem || item.imageUrl || imagens[0] || "");
    const limiteEncomenda = Number(item.limite_encomenda || 10);
    const temRegraExplicita = Object.prototype.hasOwnProperty.call(item, "sob_encomenda");
    const sobEncomenda = temRegraExplicita ? Boolean(item.sob_encomenda) : undefined;
    return {
      id: `api-${item.id}`,
      apiId: item.id,
      codigo,
      name: item.nome || item.nome_p || "Produto sem nome",
      category: item.categoria || "Produtos da loja",
      description: item.descricao || (item.categoria ? `Categoria: ${item.categoria}` : "Produto sincronizado da loja."),
      price: Number(item.preco || item.valor || 0),
      stock: Number(item.quantidade || item.estoque || 0),
      icon: item.icone || "✨",
      imageUrl: imagemPrincipal,
      images: imagens.length ? imagens : (imagemPrincipal ? [imagemPrincipal] : []),
      externalUrl: item.link_externo || item.externalUrl || "",
      tag: item.selo || item.tag || "",
      selo: item.selo || item.tag || "",
      ...(temRegraExplicita ? {
        sobEncomenda,
        sob_encomenda: sobEncomenda,
      } : {}),
      limiteEncomenda: Number.isInteger(limiteEncomenda) && limiteEncomenda > 0 ? limiteEncomenda : 10,
      limite_encomenda: Number.isInteger(limiteEncomenda) && limiteEncomenda > 0 ? limiteEncomenda : 10,
      avaliacoesTotal: Number(item.avaliacoes_total || 0),
      avaliacoesMedia: Number(item.avaliacoes_media || 0),
    };
  }

  function aplicarProdutos(lista) {
    if (!Array.isArray(lista) || typeof products === "undefined") {
      throw new Error("Resposta inválida do catálogo.");
    }
    const novos = lista.map(normalizarProduto).filter(product => product.apiId && product.codigo && Number.isFinite(product.price));
    products.splice(0, products.length, ...novos);
    stock = novos.reduce((map, product) => {
      map[product.id] = product.stock;
      return map;
    }, {});
    if (typeof renderAll === "function") renderAll();
  }

  function clearCatalog() {
    if (typeof products !== "undefined" && Array.isArray(products)) products.splice(0, products.length);
    if (typeof stock !== "undefined") stock = {};
    if (typeof renderAll === "function") renderAll();
  }

  async function sincronizarAgora() {
    if (syncRunning) return;
    syncRunning = true;
    setCatalogState("loading", "Carregando catálogo oficial...");
    try {
      const produtos = await api("/api/produtos?limite=500");
      aplicarProdutos(produtos);
      setCatalogState("ready", produtos.length ? "Online" : "Catálogo sem produtos disponíveis no momento.");
    } catch (error) {
      clearCatalog();
      setCatalogState("error", "Catálogo indisponível. Compras e Pix estão temporariamente bloqueados.");
      console.error("Falha ao carregar catálogo oficial:", error);
    } finally {
      syncRunning = false;
    }
  }

  function montarItensPedido(itens) {
    return itens.map(item => {
      const produto = products.find(candidate => candidate.id === item.id);
      if (!produto?.apiId || !produto?.codigo) throw new Error("Um produto do carrinho não está mais disponível no catálogo oficial.");
      const quantidade = Number(item.qty || 0);
      if (!Number.isInteger(quantidade) || quantidade <= 0) throw new Error("Quantidade inválida no carrinho.");
      return {
        produto_id: produto.apiId,
        codigo_p: produto.codigo,
        quantidade,
      };
    });
  }

  async function criarPedidoNoServidor(itensCarrinho) {
    if (window.misticaCatalogState !== "ready") throw new Error("O catálogo oficial ainda não está disponível.");
    if (!Array.isArray(itensCarrinho) || !itensCarrinho.length) throw new Error("Carrinho vazio.");

    const dataIso = new Date().toISOString();
    const payload = {
      origem: "site",
      cliente: "Pedido site/celular",
      telefone: (typeof storeConfig !== "undefined" && storeConfig.customerPhone) || "",
      forma_pagamento: "Pix site/celular",
      vendedor: "Site/Celular",
      status: "Aguardando pagamento",
      data_venda: new Date(dataIso).toLocaleString("pt-BR"),
      data_iso: dataIso,
      dia_operacional: dataIso.slice(0, 10),
      cupom: window.misticaCupomAtivo || null,
      itens: montarItensPedido(itensCarrinho),
    };

    const resposta = await api("/api/checkout/pedidos", {
      method: "POST",
      body: JSON.stringify(payload),
    });

    if (!resposta?.id || !resposta?.pix_copia_cola) {
      throw new Error("O servidor não retornou um Pix válido para este pedido.");
    }

    return {
      id: resposta.id,
      pixTxid: resposta.pix_txid || null,
      pixPayload: resposta.pix_copia_cola,
      dataIso,
      expiraEm: resposta.expira_em || null,
      totalFinal: Number(resposta.total_final || 0),
      desconto: Number(resposta.desconto || 0),
    };
  }

  async function consultarStatusPedido(pedidoId) {
    const resposta = await api(`/api/pedidos/${encodeURIComponent(pedidoId)}/status`, { method: "GET" });
    return {
      status: resposta.status_atual,
      estoqueBaixado: Boolean(resposta.estoque_baixado),
    };
  }

  window.misticaCriarPedido = criarPedidoNoServidor;
  window.misticaConsultarStatusPedido = consultarStatusPedido;
  window.misticaMobileSync = {
    apiBase: API_BASE,
    syncNow: sincronizarAgora,
    sendSale: criarPedidoNoServidor,
  };

  setCatalogState("loading", "Carregando catálogo oficial...");
  window.addEventListener("load", () => {
    sincronizarAgora();
    setInterval(() => {
      if (!document.hidden) sincronizarAgora();
    }, SYNC_INTERVAL_MS);
  });
})();