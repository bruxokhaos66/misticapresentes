const storeConfig = {
  name: "Mística Presentes",
  whatsappNumber: "5549984090802",
  pixKey: "07353652969",
  merchantName: "FREDINEI JEAN BACH",
  merchantCity: "PINHALZINHO",
  instagram: "@misticaprodutos",
  adminPassword: "mistica2026",
  minStock: 3
};

const PLACEHOLDER_WHATSAPP = "5549999999999";
const PLACEHOLDER_PIX = "misticapresentes@email.com";

const products = [
  { id: "incenso-natural", name: "Incensos Naturais", category: "Aromas e proteção", description: "Incensos para oração, limpeza do ambiente, acolhimento e boas energias.", price: 12.9, stock: 30, icon: "🌿", imageUrl: "" },
  { id: "vela-ritualistica", name: "Velas de Intenção", category: "Fé e luz", description: "Velas para momentos de fé, pedidos, gratidão, decoração e conexão espiritual.", price: 18.0, stock: 24, icon: "🕯️", imageUrl: "" },
  { id: "pedra-energetica", name: "Pedras e Cristais", category: "Proteção e equilíbrio", description: "Pedras selecionadas para proteção, equilíbrio, presente e cuidado energético.", price: 24.9, stock: 18, icon: "💎", imageUrl: "" },
  { id: "banho-ervas", name: "Banhos de Ervas", category: "Ervas e limpeza", description: "Preparos especiais para renovação, descarrego, harmonia e bem-estar espiritual.", price: 16.5, stock: 20, icon: "🍃", imageUrl: "" },
  { id: "aromatizador", name: "Aromatizadores Via Aroma", category: "Casa perfumada", description: "Essências e aromas para deixar o lar mais leve, acolhedor e agradável.", price: 29.9, stock: 16, icon: "✨", imageUrl: "" },
  { id: "incensario", name: "Incensários Decorativos", category: "Decoração mística", description: "Peças bonitas e funcionais para usar com incensos e compor ambientes especiais.", price: 35.0, stock: 12, icon: "🔮", imageUrl: "" },
  { id: "artigo-fe", name: "Artigos de Fé e Proteção", category: "Fé e bênçãos", description: "Itens para presentear, abençoar ambientes e fortalecer momentos de oração e esperança.", price: 32.9, stock: 14, icon: "🙏", imageUrl: "" },
  { id: "presente-mistico", name: "Kit Presente Especial", category: "Kits e presentes", description: "Combinação especial com aromas, velas, pedras e artigos escolhidos com carinho.", price: 59.9, stock: 8, icon: "🎁", imageUrl: "" }
];

let cart = loadStorage("misticaCart", []);
let clients = loadStorage("misticaClients", []);
let sales = loadStorage("misticaSales", []);
let stock = loadStorage("misticaStock", createInitialStock());
let suppliers = loadStorage("misticaSuppliers", []);

const currency = new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" });

const $ = selector => document.querySelector(selector);
const $$ = selector => document.querySelectorAll(selector);
const productGrid = $("[data-product-grid]");
const cartList = $("#cartList");
const cartTotal = $("#cartTotal");
const clientForm = $("#clientForm");
const clientSaved = $("#clientSaved");
const clientList = $("#clientList");
const salesHistory = $("#salesHistory");
const stockList = $("#stockList");
const pixPayloadInput = $("#pixPayload");
const pixStatus = $("#pixStatus");
const pixCanvas = $("#pixQr");
const pixKeyInput = $("#pixKey");
const merchantNameInput = $("#merchantName");
const merchantCityInput = $("#merchantCity");
const publishWarning = $("#publishWarning");
const adminLoginPanel = $("#adminLoginPanel");
const adminContent = $("#adminContent");
const adminLoginForm = $("#adminLoginForm");
const adminLoginStatus = $("#adminLoginStatus");
const supplierForm = $("#supplierForm");
const supplierList = $("#supplierList");
const isisForm = $("#isisForm");
const isisChat = $("#isisChat");
const isisInput = $("#isisInput");
const backupStatus = $("#backupStatus");

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
  localStorage.setItem("misticaSuppliers", JSON.stringify(suppliers));
  localStorage.setItem("misticaAutoBackup", JSON.stringify(createBackupPayload()));
  localStorage.setItem("misticaLastBackupAt", new Date().toISOString());
}

function createBackupPayload() {
  return {
    store: storeConfig.name,
    createdAt: new Date().toISOString(),
    products,
    clients,
    sales,
    stock,
    suppliers
  };
}

function text(value) { return String(value ?? ""); }
function onlyDigits(value) { return text(value).replace(/\D/g, ""); }
function getStock(productId) { return Number(stock[productId] ?? 0); }
function setStatus(message) { pixStatus.textContent = message; }
function escapeCsv(value) { return `"${text(value).replace(/"/g, '""')}"`; }
function safeId(value) { return text(value).replace(/[^a-zA-Z0-9_-]/g, ""); }

function setupConfig() {
  pixKeyInput.value = storeConfig.pixKey;
  merchantNameInput.value = storeConfig.merchantName;
  merchantCityInput.value = storeConfig.merchantCity;

  $$('[data-whatsapp-link]').forEach(link => {
    link.href = buildWhatsappUrl("Olá, vim pelo site da Mística Presentes e gostaria de atendimento.");
  });

  const warnings = [];
  if (storeConfig.whatsappNumber === PLACEHOLDER_WHATSAPP) warnings.push("WhatsApp ainda está com número de exemplo.");
  if (storeConfig.pixKey === PLACEHOLDER_PIX) warnings.push("Chave Pix ainda está com valor de exemplo.");
  if (storeConfig.adminPassword === "mistica2026") warnings.push("Senha admin está no padrão inicial; troque antes de uso real.");

  if (warnings.length) {
    publishWarning.hidden = false;
    publishWarning.innerHTML = `<strong>Atenção:</strong> ${warnings.join(" ")}`;
  }
}

function renderProducts() {
  productGrid.innerHTML = products.map(product => {
    const available = getStock(product.id);
    const disabled = available <= 0 ? "disabled" : "";
    const media = product.imageUrl
      ? `<img class="product-photo" src="${product.imageUrl}" alt="${product.name}" loading="lazy">`
      : `<div class="product-image" aria-hidden="true">${product.icon}</div>`;

    return `
      <article class="product-card">
        ${media}
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
  const qtyInput = document.getElementById(`qty-${safeId(productId)}`);
  const validation = validateQuantity(qtyInput.value, productId);
  if (!validation.ok) return setStatus(validation.message);

  const existing = cart.find(item => item.id === productId);
  if (existing) existing.qty += validation.qty;
  else cart.push({ id: product.id, name: product.name, price: product.price, qty: validation.qty });

  saveState();
  renderCart();
  renderProducts();
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
        <div><strong>${item.name}</strong><span>${item.qty}x ${currency.format(item.price)} = ${currency.format(item.price * item.qty)}</span></div>
        <button class="cart-remove" type="button" onclick="removeFromCart('${item.id}')">Remover</button>
      </div>
    `).join("");
  }
  cartTotal.textContent = currency.format(getTotal());
}

function getTotal() { return cart.reduce((sum, item) => sum + item.price * item.qty, 0); }

function renderClients() {
  if (!clients.length) {
    clientList.innerHTML = `<div class="client-item"><span>Nenhum cliente cadastrado ainda.</span></div>`;
    return;
  }
  clientList.replaceChildren();
  clients.slice(0, 5).forEach(client => {
    const item = document.createElement("div");
    item.className = "client-item";
    const name = document.createElement("strong"); name.textContent = client.name;
    const cpf = document.createElement("span"); cpf.textContent = `CPF: ${client.cpf}`;
    const whatsapp = document.createElement("span"); whatsapp.textContent = `WhatsApp: ${client.whatsapp}`;
    const address = document.createElement("span"); address.textContent = client.address;
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
  stockList.innerHTML = products.map(product => {
    const current = getStock(product.id);
    const low = current <= storeConfig.minStock;
    return `
      <div class="stock-item">
        <div><strong>${product.name}</strong><span>${product.category}</span></div>
        <span class="stock-badge ${low ? "stock-low" : ""}">${current} un.</span>
      </div>
    `;
  }).join("");
  renderAdminDashboard();
}

function maskCpf(value) {
  return onlyDigits(value).slice(0, 11).replace(/(\d{3})(\d)/, "$1.$2").replace(/(\d{3})(\d)/, "$1.$2").replace(/(\d{3})(\d{1,2})$/, "$1-$2");
}

function maskWhatsapp(value) {
  const digits = onlyDigits(value).slice(0, 11);
  if (digits.length <= 10) return digits.replace(/(\d{2})(\d)/, "($1) $2").replace(/(\d{4})(\d)/, "$1-$2");
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
  return text(textValue).normalize("NFD").replace(/[\u0300-\u036f]/g, "").replace(/[^a-zA-Z0-9 .@+\-_]/g, "").toUpperCase().slice(0, maxLength);
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
  const withoutCrc = emv("00", "01") + merchantAccount + emv("52", "0000") + emv("53", "986") + emv("54", amount.toFixed(2)) + emv("58", "BR") + emv("59", sanitizePixText(name, 25) || "MISTICA PRESENTES") + emv("60", sanitizePixText(city, 15) || "PINHALZINHO") + emv("62", emv("05", sanitizePixText(txid, 25) || "MISTICA")) + "6304";
  return withoutCrc + crc16(withoutCrc);
}

function clearQrCanvas() {
  const ctx = pixCanvas.getContext("2d");
  ctx.clearRect(0, 0, pixCanvas.width, pixCanvas.height);
  ctx.fillStyle = "#ffffff";
  ctx.fillRect(0, 0, pixCanvas.width, pixCanvas.height);
}

function hasEnoughStockForCart() { return cart.every(item => item.qty <= getStock(item.id)); }
function reduceStockFromCart() { cart.forEach(item => { stock[item.id] = Math.max(0, getStock(item.id) - item.qty); }); }

async function generatePix() {
  const total = getTotal();
  if (!cart.length || total <= 0) return setStatus("Adicione pelo menos um produto ao carrinho antes de gerar o Pix.");
  if (!hasEnoughStockForCart()) return setStatus("Existe produto no carrinho acima do estoque disponível. Ajuste antes de gerar o Pix.");
  if (!storeConfig.pixKey || storeConfig.pixKey === PLACEHOLDER_PIX) return setStatus("Configure a chave Pix real no app.js antes de publicar ou vender.");

  const saleId = `MISTICA${Date.now().toString().slice(-9)}`;
  let payload = "";
  try {
    payload = buildPixPayload({ key: storeConfig.pixKey, name: storeConfig.merchantName, city: storeConfig.merchantCity, amount: total, txid: saleId });
  } catch (error) {
    return setStatus(`Erro ao montar Pix: ${error.message}`);
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
  const total = getTotal();
  reduceStockFromCart();
  sales.unshift({ date: new Date().toISOString(), id: saleId, total, items: saleItems, pixPayload: payload, status: "Aguardando conferência do pagamento" });
  sales = sales.slice(0, 50);
  cart = [];
  saveState();
  renderAll();
}

async function copyPix() {
  const payload = pixPayloadInput.value;
  if (!payload) return setStatus("Gere o Pix antes de copiar.");
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
  return `Olá, quero finalizar um pedido na ${storeConfig.name}:\n\n${items}\n\nTotal: ${currency.format(getTotal())}`;
}

function buildWhatsappUrl(message) { return `https://wa.me/${storeConfig.whatsappNumber}?text=${encodeURIComponent(message)}`; }

function sendSaleWhatsapp() {
  if (!cart.length) return setStatus("Adicione produtos ao carrinho para enviar o resumo pelo WhatsApp.");
  window.open(buildWhatsappUrl(buildSaleSummary()), "_blank", "noopener");
}

function buyProductWhatsapp(productId) {
  const product = products.find(item => item.id === productId);
  if (!product) return;
  const message = `Olá, tenho interesse neste produto da ${storeConfig.name}:\n\n${product.name}\nValor: ${currency.format(product.price)}\nCategoria: ${product.category}\n\nGostaria de saber disponibilidade e opções parecidas.`;
  window.open(buildWhatsappUrl(message), "_blank", "noopener");
}

function exportCsv(filename, rows) {
  if (!rows.length) return alert("Não há dados para exportar.");
  const csv = rows.map(row => row.map(escapeCsv).join(";")).join("\n");
  downloadFile(filename, "\ufeff" + csv, "text/csv;charset=utf-8;");
}

function downloadFile(filename, content, type) {
  const blob = new Blob([content], { type });
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
  const rows = [["ID", "Data", "Itens", "Total", "Status"]].concat(sales.map(sale => [sale.id, sale.date, sale.items.map(item => `${item.qty}x ${item.name}`).join(" | "), sale.total.toFixed(2).replace(".", ","), sale.status]));
  exportCsv("mistica-vendas.csv", rows);
}

function renderAdminDashboard() {
  const today = new Date();
  const startDay = new Date(today.getFullYear(), today.getMonth(), today.getDate());
  const startWeek = new Date(startDay); startWeek.setDate(startDay.getDate() - startDay.getDay());
  const startMonth = new Date(today.getFullYear(), today.getMonth(), 1);
  const totalSince = date => sales.filter(s => new Date(s.date) >= date).reduce((sum, s) => sum + Number(s.total || 0), 0);
  const setText = (id, value) => { const el = document.getElementById(id); if (el) el.textContent = value; };

  setText("revenueToday", currency.format(totalSince(startDay)));
  setText("revenueWeek", currency.format(totalSince(startWeek)));
  setText("revenueMonth", currency.format(totalSince(startMonth)));
  setText("salesCount", String(sales.length));

  const lowStock = products.filter(product => getStock(product.id) <= storeConfig.minStock);
  const alerts = document.getElementById("lowStockAlerts");
  if (alerts) {
    alerts.innerHTML = lowStock.length
      ? lowStock.map(product => `<div class="history-item"><strong>${product.name}</strong><span>Estoque atual: ${getStock(product.id)} un. Reposição recomendada.</span></div>`).join("")
      : `<div class="history-item"><span>Nenhum alerta de estoque mínimo.</span></div>`;
  }

  if (backupStatus) {
    const last = localStorage.getItem("misticaLastBackupAt");
    backupStatus.textContent = last ? `Último backup automático local: ${new Date(last).toLocaleString("pt-BR")}` : "Nenhum backup automático salvo ainda.";
  }
}

function downloadBackup() {
  saveState();
  downloadFile(`mistica-backup-${new Date().toISOString().slice(0, 10)}.json`, JSON.stringify(createBackupPayload(), null, 2), "application/json;charset=utf-8;");
}

function restoreBackupInfo() {
  alert("Para restaurar um backup real, será necessário adicionar upload de arquivo JSON ou backend. O backup automático local já está salvo neste navegador.");
}

function printReceipt(sale = sales[0]) {
  if (!sale) return alert("Nenhuma venda para imprimir.");
  const items = sale.items.map(item => `<tr><td>${item.qty}x ${item.name}</td><td>${currency.format(item.price * item.qty)}</td></tr>`).join("");
  const win = window.open("", "_blank", "width=420,height=620");
  win.document.write(`
    <html><head><title>Cupom ${sale.id}</title><style>body{font-family:Arial,sans-serif;padding:18px;color:#111}h1{font-size:20px}table{width:100%;border-collapse:collapse}td{border-bottom:1px dashed #999;padding:8px 0}.total{font-size:20px;font-weight:bold;text-align:right}.small{font-size:12px;color:#555}</style></head>
    <body><h1>${storeConfig.name}</h1><p class="small">Cupom: ${sale.id}<br>${new Date(sale.date).toLocaleString("pt-BR")}</p><table>${items}</table><p class="total">Total: ${currency.format(sale.total)}</p><p>Status: ${sale.status}</p><p class="small">Obrigado pela preferência.</p></body></html>
  `);
  win.document.close();
  win.focus();
  win.print();
}

function sendLastReceiptWhatsapp() {
  const sale = sales[0];
  if (!sale) return alert("Nenhuma venda para enviar.");
  const items = sale.items.map(item => `• ${item.qty}x ${item.name} - ${currency.format(item.price * item.qty)}`).join("\n");
  const message = `Comprovante/Pedido - ${storeConfig.name}\n\nVenda: ${sale.id}\nData: ${new Date(sale.date).toLocaleString("pt-BR")}\n\n${items}\n\nTotal: ${currency.format(sale.total)}\nStatus: ${sale.status}`;
  window.open(buildWhatsappUrl(message), "_blank", "noopener");
}

function renderSuppliers() {
  if (!supplierList) return;
  if (!suppliers.length) {
    supplierList.innerHTML = `<div class="history-item"><span>Nenhum fornecedor cadastrado ainda.</span></div>`;
    return;
  }
  supplierList.innerHTML = suppliers.map(supplier => `
    <div class="history-item"><strong>${supplier.name}</strong><span>${supplier.category}</span><span>WhatsApp: ${supplier.whatsapp || "não informado"}</span><span>${supplier.notes || "Sem observação"}</span></div>
  `).join("");
}

function handleSupplierSubmit(event) {
  event.preventDefault();
  const supplier = {
    id: `FORN${Date.now()}`,
    name: $("#supplierName").value.trim(),
    category: $("#supplierCategory").value.trim(),
    whatsapp: maskWhatsapp($("#supplierWhatsapp").value.trim()),
    notes: $("#supplierNotes").value.trim(),
    createdAt: new Date().toISOString()
  };
  suppliers.unshift(supplier);
  suppliers = suppliers.slice(0, 100);
  saveState();
  renderSuppliers();
  supplierForm.reset();
}

function unlockAdmin(password) {
  if (password !== storeConfig.adminPassword) {
    adminLoginStatus.hidden = false;
    adminLoginStatus.textContent = "Senha incorreta.";
    return;
  }
  sessionStorage.setItem("misticaAdminUnlocked", "true");
  adminLoginPanel.hidden = true;
  adminContent.hidden = false;
  renderAdminDashboard();
  renderSuppliers();
}

function appendIsis(role, message) {
  const box = document.createElement("div");
  box.className = `isis-message ${role}`;
  box.textContent = message;
  isisChat.appendChild(box);
  isisChat.scrollTop = isisChat.scrollHeight;
}

function answerIsis(prompt) {
  const p = prompt.toLowerCase();
  if (p.includes("venda") || p.includes("fatur")) {
    const today = new Date();
    const start = new Date(today.getFullYear(), today.getMonth(), today.getDate());
    const total = sales.filter(s => new Date(s.date) >= start).reduce((sum, s) => sum + s.total, 0);
    return `Hoje foram registradas ${sales.filter(s => new Date(s.date) >= start).length} venda(s), totalizando ${currency.format(total)}.`;
  }
  if (p.includes("estoque")) {
    const low = products.filter(product => getStock(product.id) <= storeConfig.minStock);
    return low.length ? `Produtos com estoque baixo: ${low.map(product => `${product.name} (${getStock(product.id)} un.)`).join(", ")}.` : "Nenhum produto está abaixo do estoque mínimo.";
  }
  if (p.includes("fornecedor")) {
    return suppliers.length ? `Fornecedores cadastrados: ${suppliers.map(s => `${s.name} (${s.category})`).join(", ")}.` : "Nenhum fornecedor cadastrado ainda.";
  }
  if (p.includes("pesquisar") || p.includes("busca") || p.includes("atacado")) {
    const query = encodeURIComponent(prompt.replace(/pesquisar|busca|buscar/gi, "").trim() || "produtos místicos atacado");
    window.open(`https://www.google.com/search?q=${query}`, "_blank", "noopener");
    return "Abri uma pesquisa no navegador. Para pesquisar dentro do sistema com IA real, a próxima etapa é integrar uma API de busca/IA.";
  }
  return "Posso ajudar com: vendas de hoje, faturamento, estoque baixo, fornecedores e pesquisa de produtos. A versão atual é local; a integração com IA online pode ser adicionada no backend.";
}

function handleIsisSubmit(event) {
  event.preventDefault();
  const message = isisInput.value.trim();
  if (!message) return;
  appendIsis("user", message);
  appendIsis("bot", answerIsis(message));
  isisForm.reset();
}

clientForm.addEventListener("submit", event => {
  event.preventDefault();
  const client = {
    name: $("#clientName").value.trim(),
    cpf: $("#clientCpf").value.trim(),
    address: $("#clientAddress").value.trim(),
    whatsapp: $("#clientWhatsapp").value.trim(),
    createdAt: new Date().toISOString()
  };
  if (!isValidCpf(client.cpf)) { clientSaved.hidden = false; clientSaved.textContent = "CPF inválido. Confira os números digitados."; return; }
  if (!isValidWhatsapp(client.whatsapp)) { clientSaved.hidden = false; clientSaved.textContent = "WhatsApp inválido. Use DDD + número."; return; }
  clients.unshift(client);
  clients = clients.slice(0, 20);
  saveState();
  renderClients();
  clientSaved.hidden = false;
  clientSaved.textContent = `Cliente salvo: ${client.name} • ${client.whatsapp}`;
  clientForm.reset();
});

function renderAll() {
  renderProducts();
  renderCart();
  renderClients();
  renderHistory();
  renderStock();
  renderSuppliers();
  renderAdminDashboard();
}

$("#clientCpf").addEventListener("input", event => { event.target.value = maskCpf(event.target.value); });
$("#clientWhatsapp").addEventListener("input", event => { event.target.value = maskWhatsapp(event.target.value); });
$("[data-clear-cart]").addEventListener("click", clearCart);
$("[data-generate-pix]").addEventListener("click", generatePix);
$("[data-copy-pix]").addEventListener("click", copyPix);
$("[data-send-sale-whatsapp]").addEventListener("click", sendSaleWhatsapp);
$("[data-export-clients]").addEventListener("click", exportClients);
$("[data-export-sales]").addEventListener("click", exportSales);
$("[data-print-last-receipt]").addEventListener("click", () => printReceipt());
$("[data-send-last-receipt-whatsapp]").addEventListener("click", sendLastReceiptWhatsapp);
$("[data-download-backup]").addEventListener("click", downloadBackup);
$("[data-restore-backup]").addEventListener("click", restoreBackupInfo);
$("[data-menu-toggle]").addEventListener("click", () => $("[data-nav-links]").classList.toggle("open"));

if (supplierForm) supplierForm.addEventListener("submit", handleSupplierSubmit);
if (adminLoginForm) adminLoginForm.addEventListener("submit", event => { event.preventDefault(); unlockAdmin($("#adminPassword").value); });
if (isisForm) isisForm.addEventListener("submit", handleIsisSubmit);
$$('[data-isis-command]').forEach(button => button.addEventListener("click", () => {
  const command = button.getAttribute("data-isis-command");
  appendIsis("user", command);
  appendIsis("bot", answerIsis(command));
}));

setupConfig();
if (sessionStorage.getItem("misticaAdminUnlocked") === "true") {
  adminLoginPanel.hidden = true;
  adminContent.hidden = false;
}
renderAll();
clearQrCanvas();
appendIsis("bot", "Olá, eu sou a Isis. Posso ajudar com produtos, pedidos, vendas, estoque, fornecedores e pesquisas.");
saveState();
