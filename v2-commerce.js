(() => {
  if (window.__MISTICA_V2_COMMERCE__) return;
  window.__MISTICA_V2_COMMERCE__ = true;

  const esc = (value) => (window.MisticaXSS || {}).html ? MisticaXSS.html(value) : String(value == null ? "" : value).replace(/[&<>"']/g, (ch) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[ch]));

  const intents = [
    { label: 'Todos', value: '' },
    { label: 'Proteção', value: 'proteção' },
    { label: 'Incensos', value: 'incenso' },
    { label: 'Cristais', value: 'cristal pedra' },
    { label: 'Velas', value: 'vela fé luz' },
    { label: 'Aromas', value: 'aroma essência difusor' },
    { label: 'Presentes', value: 'presente kit' }
  ];

  function normalize(value) {
    return String(value || '').normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase();
  }

  function productCards() {
    return Array.from(document.querySelectorAll('[data-product-grid] .product-card'));
  }

  function realCategories() {
    if (typeof products === 'undefined') return [];
    const seen = new Set();
    products.forEach(product => { if (product.category) seen.add(product.category); });
    return Array.from(seen).sort((a, b) => a.localeCompare(b, 'pt-BR'));
  }

  function createToolbar() {
    const section = document.querySelector('#produtos');
    const grid = document.querySelector('[data-product-grid]');
    if (!section || !grid || section.querySelector('.v2-product-toolbar')) return;

    const toolbar = document.createElement('div');
    toolbar.className = 'container v2-product-toolbar';

    const searchWrap = document.createElement('label');
    searchWrap.className = 'v2-search-label';
    searchWrap.textContent = 'Buscar por produto ou intenção';

    const input = document.createElement('input');
    input.type = 'search';
    input.placeholder = 'Ex.: proteção, incenso, presente, vela, cristal';
    input.setAttribute('aria-label', 'Buscar produtos');
    input.dataset.v2ProductSearch = 'true';
    searchWrap.appendChild(input);

    const chips = document.createElement('div');
    chips.className = 'v2-filter-chips';
    intents.forEach((intent, index) => {
      const button = document.createElement('button');
      button.type = 'button';
      button.className = 'v2-chip';
      if (index === 0) button.classList.add('active');
      button.textContent = intent.label;
      button.dataset.filter = intent.value;
      chips.appendChild(button);
    });

    const categoryLabel = document.createElement('p');
    categoryLabel.className = 'v2-category-label';
    categoryLabel.textContent = 'Categorias';

    const categoryChips = document.createElement('div');
    categoryChips.className = 'v2-filter-chips v2-category-chips';
    categoryChips.dataset.categorySignature = '';

    const bestSellerToggle = document.createElement('button');
    bestSellerToggle.type = 'button';
    bestSellerToggle.className = 'v2-chip v2-best-toggle';
    bestSellerToggle.textContent = '🔥 Mais vendidos';

    const count = document.createElement('p');
    count.className = 'v2-product-count';
    count.setAttribute('aria-live', 'polite');

    toolbar.append(searchWrap, chips, categoryLabel, categoryChips, bestSellerToggle, count);
    grid.before(toolbar);

    function applyFilter() {
      const query = normalize(input.value);
      const active = chips.querySelector('.v2-chip.active')?.dataset.filter || '';
      const tokens = normalize(active).split(/\s+/).filter(Boolean);
      const activeCategory = categoryChips.querySelector('.v2-chip.active')?.dataset.category || '';
      const bestOnly = bestSellerToggle.classList.contains('active');
      let visible = 0;

      productCards().forEach(card => {
        const text = normalize(card.textContent);
        const matchesQuery = !query || text.includes(query);
        const matchesChip = !tokens.length || tokens.some(token => text.includes(token));
        const matchesCategory = !activeCategory || card.dataset.category === activeCategory;
        const matchesBest = !bestOnly || card.dataset.bestSeller === 'true';
        const show = matchesQuery && matchesChip && matchesCategory && matchesBest;
        card.hidden = !show;
        if (show) visible += 1;
      });

      count.textContent = visible === 1 ? '1 produto encontrado' : `${visible} produtos encontrados`;
    }

    function rebuildCategoryChips() {
      const categories = realCategories();
      const signature = categories.join('|');
      if (categoryChips.dataset.categorySignature === signature) return;
      categoryChips.dataset.categorySignature = signature;

      const previousActive = categoryChips.querySelector('.v2-chip.active')?.dataset.category || '';
      categoryChips.innerHTML = '';

      const allButton = document.createElement('button');
      allButton.type = 'button';
      allButton.className = 'v2-chip';
      allButton.textContent = 'Todas as categorias';
      allButton.dataset.category = '';
      categoryChips.appendChild(allButton);

      categories.forEach(category => {
        const button = document.createElement('button');
        button.type = 'button';
        button.className = 'v2-chip';
        button.textContent = category;
        button.dataset.category = category;
        categoryChips.appendChild(button);
      });

      const stillExists = categories.includes(previousActive);
      const toActivate = categoryChips.querySelector(`.v2-chip[data-category="${stillExists ? previousActive : ''}"]`);
      categoryChips.querySelectorAll('.v2-chip').forEach(chip => chip.classList.remove('active'));
      (toActivate || allButton).classList.add('active');
    }

    input.addEventListener('input', applyFilter);
    chips.addEventListener('click', event => {
      const button = event.target.closest('.v2-chip');
      if (!button) return;
      chips.querySelectorAll('.v2-chip').forEach(chip => chip.classList.remove('active'));
      button.classList.add('active');
      applyFilter();
    });
    categoryChips.addEventListener('click', event => {
      const button = event.target.closest('.v2-chip');
      if (!button) return;
      categoryChips.querySelectorAll('.v2-chip').forEach(chip => chip.classList.remove('active'));
      button.classList.add('active');
      applyFilter();
    });
    bestSellerToggle.addEventListener('click', () => {
      bestSellerToggle.classList.toggle('active');
      applyFilter();
    });

    rebuildCategoryChips();
    applyFilter();
    toolbar.__misticaRebuildCategories = () => { rebuildCategoryChips(); applyFilter(); };
  }

  function renderBestSellerStrip() {
    const section = document.querySelector('#produtos');
    if (!section || typeof products === 'undefined' || typeof isBestSeller !== 'function') return;

    const bestSellers = products.filter(isBestSeller);
    const signature = bestSellers.map(p => p.id).join('|');
    let strip = section.querySelector('.v2-bestseller-strip');

    if (!bestSellers.length) {
      strip?.remove();
      return;
    }

    if (strip && strip.dataset.signature === signature) return;
    if (!strip) {
      strip = document.createElement('div');
      strip.className = 'container v2-bestseller-strip';
      const grid = section.querySelector('[data-product-grid]');
      const toolbar = section.querySelector('.v2-product-toolbar');
      (toolbar || grid)?.before(strip);
    }
    strip.dataset.signature = signature;
    strip.innerHTML = `
      <p class="eyebrow">Mais vendidos</p>
      <div class="v2-bestseller-cards">
        ${bestSellers.slice(0, 6).map(product => `
          <a class="v2-bestseller-card" href="produto.html?id=${encodeURIComponent(product.id)}">
            <span>${esc(product.icon || '✨')}</span>
            <strong>${esc(product.name)}</strong>
            <small>${currency.format(Number(product.price || 0))}</small>
          </a>
        `).join('')}
      </div>
    `;
  }

  function protectHeroIsisImage() {
    const target = document.querySelector('.isis-photo');
    if (!target) return;

    // A imagem do topo agora vem do CSS em assets/isis-hero.webp.
    // Não copiamos mais a imagem inferior para o topo, pois isso deixava a hero borrada.
    target.style.removeProperty('background-image');
    target.style.removeProperty('background');
    target.classList.remove('has-real-isis');
  }

  function improveCartAnchor() {
    const checkout = document.querySelector('#checkout');
    if (!checkout || checkout.querySelector('.v2-checkout-note')) return;
    const note = document.createElement('p');
    note.className = 'v2-checkout-note';
    note.textContent = 'Finalize com segurança: revise os itens, gere o Pix ou envie o pedido pelo WhatsApp para confirmar disponibilidade.';
    checkout.querySelector('.section-title')?.appendChild(note);
  }

  function apply() {
    protectHeroIsisImage();
    createToolbar();
    renderBestSellerStrip();
    improveCartAnchor();
    document.querySelector('.v2-product-toolbar')?.__misticaRebuildCategories?.();
  }

  function schedule() {
    apply();
    window.setTimeout(apply, 250);
    window.setTimeout(apply, 900);
    window.setTimeout(apply, 1600);
    window.setInterval(() => {
      document.querySelector('.v2-product-toolbar')?.__misticaRebuildCategories?.();
      renderBestSellerStrip();
    }, 5000);
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', schedule, { once: true });
  else schedule();
})();
