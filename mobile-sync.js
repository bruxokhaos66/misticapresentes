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

  // products[] guarda texto puro (não escapado). Cada consumidor (cartão do
  // catálogo, página de produto, carrinho etc.) escapa na hora de montar
  // HTML — nunca aqui. Escapar aqui e de novo no consumidor gerava
  // entidades duplicadas (ex.: "&amp;amp;") visíveis na tela; escapar só
  // aqui e ler o valor via textContent em outro lugar mostrava a entidade
  // crua (ex.: "&amp;"), já que textContent não decodifica HTML.
  function catalogText(value, fallback = "") {
    const normalized = String(value == null ? fallback : value)
      .replace(/[\u0000-\u001F\u007F]/g, " ")
      .replace(/\s+/g, " ")
      .trim();
    return normalized || fallback;
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

  // Fica true assim que o catálogo oficial é confirmado pela primeira vez
  // nesta página. Distingue duas situações bem diferentes numa falha de
  // sincronização:
  //  - catálogo NUNCA confirmado (1º carregamento falhou): não há nada
  //    autoritativo pra mostrar, então a vitrine deve mesmo ficar vazia e
  //    bloqueada (evita exibir os produtos estáticos de exemplo de app.js
  //    como se fossem o catálogo real).
  //  - catálogo já confirmado antes e a sincronização seguinte falhou
  //    (timeout, instabilidade momentânea, celular com conexão fraca): esse
  //    erro é transitório e não pode apagar o que já está confirmado em
  //    tela. O sync roda a cada 15s (SYNC_INTERVAL_MS) para sempre, então
  //    tratar qualquer falha passageira como "catálogo vazio" fazia a
  //    vitrine inteira desaparecer, o conteúdo abaixo subir pra ocupar o
  //    espaço e, no sync seguinte com sucesso, tudo reaparecer empurrando a
  //    página de novo — o "piscar/pular" reportado.
  let catalogoConfirmado = false;
  // Assinatura do último catálogo já aplicado. O sync roda a cada 15s
  // (SYNC_INTERVAL_MS) para sempre, mesmo sem nenhuma mudança real no
  // estoque/preço/produtos; sem essa checagem, cada sync bem-sucedido
  // reconstruía o grid inteiro (innerHTML) à toa, destruindo e recriando
  // todo <img> da vitrine — uma fonte extra de "piscar" independente da
  // troca de catálogo em si. Só reconstrói quando algo de fato mudou.
  let ultimaAssinaturaCatalogo = null;

  function aplicarProdutos(lista) {
    if (!Array.isArray(lista) || typeof products === "undefined") {
      throw new Error("Resposta inválida do catálogo.");
    }
    const novos = lista.map(normalizarProduto).filter(product => product.apiId && product.codigo && Number.isFinite(product.price));
    catalogoConfirmado = true;
    const assinatura = JSON.stringify(novos);
    if (assinatura === ultimaAssinaturaCatalogo) return;
    ultimaAssinaturaCatalogo = assinatura;
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
    if (!catalogoConfirmado) setCatalogState("loading", "Carregando catálogo oficial...");
    try {
      const produtos = await api("/api/produtos?limite=500");
      aplicarProdutos(produtos);
      setCatalogState("ready", produtos.length ? "Online" : "Catálogo sem produtos disponíveis no momento.");
    } catch (error) {
      if (catalogoConfirmado) {
        // Catálogo já confirmado antes: mantém o que já está em tela e só
        // avisa da instabilidade, sem apagar nada.
        setCatalogState("error", "Falha ao atualizar o catálogo. Exibindo o último catálogo confirmado; compras e Pix ficam bloqueados até a reconexão.");
      } else {
        clearCatalog();
        setCatalogState("error", "Catálogo indisponível. Compras e Pix estão temporariamente bloqueados.");
      }
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

  // Idempotency-Key da tentativa de checkout atual. Fica em memória e é
  // espelhada via window.misticaSecureStorage (site-config.js), junto com a
  // assinatura do carrinho que a gerou: reenviar a mesma tentativa (retry de
  // rede, clique duplo, F5 depois de gerar o Pix, ou uma segunda aba com o
  // mesmo carrinho) reaproveita a mesma chave, então o backend devolve
  // sempre o mesmo pedido em vez de criar um novo e reservar estoque em
  // dobro. Uma chave nova só é gerada quando o conteúdo do carrinho muda
  // (ver window.misticaResetIdempotencyKey em app.js) ou quando a chave
  // expira (CHECKOUT_KEY_TTL_MS).
  // Menor que MISTICA_MINUTOS_EXPIRACAO_PEDIDO (padrão 30min no backend):
  // garante que a chave local sempre expira ANTES do pedido correspondente no
  // servidor, então nunca é reaproveitada apontando para um pedido já
  // cancelado/expirado (o que devolveria um Pix "morto" ao cliente). Depois
  // desse prazo, um novo clique gera uma chave nova e um pedido novo, como
  // esperado para um Pix que realmente já venceu.
  const CHECKOUT_KEY_TTL_MS = 20 * 60 * 1000;
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

  function assinaturaCarrinho(itensPedido) {
    return itensPedido
      .map(item => `${item.produto_id}:${item.quantidade}`)
      .sort()
      .join("|");
  }

  function lerChaveArmazenada() {
    const armazenada = window.misticaSecureStorage?.getCheckoutIdempotency?.();
    if (!armazenada) return null;
    if (Date.now() - armazenada.ts > CHECKOUT_KEY_TTL_MS) return null;
    return armazenada;
  }

  function gravarChaveArmazenada(key, signature) {
    window.misticaSecureStorage?.setCheckoutIdempotency?.(key, signature);
  }

  function limparChaveArmazenada() {
    window.misticaSecureStorage?.clearCheckoutIdempotency?.();
  }

  // Recupera (ou cria) a Idempotency-Key para o conteúdo exato do carrinho
  // enviado. Reload da página e múltiplas abas com o mesmo carrinho
  // convergem para a mesma chave (localStorage é compartilhado entre abas da
  // mesma origem); um carrinho diferente sempre gera uma chave nova.
  function idempotencyKeyParaItens(itensPedido) {
    const signature = assinaturaCarrinho(itensPedido);
    if (idempotencyKeyAtual) return idempotencyKeyAtual;

    const armazenada = lerChaveArmazenada();
    if (armazenada && armazenada.signature === signature) {
      idempotencyKeyAtual = armazenada.key;
    } else {
      idempotencyKeyAtual = gerarIdempotencyKey();
      gravarChaveArmazenada(idempotencyKeyAtual, signature);
    }
    return idempotencyKeyAtual;
  }

  function reiniciarIdempotencyKey() {
    idempotencyKeyAtual = null;
    limparChaveArmazenada();
  }

  async function criarPedidoNoServidor(itensCarrinho) {
    if (window.misticaCatalogState !== "ready") throw new Error("O catálogo oficial ainda não está disponível.");
    if (!Array.isArray(itensCarrinho) || !itensCarrinho.length) throw new Error("Carrinho vazio.");

    const cienteSobEncomenda = confirmarCondicoesEncomenda(itensCarrinho);
    const itensPedido = montarItensPedido(itensCarrinho);
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
      itens: itensPedido,
    };

    const resposta = await api("/api/checkout/pedidos", {
      method: "POST",
      headers: { "Idempotency-Key": idempotencyKeyParaItens(itensPedido) },
      body: JSON.stringify(payload),
    });

    if (!resposta?.id || !resposta?.pix_copia_cola) {
      throw new Error("O servidor não retornou um Pix válido para este pedido.");
    }

    // A chave usada NÃO é reiniciada aqui: o carrinho continua intacto após
    // o Pix ser gerado (por desenho, para permitir nova tentativa em caso de
    // falha de pagamento), então gerar o Pix de novo para o mesmo carrinho
    // (reload da página, segunda aba, novo clique) deve reaproveitar a mesma
    // chave e recuperar o MESMO pedido em vez de reservar estoque em dobro.
    // A chave só é descartada quando o carrinho muda de fato (ver
    // window.misticaResetIdempotencyKey, chamado em app.js ao
    // adicionar/remover/limpar itens) ou quando expira (CHECKOUT_KEY_TTL_MS).

    return {
      id: resposta.id,
      pixTxid: resposta.pix_txid || null,
      pixPayload: resposta.pix_copia_cola,
      pixInfo: resposta.pix || null,
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

  // Registra no servidor que o cliente clicou em "Já paguei — enviar
  // comprovante pelo WhatsApp" para este pedido. O pix_txid do próprio
  // pedido funciona como identificador público limitado (o mesmo já usado
  // por consultarStatusPedido acima): sem ele, o backend nega o acesso. Esta
  // chamada NUNCA marca o pedido como pago — apenas registra a intenção do
  // cliente para o painel administrativo, que confirma o pagamento
  // manualmente depois de conferir o valor no aplicativo bancário.
  async function registrarComprovanteEnviado(pedidoId, pixTxid) {
    const resposta = await api(`/api/pedidos/${encodeURIComponent(pedidoId)}/comprovante`, {
      method: "POST",
      body: JSON.stringify({ txid: pixTxid || null }),
    });
    return { status: resposta.status, jaRegistrado: Boolean(resposta.ja_registrado) };
  }

  window.misticaCriarPedido = criarPedidoNoServidor;
  window.misticaConsultarStatusPedido = consultarStatusPedido;
  window.misticaRegistrarComprovanteEnviado = registrarComprovanteEnviado;
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