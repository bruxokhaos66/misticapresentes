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

  function reviewsOf(product) {
    const list = Array.isArray(product.avaliacoes) ? product.avaliacoes : [];
    return list
      .map(item => ({
        nome: String(item?.nome || "Cliente Mística").trim(),
        nota: Math.min(5, Math.max(1, Number(item?.nota) || 0)),
        comentario: String(item?.comentario || "").trim(),
      }))
      .filter(item => item.nota > 0);
  }

  function starRow(nota) {
    const full = Math.round(nota);
    return Array.from({ length: 5 }, (_, i) => `<span class="review-star${i < full ? " is-filled" : ""}">★</span>`).join("");
  }

  function renderReviews(product) {
    const reviews = reviewsOf(product);
    const box = make("section", "product-reviews");
    box.appendChild(make("p", "eyebrow", "Avaliações"));

    if (!reviews.length) {
      box.appendChild(make("h2", "", "Ainda sem avaliações"));
      box.appendChild(make("p", "muted-note", "Seja a primeira pessoa a comprar e avaliar este produto."));
      return box;
    }

    const average = reviews.reduce((sum, r) => sum + r.nota, 0) / reviews.length;
    const head = make("div", "product-reviews-summary");
    head.innerHTML = `
      <strong class="product-reviews-average">${average.toFixed(1)}</strong>
      <div>
        <div class="review-stars">${starRow(average)}</div>
        <small>${reviews.length} avaliação${reviews.length === 1 ? "" : "ões"}</small>
      </div>
    `;
    box.appendChild(head);

    const list = make("ul", "product-reviews-list");
    reviews.slice(0, 6).forEach(review => {
      const item = make("li", "product-review-item");
      item.innerHTML = `
        <div class="review-stars">${starRow(review.nota)}</div>
        <strong>${review.nome}</strong>
        ${review.comentario ? `<p>${review.comentario}</p>` : ""}
      `;
      list.appendChild(item);
    });
    box.appendChild(list);
    return box;
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
    document.title = `${product.name} | Mística Presentes`;

    const bestSeller = /mais vendid/i.test(String(product.selo || ""));
    const reviews = reviewsOf(product);
    const average = reviews.length ? reviews.reduce((sum, r) => sum + r.nota, 0) / reviews.length : 0;

    const mainPhoto = images[0]
      ? `<img class="product-page-photo" id="productMainPhoto" src="${images[0]}" alt="${product.name}" loading="eager">`
      : `<div class="product-image product-page-icon" id="productMainPhoto">${product.icon || "✨"}</div>`;

    const thumbs = images.length > 1
      ? `<div class="product-page-thumbs">${images.map((src, i) => `<button type="button" class="product-page-thumb${i === 0 ? " is-active" : ""}" data-src="${src}"><img src="${src}" alt="${product.name} - foto ${i + 1}" loading="lazy"></button>`).join("")}</div>`
      : "";

    root.innerHTML = `
      <article class="product-page-card">
        <div class="product-page-media">
          ${bestSeller ? `<span class="product-badge-best">${product.selo}</span>` : ""}
          ${mainPhoto}
          ${thumbs}
        </div>
        <div class="product-page-info">
          <p class="eyebrow">${product.category || "Produto"}</p>
          <h1>${product.name}</h1>
          ${reviews.length ? `<div class="review-stars product-page-rating">${starRow(average)} <small>(${reviews.length})</small></div>` : ""}
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

    root.querySelectorAll(".product-page-thumb").forEach(btn => {
      btn.addEventListener("click", () => {
        const main = document.getElementById("productMainPhoto");
        if (main && main.tagName === "IMG") main.src = btn.dataset.src;
        root.querySelectorAll(".product-page-thumb").forEach(b => b.classList.toggle("is-active", b === btn));
      });
    });

    root.appendChild(renderTrust());
    root.appendChild(renderReviews(product));
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
  }

  function init() {
    const product = findProduct();
    if (!product) renderNotFound();
    else renderProduct(product);
  }

  window.addEventListener("load", () => setTimeout(init, 400));
})();
