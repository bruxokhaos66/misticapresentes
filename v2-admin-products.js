(() => {
  // Fonte única da URL da API: site-config.js (window.misticaSiteConfig).
  const API_BASE = String(
    (window.misticaSiteConfig || {}).apiBaseUrl || 'https://api.misticaesotericos.com.br'
  ).replace(/\/$/, '');
  const ready = (fn) => document.readyState === 'loading' ? document.addEventListener('DOMContentLoaded', fn) : fn();
  const money = new Intl.NumberFormat('pt-BR', { style: 'currency', currency: 'BRL' });

  const esc = (value) => String(value ?? '').replace(/[&<>"']/g, (ch) => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
  }[ch]));
  const toNumber = (value) => Number(String(value || '0').replace(',', '.')) || 0;
  const normalizar = (value) => String(value == null ? '' : value)
    .normalize('NFD').replace(/[̀-ͯ]/g, '').trim().toLowerCase().replace(/\s+/g, ' ');
  const ehSobEncomenda = (categoria, selo) =>
    normalizar(categoria) === 'achados misticos' || normalizar(selo) === 'sob encomenda';
  const PRAZO_ENCOMENDA = (window.misticaEncomenda && window.misticaEncomenda.PRAZO_TEXTO)
    || 'Prazo estimado de preparação: até 10 dias úteis, além do prazo de transporte.';
  const toInt = (value) => Math.max(0, Number.parseInt(String(value || '0'), 10) || 0);
  const normalizeUrl = (url) => {
    const value = String(url || '').trim();
    if (!value) return '';
    if (value.startsWith('http')) return value;
    if (value.startsWith('/')) return `${API_BASE}${value}`;
    return value;
  };
  const slug = (value) => String(value || 'produto')
    .normalize('NFD').replace(/[\u0300-\u036f]/g, '')
    .toLowerCase().replace(/[^a-z0-9]+/g, '-')
    .replace(/^-|-$/g, '') || 'produto';

  const mapApiProduct = (item) => ({
    id: `api-${item.id}`,
    apiId: item.id,
    name: item.nome,
    brand: item.marca || '',
    category: item.categoria || 'Produtos místicos',
    description: item.descricao || 'Produto cadastrado no Admin da Mística Presentes.',
    price: Number(item.preco || 0),
    stock: Number(item.quantidade || 0),
    icon: item.selo || '✨',
    imageUrl: normalizeUrl(item.imagem_url || item.imagens?.[0] || ''),
    gallery: (item.imagens || []).map(normalizeUrl),
    externalUrl: item.link_externo || '',
    apiProduct: item,
  });

  const applyCatalogToUi = (apiItems) => {
    if (!Array.isArray(apiItems) || typeof products === 'undefined') return;
    const fixed = products.filter((item) => !String(item.id || '').startsWith('api-'));
    const mapped = apiItems.map(mapApiProduct);
    products.splice(0, products.length, ...fixed, ...mapped);
    mapped.forEach((item) => {
      if (typeof stock !== 'undefined') stock[item.id] = item.stock;
    });
    if (typeof saveState === 'function') saveState();
    if (typeof renderAll === 'function') renderAll();
  };

  // A resposta de /api/produtos/admin é privada (pode incluir custo/margem);
  // fica só em memória (currentProducts, abaixo) e nunca em localStorage.
  const syncCatalogWithApi = (apiItems) => {
    applyCatalogToUi(apiItems);
  };

  const loadApiProductsPublic = async () => {
    const response = await fetch(`${API_BASE}/api/produtos/admin?limite=500`, { credentials: 'include' });
    if (!response.ok) throw new Error('Não foi possível carregar produtos da API.');
    const data = await response.json();
    syncCatalogWithApi(data);
    return data;
  };

  ready(() => {
    const adminContent = document.getElementById('adminContent');
    if (!adminContent) return;

    let editingId = null;
    let currentProducts = [];

    const panel = document.createElement('section');
    panel.className = 'form-panel admin-products-panel';
    panel.innerHTML = `
      <p class="eyebrow">Produtos para venda</p>
      <h2>Cadastro comercial de produtos</h2>
      <p class="privacy-note">Cadastre itens por categoria, com nome, marca, descrição, preço, estoque e imagens. Os produtos salvos na API aparecem no catálogo da loja.</p>

      <div class="checkout-actions">
        <button class="btn" type="button" data-refresh-products>Atualizar lista</button>
      </div>
      <div class="warning-box" data-product-admin-status>Carregando produtos cadastrados...</div>

      <form id="adminProductForm" class="admin-product-form">
        <input type="hidden" id="adminProductId">
        <div class="admin-product-grid">
          <label>Código interno / SKU
            <input id="adminProductCode" type="text" placeholder="Ex.: INC-001">
          </label>
          <label>Nome do produto
            <input id="adminProductName" type="text" placeholder="Ex.: Incenso natural de arruda" required>
          </label>
          <label>Marca
            <input id="adminProductBrand" type="text" placeholder="Ex.: Via Aroma, Hem, Mística">
          </label>
          <label>Categoria
            <input id="adminProductCategory" type="text" list="adminProductCategories" placeholder="Ex.: Incensos, Cristais, Velas" required>
            <datalist id="adminProductCategories">
              <option value="Incensos"></option>
              <option value="Cristais e pedras"></option>
              <option value="Velas"></option>
              <option value="Aromas e essências"></option>
              <option value="Banhos de ervas"></option>
              <option value="Presentes e kits"></option>
              <option value="Artigos de fé"></option>
            </datalist>
          </label>
          <label>Preço de venda
            <input id="adminProductPrice" type="number" min="0" step="0.01" placeholder="0,00" required>
          </label>
          <label>Custo
            <input id="adminProductCost" type="number" min="0" step="0.01" placeholder="0,00">
          </label>
          <label>Estoque
            <input id="adminProductStock" type="number" min="0" step="1" value="0" required>
          </label>
          <label>Estoque mínimo
            <input id="adminProductMinStock" type="number" min="0" step="1" value="3">
          </label>
          <label>Selo / ícone
            <input id="adminProductBadge" type="text" placeholder="Ex.: Novo, Promoção, ✨">
          </label>
          <label>Link externo opcional
            <input id="adminProductExternal" type="url" placeholder="https://...">
          </label>
        </div>
        <label>Descrição comercial do produto
          <textarea id="adminProductDescription" rows="4" placeholder="Descreva intenção, uso, aroma, material, benefício e sugestão de presente."></textarea>
        </label>
        <label>Imagem principal por link
          <input id="adminProductImageUrl" type="url" placeholder="https://... ou use upload abaixo">
        </label>
        <label>Upload de imagem principal
          <input id="adminProductImageFile" type="file" accept="image/jpeg,image/png,image/webp">
        </label>
        <label>Galeria de imagens por link, uma por linha
          <textarea id="adminProductGallery" rows="3" placeholder="https://imagem-1.webp\nhttps://imagem-2.webp"></textarea>
        </label>
        <div class="checkout-actions">
          <button class="btn" type="submit" data-save-product>Salvar produto</button>
          <button class="btn btn-ghost" type="button" data-new-product>Novo produto</button>
        </div>
      </form>

      <div class="admin-product-list" data-admin-product-list></div>
    `;

    const audioPanel = adminContent.querySelector('.audio-admin-panel');
    adminContent.insertBefore(panel, audioPanel || adminContent.firstChild);

    const status = panel.querySelector('[data-product-admin-status]');
    const list = panel.querySelector('[data-admin-product-list]');
    const form = panel.querySelector('#adminProductForm');
    const imageFile = panel.querySelector('#adminProductImageFile');

    // Destaque de "produto sob encomenda" no painel: quando a categoria for
    // Achados Místicos ou o selo for Sob encomenda, evidencia os campos internos
    // (link do fornecedor, custo, preço, margem, estoque nominal, prazo). Não
    // cria campos novos: usa os já existentes no formulário.
    const categoryInput = panel.querySelector('#adminProductCategory');
    const badgeInput = panel.querySelector('#adminProductBadge');
    const priceInput = panel.querySelector('#adminProductPrice');
    const costInput = panel.querySelector('#adminProductCost');
    const encomendaNote = document.createElement('div');
    encomendaNote.className = 'admin-encomenda-note';
    encomendaNote.hidden = true;
    form.insertBefore(encomendaNote, form.querySelector('.checkout-actions'));

    const refreshEncomendaHint = () => {
      const sob = ehSobEncomenda(categoryInput.value, badgeInput.value);
      form.classList.toggle('is-encomenda', sob);
      encomendaNote.hidden = !sob;
      if (!sob) return;
      const preco = toNumber(priceInput.value);
      const custo = toNumber(costInput.value);
      const margem = preco - custo;
      const margemPct = preco > 0 ? Math.round((margem / preco) * 100) : 0;
      encomendaNote.innerHTML = `
        <strong>✦ Produto sob encomenda (Achados Místicos)</strong>
        <span>Link do fornecedor, custo e estoque nominal ficam visíveis só aqui no painel — nunca aparecem para o cliente.</span>
        <span>Margem estimada: ${esc(money.format(margem))} (${margemPct}%).</span>
        <span>${esc(PRAZO_ENCOMENDA)}</span>`;
    };
    [categoryInput, badgeInput, priceInput, costInput].forEach((el) => {
      if (el) el.addEventListener('input', refreshEncomendaHint);
    });

    const setStatus = (message, ok = false) => {
      status.textContent = message;
      status.className = ok ? 'warning-box' : 'warning-box warning-danger';
    };

    const clearForm = () => {
      editingId = null;
      form.reset();
      panel.querySelector('#adminProductId').value = '';
      panel.querySelector('#adminProductMinStock').value = '3';
      panel.querySelector('#adminProductStock').value = '0';
      panel.querySelector('[data-save-product]').textContent = 'Salvar produto';
      refreshEncomendaHint();
    };

    const readFormPayload = () => ({
      codigo_p: panel.querySelector('#adminProductCode').value.trim() || null,
      nome: panel.querySelector('#adminProductName').value.trim(),
      marca: panel.querySelector('#adminProductBrand').value.trim() || null,
      categoria: panel.querySelector('#adminProductCategory').value.trim() || null,
      preco: toNumber(panel.querySelector('#adminProductPrice').value),
      custo: toNumber(panel.querySelector('#adminProductCost').value),
      quantidade: toInt(panel.querySelector('#adminProductStock').value),
      estoque_minimo: toInt(panel.querySelector('#adminProductMinStock').value),
      selo: panel.querySelector('#adminProductBadge').value.trim() || null,
      link_externo: panel.querySelector('#adminProductExternal').value.trim() || null,
      descricao: panel.querySelector('#adminProductDescription').value.trim() || null,
      imagem_url: panel.querySelector('#adminProductImageUrl').value.trim() || null,
      imagens: panel.querySelector('#adminProductGallery').value.split('\n').map((line) => line.trim()).filter(Boolean),
    });

    const uploadImageIfNeeded = async (payload) => {
      const file = imageFile.files?.[0];
      if (!file) return payload;
      const fd = new FormData();
      fd.append('arquivo', file);
      const produtoId = payload.codigo_p || slug(payload.nome);
      const response = await fetch(`${API_BASE}/api/uploads/produtos?produto_id=${encodeURIComponent(produtoId)}`, {
        method: 'POST',
        credentials: 'include',
        body: fd,
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok || !data.ok) throw new Error(data.detail || 'Falha no upload da imagem.');
      const url = normalizeUrl(data.url);
      payload.imagem_url = url;
      if (!payload.imagens.includes(url)) payload.imagens.unshift(url);
      return payload;
    };

    const renderList = () => {
      if (!currentProducts.length) {
        list.innerHTML = '<div class="history-item"><span>Nenhum produto cadastrado na API ainda.</span></div>';
        return;
      }
      list.innerHTML = currentProducts.map((product) => {
        const img = normalizeUrl(product.imagem_url || product.imagens?.[0] || '');
        return `
          <article class="admin-product-item">
            ${img ? `<img src="${esc(img)}" alt="${esc(product.nome)}" loading="lazy">` : '<div class="admin-product-thumb">✨</div>'}
            <div>
              <strong>${esc(product.nome)}</strong>
              <span>${esc(product.marca || 'Sem marca')} • ${esc(product.categoria || 'Sem categoria')}</span>
              <span>${money.format(Number(product.preco || 0))} • Estoque: ${Number(product.quantidade || 0)}</span>
              <small>${esc(product.descricao || 'Sem descrição.')}</small>
            </div>
            <div class="admin-product-actions">
              <button class="btn btn-ghost" type="button" data-edit-product="${product.id}">Editar</button>
              <button class="btn btn-ghost" type="button" data-delete-product="${product.id}">Excluir</button>
            </div>
          </article>
        `;
      }).join('');
    };

    const loadProducts = async () => {
      try {
        currentProducts = await loadApiProductsPublic();
        renderList();
        setStatus(`Produtos atualizados: ${currentProducts.length} item(ns).`, true);
      } catch (error) {
        // Sem cache local: a resposta privada da API nunca é persistida no
        // navegador. Em caso de falha, o operador só pode tentar novamente.
        setStatus(error.message || 'Falha ao carregar produtos.');
      }
    };

    const editProduct = (id) => {
      const product = currentProducts.find((item) => String(item.id) === String(id));
      if (!product) return;
      editingId = product.id;
      panel.querySelector('#adminProductId').value = product.id;
      panel.querySelector('#adminProductCode').value = product.codigo_p || '';
      panel.querySelector('#adminProductName').value = product.nome || '';
      panel.querySelector('#adminProductBrand').value = product.marca || '';
      panel.querySelector('#adminProductCategory').value = product.categoria || '';
      panel.querySelector('#adminProductPrice').value = product.preco || 0;
      panel.querySelector('#adminProductCost').value = product.custo || 0;
      panel.querySelector('#adminProductStock').value = product.quantidade || 0;
      panel.querySelector('#adminProductMinStock').value = product.estoque_minimo || 0;
      panel.querySelector('#adminProductBadge').value = product.selo || '';
      panel.querySelector('#adminProductExternal').value = product.link_externo || '';
      panel.querySelector('#adminProductDescription').value = product.descricao || '';
      panel.querySelector('#adminProductImageUrl').value = normalizeUrl(product.imagem_url || '');
      panel.querySelector('#adminProductGallery').value = (product.imagens || []).map(normalizeUrl).join('\n');
      panel.querySelector('[data-save-product]').textContent = 'Atualizar produto';
      refreshEncomendaHint();
      panel.scrollIntoView({ behavior: 'smooth', block: 'start' });
    };

    const deleteProduct = async (id) => {
      const product = currentProducts.find((item) => String(item.id) === String(id));
      if (!product) return;
      if (!confirm(`Excluir ${product.nome} do catálogo?`)) return;
      const response = await fetch(`${API_BASE}/api/produtos/${id}`, {
        method: 'DELETE',
        credentials: 'include',
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok || !data.ok) throw new Error(data.detail || 'Falha ao excluir produto.');
      await loadProducts();
      setStatus('Produto excluído do catálogo.', true);
    };

    form.addEventListener('submit', async (event) => {
      event.preventDefault();
      const saveButton = panel.querySelector('[data-save-product]');
      if (saveButton.disabled) return;
      const basePayload = readFormPayload();
      if (!basePayload.nome) return setStatus('Informe o nome do produto.');
      saveButton.disabled = true;
      setStatus('Salvando produto na API...', true);
      try {
        const payload = await uploadImageIfNeeded(basePayload);
        const url = editingId ? `${API_BASE}/api/produtos/${editingId}` : `${API_BASE}/api/produtos`;
        const method = editingId ? 'PUT' : 'POST';
        const response = await fetch(url, {
          method,
          credentials: 'include',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload),
        });
        const data = await response.json().catch(() => ({}));
        if (!response.ok || !data.ok) throw new Error(data.detail || 'Falha ao salvar produto.');
        clearForm();
        await loadProducts();
        setStatus('Produto salvo e catálogo atualizado.', true);
      } catch (error) {
        setStatus(error.message || 'Erro ao salvar produto.');
      } finally {
        saveButton.disabled = false;
      }
    });

    panel.querySelector('[data-refresh-products]').addEventListener('click', loadProducts);
    panel.querySelector('[data-new-product]').addEventListener('click', clearForm);
    list.addEventListener('click', async (event) => {
      const editButton = event.target.closest('[data-edit-product]');
      const deleteButton = event.target.closest('[data-delete-product]');
      if (editButton) editProduct(editButton.dataset.editProduct);
      if (deleteButton) {
        try { await deleteProduct(deleteButton.dataset.deleteProduct); }
        catch (error) { setStatus(error.message || 'Erro ao excluir produto.'); }
      }
    });

    loadProducts();
  });
})();
