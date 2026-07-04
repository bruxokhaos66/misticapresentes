(() => {
  const kits = [
    { nome: "Kit Proteção", icone: "🛡️", texto: "Incenso, vela ou cristal para proteção e limpeza.", termos: ["prote", "incenso", "vela", "cristal", "arruda", "sálvia", "salvia"] },
    { nome: "Kit Limpeza Energética", icone: "🌿", texto: "Sugestão rápida para harmonizar o ambiente.", termos: ["limpeza", "banho", "erva", "defuma", "incenso"] },
    { nome: "Kit Presente Místico", icone: "🎁", texto: "Combinação simples para presentear com significado.", termos: ["presente", "aroma", "difusor", "cristal", "vela"] },
  ];

  function q(sel) { return document.querySelector(sel); }
  function make(tag, cls, text) {
    const el = document.createElement(tag);
    if (cls) el.className = cls;
    if (text !== undefined) el.textContent = text;
    return el;
  }
  function clean(value) {
    return String(value || "").normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase();
  }
  function productLink(p) { return `produto.html?id=${encodeURIComponent(p.id)}`; }
  function textProduct(p) {
    return clean(`${p.name} ${p.category} ${p.description} ${p.tag || ""}`);
  }
  function money(value) {
    try { return currency.format(Number(value || 0)); } catch { return `R$ ${Number(value || 0).toFixed(2)}`; }
  }
  function available(p) {
    try { return getStock(p.id); } catch { return Number(p.stock || 0); }
  }

  function carregarScript(id, src) {
    if (document.getElementById(id)) return;
    const script = document.createElement("script");
    script.id = id;
    script.src = src;
    script.defer = true;
    document.head.appendChild(script);
  }

  function carregarAdminImageUpload() {
    carregarScript("adminImageUploadScript", "admin-image-upload.js");
  }

  function carregarAdminProductApi() {
    carregarScript("adminProductApiScript", "admin-product-api.js");
  }

  function produtosDoKit(kit) {
    const achados = [];
    kit.termos.forEach(t => {
      const item = products.find(p => !achados.includes(p) && available(p) > 0 && textProduct(p).includes(clean(t)));
      if (item) achados.push(item);
    });
    return achados.slice(0, 4);
  }

  function adicionarProduto(productId) {
    const input = document.getElementById(`qty-${safeId(productId)}`);
    if (input) input.value = "1";
    addToCart(productId);
  }

  function montarKits() {
    const grid = document.querySelector("[data-product-grid]");
    if (!grid || q("#kitsSection")) return;
    const wrap = make("section", "container kits-section");
    wrap.id = "kitsSection";
    wrap.appendChild(make("p", "eyebrow", "Kits prontos"));
    wrap.appendChild(make("h3", "", "Combinações rápidas para presentear ou harmonizar"));
    const cards = make("div", "kit-grid");
    kits.forEach(kit => {
      const card = make("article", "kit-card");
      card.appendChild(make("span", "kit-icon", kit.icone));
      card.appendChild(make("strong", "", kit.nome));
      card.appendChild(make("p", "", kit.texto));
      const btn = make("button", "btn btn-ghost btn-full", "Adicionar sugestão");
      btn.type = "button";
      btn.addEventListener("click", () => {
        const itens = produtosDoKit(kit);
        if (!itens.length) return alert("Nenhum item disponível para este kit no momento.");
        itens.forEach(p => adicionarProduto(p.id));
      });
      card.appendChild(btn);
      cards.appendChild(card);
    });
    wrap.appendChild(cards);
    grid.parentNode.insertBefore(wrap, grid);
  }

  function relacionados(produto) {
    const cat = clean(produto.category);
    return products
      .filter(p => p.id !== produto.id && available(p) > 0)
      .map(p => ({ p, score: clean(p.category) === cat ? 3 : 0 }))
      .filter(x => x.score > 0)
      .slice(0, 3)
      .map(x => x.p);
  }

  function abrirDetalhe(productId) {
    const produto = products.find(p => String(p.id) === String(productId));
    if (!produto) return;
    let modal = q("#productDetailModal");
    if (!modal) {
      modal = make("div", "product-modal");
      modal.id = "productDetailModal";
      modal.innerHTML = `<div class="product-modal-card"><button class="modal-close" type="button">×</button><div id="productDetailContent"></div></div>`;
      document.body.appendChild(modal);
      modal.addEventListener("click", e => { if (e.target === modal || e.target.classList.contains("modal-close")) modal.hidden = true; });
    }
    const content = q("#productDetailContent");
    content.innerHTML = "";
    const box = make("div", "product-detail-layout");
    const foto = make("div", "product-image", produto.icon || "✨");
    const imgs = Array.isArray(produto.images) ? produto.images : [];
    if (imgs[0]) {
      const img = document.createElement("img");
      img.className = "product-photo";
      img.src = imgs[0];
      img.alt = produto.name;
      foto.textContent = "";
      foto.appendChild(img);
    }
    const info = make("div", "product-detail-info");
    info.appendChild(make("p", "eyebrow", produto.category || "Produto"));
    info.appendChild(make("h2", "", produto.name));
    info.appendChild(make("p", "", produto.description || "Produto selecionado pela Mística Presentes."));
    info.appendChild(make("strong", "product-price", money(produto.price)));
    info.appendChild(make("span", "stock-badge", available(produto) > 0 ? `Estoque: ${available(produto)}` : "Sob encomenda"));
    const add = make("button", "btn", "Adicionar ao carrinho");
    add.type = "button";
    add.disabled = available(produto) <= 0;
    add.addEventListener("click", () => adicionarProduto(produto.id));
    const page = make("a", "btn btn-ghost", "Abrir página do produto");
    page.href = productLink(produto);
    info.append(add, page);
    box.append(foto, info);
    content.appendChild(box);

    const rel = relacionados(produto);
    if (rel.length) {
      const area = make("div", "related-products");
      area.appendChild(make("h3", "", "Produtos relacionados"));
      const list = make("div", "related-grid");
      rel.forEach(p => {
        const b = make("a", "related-item", `${p.icon || "✨"} ${p.name} • ${money(p.price)}`);
        b.href = productLink(p);
        list.appendChild(b);
      });
      area.appendChild(list);
      content.appendChild(area);
    }
    modal.hidden = false;
  }

  function inserirBotoesDetalhe() {
    document.querySelectorAll(".product-card").forEach(card => {
      if (card.querySelector("[data-open-detail]")) return;
      const title = card.querySelector("h3")?.textContent || "";
      const produto = products.find(p => p.name === title);
      if (!produto) return;
      const btn = make("button", "btn btn-ghost btn-full", "Ver detalhes");
      btn.type = "button";
      btn.dataset.openDetail = produto.id;
      btn.addEventListener("click", () => abrirDetalhe(produto.id));
      const link = make("a", "btn btn-ghost btn-full", "Página do produto");
      link.href = productLink(produto);
      const whats = [...card.querySelectorAll("button")].find(b => b.textContent.includes("WhatsApp"));
      card.insertBefore(btn, whats || null);
      card.insertBefore(link, whats || null);
    });
  }

  function ativarExtras() {
    if (typeof products === "undefined") return;
    carregarAdminImageUpload();
    carregarAdminProductApi();
    montarKits();
    inserirBotoesDetalhe();
  }

  window.addEventListener("load", () => {
    ativarExtras();
    setInterval(ativarExtras, 1200);
  });
})();
