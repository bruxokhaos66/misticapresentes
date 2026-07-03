const CUSTOM_PRODUCTS_KEY = "misticaCustomProducts";
let customProducts = loadStorage(CUSTOM_PRODUCTS_KEY, []);

function normalizePrice(value) {
  const number = Number(String(value).replace(/\./g, "").replace(",", "."));
  return Number.isFinite(number) ? number : 0;
}

function isSafeImageUrl(url) {
  try {
    const parsed = new URL(url);
    return parsed.protocol === "https:" || parsed.protocol === "http:";
  } catch {
    return false;
  }
}

function normalizeImages(value) {
  return String(value || "")
    .split("\n")
    .map(url => url.trim())
    .filter(isSafeImageUrl)
    .slice(0, 6);
}

function getProductImages(product) {
  if (Array.isArray(product.images) && product.images.length) return product.images;
  if (product.imageUrl && isSafeImageUrl(product.imageUrl)) return [product.imageUrl];
  return [];
}

function syncCustomProducts() {
  customProducts.forEach(product => {
    if (!products.some(item => item.id === product.id)) products.push(product);
    if (stock[product.id] === undefined) stock[product.id] = product.stock || 0;
  });
}

function productCardHtml(product) {
  const available = getStock(product.id);
  const disabled = available <= 0 ? "disabled" : "";
  const images = getProductImages(product);
  const imageMarkup = images.length
    ? `<div class="product-gallery" data-gallery="${product.id}"><img class="product-photo" src="${images[0]}" alt="${product.name}" loading="lazy"><div class="gallery-dots">${images.map((_, index) => `<button type="button" data-product-id="${product.id}" data-image-index="${index}" aria-label="Ver foto ${index + 1}"></button>`).join("")}</div></div>`
    : `<div class="product-image" aria-hidden="true">${product.icon || "✨"}</div>`;

  return `
    <article class="product-card">
      ${imageMarkup}
      <div>
        <p class="eyebrow">${product.category}</p>
        <h3>${product.name}</h3>
        <p>${product.description}</p>
      </div>
      <strong class="product-price">${currency.format(product.price)}</strong>
      <span class="stock-badge ${available <= storeConfig.minStock ? "stock-low" : ""}">Estoque: ${available}</span>
      <div class="qty-row">
        <input id="qty-${safeId(product.id)}" type="number" min="1" max="${available}" step="1" value="1" aria-label="Quantidade de ${product.name}" ${disabled} />
        <button class="btn" type="button" onclick="addToCart('${product.id}')" ${disabled}>Adicionar</button>
      </div>
      <button class="btn btn-ghost btn-full" type="button" onclick="buyProductWhatsapp('${product.id}')">Comprar pelo WhatsApp</button>
    </article>
  `;
}

renderProducts = function renderProductsWithGallery() {
  productGrid.innerHTML = products.map(productCardHtml).join("");
  productGrid.querySelectorAll("[data-product-id][data-image-index]").forEach(button => {
    button.addEventListener("click", () => {
      const product = products.find(item => item.id === button.dataset.productId);
      const image = productGrid.querySelector(`[data-gallery="${button.dataset.productId}"] .product-photo`);
      const next = getProductImages(product)[Number(button.dataset.imageIndex)];
      if (image && next) image.src = next;
    });
  });
};

function createInput(labelText, id, type, placeholder, required = true) {
  const label = document.createElement("label");
  label.textContent = labelText;
  const input = document.createElement(type === "textarea" ? "textarea" : "input");
  input.id = id;
  if (type !== "textarea") input.type = type;
  input.placeholder = placeholder;
  input.required = required;
  label.appendChild(input);
  return label;
}

function mountProductAdmin() {
  const mount = document.getElementById("productAdminMount");
  if (!mount) return;

  const wrapper = document.createElement("div");
  wrapper.className = "checkout-grid admin-grid";

  const formPanel = document.createElement("div");
  formPanel.className = "form-panel";
  formPanel.innerHTML = `<p class="eyebrow">Produtos</p><h2>Cadastrar item à venda</h2>`;

  const form = document.createElement("form");
  form.id = "productAdminForm";
  form.className = "form";
  form.append(
    createInput("Nome do item", "productName", "text", "Ex.: Incenso de Sálvia Branca"),
    createInput("Categoria", "productCategory", "text", "Ex.: Incensos, Cristais, Velas"),
    createInput("Descrição", "productDescription", "textarea", "Descrição curta e comercial"),
    createInput("Preço", "productPrice", "text", "Ex.: 18,00"),
    createInput("Estoque", "productStock", "number", "Ex.: 10"),
    createInput("Ícone", "productIcon", "text", "Ex.: 🌿", false),
    createInput("Fotos do produto", "productImages", "textarea", "Cole uma URL de imagem por linha. Pode usar várias fotos.", false)
  );

  const submit = document.createElement("button");
  submit.className = "btn";
  submit.type = "submit";
  submit.textContent = "Adicionar produto";
  form.appendChild(submit);
  formPanel.appendChild(form);

  const listPanel = document.createElement("div");
  listPanel.className = "form-panel dark-panel";
  listPanel.innerHTML = `<p class="eyebrow">Catálogo</p><h2>Itens cadastrados</h2><div id="productAdminList" class="history-list"></div>`;

  wrapper.append(formPanel, listPanel);
  mount.appendChild(wrapper);

  form.addEventListener("submit", event => {
    event.preventDefault();
    const product = {
      id: `produto-${Date.now()}`,
      name: document.getElementById("productName").value.trim(),
      category: document.getElementById("productCategory").value.trim(),
      description: document.getElementById("productDescription").value.trim(),
      price: normalizePrice(document.getElementById("productPrice").value),
      stock: Number.parseInt(document.getElementById("productStock").value, 10) || 0,
      icon: document.getElementById("productIcon").value.trim() || "✨",
      imageUrl: "",
      images: normalizeImages(document.getElementById("productImages").value)
    };

    customProducts.unshift(product);
    localStorage.setItem(CUSTOM_PRODUCTS_KEY, JSON.stringify(customProducts));
    products.unshift(product);
    stock[product.id] = product.stock;
    saveState();
    renderProducts();
    renderStock();
    renderProductAdminList();
    form.reset();
  });

  renderProductAdminList();
}

function renderProductAdminList() {
  const list = document.getElementById("productAdminList");
  if (!list) return;
  list.replaceChildren();
  if (!customProducts.length) {
    const empty = document.createElement("div");
    empty.className = "history-item";
    empty.textContent = "Nenhum produto personalizado cadastrado ainda.";
    list.appendChild(empty);
    return;
  }
  customProducts.forEach(product => {
    const item = document.createElement("div");
    item.className = "history-item";
    item.textContent = `${product.name} • ${product.category} • ${currency.format(product.price)} • Fotos: ${getProductImages(product).length}`;
    list.appendChild(item);
  });
}

syncCustomProducts();
mountProductAdmin();
renderProducts();
renderStock();
