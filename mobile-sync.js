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

  function escapeHtml(value) {
    return String(value == null ? "" : value)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  function catalogText(value, fallback = "") {
    const normalized = String(value == null ? fallback : value)
      .replace(/[\u0000-\u001F\u007F]/g, " ")
      .replace(/\s+/g, " ")
      .trim();
    return escapeHtml(normalized || fallback);
  }

  function fullUrl(path) {
    const value = String(path || "").trim();
    if (!value) return "";
    if (/^https:\/\//i.test(value)) return value;
    if (value.startsWith("/")) return `${API_BASE}${value}`;
    return "";
  }

  function normalizarProduto(item) {
    const codigo = String(item.codigo_p || item.codigo || item.id || "").trim();
    const imagens = Array.isArray(item.imagens) ? item.imagens.map(fullUrl).filter(Boolean) : [];
    const imagemPrincipal = fullUrl(item.imagem_url || item.imagem || item.imageUrl || imagens[0] || "");
    const limiteEncomenda = Number(item.limite_encomenda || 10);
    const temRegraExplicita = Object.prototype.hasOwnProperty.call(item, "sob_encomenda");
    const sobEncomenda = temRegraExplicita ? Boolean(item.sob_encomenda) : undefined;
    const categoriaOriginal = item.categoria || "Produtos da loja";
    return {
      id: `api-${item.id}`,
      apiId: item.id,
      codigo,
      name: catalogText(item.nome || item.nome_p, "Produto sem nome"),
      category: catalogText(categoriaOriginal, "Produtos da loja"),
      description: catalogText(item.descricao || (item.categoria ? `Categoria: ${item.categoria}` : "Produto sincronizado da loja.")),
      price: Number(item.preco || item.valor || 0),
      stock: Number(item.quantidade || item.estoque || 0),
      icon: catalogText(item.icone || "✨", "✨"),
      imageUrl: imagemPrincipal,
      images: imagens.length ? imagens : (imagemPrincipal ? [imagemPrincipal] : []),
      externalUrl: fullUrl(item.link_externo || item.externalUrl || ""),
      tag: catalogText(item.selo || item.tag || ""),
      selo: catalogText(item.selo || item.tag || ""),
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
    // Sempre que o catálogo oficial muda, o carrinho é reconstruído a
    // partir dele: produtos removidos/inativos saem, preço e estoque são
    // atualizados. window.misticaReconcileCart já chama renderAll().
    if (typeof window.misticaReconcileCart === "function") window.misticaReconcileCart();
    else if (typeof renderAll === "function") renderAll();
  }

  function clearCatalog() {
    if (typeof products !== "undefined" && Array.isArray(products)) products.splice(0, products.length);
    if (typeof stock !== "undefined") stock = {};
    // Falha de rede ao buscar o catálogo NUNCA reconcilia o carrinho: um
    // catálogo vazio por erro transitório não pode ser tratado como fonte
    // autoritativa e apagar o carrinho mínimo salvo. O carrinho persistido
    // continua intacto para quando a API voltar; a UI só mostra o estado de
    // indisponibilidade (checkout permanece bloqueado via misticaCatalogState).
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

  function produtoDoCarrinho(item) {
    return products.find(candidate => candidate.id === item.id);
  }

  function montarItensPedido(itens) {
    return itens.map(item => {
      const produto = produtoDoCarrinho(item);
      if (!produto?.apiId || !produto?.codigo) throw new Error("Um produto do carrinho não está mais disponível no catálogo oficial.");
      const quantidade = Number(item.qty || 0);
      if (!Number.isInteger(quantidade) || quantidade <= 0) throw new Error("Quantidade inválida no carrinho.");
      if (window.misticaEncomenda?.isSobEncomenda(produto)) {
        const limite = window.misticaEncomenda?.limiteDe(produto) || 10;
        if (quantidade > limite) throw new Error(`Quantidade máxima sob encomenda para ${produto.name}: ${limite}.`);
      }
      return {
        produto_id: produto.apiId,
        codigo_p: produto.codigo,
        quantidade,
      };
    });
  }

  function confirmarCondicoesEncomenda(itensCarrinho) {
    const produtosCarrinho = itensCarrinho.map(produtoDoCarrinho).filter(Boolean);
    const flags = produtosCarrinho.map(produto => Boolean(window.misticaEncomenda?.isSobEncomenda(produto)));
    const possuiEncomenda = flags.some(Boolean);
    const possuiEstoque = flags.some(flag => !flag);

    if (possuiEncomenda && possuiEstoque) {
      throw new Error("Produtos disponíveis em estoque e produtos sob encomenda devem ser finalizados em pedidos separados.");
    }
    if (!possuiEncomenda) return false;

    const aviso = window.misticaEncomenda?.CHECKOUT_AVISO || "Este pedido contém produto sob encomenda.";
    const confirma = window.misticaEncomenda?.CHECKOUT_CONFIRMA || "Estou ciente das condições da encomenda.";
    if (!window.confirm(`${aviso}\n\n${confirma}`)) {
      throw new Error("Confirmação da encomenda cancelada.");
    }
    return true;
  }

  // Idempotency-Key da tentativa de checkout atual. Fica só em memória
  // (nunca em localStorage): reenviar a mesma tentativa (retry de rede,
  // clique duplo) usa a mesma chave, então o backend devolve sempre o mesmo
  // pedido em vez de criar um novo. Uma chave nova só é gerada quando o
  // pedido é criado com sucesso, o carrinho muda/é limpo, ou o cliente inicia
  // uma nova tentativa depois de um erro definitivo (ver app.js).
  let idempotencyKeyAtual = null;

  function gerarIdempotencyKey() {
    if (window.crypto?.randomUUID) return window.crypto.randomUUID();
    const bytes = new Uint8Array(16);
    if (window.crypto?.getRandomValues) {
      window.crypto.getRandomValues(bytes);
    } else {
      for (let i = 0; i < bytes.length; i++) bytes[i] = Math.floor(Math.random() * 256);
    }
    bytes[6] = (bytes[6] & 0x0f) | 0x40;
    bytes[8] = (bytes[8] & 0x3f) | 0x80;
    const hex = Array.from(bytes, byte => byte.toString(16).padStart(2, "0")).join("");
    return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`;
  }

  function idempotencyKeyDaTentativa() {
    if (!idempotencyKeyAtual) idempotencyKeyAtual = gerarIdempotencyKey();
    return idempotencyKeyAtual;
  }

  function reiniciarIdempotencyKey() {
    idempotencyKeyAtual = null;
  }

  async function criarPedidoNoServidor(itensCarrinho) {
    if (window.misticaCatalogState !== "ready") throw new Error("O catálogo oficial ainda não está disponível.");
    if (!Array.isArray(itensCarrinho) || !itensCarrinho.length) throw new Error("Carrinho vazio.");

    const cienteSobEncomenda = confirmarCondicoesEncomenda(itensCarrinho);
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
      ciente_sob_encomenda: cienteSobEncomenda,
      itens: montarItensPedido(itensCarrinho),
    };

    const resposta = await api("/api/checkout/pedidos", {
      method: "POST",
      headers: { "Idempotency-Key": idempotencyKeyDaTentativa() },
      body: JSON.stringify(payload),
    });

    if (!resposta?.id || !resposta?.pix_copia_cola) {
      throw new Error("O servidor não retornou um Pix válido para este pedido.");
    }

    // Pedido criado com sucesso: a próxima compra deve usar uma chave nova.
    reiniciarIdempotencyKey();

    return {
      id: resposta.id,
      pixTxid: resposta.pix_txid || null,
      pixPayload: resposta.pix_copia_cola,
      dataIso,
      expiraEm: resposta.expira_em || null,
      totalFinal: Number(resposta.total_final || 0),
      desconto: Number(resposta.desconto || 0),
      sobEncomenda: Boolean(resposta.sob_encomenda),
    };
  }

  async function consultarStatusPedido(pedidoId, pixTxid) {
    const query = pixTxid ? `?txid=${encodeURIComponent(pixTxid)}` : "";
    const resposta = await api(`/api/pedidos/${encodeURIComponent(pedidoId)}/status${query}`, { method: "GET" });
    return {
      status: resposta.status_atual,
      estoqueBaixado: Boolean(resposta.estoque_baixado),
    };
  }

  window.misticaCriarPedido = criarPedidoNoServidor;
  window.misticaConsultarStatusPedido = consultarStatusPedido;
  window.misticaResetIdempotencyKey = reiniciarIdempotencyKey;
  window.misticaMobileSync = {
    apiBase: API_BASE,
    syncNow: sincronizarAgora,
    sendSale: criarPedidoNoServidor,
    resetIdempotencyKey: reiniciarIdempotencyKey,
  };

  setCatalogState("loading", "Carregando catálogo oficial...");
  window.addEventListener("load", () => {
    sincronizarAgora();
    setInterval(() => {
      if (!document.hidden) sincronizarAgora();
    }, SYNC_INTERVAL_MS);
  });
})();