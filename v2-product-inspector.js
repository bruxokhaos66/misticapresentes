(() => {
  const categoryRules = [
    { match: /incenso|aroma|ess[eê]ncia|via aroma|perfume/i, icon: '🌿', tone: 'aromas', label: 'Aromas' },
    { match: /cristal|pedra|quartzo|ametista|energia/i, icon: '💎', tone: 'cristais', label: 'Cristais' },
    { match: /vela|luz|chama|ritual/i, icon: '🕯️', tone: 'velas', label: 'Velas' },
    { match: /banho|erva|limpeza|defuma/i, icon: '🍃', tone: 'ervas', label: 'Ervas' },
    { match: /kit|presente|combo/i, icon: '🎁', tone: 'kits', label: 'Kits' },
    { match: /f[eé]|prote[cç][aã]o|guia|santo|or[aã][cç][aã]o/i, icon: '🙏', tone: 'fe', label: 'Fé' },
  ];

  const ready = (fn) => document.readyState === 'loading' ? document.addEventListener('DOMContentLoaded', fn) : fn();
  const clean = (value) => String(value ?? '');
  const safeId = (value) => clean(value).replace(/[^a-zA-Z0-9_-]/g, '');
  const productById = (productId) => products.find((item) => item.id === productId);
  const esc = (value) => clean(value).replace(/[&<>'"]/g, (char) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;' }[char]));
  const encomenda = () => window.misticaEncomenda || null;
  const isSobEncomenda = (product) => Boolean(encomenda()?.isSobEncomenda?.(product));

  function categoryInfo(product) {
    const source = `${product.category || ''} ${product.name || ''} ${product.description || ''}`;
    return categoryRules.find((rule) => rule.match.test(source)) || { icon: product.icon || '✨', tone: 'mistico', label: product.category || 'Mística' };
  }

  function productMedia(product, large = false) {
    const info = categoryInfo(product);
    const image = product.imageUrl || product.gallery?.[0] || '';
    if (image) {
      return `<img class="${large ? 'product-inspector-photo' : 'product-photo'}" src="${esc(image)}" alt="${esc(product.name)}" loading="lazy">`;
    }
    return `<div class="${large ? 'product-inspector-category-image' : 'product-category-image'} category-${info.tone}" role="img" aria-label="Imagem da categoria ${esc(info.label)}"><span>${info.icon}</span><strong>${esc(info.label)}</strong></div>`;
  }

  function galleryHtml(product) {
    const images = [product.imageUrl, ...(product.gallery || [])].filter(Boolean);
    const unique = [...new Set(images)];
    if (!unique.length) return '';
    return `<div class="product-inspector-gallery">${unique.map((url) => `<button type="button" data-inspector-gallery="${esc(url)}"><img src="${esc(url)}" alt="Imagem de ${esc(product.name)}" loading="lazy"></button>`).join('')}</div>`;
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
            <button class="btn" type="button" data-action-add="${esc(product.id)}" ${available <= 0 ? 'disabled' : ''}>Adicionar ao carrinho</button>
            <button class="btn btn-ghost" type="button" data-action-whatsapp="${esc(product.id)}">WhatsApp</button>
          </div>
          ${encomendaInfo}
          ${external}
        </div>
      </div>`;
    modal.hidden = false;
    document.body.classList.add('product-inspector-open');
  };

  function renderProductsWithInspector() {
    if (!productGrid) return;
    productGrid.innerHTML = products.map((product) => {
      const available = getStock(product.id);
      const disabled = available <= 0 ? 'disabled' : '';
      const media = `<div class="product-media-wrap">${productMedia(product)}<button class="product-zoom-button" type="button" data-action-inspect="${esc(product.id)}" aria-label="Inspecionar ${esc(product.name)}">🔍</button></div>`;
      const bestSeller = typeof isBestSeller === 'function' && isBestSeller(product) ? `<span class="product-badge-best">${esc(typeof productBadgeText === 'function' ? productBadgeText(product) : product.selo)}</span>` : '';
      const rating = typeof socialProofHtml === 'function' ? socialProofHtml(product) : '';
      const sob = isSobEncomenda(product);
      const t = encomenda();
      const encomendaBadge = sob && t ? `<span class="product-badge-encomenda">${esc(t.BADGE)}</span>` : '';
      const encomendaNote = sob && t ? `<p class="product-encomenda-note">${esc(t.CARD_NOTE)}</p>` : '';
      const stockBadge = sob && t
        ? `<span class="stock-badge">${esc(t.ESTOQUE_NOTE)}</span>`
        : `<span class="stock-badge ${available <= storeConfig.minStock ? 'stock-low' : ''}">Estoque: ${available}</span>`;
      return `<article class="product-card" data-category="${esc(product.category || '')}" data-best-seller="${typeof isBestSeller === 'function' ? isBestSeller(product) : false}">${bestSeller}${encomendaBadge}${media}<div><p class="eyebrow">${esc(product.category)}</p><h3>${esc(product.name)}</h3>${rating}<p>${esc(product.description)}</p>${encomendaNote}</div><strong class="product-price">${currency.format(product.price)}</strong>${stockBadge}<div class="qty-row"><input id="qty-${safeId(product.id)}" type="number" min="1" max="${available}" step="1" value="1" aria-label="Quantidade de ${esc(product.name)}" ${disabled} /><button class="btn" type="button" data-action-add="${esc(product.id)}" ${disabled}>Adicionar</button></div><button class="btn btn-ghost btn-full" type="button" data-action-whatsapp="${esc(product.id)}">Comprar pelo WhatsApp</button></article>`;
    }).join('');
  }

  ready(() => {
    if (typeof renderProducts === 'function') {
      window.renderProductsOriginal = renderProducts;
      renderProducts = renderProductsWithInspector;
      renderProducts();
    }
    // Delegação de eventos para ações do inspetor e cards. Complementa
    // a delegação global de app.js (data-action-add / data-action-whatsapp).
    document.addEventListener('click', (event) => {
      const inspectBtn = event.target.closest('[data-action-inspect]');
      if (inspectBtn) inspectProduct(inspectBtn.dataset.actionInspect);
    });
    // O botão "Adicionar" dentro do modal do inspetor fecha o modal após adicionar.
    document.addEventListener('click', (event) => {
      const addBtn = event.target.closest('.product-inspector-actions [data-action-add]');
      if (addBtn) closeProductInspector();
    }, true);
  });
})();
