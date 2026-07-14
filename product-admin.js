// Produtos cadastrados pelo painel local nunca são persistidos no
// navegador (preço, estoque e link externo são dados comerciais): existem
// só em memória durante a sessão da página. O cadastro real acontece pela
// API autenticada (ver site-production-guard.js, que bloqueia este
// formulário no site público).
let customProducts = [];
let catalogFilters = { search: "", category: "todos", sort: "destaques" };

function isMisticaAdminMode() {
  const params = new URLSearchParams(window.location.search);
  return params.get("admin") === "mistica" || window.location.hash === "#admin-mistica";
}

function parseMoney(value) {
  const normalized = String(value || "").replace(/\./g, "").replace(",", ".");
  const number = Number(normalized);
  return Number.isFinite(number) && number >= 0 ? number : 0;
}

function parseImages(value) {
  return String(value || "").split("\n").map(item => item.trim()).filter(item => item.startsWith("http://") || item.startsWith("https://")).slice(0, 8);
}

function safeUrl(value) {
  const raw = String(value || "").trim();
  if (!raw) return "";
  try {
    const url = new URL(raw);
    return ["http:", "https:"].includes(url.protocol) ? url.href : "";
  } catch {
    return "";
  }
}

function validateProduct(product, rawExternalUrl) {
  const errors = [];
  if (!product.name) errors.push("Informe o nome do produto.");
  if (!product.category) errors.push("Informe a categoria do produto.");
  if (!product.description) errors.push("Informe uma descrição curta do produto.");
  if (!Number.isFinite(product.price) || product.price <= 0) errors.push("Informe um valor de venda maior que zero.");
  if (!Number.isInteger(product.stock) || product.stock < 0) errors.push("Informe um estoque válido, igual ou maior que zero.");
  if (rawExternalUrl && !product.externalUrl) errors.push("O link externo precisa começar com http:// ou https:// e ser uma URL válida.");
  return errors;
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

function clearNode(node) { while (node.firstChild) node.removeChild(node.firstChild); }
function make(tag, className, text) {
  const el = document.createElement(tag);
  if (className) el.className = className;
  if (text !== undefined) el.textContent = text;
  return el;
}
function normalizeText(value) { return String(value || "").normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase(); }

function getProductTag(product, available) {
  if (product.tag) return product.tag;
  if (available <= 0) return "Sob encomenda";
  if (available <= storeConfig.minStock) return "Poucas unidades";
  if (String(product.category || "").toLowerCase().includes("kit")) return "Kit especial";
  if (product.externalUrl) return "Loja parceira";
  return "Produto disponível";
}

function getCategories() {
  const categories = [...new Set(products.map(product => product.category).filter(Boolean))];
  return categories.sort((a, b) => a.localeCompare(b, "pt-BR"));
}

function mountCatalogTools() {
  const section = document.getElementById("produtos");
  const grid = productGrid;
  if (!section || !grid || document.getElementById("catalogTools")) return;
  const tools = make("div", "container catalog-tools");
  tools.id = "catalogTools";
  const search = document.createElement("input");
  search.type = "search";
  search.placeholder = "Buscar por produto, intenção ou categoria...";
  search.setAttribute("aria-label", "Buscar produtos");
  search.addEventListener("input", () => { catalogFilters.search = search.value; renderProducts(); });
  const category = document.createElement("select");
  category.setAttribute("aria-label", "Filtrar categoria");
  category.addEventListener("change", () => { catalogFilters.category = category.value; renderProducts(); });
  const sort = document.createElement("select");
  sort.setAttribute("aria-label", "Ordenar produtos");
  [["destaques", "Destaques"], ["preco-menor", "Menor preço"], ["preco-maior", "Maior preço"], ["estoque", "Mais estoque"], ["nome", "Nome A-Z"]].forEach(([value, label]) => {
    const option = document.createElement("option");
    option.value = value;
    option.textContent = label;
    sort.appendChild(option);
  });
  sort.addEventListener("change", () => { catalogFilters.sort = sort.value; renderProducts(); });
  tools.append(search, category, sort);
  grid.parentNode.insertBefore(tools, grid);
  updateCategoryOptions();
}

function updateCategoryOptions() {
  const category = document.querySelector("#catalogTools select[aria-label='Filtrar categoria']");
  if (!category) return;
  const current = category.value || "todos";
  clearNode(category);
  const all = document.createElement("option");
  all.value = "todos";
  all.textContent = "Todas as categorias";
  category.appendChild(all);
  getCategories().forEach(cat => {
    const option = document.createElement("option");
    option.value = cat;
    option.textContent = cat;
    category.appendChild(option);
  });
  category.value = [...category.options].some(option => option.value === current) ? current : "todos";
}

function getFilteredProducts() {
  const search = normalizeText(catalogFilters.search);
  let list = products.filter(product => {
    const text = normalizeText(`${product.name} ${product.category} ${product.description} ${product.tag || ""}`);
    return (!search || text.includes(search)) && (catalogFilters.category === "todos" || product.category === catalogFilters.category);
  });
  list = [...list].sort((a, b) => {
    if (catalogFilters.sort === "preco-menor") return Number(a.price || 0) - Number(b.price || 0);
    if (catalogFilters.sort === "preco-maior") return Number(b.price || 0) - Number(a.price || 0);
    if (catalogFilters.sort === "estoque") return getStock(b.id) - getStock(a.id);
    if (catalogFilters.sort === "nome") return String(a.name).localeCompare(String(b.name), "pt-BR");
    return Number(Boolean(b.tag)) - Number(Boolean(a.tag));
  });
  return list;
}

function renderProductGallery(card, product) {
  const images = productImages(product);
  if (!images.length) { card.appendChild(make("div", "product-image", product.icon || "✨")); return; }
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
  if (!productGrid) return;
  mountCatalogTools();
  updateCategoryOptions();
  clearNode(productGrid);
  const list = getFilteredProducts();
  if (!list.length) {
    productGrid.appendChild(make("div", "empty-catalog", "Nenhum produto encontrado. Tente outra busca ou categoria."));
    return;
  }
  const encomenda = window.misticaEncomenda || null;
  list.forEach(product => {
    const available = getStock(product.id);
    const sob = Boolean(encomenda && encomenda.isSobEncomenda(product));
    const card = make("article", "product-card");
    if (sob) card.appendChild(make("span", "product-badge-encomenda", encomenda.BADGE));
    card.appendChild(make("span", "product-tag", getProductTag(product, available)));
    renderProductGallery(card, product);
    const info = make("div");
    info.appendChild(make("p", "eyebrow", product.category));
    info.appendChild(make("h3", "", product.name));
    info.appendChild(make("p", "", product.description));
    if (sob) info.appendChild(make("p", "product-encomenda-note", encomenda.CARD_NOTE));
    card.appendChild(info);
    card.appendChild(make("strong", "product-price", currency.format(product.price)));
    const stockText = sob
      ? encomenda.ESTOQUE_NOTE
      : (available > 0 ? `Estoque: ${available}` : `Sob encomenda${product.deliveryDate ? " • entrega: " + product.deliveryDate : ""}`);
    card.appendChild(make("span", `stock-badge ${!sob && available <= storeConfig.minStock ? "stock-low" : ""}`, stockText));
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
    // O link do fornecedor nunca é exibido publicamente em produtos sob
    // encomenda (uso interno do administrador). Produtos comuns mantêm o
    // comportamento anterior.
    if (product.externalUrl && !sob) {
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
  if (!isMisticaAdminMode()) return;
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
  addField(form, "Selo comercial", "productTag", "text", "Ex.: Mais vendido, Promoção, Novidade", false);
  addField(form, "Data de entrega se não houver estoque", "productDelivery", "date", "", false);
  addField(form, "Ícone", "productIcon", "text", "Ex.: 🌿", false);
  addField(form, "Imagens", "productImages", "textarea", "Cole uma URL de imagem por linha", false);
  addField(form, "Link externo ou afiliado", "productExternal", "url", "Ex.: link da Shopee afiliado", false);
  const status = make("div", "saved-box");
  status.id = "productAdminStatus";
  status.hidden = true;
  form.appendChild(status);
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
    const rawExternalUrl = document.getElementById("productExternal").value.trim();
    const product = {
      id: `produto-${Date.now()}`,
      name: document.getElementById("productName").value.trim(),
      category: document.getElementById("productCategory").value.trim(),
      description: document.getElementById("productDescription").value.trim(),
      price: parseMoney(document.getElementById("productPrice").value),
      stock: Number.parseInt(document.getElementById("productStock").value, 10),
      tag: document.getElementById("productTag").value.trim(),
      deliveryDate: document.getElementById("productDelivery").value,
      icon: document.getElementById("productIcon").value.trim() || "✨",
      imageUrl: "",
      images: parseImages(document.getElementById("productImages").value),
      externalUrl: safeUrl(rawExternalUrl)
    };
    const errors = validateProduct(product, rawExternalUrl);
    if (errors.length) { status.hidden = false; status.textContent = errors.join(" "); return; }
    customProducts.unshift(product);
    products.unshift(product);
    stock[product.id] = product.stock;
    saveState();
    renderAll();
    renderProductAdminList();
    status.hidden = false;
    status.textContent = `Produto salvo: ${product.name}`;
    form.reset();
  });
  renderProductAdminList();
}

function renderProductAdminList() {
  const list = document.getElementById("productAdminList");
  if (!list) return;
  clearNode(list);
  if (!customProducts.length) { list.appendChild(make("div", "history-item", "Nenhum produto cadastrado pelo painel ainda.")); return; }
  customProducts.forEach(product => {
    const item = make("div", "history-item");
    item.appendChild(make("strong", "", product.name));
    item.appendChild(make("span", "", `${product.category} • ${currency.format(product.price)} • Estoque: ${getStock(product.id)}`));
    if (product.tag) item.appendChild(make("span", "", `Selo: ${product.tag}`));
    if (product.deliveryDate) item.appendChild(make("span", "", `Entrega se faltar estoque: ${product.deliveryDate}`));
    if (product.externalUrl) item.appendChild(make("span", "", "Possui link externo/parceiro."));
    list.appendChild(item);
  });
}

mergeCustomProducts();
mountProductAdmin();
renderProducts();
renderStock();
