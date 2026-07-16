(() => {
  const ready = (fn) => document.readyState === 'loading' ? document.addEventListener('DOMContentLoaded', fn) : fn();
  const clean = (value) => String(value ?? '');
  const safeId = (value) => clean(value).replace(/[^a-zA-Z0-9_-]/g, '');
  const productById = (productId) => products.find((item) => item.id === productId);
  const esc = (value) => clean(value).replace(/[&<>'"]/g, (char) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;' }[char]));
  const encomenda = () => window.misticaEncomenda || null;
  const isSobEncomenda = (product) => Boolean(encomenda()?.isSobEncomenda?.(product));
  // Imagem local, sempre disponível, usada sempre que o produto não tem
  // foto cadastrada OU a foto cadastrada falha ao carregar (404, CORS,
  // link quebrado etc. — ver onerror abaixo). Nunca deixamos o <img> sem
  // src válido: sem isso, o navegador mostra o alt em texto gigante
  // ocupando o card inteiro quando a imagem falha.
  const FALLBACK_IMAGE = (typeof window !== 'undefined' && window.PRODUCT_FALLBACK_IMAGE) || '/assets/images/produto-sem-imagem.webp';
  const onErrorFallback = (large) => `this.onerror=null;this.src='${FALLBACK_IMAGE}';this.classList.add('is-fallback');${large ? "this.closest('.product-inspector-gallery, .product-inspector-photo')?.classList?.add('is-fallback');" : ''}`;

  function productMedia(product, large = false) {
    // product.images é o nome real gravado por mobile-sync.js normalizarProduto();
    // "gallery" nunca existiu nesse objeto (mismatch corrigido aqui).
    const image = product.imageUrl || product.images?.[0] || '';
    const src = image ? esc(image) : FALLBACK_IMAGE;
    const cls = large ? 'product-inspector-photo' : 'product-photo';
    return `<img class="${cls}" src="${src}" alt="${esc(product.name || 'Produto Mística Presentes')}" loading="lazy" decoding="async" onerror="${onErrorFallback(large)}">`;
  }

  function galleryHtml(product) {
    const images = [product.imageUrl, ...(product.images || [])].filter(Boolean);
    const unique = [...new Set(images)];
    if (!unique.length) return '';
    return `<div class="product-inspector-gallery">${unique.map((url) => `<button type="button" data-inspector-gallery="${esc(url)}"><img src="${esc(url)}" alt="Imagem de ${esc(product.name)}" loading="lazy" decoding="async" onerror="this.onerror=null;this.src='${FALLBACK_IMAGE}';"></button>`).join('')}</div>`;
  }

  function ensureModal() {
    let modal = document.querySelector('[data-product-inspector-modal]');
    if (modal) return modal;
    modal = document.createElement('div');
    modal.className = 'product-inspector-modal';
    modal.setAttribute('data-product-inspector-modal', 'true');
    modal.hidden = true;
    modal.innerHTML = `<div class="product-inspector-backdrop" data-close-product-inspector></div><article class="product-inspector-card" role="dialog" aria-modal="true" aria-label="Detalhes do produto"><button class="product-inspector-close" type="button" data-close-product-inspector aria-label="Fechar detalhes">×</button><div data-product-inspector-content></div></article>`;
    document.body.appendChild(modal);
    modal.addEventListener('click', (event) => {
      if (event.target.closest('[data-close-product-inspector]')) closeProductInspector();
      const galleryButton = event.target.closest('[data-inspector-gallery]');
      if (galleryButton) {
        const img = modal.querySelector('[data-inspector-main-media]');
        if (img) img.innerHTML = `<img class="product-inspector-photo" src="${esc(galleryButton.dataset.inspectorGallery)}" alt="Imagem ampliada" loading="lazy">`;
      }
    });
    document.addEventListener('keydown', (event) => {
      if (event.key === 'Escape') closeProductInspector();
    });
    return modal;
  }

  window.closeProductInspector = function closeProductInspector() {
    const modal = document.querySelector('[data-product-inspector-modal]');
    if (!modal) return;
    modal.hidden = true;
    document.body.classList.remove('product-inspector-open');
  };

  window.inspectProduct = function inspectProduct(productId) {
    const product = productById(productId);
    if (!product) return;
    const available = typeof getStock === 'function' ? getStock(product.id) : Number(product.stock || 0);
    const modal = ensureModal();
    const content = modal.querySelector('[data-product-inspector-content]');
    const sob = isSobEncomenda(product);
    const brand = product.brand ? `<span>Marca: ${esc(product.brand)}</span>` : '';
    // O link do fornecedor nunca é exibido para produtos sob encomenda (uso
    // interno do administrador). Para produtos comuns, o comportamento anterior
    // é preservado.
    const external = (!sob && product.externalUrl) ? `<a class="btn btn-ghost btn-full" href="${esc(product.externalUrl)}" target="_blank" rel="noopener">Ver link do produto</a>` : '';
    const t = encomenda();
    const stockLabel = sob ? (t?.ESTOQUE_NOTE || 'Disponibilidade confirmada após o pagamento') : `Estoque: ${available}`;
    const encomendaInfo = (sob && t) ? `
          <div class="encomenda-info">
            <p class="encomenda-info-title">${esc(t.COMO_FUNCIONA_TITULO)}</p>
            <p>${esc(t.COMO_FUNCIONA_TEXTO)}</p>
            <span class="encomenda-prazo">⏳ ${esc(t.PRAZO_TEXTO)}</span>
            <p class="encomenda-aviso">${esc(t.COMO_FUNCIONA_AVISO)}</p>
          </div>` : '';
    content.innerHTML = `
      <div class="product-inspector-grid">
        <div>
          <div data-inspector-main-media>${productMedia(product, true)}</div>
          ${galleryHtml(product)}
        </div>
        <div class="product-inspector-copy">
          <p class="eyebrow">${esc(product.category || 'Produto místico')}</p>
          <h3>${esc(product.name)}</h3>
          <div class="product-inspector-meta">${brand}<span>${esc(stockLabel)}</span></div>
          <p>${esc(product.description || 'Produto selecionado pela Mística Presentes.')}</p>
          <strong class="product-inspector-price">${currency.format(Number(product.price || 0))}</strong>
          <div class="product-inspector-actions">
            <button class="btn" type="button" onclick="addToCart('${esc(product.id)}'); closeProductInspector();" ${available <= 0 ? 'disabled' : ''}>Adicionar ao carrinho</button>
            <button class="btn btn-ghost" type="button" onclick="buyProductWhatsapp('${esc(product.id)}')">WhatsApp</button>
          </div>
          ${encomendaInfo}
          ${external}
        </div>
      </div>`;
    modal.hidden = false;
    document.body.classList.add('product-inspector-open');
  };

  // Descrição fica escondida por padrão (gaveta/accordion) — só a foto,
  // categoria, nome, preço e os botões de ação aparecem de cara. O estado
  // aberto/fechado de cada card é lembrado aqui: sempre que o grid inteiro é
  // reconstruído (ex.: depois de "Adicionar ao carrinho", que chama
  // renderProducts() de novo), a gaveta que o cliente já tinha aberto
  // continua aberta — só o toggle isolado (clique em "Ver descrição") evita
  // reconstruir o grid inteiro, pra animação ficar suave e não mexer nos
  // outros cards.
  const openDrawers = (typeof window !== 'undefined' && window.openProductDrawers) || new Set();

  function renderProductsWithInspector() {
    if (!productGrid) return;
    productGrid.innerHTML = products.map((product) => {
      const available = getStock(product.id);
      const disabled = available <= 0 ? 'disabled' : '';
      const id = safeId(product.id);
      const descId = `desc-${id}`;
      const isOpen = openDrawers.has(product.id);
      const media = `<div class="product-media-wrap"><div class="product-media-frame">${productMedia(product)}</div><button class="product-zoom-button" type="button" onclick="inspectProduct('${esc(product.id)}')" aria-label="Inspecionar ${esc(product.name)}">🔍</button></div>`;
      const bestSeller = typeof isBestSeller === 'function' && isBestSeller(product) ? `<span class="product-badge-best">${esc(typeof productBadgeText === 'function' ? productBadgeText(product) : product.selo)}</span>` : '';
      const rating = typeof socialProofHtml === 'function' ? socialProofHtml(product) : '';
      const sob = isSobEncomenda(product);
      const t = encomenda();
      const encomendaBadge = sob && t ? `<span class="product-badge-encomenda">${esc(t.BADGE)}</span>` : '';
      const encomendaNote = sob && t ? `<p class="product-encomenda-note">${esc(t.CARD_NOTE)}</p>` : '';
      const stockBadge = sob && t
        ? `<span class="stock-badge">${esc(t.ESTOQUE_NOTE)}</span>`
        : `<span class="stock-badge ${available <= storeConfig.minStock ? 'stock-low' : ''}">Estoque: ${available}</span>`;
      const descriptionText = product.description || 'Produto selecionado pela Mística Presentes.';
      const drawer = `<button class="product-desc-toggle" type="button" aria-expanded="${isOpen}" aria-controls="${descId}" onclick="toggleProductDescription('${esc(product.id)}')"><span>Ver descrição</span><svg class="product-desc-chevron" viewBox="0 0 20 20" aria-hidden="true"><path d="M5 7l5 5 5-5" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg></button><div class="product-desc-drawer${isOpen ? ' is-open' : ''}" id="${descId}"><div class="product-desc-drawer-inner"><p>${esc(descriptionText)}</p>${encomendaNote}</div></div>`;
      return `<article class="product-card" data-category="${esc(product.category || '')}" data-best-seller="${typeof isBestSeller === 'function' ? isBestSeller(product) : false}">${bestSeller}${encomendaBadge}${media}<div class="product-card-body"><p class="eyebrow">${esc(product.category)}</p><h3>${esc(product.name)}</h3>${rating}<strong class="product-price">${currency.format(product.price)}</strong>${stockBadge}<div class="qty-row"><input id="qty-${id}" type="number" min="1" max="${available}" step="1" value="1" aria-label="Quantidade de ${esc(product.name)}" ${disabled} /><button class="btn" type="button" onclick="addToCart('${esc(product.id)}')" ${disabled}>Adicionar</button></div><button class="btn btn-ghost btn-full" type="button" onclick="buyProductWhatsapp('${esc(product.id)}')">Comprar pelo WhatsApp</button>${drawer}</div></article>`;
    }).join('');
  }

  ready(() => {
    if (typeof renderProducts === 'function') {
      window.renderProductsOriginal = renderProducts;
      renderProducts = renderProductsWithInspector;
      renderProducts();
    }
  });
})();
