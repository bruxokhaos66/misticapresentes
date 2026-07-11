(() => {
  const config = window.misticaSiteConfig || {};
  const API_BASE = (config.apiBaseUrl || "https://api.misticaesotericos.com.br").replace(/\/$/, "");
  const SYNC_INTERVAL_MS = 5000;
  const STATUS_RAPIDOS = [
    "Aguardando pagamento",
    "Pago",
    "Em separação",
    "Pronto para retirada",
    "Entregue",
    "Cancelado",
  ];

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
    if (!response.ok) {
      let detail = `API ${response.status}`;
      try {
        const body = await response.json();
        detail = body.detail || body.message || detail;
      } catch {}
      throw new Error(detail);
    }
    return response.json();
  }

  function fullUrl(path) {
    const value = String(path || "").trim();
    if (!value) return "";
    if (value.startsWith("http://") || value.startsWith("https://")) return value;
    return `${API_BASE}${value.startsWith("/") ? "" : "/"}${value}`;
  }

  function normalizarProduto(item) {
    const codigo = item.codigo_p || item.codigo || String(item.id || "");
    const id = `api-${item.id}`;
    const imagens = Array.isArray(item.imagens) ? item.imagens.map(fullUrl).filter(Boolean) : [];
    const imagemPrincipal = fullUrl(item.imagem_url || item.imagem || item.imageUrl || imagens[0] || "");
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
      imageUrl: imagemPrincipal,
      images: imagens.length ? imagens : (imagemPrincipal ? [imagemPrincipal] : []),
      externalUrl: item.link_externo || item.externalUrl || "",
      tag: item.selo || item.tag || "",
      avaliacoesTotal: Number(item.avaliacoes_total || 0),
      avaliacoesMedia: Number(item.avaliacoes_media || 0),
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

  async function sincronizarAgora() {
    if (syncRunning) return;
    syncRunning = true;
    try {
      const [status, produtos] = await Promise.all([
        api("/api/status"),
        api("/api/produtos?limite=500"),
      ]);

      aplicarProdutos(produtos);
      lastSyncAt = new Date();

      try {
        saveState();
        renderAll();
      } catch {}

      setSyncStatus(`Online • estoque sincronizado • ${status.produtos || 0} produtos • ${lastSyncAt.toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" })}`, true);
    } catch {
      setSyncStatus("Catálogo local carregado • confirme disponibilidade pelo WhatsApp", true);
    } finally {
      syncRunning = false;
    }
  }

  function montarItensVenda(itens) {
    return itens.map(item => {
      const produto = products.find(p => p.id === item.id);
      const temCodigoReal = Boolean(produto?.apiId || produto?.codigo);
      if (!temCodigoReal) console.warn("Produto sem código sincronizado; envio ignorado.", item.name);
      return {
        produto_id: produto?.apiId || null,
        codigo_p: produto?.codigo || item.id,
        nome_p: item.name,
        quantidade: Number(item.qty || 0),
        custo_unitario: 0,
        valor_unitario: Number(item.price || 0),
        valor_total: Number(item.price || 0) * Number(item.qty || 0),
        valido: temCodigoReal,
      };
    });
  }

  async function criarPedidoNoServidor(itensCarrinho) {
    const itensPayload = montarItensVenda(itensCarrinho);
    if (!itensPayload.length || itensPayload.some(item => !item.valido)) {
      throw new Error("Um ou mais produtos não estão sincronizados com o catálogo.");
    }

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
      itens: itensPayload.map(({ valido, ...item }) => item),
    };
    // O Pix (chave, nome, cidade) é gerado só no servidor a partir do pedido
    // real (ver backend/pix.py); o navegador nunca monta o payload sozinho.
    const resposta = await api("/api/checkout/pedidos", { method: "POST", body: JSON.stringify(payload) });
    if (!resposta || !resposta.id || !resposta.pix_copia_cola) {
      throw new Error("O servidor não retornou um Pix válido para este pedido.");
    }
    return { id: resposta.id, pixTxid: resposta.pix_txid || null, pixPayload: resposta.pix_copia_cola, dataIso, expiraEm: resposta.expira_em || null };
  }
  window.misticaCriarPedido = criarPedidoNoServidor;

  async function consultarStatusPedido(pedidoId) {
    const resposta = await api(`/api/pedidos/${encodeURIComponent(pedidoId)}/status`, { method: "GET" });
    return { status: resposta.status_atual, estoqueBaixado: Boolean(resposta.estoque_baixado) };
  }
  window.misticaConsultarStatusPedido = consultarStatusPedido;

  function textoNormalizado(value) {
    return String(value || "").normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase();
  }

  function vendaCancelada(venda) {
    return Boolean(venda?.estoqueReposto) || textoNormalizado(venda?.status).includes("cancelad");
  }

  function escapeInline(value) {
    return String(value || "").replace(/\\/g, "\\\\").replace(/'/g, "\\'");
  }

  function mensagemStatusPedido(venda, status) {
    const nomeLoja = typeof storeConfig !== "undefined" ? storeConfig.name : "Mística Presentes";
    const itens = (venda.items || []).map(item => `• ${item.qty || 1}x ${item.name || "Item"}`).join("\n");
    const prefixo = `Olá! Aqui é da ${nomeLoja}.`;
    const pedido = `Pedido: ${venda.id || ""}`;
    const total = `Total: ${currency.format(Number(venda.total || 0))}`;
    const mensagens = {
      "Aguardando pagamento": "Seu pedido está aguardando confirmação do pagamento.",
      "Pago": "Pagamento confirmado. Gratidão pela preferência!",
      "Em separação": "Seu pedido está em separação com carinho pela nossa equipe.",
      "Pronto para retirada": "Seu pedido já está pronto para retirada.",
      "Entregue": "Seu pedido foi entregue. Gratidão pela preferência!",
      "Cancelado": "Seu pedido foi cancelado. Se precisar, podemos ajudar com um novo atendimento.",
    };
    // O link de recibo só funciona com o pix_txid do próprio pedido (ver
    // backend/order_status_routes.py::recibo_pedido); sem ele o servidor recusa
    // o acesso, então só incluímos o link quando temos esse código.
    const recibo = venda.pedidoBackendId && venda.pixTxid
      ? `\n\nRecibo: ${API_BASE}/api/pedidos/${venda.pedidoBackendId}/recibo?txid=${encodeURIComponent(venda.pixTxid)}`
      : "";
    return `${prefixo}\n${pedido}\nStatus: ${status}\n${mensagens[status] || "Atualizamos o status do seu pedido."}\n\n${itens}\n\n${total}${recibo}`;
  }

  function buildWhatsappStatusUrl(venda, status) {
    const numero = (config.whatsappNumber || (typeof storeConfig !== "undefined" ? storeConfig.whatsappNumber : "554999172137"));
    return `https://wa.me/${String(numero).replace(/\D/g, "")}?text=${encodeURIComponent(mensagemStatusPedido(venda, status))}`;
  }

  function atualizarStatusVendaLocal(vendaId, novoStatus, abrirWhatsapp = false) {
    const venda = sales.find(item => String(item.id) === String(vendaId));
    if (!venda) return setSyncStatus("Venda não encontrada para atualizar status.", false);
    const statusAnterior = venda.status;
    venda.status = novoStatus;
    venda.statusUpdatedAt = new Date().toISOString();

    if (textoNormalizado(novoStatus).includes("cancelad") && !vendaCancelada(venda)) {
      const totalReposto = reporEstoqueDaVenda(venda);
      venda.cancelledAt = venda.cancelledAt || new Date().toISOString();
      venda.estoqueReposto = true;
      setSyncStatus(totalReposto > 0 ? `Pedido ${venda.id} cancelado. ${totalReposto} item(ns) devolvido(s) ao estoque.` : `Pedido ${venda.id} cancelado. Sem itens vinculados para repor automaticamente.`, totalReposto > 0);
    } else {
      setSyncStatus(`Pedido ${venda.id}: ${statusAnterior || "sem status"} → ${novoStatus}.`, true);
    }

    saveState();
    renderAll();
    if (abrirWhatsapp) window.open(buildWhatsappStatusUrl(venda, novoStatus), "_blank", "noopener");
  }

  function abrirWhatsappStatus(vendaId, status) {
    const venda = sales.find(item => String(item.id) === String(vendaId));
    if (!venda) return setSyncStatus("Venda não encontrada para WhatsApp.", false);
    window.open(buildWhatsappStatusUrl(venda, status || venda.status || "Atualização"), "_blank", "noopener");
  }

  function reporEstoqueDaVenda(venda) {
    let totalReposto = 0;
    (venda.items || []).forEach(item => {
      if (!item.id) return;
      const quantidade = Number(item.qty || item.quantidade || 0);
      if (!Number.isFinite(quantidade) || quantidade <= 0) return;
      stock[item.id] = getStock(item.id) + quantidade;
      totalReposto += quantidade;
    });
    return totalReposto;
  }

  function cancelarVendaLocal(vendaId) {
    const venda = sales.find(item => String(item.id) === String(vendaId));
    if (!venda) return setSyncStatus("Venda não encontrada para cancelamento.", false);
    if (vendaCancelada(venda)) return setSyncStatus("Venda já estava cancelada; estoque não será reposto novamente.", false);
    if (!confirm(`Cancelar pedido ${venda.id} e devolver os itens ao estoque?`)) return;

    const totalReposto = reporEstoqueDaVenda(venda);
    venda.status = "Cancelado";
    venda.cancelledAt = new Date().toISOString();
    venda.estoqueReposto = true;
    saveState();
    renderAll();
    setSyncStatus(totalReposto > 0 ? `Pedido ${venda.id} cancelado. ${totalReposto} item(ns) devolvido(s) ao estoque.` : `Pedido ${venda.id} cancelado. Sem itens vinculados para repor automaticamente.`, totalReposto > 0);
  }

  function instalarCancelamentoVendas() {
    if (window.__misticaCancelSaleInstalled || typeof renderHistory !== "function") return;
    window.__misticaCancelSaleInstalled = true;
    window.cancelSale = cancelarVendaLocal;
    window.updateSaleStatus = atualizarStatusVendaLocal;
    window.openSaleStatusWhatsapp = abrirWhatsappStatus;
    renderHistory = function renderHistoryWithCancelActions() {
      if (!salesHistory) return;
      if (!sales.length) {
        salesHistory.innerHTML = `<div class="history-item"><span>Nenhuma venda registrada ainda.</span></div>`;
        return;
      }
      salesHistory.innerHTML = sales.slice(0, 10).map(sale => {
        const cancelada = vendaCancelada(sale);
        const vendaId = escapeInline(sale.id);
        const statusAtual = escapeInline(sale.status || "Atualização");
        const cancelledInfo = sale.cancelledAt ? `<span>Cancelado em: ${new Date(sale.cancelledAt).toLocaleString("pt-BR")}</span>` : "";
        const cancelAction = cancelada
          ? `<span class="privacy-note">Estoque já reposto</span>`
          : `<button class="btn btn-ghost btn-full" type="button" onclick="cancelSale('${vendaId}')">Cancelar e repor estoque</button>`;
        const statusButtons = STATUS_RAPIDOS.map(status => {
          const active = textoNormalizado(status) === textoNormalizado(sale.status) ? " disabled" : "";
          return `<button class="btn btn-ghost" type="button" onclick="updateSaleStatus('${vendaId}', '${escapeInline(status)}')"${active}>${status}</button>`;
        }).join("");
        const whatsAction = `<button class="btn btn-ghost btn-full" type="button" onclick="openSaleStatusWhatsapp('${vendaId}', '${statusAtual}')">WhatsApp do status</button>`;
        return `
          <div class="history-item">
            <strong>${currency.format(sale.total)} • ${new Date(sale.date).toLocaleString("pt-BR")}</strong>
            <span>${(sale.items || []).map(item => `${item.qty}x ${item.name}`).join(" | ")}</span>
            <span>Status: ${sale.status}</span>
            ${cancelledInfo}
            <div class="admin-activity-tools">${statusButtons}</div>
            ${whatsAction}
            ${cancelAction}
          </div>
        `;
      }).join("");
    };
    renderHistory();
  }

  window.misticaMobileSync = {
    apiBase: API_BASE,
    syncNow: sincronizarAgora,
    sendSale: criarPedidoNoServidor,
    cancelSale: cancelarVendaLocal,
    updateSaleStatus: atualizarStatusVendaLocal,
    openSaleStatusWhatsapp: abrirWhatsappStatus,
  };

  window.addEventListener("load", () => {
    carregarPainelAuth();
    instalarCancelamentoVendas();
    sincronizarAgora();
    setInterval(sincronizarAgora, SYNC_INTERVAL_MS);
  });
})();
