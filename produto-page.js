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
    document.title = `${product.name} | Mística Presentes`;

    const media = images[0]
      ? `<img class="product-page-photo" src="${images[0]}" alt="${product.name}" loading="eager">`
      : `<div class="product-image product-page-icon">${product.icon || "✨"}</div>`;

    root.innerHTML = `
      <article class="product-page-card">
        <div class="product-page-media">${media}</div>
        <div class="product-page-info">
          <p class="eyebrow">${product.category || "Produto"}</p>
          <h1>${product.name}</h1>
          <p>${product.description || "Produto especial selecionado pela Mística Presentes."}</p>
          <strong class="product-price">${money(product.price)}</strong>
          <span class="stock-badge ${stock <= storeConfig.minStock ? "stock-low" : ""}">${stock > 0 ? `Estoque: ${stock}` : "Sob encomenda"}</span>
          <div class="product-page-actions">
            <a class="btn" href="${whatsappUrl(product)}" target="_blank" rel="noopener">Comprar pelo WhatsApp</a>
            <button class="btn btn-ghost" type="button" id="copyProductLink">Copiar link</button>
            <a class="btn btn-ghost" href="index.html#produtos">Voltar à vitrine</a>
          </div>
          <small class="privacy-note">Confira disponibilidade, valor e prazo de entrega pelo WhatsApp antes de finalizar.</small>
        </div>
      </article>
    `;

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

  window.addEventListener("load", () => setTimeout(init, 400));
})();
