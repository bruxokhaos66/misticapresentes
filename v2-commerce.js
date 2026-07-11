(() => {
  if (window.__MISTICA_V2_COMMERCE__) return;
  window.__MISTICA_V2_COMMERCE__ = true;

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

  function currentCategories() {
    if (typeof products === 'undefined' || !Array.isArray(products)) return [];
    return [...new Set(products.map(product => product.category).filter(Boolean))].sort((a, b) => a.localeCompare(b, 'pt-BR'));
  }

  function createToolbar() {
    const section = document.querySelector('#produtos');
    const grid = document.querySelector('[data-product-grid]');
    if (!section || !grid) return;

    let toolbar = section.querySelector('.v2-product-toolbar');
    if (toolbar) {
      syncCategoryOptions(toolbar);
      return;
    }

    toolbar = document.createElement('div');
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

    const categoryWrap = document.createElement('label');
    categoryWrap.className = 'v2-category-label';
    categoryWrap.textContent = 'Categoria';
    const categorySelect = document.createElement('select');
    categorySelect.setAttribute('aria-label', 'Filtrar por categoria');
    categorySelect.dataset.v2CategoryFilter = 'true';
    categoryWrap.appendChild(categorySelect);

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

    const count = document.createElement('p');
    count.className = 'v2-product-count';
    count.setAttribute('aria-live', 'polite');

    toolbar.append(searchWrap, categoryWrap, chips, count);
    grid.before(toolbar);
    syncCategoryOptions(toolbar);

    function applyFilter() {
      const query = normalize(input.value);
      const active = chips.querySelector('.v2-chip.active')?.dataset.filter || '';
      const tokens = normalize(active).split(/\s+/).filter(Boolean);
      const categoria = categorySelect.value;
      let visible = 0;

      productCards().forEach(card => {
        const text = normalize(card.textContent);
        const matchesQuery = !query || text.includes(query);
        const matchesChip = !tokens.length || tokens.some(token => text.includes(token));
        const matchesCategory = !categoria || card.querySelector('.eyebrow')?.textContent === categoria;
        const show = matchesQuery && matchesChip && matchesCategory;
        card.hidden = !show;
        if (show) visible += 1;
      });

      count.textContent = visible === 1 ? '1 produto encontrado' : `${visible} produtos encontrados`;
    }

    input.addEventListener('input', applyFilter);
    categorySelect.addEventListener('change', applyFilter);
    chips.addEventListener('click', event => {
      const button = event.target.closest('.v2-chip');
      if (!button) return;
      chips.querySelectorAll('.v2-chip').forEach(chip => chip.classList.remove('active'));
      button.classList.add('active');
      applyFilter();
    });

    toolbar.__misticaApplyFilter = applyFilter;

    const observer = new MutationObserver(() => {
      syncCategoryOptions(toolbar);
      applyFilter();
    });
    observer.observe(grid, { childList: true });

    applyFilter();
  }

  function syncCategoryOptions(toolbar) {
    const select = toolbar.querySelector('[data-v2-category-filter]');
    if (!select) return;
    const atual = select.value;
    const categorias = currentCategories();
    select.innerHTML = `<option value="">Todas as categorias</option>${categorias.map(categoria => `<option value="${categoria}">${categoria}</option>`).join('')}`;
    if (categorias.includes(atual)) select.value = atual;
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

  function appendIsisMessage(role, text) {
    const chat = document.querySelector('#isisChat');
    if (!chat) return;
    const box = document.createElement('div');
    box.className = `isis-message ${role}`;
    box.textContent = text;
    chat.appendChild(box);
    chat.scrollTop = chat.scrollHeight;
  }

  function setupIsisQuickActions() {
    document.querySelectorAll('[data-isis-command]').forEach(button => {
      if (button.dataset.v2Ready) return;
      button.dataset.v2Ready = 'true';
      button.addEventListener('click', () => {
        const command = button.dataset.isisCommand || button.textContent;
        appendIsisMessage('user', command);
        appendIsisMessage('bot', 'A Isis pode ajudar a escolher produtos por intenção. Use o catálogo, filtre os produtos e finalize pelo WhatsApp para atendimento humano.');
        document.querySelector('#produtos')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
      });
    });
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
    setupIsisQuickActions();
    improveCartAnchor();
  }

  function schedule() {
    apply();
    window.setTimeout(apply, 250);
    window.setTimeout(apply, 900);
    window.setTimeout(apply, 1600);
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', schedule, { once: true });
  else schedule();
})();
