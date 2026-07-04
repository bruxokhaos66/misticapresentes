(() => {
  const cfg = window.misticaSiteConfig || {};
  const API_BASE = (cfg.apiBaseUrl || "https://api.misticaesotericos.com.br").replace(/\/$/, "");
  const SITE_API_KEY = String(cfg.siteApiKey || "").trim();
  const WHATSAPP = cfg.whatsappNumber || "554999172137";

  function money(value) {
    try { return currency.format(Number(value || 0)); } catch { return `R$ ${Number(value || 0).toFixed(2)}`; }
  }

  function headers() {
    return {
      "Content-Type": "application/json",
      ...(SITE_API_KEY ? { "X-Mistica-Api-Key": SITE_API_KEY } : {}),
    };
  }

  async function api(path, options = {}) {
    const response = await fetch(`${API_BASE}${path}`, {
      ...options,
      headers: { ...headers(), ...(options.headers || {}) },
    });
    if (!response.ok) {
      let detail = `API ${response.status}`;
      try {
        const body = await response.json();
        detail = body.detail || detail;
      } catch {}
      throw new Error(detail);
    }
    return response.json();
  }

  function montarItensDoKit(kit) {
    return kit.items.map(row => ({
      produto_id: row.product.apiId || null,
      codigo_p: row.product.codigo || row.product.id,
      nome_p: row.product.name,
      quantidade: 1,
      custo_unitario: 0,
      valor_unitario: Number(row.product.price || 0),
      valor_total: Number(row.product.price || 0),
    }));
  }

  function mensagemPedido(pedidoId, kit) {
    const itens = kit.items.map(row => `• ${row.product.name} - ${money(row.product.price)}`).join("\n");
    return `Olá, vim pelo site da Mística Presentes.\n\nA Isis montou este pedido para mim:\n\nPedido: #${pedidoId}\n${kit.title}\n\n${itens}\n\nTotal sugerido: ${money(kit.total)}\n\nPode confirmar o Pix, disponibilidade e retirada?`;
  }

  function abrirWhatsApp(texto) {
    window.open(`https://wa.me/${WHATSAPP}?text=${encodeURIComponent(texto)}`, "_blank", "noopener");
  }

  async function criarPedidoKit(kitKey) {
    const lista = window.__isisLastProducts || window.products || [];
    const kit = window.misticaIsisCommerce?.buildKit?.(lista, kitKey);
    if (!kit) return alert("Não consegui montar este kit agora.");

    const payload = {
      origem: "isis_site",
      cliente: "Pedido gerado pela Isis",
      subtotal: Number(kit.total || 0),
      desconto: 0,
      taxa: 0,
      total_final: Number(kit.total || 0),
      forma_pagamento: "Pix",
      vendedor: "Isis/Site",
      status: "Aguardando pagamento",
      data_venda: new Date().toLocaleString("pt-BR"),
      data_iso: new Date().toISOString(),
      dia_operacional: new Date().toISOString().slice(0, 10),
      baixa_estoque: false,
      itens: montarItensDoKit(kit),
    };

    try {
      const result = await api("/api/vendas", { method: "POST", body: JSON.stringify(payload) });
      alert(`Pedido #${result.id} gerado na API.`);
      abrirWhatsApp(mensagemPedido(result.id, kit));
      if (window.misticaPedidos?.reload) window.misticaPedidos.reload();
    } catch (error) {
      alert(`Falha ao gerar pedido na API: ${error.message}`);
    }
  }

  function instalarBotoesPedido() {
    document.querySelectorAll("[data-isis-add-kit]").forEach(btn => {
      if (btn.dataset.orderReady === "1") return;
      btn.dataset.orderReady = "1";
      const kitKey = btn.dataset.isisAddKit;
      const order = document.createElement("button");
      order.className = "btn btn-ghost";
      order.type = "button";
      order.textContent = "Gerar pedido na loja";
      order.dataset.isisOrderKit = kitKey;
      btn.insertAdjacentElement("afterend", order);
    });
  }

  document.addEventListener("click", event => {
    const kitKey = event.target?.dataset?.isisOrderKit;
    if (kitKey) criarPedidoKit(kitKey);
  });

  window.addEventListener("load", () => {
    instalarBotoesPedido();
    setInterval(instalarBotoesPedido, 1200);
  });
})();
