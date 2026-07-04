const CUSTOM_PRODUCTS_KEY = "misticaCustomProducts";
let customProducts = loadStorage(CUSTOM_PRODUCTS_KEY, []);

function parseMoney(value) {
  const normalized = String(value || "").replace(/\./g, "").replace(",", ".");
  const number = Number(normalized);
  return Number.isFinite(number) && number >= 0 ? number : 0;
}

function parseImages(value) {
  return String(value || "")
    .split("\n")
    .map(item => item.trim())
    .filter(item => item.startsWith("http://") || item.startsWith("https://"))
    .slice(0, 8);
}

function safeUrl(value) {
  const url = String(value || "").trim();
  return url.startsWith("http://") || url.startsWith("https://") ? url : "";
}

function mergeCustomProducts() {
  customProducts.forEach(product => {
    if (!products.some(item => item.id === product.id)) products.push(product);
    if (stock[product.id] === undefined) stock[product.id] = Number(product.stock || 0);
  });
}

function productImages(product) {
  if (Array.isArray(product.images) && product.images.length) return product.images;
  if (product.imageUrl) return [product.imageUrl];
  return [];
}

function clearNode(node) {
  while (node.firstChild) node.removeChild(node.firstChild);
}

function make(tag, className, text) {
  const el = document.createElement(tag);
  if (className) el.className = className;
  if (text !== undefined) el.textContent = text;
  return el;
}

function renderProductGallery(card, product) {
  const images = productImages(product);
  if (!images.length) {
    card.appendChild(make("div", "product-image", product.icon || "✨"));
    return;
  }

  const wrap = make("div", "product-gallery");
  const img = document.createElement("img");
  img.className = "product-photo";
  img.src = images[0];
  img.alt = product.name;
  img.loading = "lazy";
  wrap.appendChild(img);

  if (images.length > 1) {
    const dots = make("div", "gallery-dots");
    images.forEach(url => {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.addEventListener("click", () => { img.src = url; });
      dots.appendChild(btn);
    });
    wrap.appendChild(dots);
  }
  card.appendChild(wrap);
}

renderProducts = function renderProductsWithAdminItems() {
  clearNode(productGrid);
  products.forEach(product => {
    const available = getStock(product.id);
    const card = make("article", "product-card");
    renderProductGallery(card, product);

    const info = make("div");
    info.appendChild(make("p", "eyebrow", product.category));
    info.appendChild(make("h3", "", product.name));
    info.appendChild(make("p", "", product.description));
    card.appendChild(info);

    card.appendChild(make("strong", "product-price", currency.format(product.price)));

    const stockText = available > 0 ? `Estoque: ${available}` : `Sob encomenda${product.deliveryDate ? " • entrega: " + product.deliveryDate : ""}`;
    card.appendChild(make("span", `stock-badge ${available <= storeConfig.minStock ? "stock-low" : ""}`, stockText));

    const qtyRow = make("div", "qty-row");
    const input = document.createElement("input");
    input.id = `qty-${safeId(product.id)}`;
    input.type = "number";
    input.min = "1";
    input.max = String(Math.max(available, 1));
    input.step = "1";
    input.value = "1";
    if (available <= 0) input.disabled = true;

    const add = make("button", "btn", "Adicionar");
    add.type = "button";
    add.disabled = available <= 0;
    add.addEventListener("click", () => addToCart(product.id));
    qtyRow.append(input, add);
    card.appendChild(qtyRow);

    const whats = make("button", "btn btn-ghost btn-full", available > 0 ? "Comprar pelo WhatsApp" : "Consultar entrega pelo WhatsApp");
    whats.type = "button";
    whats.addEventListener("click", () => buyProductWhatsapp(product.id));
    card.appendChild(whats);

    if (product.externalUrl) {
      const external = document.createElement("a");
      external.className = "btn btn-ghost btn-full";
      external.href = product.externalUrl;
      external.target = "_blank";
      external.rel = "noopener sponsored";
      external.textContent = "Ver na loja parceira";
      card.appendChild(external);
    }

    productGrid.appendChild(card);
  });
};

function addField(form, labelText, id, type, placeholder, required) {
  const label = document.createElement("label");
  label.textContent = labelText;
  const field = document.createElement(type === "textarea" ? "textarea" : "input");
  field.id = id;
  if (type !== "textarea") field.type = type;
  field.placeholder = placeholder || "";
  field.required = required !== false;
  label.appendChild(field);
  form.appendChild(label);
}

function mountProductAdmin() {
  if (!adminContent || document.getElementById("productAdminForm")) return;

  const grid = make("div", "checkout-grid admin-grid");
  const panel = make("div", "form-panel");
  panel.appendChild(make("p", "eyebrow", "Produtos"));
  panel.appendChild(make("h2", "", "Cadastrar item"));

  const form = document.createElement("form");
  form.id = "productAdminForm";
  form.className = "form";
  addField(form, "Nome do produto", "productName", "text", "Ex.: Incenso de Sálvia Branca");
  addField(form, "Categoria", "productCategory", "text", "Ex.: Incensos, Cristais, Velas");
  addField(form, "Descrição", "productDescription", "textarea", "Descrição comercial curta");
  addField(form, "Valor de venda", "productPrice", "text", "Ex.: 18,00");
  addField(form, "Estoque", "productStock", "number", "Ex.: 10");
  addField(form, "Data de entrega se não houver estoque", "productDelivery", "date", "", false);
  addField(form, "Ícone", "productIcon", "text", "Ex.: 🌿", false);
  addField(form, "Imagens", "productImages", "textarea", "Cole uma URL de imagem por linha", false);
  addField(form, "Link externo ou afiliado", "productExternal", "url", "Ex.: link da Shopee afiliado", false);

  const submit = make("button", "btn", "Salvar produto");
  submit.type = "submit";
  form.appendChild(submit);
  panel.appendChild(form);

  const listPanel = make("div", "form-panel dark-panel");
  listPanel.appendChild(make("p", "eyebrow", "Catálogo"));
  listPanel.appendChild(make("h2", "", "Itens adicionados"));
  const list = make("div", "history-list");
  list.id = "productAdminList";
  listPanel.appendChild(list);

  grid.append(panel, listPanel);
  adminContent.insertBefore(grid, adminContent.firstChild);

  form.addEventListener("submit", event => {
    event.preventDefault();
    const product = {
      id: `produto-${Date.now()}`,
      name: document.getElementById("productName").value.trim(),
      category: document.getElementById("productCategory").value.trim(),
      description: document.getElementById("productDescription").value.trim(),
      price: parseMoney(document.getElementById("productPrice").value),
      stock: Number.parseInt(document.getElementById("productStock").value, 10) || 0,
      deliveryDate: document.getElementById("productDelivery").value,
      icon: document.getElementById("productIcon").value.trim() || "✨",
      imageUrl: "",
      images: parseImages(document.getElementById("productImages").value),
      externalUrl: safeUrl(document.getElementById("productExternal").value)
    };

    customProducts.unshift(product);
    products.unshift(product);
    stock[product.id] = product.stock;
    localStorage.setItem(CUSTOM_PRODUCTS_KEY, JSON.stringify(customProducts));
    saveState();
    renderAll();
    renderProductAdminList();
    form.reset();
  });

  renderProductAdminList();
}

function renderProductAdminList() {
  const list = document.getElementById("productAdminList");
  if (!list) return;
  clearNode(list);
  if (!customProducts.length) {
    list.appendChild(make("div", "history-item", "Nenhum produto cadastrado pelo painel ainda."));
    return;
  }
  customProducts.forEach(product => {
    const item = make("div", "history-item");
    item.appendChild(make("strong", "", product.name));
    item.appendChild(make("span", "", `${product.category} • ${currency.format(product.price)} • Estoque: ${getStock(product.id)}`));
    if (product.deliveryDate) item.appendChild(make("span", "", `Entrega se faltar estoque: ${product.deliveryDate}`));
    if (product.externalUrl) item.appendChild(make("span", "", "Possui link externo/parceiro."));
    list.appendChild(item);
  });
}

mergeCustomProducts();
mountProductAdmin();
renderProducts();
renderStock();
