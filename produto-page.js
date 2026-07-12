(() => {
  function qs(name) {
    return new URLSearchParams(window.location.search).get(name) || "";
  }

  function make(tag, cls, text) {
    const el = document.createElement(tag);
    if (cls) el.className = cls;
    if (text !== undefined) el.textContent = text;
    return el;
  }

  function clean(value) {
    return String(value || "").normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase();
  }

  function money(value) {
    try { return currency.format(Number(value || 0)); } catch { return `R$ ${Number(value || 0).toFixed(2)}`; }
  }

  function available(product) {
    try { return getStock(product.id); } catch { return Number(product.stock || 0); }
  }

  function productImages(product) {
    if (Array.isArray(product.images) && product.images.length) return product.images;
    if (product.imageUrl) return [product.imageUrl];
    return [];
  }

  function productSlug(product) {
    return String(product.id || "");
  }

  function findProduct() {
    const id = qs("id") || qs("produto") || window.location.hash.replace("#", "");
    if (!id || typeof products === "undefined") return null;
    return products.find(product => String(product.id) === id || productSlug(product) === id || clean(product.name).replace(/[^a-z0-9]+/g, "-") === id);
  }

  function relatedProducts(product) {
    const cat = clean(product.category);
    const words = clean(`${product.name} ${product.description}`).split(/\s+/).filter(word => word.length > 3);
    return products
      .filter(item => item.id !== product.id && available(item) > 0)
      .map(item => {
        const text = clean(`${item.name} ${item.category} ${item.description}`);
        const score = (clean(item.category) === cat ? 5 : 0) + words.filter(word => text.includes(word)).length;
        return { item, score };
      })
      .filter(row => row.score > 0)
      .sort((a, b) => b.score - a.score)
      .slice(0, 4)
      .map(row => row.item);
  }

  function productUrl(product) {
    const base = window.misticaSiteConfig?.publicBaseUrl || window.location.origin + window.location.pathname.replace(/produto\.html$/, "");
    return `${base.replace(/\/$/, "")}/produto.html?id=${encodeURIComponent(product.id)}`;
  }

  function whatsappUrl(product) {
    const number = window.misticaSiteConfig?.whatsappNumber || storeConfig.whatsappNumber || "554999172137";
    const message = `Olá, tenho interesse neste produto da Mística Presentes:\n\n${product.name}\nValor: ${money(product.price)}\nCategoria: ${product.category}\nLink: ${productUrl(product)}\n\nGostaria de consultar disponibilidade.`;
    return `https://wa.me/${number}?text=${encodeURIComponent(message)}`;
  }

  function renderTrust() {
    const rawCity = window.misticaSiteConfig?.city || storeConfig.merchantCity || "";
    const city = rawCity
      ? rawCity.toLowerCase().replace(/(^|\s)\p{L}/gu, c => c.toUpperCase())
      : "";
    const box = make("section", "product-trust");
    const badges = [
      { icon: "🔒", text: "Compra combinada direto com a loja pelo WhatsApp" },
      { icon: "🚚", text: city ? `Envios a partir de ${city}, para todo o Brasil` : "Envios para todo o Brasil" },
      { icon: "💬", text: "Atendimento humano, sem robôs de compra" },
      { icon: "↩️", text: "Troca em até 7 dias caso o produto chegue com defeito" },
    ];
    box.innerHTML = badges.map(b => `<div class="trust-badge"><span>${b.icon}</span><small>${b.text}</small></div>`).join("");
    return box;
  }

  function renderPolicies() {
    const box = make("section", "product-policies");
    box.appendChild(make("p", "eyebrow", "Antes de comprar"));
    box.appendChild(make("h2", "", "Políticas da loja"));
    const items = [
      ["Trocas e devoluções", "Aceitamos troca em até 7 dias corridos após o recebimento, caso o produto apresente defeito ou divergência com o combinado."],
      ["Frete e entrega", "O frete e o prazo são combinados diretamente pelo WhatsApp conforme a sua cidade, com opções de envio ou retirada."],
      ["Garantia", "Todos os produtos passam por conferência antes do envio. Qualquer divergência é resolvida diretamente com a Mística Presentes."],
    ];
    const grid = make("div", "product-policies-grid");
    items.forEach(([title, text]) => {
      const cell = make("div", "product-policy-item");
      cell.innerHTML = `<strong>${title}</strong><p>${text}</p>`;
      grid.appendChild(cell);
    });
    box.appendChild(grid);
    const link = make("p", "product-policies-link");
    link.innerHTML = `<a href="politica-de-trocas.html">Ver política completa de trocas e devoluções</a>`;
    box.appendChild(link);
    return box;
  }

  function renderNotFound() {
    const root = document.getElementById("produtoPageRoot");
    root.innerHTML = `
      <div class="form-panel">
        <p class="eyebrow">Produto não encontrado</p>
        <h1>Não encontramos este produto.</h1>
        <p>Ele pode ter sido removido, estar fora de estoque ou ainda não ter sido sincronizado.</p>
        <a class="btn" href="index.html#produtos">Voltar para a loja</a>
      </div>
    `;
  }

  function renderProduct(product) {
    const root = document.getElementById("produtoPageRoot");
    const images = productImages(product);
    const stock = available(product);
    const related = relatedProducts(product);
    // Mesmo saneamento de id usado por safeId() em app.js, para que o input
    // de quantidade case com o que addToCart() procura (qty-<id>).
    const cartId = String(product.id).replace(/[^a-zA-Z0-9_-]/g, "");
    document.title = `${product.name} | Mística Presentes`;

    const badgeText = String(product.selo || product.tag || "");
    const bestSeller = /mais vendid/i.test(badgeText);

    const mainPhoto = images[0]
      ? `<img class="product-page-photo" id="productMainPhoto" src="${images[0]}" alt="${product.name}" loading="eager">`
      : `<div class="product-image product-page-icon" id="productMainPhoto">${product.icon || "✨"}</div>`;

    const thumbs = images.length > 1
      ? `<div class="product-page-thumbs">${images.map((src, i) => `<button type="button" class="product-page-thumb${i === 0 ? " is-active" : ""}" data-src="${src}"><img src="${src}" alt="${product.name} - foto ${i + 1}" loading="lazy"></button>`).join("")}</div>`
      : "";

    root.innerHTML = `
      <article class="product-page-card">
        <div class="product-page-media">
          ${bestSeller ? `<span class="product-badge-best">${badgeText}</span>` : ""}
          ${mainPhoto}
          ${thumbs}
        </div>
        <div class="product-page-info">
          <p class="eyebrow">${product.category || "Produto"}</p>
          <h1>${product.name}</h1>
          <p>${product.description || "Produto especial selecionado pela Mística Presentes."}</p>
          <strong class="product-price">${money(product.price)}</strong>
          <span class="stock-badge ${stock <= storeConfig.minStock ? "stock-low" : ""}">${stock > 0 ? `Estoque: ${stock}` : "Sob encomenda"}</span>
          <div class="product-page-buy">
            <input id="qty-${cartId}" class="product-page-qty" type="number" min="1" max="${Math.max(stock, 1)}" step="1" value="1" aria-label="Quantidade de ${product.name}" ${stock <= 0 ? "disabled" : ""}>
            <button class="btn" type="button" id="addProductToCart" ${stock <= 0 ? "disabled" : ""}>${stock > 0 ? "Adicionar ao carrinho" : "Sob encomenda"}</button>
          </div>
          <p class="product-page-buy-feedback" id="addProductFeedback" role="status" hidden></p>
          <div class="product-page-actions">
            <a class="btn btn-ghost" href="${whatsappUrl(product)}" target="_blank" rel="noopener" id="buyProductWhatsapp">Comprar pelo WhatsApp</a>
            <a class="btn btn-ghost" href="#checkout-jump" id="goToCartFromProduct">Ir para o carrinho</a>
            <button class="btn btn-ghost" type="button" id="copyProductLink">Copiar link</button>
          </div>
          <small class="privacy-note">Adicione ao carrinho e finalize com Pix ou WhatsApp. Confira disponibilidade e prazo de entrega antes de pagar.</small>
        </div>
      </article>
    `;

    window.misticaTrack?.("view_item", { currency: "BRL", value: product.price, items: [{ item_id: product.id, item_name: product.name, price: product.price }] });
    document.getElementById("buyProductWhatsapp")?.addEventListener("click", () => {
      window.misticaTrack?.("contact_whatsapp", { method: "produto_pagina", item_id: product.id, item_name: product.name });
    });

    const addButton = document.getElementById("addProductToCart");
    const feedback = document.getElementById("addProductFeedback");
    addButton?.addEventListener("click", () => {
      if (typeof window.addToCart !== "function") {
        if (feedback) { feedback.hidden = false; feedback.textContent = "Carregando a loja, tente novamente em instantes."; }
        return;
      }
      const antes = typeof getTotal === "function" ? getTotal() : 0;
      window.addToCart(product.id);
      const depois = typeof getTotal === "function" ? getTotal() : 0;
      if (feedback) {
        feedback.hidden = false;
        feedback.textContent = depois > antes
          ? "Produto adicionado ao carrinho. Toque em “Ir para o carrinho” para finalizar."
          : "Não foi possível adicionar (confira o estoque disponível).";
      }
    });

    document.getElementById("goToCartFromProduct")?.addEventListener("click", event => {
      event.preventDefault();
      window.location.href = "index.html#checkout";
    });

    const copy = document.getElementById("copyProductLink");
    copy?.addEventListener("click", async () => {
      const url = productUrl(product);
      try {
        await navigator.clipboard.writeText(url);
        copy.textContent = "Link copiado";
      } catch {
        window.prompt("Copie o link do produto:", url);
      }
    });

    root.querySelectorAll(".product-page-thumb").forEach(btn => {
      btn.addEventListener("click", () => {
        const main = document.getElementById("productMainPhoto");
        if (main && main.tagName === "IMG") main.src = btn.dataset.src;
        root.querySelectorAll(".product-page-thumb").forEach(b => b.classList.toggle("is-active", b === btn));
      });
    });

    root.appendChild(renderTrust());
    root.appendChild(renderPolicies());

    if (related.length) {
      const rel = make("section", "product-page-related");
      rel.appendChild(make("p", "eyebrow", "Relacionados"));
      rel.appendChild(make("h2", "", "Produtos que combinam"));
      const grid = make("div", "related-product-cards");
      related.forEach(item => {
        const card = make("a", "related-product-card");
        card.href = `produto.html?id=${encodeURIComponent(item.id)}`;
        card.innerHTML = `<span>${item.icon || "✨"}</span><strong>${item.name}</strong><small>${money(item.price)}</small>`;
        grid.appendChild(card);
      });
      rel.appendChild(grid);
      root.appendChild(rel);
    }

    window.misticaCurrentProduct = product;
    window.dispatchEvent(new CustomEvent("mistica:product-rendered", { detail: { product } }));
  }

  function init() {
    const product = findProduct();
    if (!product) renderNotFound();
    else renderProduct(product);
  }

  // Renderiza o quanto antes (sem atraso artificial) para reduzir CLS/LCP; o
  // espaço já é reservado no CSS (.product-page-shell / .product-page-photo).
  // Um único re-render tardio capta o catálogo sincronizado pela API
  // (mobile-sync.js) sem provocar novo salto de layout, pois o espaço é fixo.
  function boot() {
    init();
    window.setTimeout(init, 1500);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot, { once: true });
  } else {
    boot();
  }
})();
