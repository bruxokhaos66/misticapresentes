(() => {
  const config = window.misticaSiteConfig || {};
  const isProduction = config.serverMode === "production" || config.storageMode === "api_first" || config.usePublicDomainAccess === true;
  const API_BASE = String(config.apiBaseUrl || "https://api.misticaesotericos.com.br").replace(/\/$/, "");
  // O checkout público nunca envia uma chave de API pelo navegador (ver
  // backend/product_routes.py::criar_pedido_checkout_publico e
  // tests/test_no_browser_api_secret.py); a chave global fica só no servidor.
  const SYNC_CACHE_MS = 15000;
  const syncCache = new Map();
  let guardInstalled = false;

  if (!isProduction) return;

  function qs(selector) {
    return document.querySelector(selector);
  }

  function text(value) {
    return String(value ?? "");
  }

  function status(message, ok = false) {
    if (typeof setStatus === "function") setStatus(message);
    const el = document.getElementById("mobileSyncStatus") || document.getElementById("pixStatus");
    if (el) {
      el.textContent = message;
      if (el.id === "mobileSyncStatus") {
        el.style.background = ok ? "#162116" : "#3b1c1c";
        el.style.color = ok ? "#dff5d8" : "#ffd7d7";
      }
    }
  }

  function headers(extra = {}) {
    return {
      "Content-Type": "application/json",
      ...extra,
    };
  }

  async function api(path, options = {}) {
    const response = await fetch(`${API_BASE}${path}`, {
      ...options,
      headers: headers(options.headers || {}),
    });
    const textBody = await response.text();
    if (!response.ok) {
      let detail = textBody || `API ${response.status}`;
      try {
        const body = JSON.parse(textBody);
        detail = body.detail || body.message || detail;
      } catch {}
      throw new Error(detail);
    }
    try { return JSON.parse(textBody); } catch { return textBody; }
  }

  function number(value) {
    const parsed = Number(value || 0);
    return Number.isFinite(parsed) ? parsed : 0;
  }

  function currentCart() {
    return Array.isArray(cart) ? cart.map(item => ({ ...item })) : [];
  }

  function productForCartItem(item) {
    return Array.isArray(products) ? products.find(product => product.id === item.id) : null;
  }

  function buildApiItems(items) {
    return items.map(item => {
      const product = productForCartItem(item);
      return {
        produto_id: product?.apiId || null,
        codigo_p: product?.codigo || item.id,
        nome_p: item.name,
        quantidade: number(item.qty),
        custo_unitario: 0,
        valor_unitario: number(item.price),
        valor_total: number(item.price) * number(item.qty),
      };
    });
  }

  function canSendToApi(items) {
    return items.length > 0 && items.every(item => {
      const product = productForCartItem(item);
      return Boolean(product?.apiId || product?.codigo);
    });
  }

  function storePendingOrder(order) {
    try {
      const key = "misticaPendingOrders";
      const current = JSON.parse(localStorage.getItem(key) || "[]");
      current.unshift({ ...order, pendingAt: new Date().toISOString() });
      localStorage.setItem(key, JSON.stringify(current.slice(0, 20)));
    } catch {}
  }

  async function sendSaleToApi(localSale, items) {
    const payload = {
      origem: "site",
      cliente: "Pedido site/celular",
      subtotal: number(localSale.total),
      desconto: 0,
      taxa: 0,
      total_final: number(localSale.total),
      forma_pagamento: "Pix site/celular",
      vendedor: "Site/Celular",
      status: "Aguardando pagamento",
      data_venda: new Date(localSale.date).toLocaleString("pt-BR"),
      data_iso: localSale.date,
      dia_operacional: new Date(localSale.date).toISOString().slice(0, 10),
      itens: buildApiItems(items),
    };
    // Rota pública sem segredo: o navegador nunca envia a chave de API (ela
    // fica só no servidor). O backend reserva o estoque na criação do pedido
    // e devolve automaticamente se o Pix expirar/for cancelado (ver
    // backend/product_routes.py::criar_pedido_checkout_publico).
    return api("/api/checkout/pedidos", { method: "POST", body: JSON.stringify(payload) });
  }

  async function guardedGeneratePix(event) {
    event.preventDefault();
    event.stopImmediatePropagation();

    const items = currentCart();
    const total = typeof getTotal === "function" ? getTotal() : items.reduce((sum, item) => sum + number(item.price) * number(item.qty), 0);
    if (!items.length || total <= 0) return status("Adicione pelo menos um produto ao carrinho antes de gerar o Pix.");
    if (typeof hasEnoughStockForCart === "function" && !hasEnoughStockForCart()) {
      return status("Existe produto no carrinho acima do estoque disponível. Ajuste antes de gerar o Pix.");
    }
    if (!canSendToApi(items)) {
      return status("Venda bloqueada em produção: sincronize o catálogo pela API antes de baixar estoque.");
    }
    if (!storeConfig?.pixKey || storeConfig.pixKey === "misticapresentes@email.com") {
      return status("Configure a chave Pix real antes de publicar ou vender.");
    }

    const saleId = `MISTICA${Date.now().toString().slice(-9)}`;
    let payload = "";
    try {
      payload = buildPixPayload({
        key: storeConfig.pixKey,
        name: storeConfig.merchantName,
        city: storeConfig.merchantCity,
        amount: total,
        txid: saleId,
      });
      if (pixPayloadInput) pixPayloadInput.value = payload;
      if (window.QRCode && pixCanvas) {
        await window.QRCode.toCanvas(pixCanvas, payload, { width: 220, margin: 2, errorCorrectionLevel: "M" });
      }
    } catch (error) {
      return status(`Erro ao montar Pix: ${error.message || error}`);
    }

    const localSale = {
      date: new Date().toISOString(),
      id: saleId,
      total,
      items,
      pixPayload: payload,
      status: "Aguardando pagamento",
      estoqueReposto: false,
    };

    try {
      status("Enviando pedido para o sistema. O estoque só será baixado após a confirmação do pagamento...");
      const saved = await sendSaleToApi(localSale, items);
      const savedId = saved?.id || saved?.venda_id || saleId;
      sales.unshift({ ...localSale, id: String(savedId), apiId: savedId });
      sales = sales.slice(0, 50);
      cart = [];
      saveState();
      if (typeof renderAll === "function") renderAll();
      status("Pedido criado como \"Aguardando pagamento\". O estoque só será baixado quando o pagamento for confirmado no painel.", true);
      if (window.misticaMobileSync?.syncNow) window.misticaMobileSync.syncNow();
    } catch (error) {
      storePendingOrder(localSale);
      status(`API não confirmou o pedido. Carrinho preservado e estoque não foi baixado: ${String(error.message || error).slice(0, 120)}`);
    }
  }

  async function submitClientToApi(event) {
    event.preventDefault();
    event.stopImmediatePropagation();
    const payload = {
      nome: qs("#clientName")?.value?.trim() || "",
      cpf: qs("#clientCpf")?.value?.trim() || "",
      endereco: qs("#clientAddress")?.value?.trim() || "",
      telefone: qs("#clientWhatsapp")?.value?.trim() || "",
    };
    if (!payload.nome || !payload.telefone) return status("Informe nome e WhatsApp do cliente.");
    try {
      await api("/api/clientes", { method: "POST", body: JSON.stringify(payload) });
      qs("#clientForm")?.reset();
      const saved = qs("#clientSaved");
      if (saved) {
        saved.hidden = false;
        saved.textContent = "Cliente enviado para a API. Dados sensíveis não foram salvos neste navegador.";
      }
      clients = [];
      try { localStorage.removeItem("misticaClients"); } catch {}
      saveState();
      status("Cliente salvo na API com segurança.", true);
    } catch (error) {
      const saved = qs("#clientSaved");
      if (saved) {
        saved.hidden = false;
        saved.textContent = `Não foi possível salvar na API. Nada foi gravado localmente: ${String(error.message || error).slice(0, 100)}`;
      }
      try { localStorage.removeItem("misticaClients"); } catch {}
      status("Cliente não salvo localmente por segurança.");
    }
  }

  function blockAdminAction(event, message = "Ação administrativa bloqueada no site público. Use o Mística Painel com login da API.") {
    event.preventDefault();
    event.stopImmediatePropagation();
    const adminStatus = qs("#adminLoginStatus") || qs("#productAdminStatus") || qs("#backupStatus");
    if (adminStatus) {
      adminStatus.hidden = false;
      adminStatus.textContent = message;
    }
    status(message);
  }

  async function updateSaleStatusApi(vendaId, novoStatus) {
    const body = JSON.stringify({ status: novoStatus });
    const endpoints = [`/api/vendas/${encodeURIComponent(vendaId)}/status`, `/api/pedidos/${encodeURIComponent(vendaId)}/status`];
    let lastError = null;
    for (const endpoint of endpoints) {
      try { return await api(endpoint, { method: "POST", body }); } catch (error) { lastError = error; }
    }
    throw lastError || new Error("Endpoint de status não disponível.");
  }

  async function cancelSaleApi(vendaId) {
    const endpoints = [`/api/vendas/${encodeURIComponent(vendaId)}/cancelar`, `/api/pedidos/${encodeURIComponent(vendaId)}/cancelar`];
    let lastError = null;
    for (const endpoint of endpoints) {
      try { return await api(endpoint, { method: "POST", body: JSON.stringify({ motivo: "Cancelamento pelo site" }) }); } catch (error) { lastError = error; }
    }
    throw lastError || new Error("Endpoint de cancelamento não disponível.");
  }

  function extractCallArgs(onclick) {
    return [...String(onclick || "").matchAll(/'([^']*)'/g)].map(match => match[1]);
  }

  async function guardedSaleAction(event, target) {
    const onclick = target.getAttribute("onclick") || "";
    if (!/cancelSale|updateSaleStatus/.test(onclick)) return false;
    event.preventDefault();
    event.stopImmediatePropagation();
    const args = extractCallArgs(onclick);
    const vendaId = args[0];
    if (!vendaId) return true;
    try {
      if (onclick.includes("cancelSale")) {
        if (!confirm(`Cancelar pedido ${vendaId} pela API?`)) return true;
        await cancelSaleApi(vendaId);
        status(`Pedido ${vendaId} cancelado pela API. Estoque será reposto pelo sistema.`, true);
      } else {
        const novoStatus = args[1] || target.textContent.trim();
        await updateSaleStatusApi(vendaId, novoStatus);
        status(`Pedido ${vendaId} atualizado para ${novoStatus} pela API.`, true);
      }
      if (window.misticaMobileSync?.syncNow) window.misticaMobileSync.syncNow();
    } catch (error) {
      status(`API não confirmou a alteração. Nada foi alterado localmente: ${String(error.message || error).slice(0, 120)}`);
    }
    return true;
  }

  const SENSITIVE_LOCAL_KEYS = [
    "misticaClients",
    "misticaSales",
    "misticaStock",
    "misticaSuppliers",
    "misticaAutoBackup",
    "misticaLastBackupAt",
  ];

  function removeSensitiveLocalKeys() {
    SENSITIVE_LOCAL_KEYS.forEach(key => {
      try { localStorage.removeItem(key); } catch {}
    });
  }

  function installSafeSaveState() {
    if (window.__misticaSafeSaveStateInstalled || typeof saveState !== "function") return;
    window.__misticaSafeSaveStateInstalled = true;
    saveState = function safeProductionSaveState() {
      try { localStorage.setItem("misticaCart", JSON.stringify(cart || [])); } catch {}
      removeSensitiveLocalKeys();
    };
  }

  function installFetchThrottle() {
    if (window.__misticaFetchThrottleInstalled || typeof fetch !== "function") return;
    window.__misticaFetchThrottleInstalled = true;
    const originalFetch = window.fetch.bind(window);
    window.fetch = async function throttledFetch(input, init = {}) {
      const url = typeof input === "string" ? input : input?.url || "";
      const method = String(init?.method || "GET").toUpperCase();
      const isCommonSync = method === "GET" && url.startsWith(API_BASE) && /\/api\/(status|produtos|vendas|clientes)(\?|$)/.test(new URL(url, location.href).pathname + new URL(url, location.href).search);
      if (isCommonSync) {
        const key = url.replace(/[?&]_=\d+/, "");
        const cached = syncCache.get(key);
        const fresh = cached && Date.now() - cached.at < SYNC_CACHE_MS;
        if ((document.hidden || fresh) && cached?.response) return cached.response.clone();
        const response = await originalFetch(input, init);
        try { syncCache.set(key, { at: Date.now(), response: response.clone() }); } catch {}
        return response;
      }
      return originalFetch(input, init);
    };
  }

  function installCaptureGuards() {
    if (guardInstalled) return;
    guardInstalled = true;
    document.addEventListener("click", event => {
      const target = event.target?.closest?.("button, a");
      if (!target) return;
      if (target.matches("[data-generate-pix]")) return guardedGeneratePix(event);
      if (target.matches("[data-export-clients], [data-export-sales], [data-download-backup], [data-restore-backup]")) return blockAdminAction(event);
      if (target.closest("#productAdminForm") || target.closest("#adminContent")) {
        const onclick = target.getAttribute("onclick") || "";
        if (/cancelSale|updateSaleStatus/.test(onclick)) return guardedSaleAction(event, target);
        if (!onclick.includes("openSaleStatusWhatsapp")) return blockAdminAction(event);
      }
      return undefined;
    }, true);

    document.addEventListener("submit", event => {
      const form = event.target;
      if (form?.id === "clientForm") return submitClientToApi(event);
      if (form?.id === "adminLoginForm") return blockAdminAction(event, "Admin local bloqueado. Use o Mística Painel autenticado pela API.");
      if (form?.id === "productAdminForm" || form?.id === "supplierForm") return blockAdminAction(event);
      return undefined;
    }, true);
  }

  function scrubLocalClientData() {
    removeSensitiveLocalKeys();
    try {
      if (Array.isArray(clients)) clients = [];
      if (typeof renderClients === "function") renderClients();
    } catch {}
  }

  function install() {
    installSafeSaveState();
    installFetchThrottle();
    installCaptureGuards();
    scrubLocalClientData();
    if (typeof saveState === "function") saveState();
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", install);
  else install();

  window.misticaProductionGuard = {
    enabled: true,
    apiBase: API_BASE,
    sendSaleToApi,
    updateSaleStatusApi,
    cancelSaleApi,
    scrubLocalClientData,
  };
})();
