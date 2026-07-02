const storeConfig = {
  name: "Mística Presentes",
  whatsappNumber: "5549999999999", // TROCAR antes de publicar. Formato: 55 + DDD + número.
  pixKey: "misticapresentes@email.com", // TROCAR pela chave Pix real da loja.
  merchantName: "MISTICA PRESENTES",
  merchantCity: "PINHALZINHO",
  instagram: "@misticaprodutos"
};

const PLACEHOLDER_WHATSAPP = "5549999999999";
const PLACEHOLDER_PIX = "misticapresentes@email.com";

const products = [
  { id: "incenso-natural", name: "Incenso Natural", category: "Aromas", description: "Aromas para purificação, proteção e harmonização do ambiente.", price: 12.9, stock: 30, icon: "🌿" },
  { id: "vela-ritualistica", name: "Vela Ritualística", category: "Velas", description: "Cores e intenções para rituais, decoração e momentos especiais.", price: 18.0, stock: 24, icon: "🕯️" },
  { id: "pedra-energetica", name: "Pedra Energética", category: "Cristais", description: "Pedras selecionadas para proteção, equilíbrio e boas vibrações.", price: 24.9, stock: 18, icon: "💎" },
  { id: "banho-ervas", name: "Banho de Ervas", category: "Ervas", description: "Preparos especiais para limpeza energética e renovação espiritual.", price: 16.5, stock: 20, icon: "🍃" },
  { id: "aromatizador", name: "Aromatizador Via Aroma", category: "Aromas", description: "Perfume o ambiente com essências marcantes e acolhedoras.", price: 29.9, stock: 16, icon: "✨" },
  { id: "incensario", name: "Incensário Decorativo", category: "Presentes", description: "Peça prática e bonita para usar com incensos na loja ou em casa.", price: 35.0, stock: 12, icon: "🔮" },
  { id: "oleo-essencial", name: "Óleo Essencial", category: "Bem-estar", description: "Opções para relaxar, perfumar e criar experiências sensoriais.", price: 39.9, stock: 10, icon: "🌙" },
  { id: "presente-mistico", name: "Kit Presente Místico", category: "Kits", description: "Combinação especial de produtos para presentear com significado.", price: 59.9, stock: 8, icon: "🎁" }
];

let cart = loadStorage("misticaCart", []);
let clients = loadStorage("misticaClients", []);
let sales = loadStorage("misticaSales", []);
let stock = loadStorage("misticaStock", createInitialStock());

const currency = new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" });
const productGrid = document.querySelector("[data-product-grid]");
const cartList = document.getElementById("cartList");
const cartTotal = document.getElementById("cartTotal");
const clientForm = document.getElementById("clientForm");
const clientSaved = document.getElementById("clientSaved");
const clientList = document.getElementById("clientList");
const salesHistory = document.getElementById("salesHistory");
const stockList = document.getElementById("stockList");
const pixPayloadInput = document.getElementById("pixPayload");
const pixStatus = document.getElementById("pixStatus");
const pixCanvas = document.getElementById("pixQr");
const pixKeyInput = document.getElementById("pixKey");
const merchantNameInput = document.getElementById("merchantName");
const merchantCityInput = document.getElementById("merchantCity");
const publishWarning = document.getElementById("publishWarning");

function loadStorage(key, fallback) {
  try {
    const value = localStorage.getItem(key);
    return value ? JSON.parse(value) : fallback;
  } catch {
    localStorage.removeItem(key);
    return fallback;
  }
}

function createInitialStock() {
  return products.reduce((map, product) => {
    map[product.id] = product.stock;
    return map;
  }, {});
}

function saveState() {
  localStorage.setItem("misticaCart", JSON.stringify(cart));
  localStorage.setItem("misticaClients", JSON.stringify(clients));
  localStorage.setItem("misticaSales", JSON.stringify(sales));
  localStorage.setItem("misticaStock", JSON.stringify(stock));
}

function text(value) {
  return String(value ?? "");
}

function onlyDigits(value) {
  return text(value).replace(/\D/g, "");
}

function escapeCsv(value) {
  return `"${text(value).replace(/"/g, '""')}"`;
}

function getStock(productId) {
  return Number(stock[productId] ?? 0);
}

function setStatus(message) {
  pixStatus.textContent = message;
}

function setupConfig() {
  pixKeyInput.value = storeConfig.pixKey;
  merchantNameInput.value = storeConfig.merchantName;
  merchantCityInput.value = storeConfig.merchantCity;

  document.querySelectorAll("[data-whatsapp-link]").forEach(link => {
    link.href = buildWhatsappUrl("Olá, vim pelo site da Mística Presentes e gostaria de atendimento.");
  });

  const warnings = [];
  if (storeConfig.whatsappNumber === PLACEHOLDER_WHATSAPP) warnings.push("WhatsApp ainda está com número de exemplo.");
  if (storeConfig.pixKey === PLACEHOLDER_PIX) warnings.push("Chave Pix ainda está com valor de exemplo.");

  if (warnings.length) {
    publishWarning.hidden = false;
    publishWarning.innerHTML = `<strong>Atenção antes de publicar:</strong> ${warnings.join(" ")}`;
  }
}

function renderProducts() {
  productGrid.innerHTML = products.map(product => {
    const available = getStock(product.id);
    const disabled = available <= 0 ? "disabled" : "";
    return `
      <article class="product-card">
        <div class="product-image" aria-hidden="true">${product.icon}</div>
        <div>
          <p class="eyebrow">${product.category}</p>
          <h3>${product.name}</h3>
          <p>${product.description}</p>
        </div>
        <strong class="product-price">${currency.format(product.price)}</strong>
        <span class="stock-badge ${available <= 3 ? "stock-low" : ""}">Estoque: ${available}</span>
        <div class="qty-row">
          <input id="qty-${product.id}" type="number" min="1" max="${available}" step="1" value="1" aria-label="Quantidade de ${product.name}" ${disabled} />
          <button class="btn" type="button" onclick="addToCart('${product.id}')" ${disabled}>Adicionar</button>
        </div>
        <button class="btn btn-ghost btn-full" type="button" onclick="buyProductWhatsapp('${product.id}')">Comprar pelo WhatsApp</button>
      </article>
    `;
  }).join("");
}

function validateQuantity(rawQty, productId) {
  const qty = Number.parseInt(rawQty, 10);
  const available = getStock(productId);
  const inCart = cart.find(item => item.id === productId)?.qty || 0;

  if (!Number.isInteger(qty) || qty < 1) return { ok: false, message: "Informe uma quantidade inteira maior que zero." };
  if (qty + inCart > available) return { ok: false, message: `Estoque insuficiente. Disponível: ${Math.max(available - inCart, 0)}.` };
  return { ok: true, qty };
}

function addToCart(productId) {
  const product = products.find(item => item.id === productId);
  if (!product) return;

  const qtyInput = document.getElementById(`qty-${productId}`);
  const validation = validateQuantity(qtyInput.value, productId);

  if (!validation.ok) {
    setStatus(validation.message);
    return;
  }

  const existing = cart.find(item => item.id === productId);
  if (existing) {
    existing.qty += validation.qty;
  } else {
    cart.push({ id: product.id, name: product.name, price: product.price, qty: validation.qty });
  }

  saveState();
  renderCart();
  setStatus(`${product.name} adicionado ao carrinho.`);
}

function removeFromCart(productId) {
  cart = cart.filter(item => item.id !== productId);
  saveState();
  renderCart();
  renderProducts();
}

function clearCart() {
  cart = [];
  pixPayloadInput.value = "";
  setStatus("Carrinho limpo. Adicione produtos para gerar um novo Pix.");
  clearQrCanvas();
  saveState();
  renderCart();
  renderProducts();
}

function renderCart() {
  if (!cart.length) {
    cartList.innerHTML = `<div class="cart-item"><span>Nenhum produto adicionado ainda.</span></div>`;
  } else {
    cartList.innerHTML = cart.map(item => `
      <div class="cart-item">
        <div>
          <strong>${item.name}</strong>
          <span>${item.qty}x ${currency.format(item.price)} = ${currency.format(item.price * item.qty)}</span>
        </div>
        <button class="cart-remove" type="button" onclick="removeFromCart('${item.id}')">Remover</button>
      </div>
    `).join("");
  }

  cartTotal.textContent = currency.format(getTotal());
}

function getTotal() {
  return cart.reduce((sum, item) => sum + item.price * item.qty, 0);
}

function renderClients() {
  if (!clients.length) {
    clientList.innerHTML = `<div class="client-item"><span>Nenhum cliente cadastrado ainda.</span></div>`;
    return;
  }

  clientList.replaceChildren();
  clients.slice(0, 5).forEach(client => {
    const item = document.createElement("div");
    item.className = "client-item";

    const name = document.createElement("strong");
    name.textContent = client.name;
    const cpf = document.createElement("span");
    cpf.textContent = `CPF: ${client.cpf}`;
    const whatsapp = document.createElement("span");
    whatsapp.textContent = `WhatsApp: ${client.whatsapp}`;
    const address = document.createElement("span");
    address.textContent = client.address;

    item.append(name, cpf, document.createElement("br"), whatsapp, document.createElement("br"), address);
    clientList.appendChild(item);
  });
}

function renderHistory() {
  if (!sales.length) {
    salesHistory.innerHTML = `<div class="history-item"><span>Nenhuma venda registrada ainda.</span></div>`;
    return;
  }

  salesHistory.innerHTML = sales.slice(0, 10).map(sale => `
    <div class="history-item">
      <strong>${currency.format(sale.total)} • ${new Date(sale.date).toLocaleString("pt-BR")}</strong>
      <span>${sale.items.map(item => `${item.qty}x ${item.name}`).join(" | ")}</span>
      <span>Status: ${sale.status}</span>
    </div>
  `).join("");
}

function renderStock() {
  stockList.innerHTML = products.map(product => `
    <div class="stock-item">
      <div>
        <strong>${product.name}</strong>
        <span>${product.category}</span>
      </div>
      <span class="stock-badge ${getStock(product.id) <= 3 ? "stock-low" : ""}">${getStock(product.id)} un.</span>
    </div>
  `).join("");
}

function maskCpf(value) {
  return onlyDigits(value)
    .slice(0, 11)
    .replace(/(\d{3})(\d)/, "$1.$2")
    .replace(/(\d{3})(\d)/, "$1.$2")
    .replace(/(\d{3})(\d{1,2})$/, "$1-$2");
}

function maskWhatsapp(value) {
  const digits = onlyDigits(value).slice(0, 11);
  if (digits.length <= 10) {
    return digits.replace(/(\d{2})(\d)/, "($1) $2").replace(/(\d{4})(\d)/, "$1-$2");
  }
  return digits.replace(/(\d{2})(\d)/, "($1) $2").replace(/(\d{5})(\d)/, "$1-$2");
}

function isValidCpf(cpf) {
  const digits = onlyDigits(cpf);
  if (digits.length !== 11 || /^(\d)\1{10}$/.test(digits)) return false;

  let sum = 0;
  for (let i = 0; i < 9; i++) sum += Number(digits[i]) * (10 - i);
  let first = (sum * 10) % 11;
  if (first === 10) first = 0;
  if (first !== Number(digits[9])) return false;

  sum = 0;
  for (let i = 0; i < 10; i++) sum += Number(digits[i]) * (11 - i);
  let second = (sum * 10) % 11;
  if (second === 10) second = 0;
  return second === Number(digits[10]);
}

function isValidWhatsapp(value) {
  const digits = onlyDigits(value);
  return digits.length === 10 || digits.length === 11;
}

function sanitizePixText(textValue, maxLength) {
  return text(textValue)
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/[^a-zA-Z0-9 .@+\-_]/g, "")
    .toUpperCase()
    .slice(0, maxLength);
}

function emv(id, value) {
  const cleanValue = text(value);
  if (cleanValue.length > 99) throw new Error(`Campo Pix ${id} excedeu 99 caracteres.`);
  return `${id}${String(cleanValue.length).padStart(2, "0")}${cleanValue}`;
}

function crc16(payload) {
  let crc = 0xffff;
  for (let i = 0; i < payload.length; i++) {
    crc ^= payload.charCodeAt(i) << 8;
    for (let bit = 0; bit < 8; bit++) {
      crc = (crc & 0x8000) ? (crc << 1) ^ 0x1021 : crc << 1;
      crc &= 0xffff;
    }
  }
  return crc.toString(16).toUpperCase().padStart(4, "0");
}

function buildPixPayload({ key, name, city, amount, txid }) {
  const merchantAccount = emv("26", emv("00", "br.gov.bcb.pix") + emv("01", text(key).trim()));
  const payloadFormat = emv("00", "01");
  const merchantCategory = emv("52", "0000");
  const currencyCode = emv("53", "986");
  const transactionAmount = emv("54", amount.toFixed(2));
  const countryCode = emv("58", "BR");
  const merchantName = emv("59", sanitizePixText(name, 25) || "MISTICA PRESENTES");
  const merchantCity = emv("60", sanitizePixText(city, 15) || "PINHALZINHO");
  const txId = emv("62", emv("05", sanitizePixText(txid, 25) || "MISTICA"));
  const withoutCrc = payloadFormat + merchantAccount + merchantCategory + currencyCode + transactionAmount + countryCode + merchantName + merchantCity + txId + "6304";
  return withoutCrc + crc16(withoutCrc);
}

function clearQrCanvas() {
  const ctx = pixCanvas.getContext("2d");
  ctx.clearRect(0, 0, pixCanvas.width, pixCanvas.height);
  ctx.fillStyle = "#ffffff";
  ctx.fillRect(0, 0, pixCanvas.width, pixCanvas.height);
}

function hasEnoughStockForCart() {
  return cart.every(item => item.qty <= getStock(item.id));
}

function reduceStockFromCart() {
  cart.forEach(item => {
    stock[item.id] = Math.max(0, getStock(item.id) - item.qty);
  });
}

async function generatePix() {
  const total = getTotal();

  if (!cart.length || total <= 0) {
    setStatus("Adicione pelo menos um produto ao carrinho antes de gerar o Pix.");
    return;
  }

  if (!hasEnoughStockForCart()) {
    setStatus("Existe produto no carrinho acima do estoque disponível. Ajuste antes de gerar o Pix.");
    return;
  }

  if (!storeConfig.pixKey || storeConfig.pixKey === PLACEHOLDER_PIX) {
    setStatus("Configure a chave Pix real no app.js antes de publicar ou vender.");
    return;
  }

  const saleId = `MISTICA${Date.now().toString().slice(-9)}`;
  let payload = "";

  try {
    payload = buildPixPayload({
      key: storeConfig.pixKey,
      name: storeConfig.merchantName,
      city: storeConfig.merchantCity,
      amount: total,
      txid: saleId
    });
  } catch (error) {
    setStatus(`Erro ao montar Pix: ${error.message}`);
    return;
  }

  pixPayloadInput.value = payload;

  try {
    if (!window.QRCode) throw new Error("Biblioteca de QR Code não carregou.");
    await window.QRCode.toCanvas(pixCanvas, payload, { width: 220, margin: 2, errorCorrectionLevel: "M" });
    setStatus(`QR Code gerado para ${currency.format(total)}. Confira valor e recebedor no banco antes de pagar.`);
  } catch {
    setStatus("Pix copia e cola gerado. Não foi possível desenhar o QR Code agora.");
  }

  saveSale(payload, saleId);
}

function saveSale(payload, saleId) {
  const saleItems = cart.map(item => ({ ...item }));
  reduceStockFromCart();
  sales.unshift({ date: new Date().toISOString(), id: saleId, total: getTotal(), items: saleItems, pixPayload: payload, status: "Aguardando conferência do pagamento" });
  sales = sales.slice(0, 50);
  cart = [];
  saveState();
  renderCart();
  renderProducts();
  renderStock();
  renderHistory();
}

async function copyPix() {
  const payload = pixPayloadInput.value;
  if (!payload) {
    setStatus("Gere o Pix antes de copiar.");
    return;
  }

  try {
    await navigator.clipboard.writeText(payload);
    setStatus("Pix copia e cola copiado.");
  } catch {
    pixPayloadInput.select();
    document.execCommand("copy");
    setStatus("Pix copia e cola selecionado para copiar.");
  }
}

function buildSaleSummary() {
  if (!cart.length) return "";
  const items = cart.map(item => `• ${item.qty}x ${item.name} - ${currency.format(item.price * item.qty)}`).join("\n");
  return `Olá, quero finalizar uma venda/pedido na ${storeConfig.name}:\n\n${items}\n\nTotal: ${currency.format(getTotal())}`;
}

function buildWhatsappUrl(message) {
  return `https://wa.me/${storeConfig.whatsappNumber}?text=${encodeURIComponent(message)}`;
}

function sendSaleWhatsapp() {
  if (!cart.length) {
    setStatus("Adicione produtos ao carrinho para enviar o resumo pelo WhatsApp.");
    return;
  }
  window.open(buildWhatsappUrl(buildSaleSummary()), "_blank", "noopener");
}

function buyProductWhatsapp(productId) {
  const product = products.find(item => item.id === productId);
  if (!product) return;
  const message = `Olá, tenho interesse neste produto da ${storeConfig.name}:\n\n${product.name}\nValor: ${currency.format(product.price)}\nCategoria: ${product.category}`;
  window.open(buildWhatsappUrl(message), "_blank", "noopener");
}

function exportCsv(filename, rows) {
  if (!rows.length) {
    alert("Não há dados para exportar.");
    return;
  }
  const csv = rows.map(row => row.map(escapeCsv).join(";")).join("\n");
  const blob = new Blob(["\ufeff" + csv], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}

function exportClients() {
  const rows = [["Nome", "CPF", "Endereco", "WhatsApp", "Cadastro"]].concat(clients.map(client => [client.name, client.cpf, client.address, client.whatsapp, client.createdAt]));
  exportCsv("mistica-clientes.csv", rows);
}

function exportSales() {
  const rows = [["ID", "Data", "Itens", "Total", "Status"]].concat(sales.map(sale => [
    sale.id,
    sale.date,
    sale.items.map(item => `${item.qty}x ${item.name}`).join(" | "),
    sale.total.toFixed(2).replace(".", ","),
    sale.status
  ]));
  exportCsv("mistica-vendas.csv", rows);
}

clientForm.addEventListener("submit", event => {
  event.preventDefault();

  const client = {
    name: document.getElementById("clientName").value.trim(),
    cpf: document.getElementById("clientCpf").value.trim(),
    address: document.getElementById("clientAddress").value.trim(),
    whatsapp: document.getElementById("clientWhatsapp").value.trim(),
    createdAt: new Date().toISOString()
  };

  if (!isValidCpf(client.cpf)) {
    clientSaved.hidden = false;
    clientSaved.textContent = "CPF inválido. Confira os números digitados.";
    return;
  }

  if (!isValidWhatsapp(client.whatsapp)) {
    clientSaved.hidden = false;
    clientSaved.textContent = "WhatsApp inválido. Use DDD + número.";
    return;
  }

  clients.unshift(client);
  clients = clients.slice(0, 20);
  saveState();
  renderClients();

  clientSaved.hidden = false;
  clientSaved.textContent = `Cliente salvo: ${client.name} • ${client.whatsapp}`;
  clientForm.reset();
});

document.getElementById("clientCpf").addEventListener("input", event => {
  event.target.value = maskCpf(event.target.value);
});

document.getElementById("clientWhatsapp").addEventListener("input", event => {
  event.target.value = maskWhatsapp(event.target.value);
});

document.querySelector("[data-clear-cart]").addEventListener("click", clearCart);
document.querySelector("[data-generate-pix]").addEventListener("click", generatePix);
document.querySelector("[data-copy-pix]").addEventListener("click", copyPix);
document.querySelector("[data-send-sale-whatsapp]").addEventListener("click", sendSaleWhatsapp);
document.querySelector("[data-export-clients]").addEventListener("click", exportClients);
document.querySelector("[data-export-sales]").addEventListener("click", exportSales);
document.querySelector("[data-menu-toggle]").addEventListener("click", () => {
  document.querySelector("[data-nav-links]").classList.toggle("open");
});

setupConfig();
renderProducts();
renderCart();
renderClients();
renderHistory();
renderStock();
clearQrCanvas();
