(() => {
  const cfg = window.misticaSiteConfig || {};
  const API_BASE = (cfg.apiBaseUrl || "https://api.misticaesotericos.com.br").replace(/\/$/, "");
  const SITE_API_KEY = String(cfg.siteApiKey || "").trim();
  let editingApiProductId = null;

  function headers() {
    return {
      "Content-Type": "application/json",
      ...(SITE_API_KEY ? { "X-Mistica-Api-Key": SITE_API_KEY } : {}),
    };
  }

  async function api(path, options = {}) {
    const response = await fetch(`${API_BASE}${path}`, { ...options, headers: { ...headers(), ...(options.headers || {}) } });
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

  function parseMoney(value) {
    const normalized = String(value || "").replace(/\./g, "").replace(",", ".");
    const number = Number(normalized);
    return Number.isFinite(number) && number >= 0 ? number : 0;
  }

  function parseImages(value) {
    return String(value || "")
      .split("\n")
      .map(item => item.trim())
      .filter(Boolean)
      .slice(0, 8);
  }

  function setField(id, value) {
    const el = document.getElementById(id);
    if (el) el.value = value || "";
  }

  function getPayload() {
    const imagens = parseImages(document.getElementById("productImages")?.value || "");
    return {
      codigo_p: editingApiProductId ? `API-${editingApiProductId}` : undefined,
      nome: document.getElementById("productName")?.value.trim() || "Produto sem nome",
      categoria: document.getElementById("productCategory")?.value.trim() || "Produtos da loja",
      descricao: document.getElementById("productDescription")?.value.trim() || "",
      preco: parseMoney(document.getElementById("productPrice")?.value || "0"),
      quantidade: Number.parseInt(document.getElementById("productStock")?.value || "0", 10) || 0,
      estoque_minimo: 0,
      custo: 0,
      lucro: 0,
      selo: document.getElementById("productTag")?.value.trim() || "",
      imagem_url: imagens[0] || "",
      imagens,
      link_externo: document.getElementById("productExternal")?.value.trim() || "",
    };
  }

  function status(text, ok = true) {
    const el = document.getElementById("apiProductStatus");
    if (!el) return;
    el.textContent = text;
    el.className = ok ? "saved-box" : "warning-box warning-danger";
    el.hidden = false;
  }

  async function salvarProdutoApi() {
    const payload = getPayload();
    const method = editingApiProductId ? "PUT" : "POST";
    const path = editingApiProductId ? `/api/produtos/${editingApiProductId}` : "/api/produtos";
    const result = await api(path, { method, body: JSON.stringify(payload) });
    editingApiProductId = null;
    status(`Produto ${result.status || "salvo"} na API.`, true);
    await carregarProdutosApi();
    if (window.misticaMobileSync?.syncNow) window.misticaMobileSync.syncNow();
  }

  function preencherFormulario(produto) {
    editingApiProductId = produto.id;
    setField("productName", produto.nome || "");
    setField("productCategory", produto.categoria || "");
    setField("productDescription", produto.descricao || "");
    setField("productPrice", String(produto.preco || 0).replace(".", ","));
    setField("productStock", produto.quantidade || 0);
    setField("productTag", produto.selo || "");
    setField("productImages", (produto.imagens || []).join("\n") || produto.imagem_url || "");
    setField("productExternal", produto.link_externo || "");
    status(`Editando produto API #${produto.id}. Após ajustar, clique em Salvar na API.`, true);
    document.getElementById("productAdminForm")?.scrollIntoView({ behavior: "smooth" });
  }

  async function excluirProdutoApi(id) {
    if (!confirm("Excluir este produto da API?")) return;
    await api(`/api/produtos/${id}`, { method: "DELETE" });
    status("Produto excluído da API.", true);
    await carregarProdutosApi();
    if (window.misticaMobileSync?.syncNow) window.misticaMobileSync.syncNow();
  }

  function renderListaApi(lista) {
    const root = document.getElementById("apiProductsList");
    if (!root) return;
    if (!lista.length) {
      root.innerHTML = `<div class="history-item"><span>Nenhum produto vindo da API.</span></div>`;
      return;
    }
    root.innerHTML = lista.slice(0, 80).map(produto => `
      <div class="history-item api-product-item">
        <strong>${produto.nome}</strong>
        <span>${produto.categoria || "Sem categoria"} • R$ ${Number(produto.preco || 0).toFixed(2).replace(".", ",")} • Estoque: ${produto.quantidade || 0}</span>
        <span>${produto.selo ? "Selo: " + produto.selo : "Sem selo"}</span>
        <div class="pedido-actions">
          <button class="btn btn-ghost" type="button" data-api-edit-product="${produto.id}">Editar</button>
          <button class="btn btn-ghost" type="button" data-api-delete-product="${produto.id}">Excluir</button>
        </div>
      </div>
    `).join("");
    root.querySelectorAll("[data-api-edit-product]").forEach(btn => {
      btn.addEventListener("click", () => {
        const produto = lista.find(item => String(item.id) === String(btn.dataset.apiEditProduct));
        if (produto) preencherFormulario(produto);
      });
    });
    root.querySelectorAll("[data-api-delete-product]").forEach(btn => {
      btn.addEventListener("click", () => excluirProdutoApi(btn.dataset.apiDeleteProduct).catch(error => status(error.message, false)));
    });
  }

  async function carregarProdutosApi() {
    const lista = await api("/api/produtos?limite=500");
    renderListaApi(lista);
    return lista;
  }

  function mountApiProductPanel() {
    if (document.getElementById("apiProductPanel")) return;
    const form = document.getElementById("productAdminForm");
    if (!form) return;

    const panel = document.createElement("div");
    panel.id = "apiProductPanel";
    panel.className = "image-upload-panel api-product-panel";
    panel.innerHTML = `
      <p class="eyebrow">API</p>
      <h3>Salvar produto no banco real</h3>
      <p class="privacy-note">Use estes botões para gravar o produto na API e manter o site sincronizado com o programa da loja.</p>
      <div class="image-upload-actions">
        <button class="btn" type="button" id="saveProductApi">Salvar na API</button>
        <button class="btn btn-ghost" type="button" id="reloadProductsApi">Recarregar produtos</button>
        <button class="btn btn-ghost" type="button" id="clearProductApiEdit">Novo produto</button>
      </div>
      <div id="apiProductStatus" hidden></div>
      <div id="apiProductsList" class="history-list"></div>
    `;
    form.appendChild(panel);

    document.getElementById("saveProductApi")?.addEventListener("click", () => salvarProdutoApi().catch(error => status(error.message, false)));
    document.getElementById("reloadProductsApi")?.addEventListener("click", () => carregarProdutosApi().catch(error => status(error.message, false)));
    document.getElementById("clearProductApiEdit")?.addEventListener("click", () => {
      editingApiProductId = null;
      form.reset();
      status("Pronto para cadastrar novo produto.", true);
    });
    carregarProdutosApi().catch(error => status(`API offline: ${error.message}`, false));
  }

  window.addEventListener("load", () => {
    mountApiProductPanel();
    setInterval(mountApiProductPanel, 1500);
  });
})();
