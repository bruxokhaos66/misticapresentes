(() => {
  const config = window.misticaSiteConfig || {};
  const isProduction = config.serverMode === "production" || config.storageMode === "api_first" || config.usePublicDomainAccess === true;
  const API_BASE = String(config.apiBaseUrl || "https://api.misticaesotericos.com.br").replace(/\/$/, "");
  const PUBLIC_CHECKOUT_PATH = "/api/checkout/pedidos";

  if (!isProduction) return;

  let checkoutRunning = false;
  let guardInstalled = false;
  let pendingOrderId = null;

  function qs(selector) {
    return document.querySelector(selector);
  }

  function status(message, ok = false) {
    if (typeof setStatus === "function") setStatus(message);
    const el = document.getElementById("mobileSyncStatus") || document.getElementById("pixStatus");
    if (!el) return;
    el.textContent = message;
    if (el.id === "mobileSyncStatus") {
      el.style.background = ok ? "#162116" : "#3b1c1c";
      el.style.color = ok ? "#dff5d8" : "#ffd7d7";
    }
  }

  // A limpeza de chaves proibidas e a persistência do carrinho mínimo já são
  // responsabilidade estrutural de window.misticaSecureStorage (site-config.js,
  // carregado antes de qualquer script comercial). Este guard não repete
  // essa lógica nem sobrescreve Storage.prototype ou a função saveState —
  // ele só aciona a limpeza como reforço defensivo em pontos do fluxo.
  function removeSensitiveLocalKeys() {
    if (window.misticaSecureStorage) window.misticaSecureStorage.removeForbiddenKeys();
  }

  function currentCart() {
    return Array.isArray(cart) ? cart.map(item => ({ ...item })) : [];
  }

  function catalogReady() {
    return window.misticaCatalogState === "ready";
  }

  function canSendToApi(items) {
    return items.length > 0 && Array.isArray(products) && items.every(item => {
      const product = products.find(candidate => candidate.id === item.id);
      return Boolean(product && (product.apiId || product.codigo));
    });
  }

  // O id do pedido pendente fica só em memória (não em localStorage): serve
  // apenas para acompanhamento na sessão atual da aba (ver
  // iniciarAcompanhamentoPedido em app.js, que já usa o objeto `pedido` em
  // memória, não esta variável).
  function persistPendingOrder(order) {
    pendingOrderId = order?.id ?? null;
  }

  function setCheckoutButtonBusy(busy) {
    const button = qs("[data-generate-pix]");
    if (!button) return;
    button.disabled = Boolean(busy);
    button.setAttribute("aria-busy", busy ? "true" : "false");
  }

  async function guardedGeneratePix(event) {
    event.preventDefault();
    event.stopImmediatePropagation();

    if (checkoutRunning) {
      status("Seu pedido já está sendo criado. Aguarde a resposta do servidor.");
      return;
    }

    if (!catalogReady()) {
      status("Compra temporariamente indisponível: aguarde o catálogo carregar novamente.");
      return;
    }

    const items = currentCart();
    const total = typeof getTotal === "function"
      ? getTotal()
      : items.reduce((sum, item) => sum + Number(item.price || 0) * Number(item.qty || 0), 0);

    if (!items.length || total <= 0) {
      status("Adicione pelo menos um produto ao carrinho antes de gerar o Pix.");
      return;
    }

    if (typeof hasEnoughStockForCart === "function" && !hasEnoughStockForCart()) {
      status("Existe produto no carrinho acima do estoque disponível. Ajuste antes de gerar o Pix.");
      return;
    }

    if (!canSendToApi(items)) {
      status("Compra bloqueada: um ou mais produtos não estão sincronizados com o catálogo oficial.");
      return;
    }

    if (typeof cartHasEncomenda === "function" && cartHasEncomenda()) {
      const check = document.getElementById("encomendaConfirm");
      if (check && !check.checked) {
        const box = document.getElementById("encomendaCheckoutBox");
        if (box) box.hidden = false;
        status("Confirme que está ciente do produto sob encomenda para continuar.");
        return;
      }
    }

    if (typeof window.misticaCriarPedido !== "function") {
      status(`Não foi possível conectar ao servidor de pedidos (${PUBLIC_CHECKOUT_PATH}). Tente novamente em instantes.`);
      return;
    }

    checkoutRunning = true;
    setCheckoutButtonBusy(true);
    if (typeof pararAcompanhamentoPedido === "function") pararAcompanhamentoPedido();
    if (typeof clearQrCanvas === "function") clearQrCanvas();
    if (typeof pixPayloadInput !== "undefined" && pixPayloadInput) pixPayloadInput.value = "";
    status("Enviando pedido e gerando o Pix com segurança...");

    try {
      const pedido = await window.misticaCriarPedido(items);
      if (!pedido?.id || !pedido?.pixPayload) throw new Error("O servidor não retornou um Pix válido.");

      if (typeof pixPayloadInput !== "undefined" && pixPayloadInput) pixPayloadInput.value = pedido.pixPayload;
      if (pedido.pixInfo) {
        if (typeof pixKeyInput !== "undefined" && pixKeyInput) pixKeyInput.value = pedido.pixInfo.chave_mascarada || "";
        if (typeof merchantNameInput !== "undefined" && merchantNameInput) merchantNameInput.value = pedido.pixInfo.recebedor || "";
        if (typeof storeNameInput !== "undefined" && storeNameInput) storeNameInput.value = pedido.pixInfo.nome_loja || "";
        if (typeof merchantCityInput !== "undefined" && merchantCityInput) merchantCityInput.value = pedido.pixInfo.cidade || "";
      }
      if (window.QRCode && typeof pixCanvas !== "undefined" && pixCanvas) {
        try {
          await window.QRCode.toCanvas(pixCanvas, pedido.pixPayload, {
            width: 220,
            margin: 2,
            errorCorrectionLevel: "M",
          });
        } catch {}
      }

      persistPendingOrder(pedido);
      if (typeof iniciarAcompanhamentoPedido === "function") iniciarAcompanhamentoPedido(pedido);
      status(`Pedido #${pedido.id} criado — aguardando pagamento. Seu carrinho foi preservado até a confirmação.`, true);
    } catch (error) {
      status(error?.message || "Não foi possível gerar o Pix agora. Seu carrinho foi preservado.");
    } finally {
      checkoutRunning = false;
      setCheckoutButtonBusy(false);
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
      const response = await fetch(`${API_BASE}/api/clientes`, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(data.detail || data.message || `API ${response.status}`);
      qs("#clientForm")?.reset();
      const saved = qs("#clientSaved");
      if (saved) {
        saved.hidden = false;
        saved.textContent = "Cliente enviado para a API. Dados sensíveis não foram salvos neste navegador.";
      }
      if (Array.isArray(clients)) clients = [];
      removeSensitiveLocalKeys();
      status("Cliente salvo na API com segurança.", true);
    } catch (error) {
      removeSensitiveLocalKeys();
      status(`Cliente não salvo localmente: ${String(error?.message || error).slice(0, 120)}`);
    }
  }

  function blockAdminAction(event, message = "Ação administrativa bloqueada no site público. Use o Mística Painel.") {
    event.preventDefault();
    event.stopImmediatePropagation();
    const adminStatus = qs("#adminLoginStatus") || qs("#productAdminStatus") || qs("#backupStatus");
    if (adminStatus) {
      adminStatus.hidden = false;
      adminStatus.textContent = message;
    }
    status(message);
  }

  function installCaptureGuards() {
    if (guardInstalled) return;
    guardInstalled = true;

    document.addEventListener("click", event => {
      const target = event.target?.closest?.("button, a");
      if (!target) return;
      if (target.matches("[data-generate-pix]")) return guardedGeneratePix(event);
      if (target.matches("[data-export-clients], [data-export-sales], [data-download-backup], [data-restore-backup]")) {
        return blockAdminAction(event);
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

  function install() {
    removeSensitiveLocalKeys();
    installCaptureGuards();
    try {
      if (Array.isArray(clients)) clients = [];
      if (Array.isArray(sales)) sales = [];
      if (Array.isArray(suppliers)) suppliers = [];
    } catch {}
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", install, { once: true });
  else install();

  window.misticaProductionGuard = {
    enabled: true,
    apiBase: API_BASE,
    checkoutPath: PUBLIC_CHECKOUT_PATH,
    checkout: guardedGeneratePix,
    scrubLocalData: removeSensitiveLocalKeys,
    get pendingOrderId() { return pendingOrderId; },
  };
})();