const products = [
  {
    id: "incenso-natural",
    name: "Incenso Natural",
    category: "Aromas",
    description: "Aromas para purificação, proteção e harmonização do ambiente.",
    price: 12.9,
    icon: "🌿"
  },
  {
    id: "vela-ritualistica",
    name: "Vela Ritualística",
    category: "Velas",
    description: "Cores e intenções para rituais, decoração e momentos especiais.",
    price: 18.0,
    icon: "🕯️"
  },
  {
    id: "pedra-energetica",
    name: "Pedra Energética",
    category: "Cristais",
    description: "Pedras selecionadas para proteção, equilíbrio e boas vibrações.",
    price: 24.9,
    icon: "💎"
  },
  {
    id: "banho-ervas",
    name: "Banho de Ervas",
    category: "Ervas",
    description: "Preparos especiais para limpeza energética e renovação espiritual.",
    price: 16.5,
    icon: "🍃"
  },
  {
    id: "aromatizador",
    name: "Aromatizador Via Aroma",
    category: "Aromas",
    description: "Perfume o ambiente com essências marcantes e acolhedoras.",
    price: 29.9,
    icon: "✨"
  },
  {
    id: "incensario",
    name: "Incensário Decorativo",
    category: "Presentes",
    description: "Peça prática e bonita para usar com incensos na loja ou em casa.",
    price: 35.0,
    icon: "🔮"
  },
  {
    id: "oleo-essencial",
    name: "Óleo Essencial",
    category: "Bem-estar",
    description: "Opções para relaxar, perfumar e criar experiências sensoriais.",
    price: 39.9,
    icon: "🌙"
  },
  {
    id: "presente-mistico",
    name: "Kit Presente Místico",
    category: "Kits",
    description: "Combinação especial de produtos para presentear com significado.",
    price: 59.9,
    icon: "🎁"
  }
];

let cart = JSON.parse(localStorage.getItem("misticaCart")) || [];
let clients = JSON.parse(localStorage.getItem("misticaClients")) || [];

const currency = new Intl.NumberFormat("pt-BR", {
  style: "currency",
  currency: "BRL"
});

const productGrid = document.querySelector("[data-product-grid]");
const cartList = document.getElementById("cartList");
const cartTotal = document.getElementById("cartTotal");
const clientForm = document.getElementById("clientForm");
const clientSaved = document.getElementById("clientSaved");
const clientList = document.getElementById("clientList");
const pixPayloadInput = document.getElementById("pixPayload");
const pixStatus = document.getElementById("pixStatus");
const pixCanvas = document.getElementById("pixQr");

function saveState() {
  localStorage.setItem("misticaCart", JSON.stringify(cart));
  localStorage.setItem("misticaClients", JSON.stringify(clients));
}

function renderProducts() {
  productGrid.innerHTML = products.map(product => `
    <article class="product-card">
      <div class="product-image" aria-hidden="true">${product.icon}</div>
      <div>
        <p class="eyebrow">${product.category}</p>
        <h3>${product.name}</h3>
        <p>${product.description}</p>
      </div>
      <strong class="product-price">${currency.format(product.price)}</strong>
      <div class="qty-row">
        <input id="qty-${product.id}" type="number" min="1" value="1" aria-label="Quantidade de ${product.name}" />
        <button class="btn" type="button" onclick="addToCart('${product.id}')">Adicionar</button>
      </div>
    </article>
  `).join("");
}

function addToCart(productId) {
  const product = products.find(item => item.id === productId);
  const qtyInput = document.getElementById(`qty-${productId}`);
  const qty = Math.max(1, Number(qtyInput.value || 1));
  const existing = cart.find(item => item.id === productId);

  if (existing) {
    existing.qty += qty;
  } else {
    cart.push({ ...product, qty });
  }

  saveState();
  renderCart();
}

function removeFromCart(productId) {
  cart = cart.filter(item => item.id !== productId);
  saveState();
  renderCart();
}

function clearCart() {
  cart = [];
  pixPayloadInput.value = "";
  pixStatus.textContent = "Carrinho limpo. Adicione produtos para gerar um novo Pix.";
  clearQrCanvas();
  saveState();
  renderCart();
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

  clientList.innerHTML = clients.slice(0, 5).map(client => `
    <div class="client-item">
      <strong>${client.name}</strong>
      <span>CPF: ${client.cpf}</span><br>
      <span>WhatsApp: ${client.whatsapp}</span><br>
      <span>${client.address}</span>
    </div>
  `).join("");
}

function maskCpf(value) {
  return value
    .replace(/\D/g, "")
    .replace(/(\d{3})(\d)/, "$1.$2")
    .replace(/(\d{3})(\d)/, "$1.$2")
    .replace(/(\d{3})(\d{1,2})$/, "$1-$2");
}

function maskWhatsapp(value) {
  return value
    .replace(/\D/g, "")
    .replace(/(\d{2})(\d)/, "($1) $2")
    .replace(/(\d{5})(\d)/, "$1-$2")
    .slice(0, 15);
}

function sanitizePixText(text, maxLength) {
  return String(text || "")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/[^a-zA-Z0-9 .@+\-_]/g, "")
    .toUpperCase()
    .slice(0, maxLength);
}

function emv(id, value) {
  const size = String(value.length).padStart(2, "0");
  return `${id}${size}${value}`;
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

function buildPixPayload({ key, name, city, amount, description }) {
  const gui = emv("00", "br.gov.bcb.pix");
  const pixKey = emv("01", String(key).trim());
  const pixDescription = description ? emv("02", sanitizePixText(description, 60)) : "";
  const merchantAccount = emv("26", gui + pixKey + pixDescription);
  const payloadFormat = emv("00", "01");
  const merchantCategory = emv("52", "0000");
  const currencyCode = emv("53", "986");
  const transactionAmount = amount > 0 ? emv("54", amount.toFixed(2)) : "";
  const countryCode = emv("58", "BR");
  const merchantName = emv("59", sanitizePixText(name, 25) || "MISTICA PRESENTES");
  const merchantCity = emv("60", sanitizePixText(city, 15) || "PINHALZINHO");
  const txId = emv("62", emv("05", "MISTICA"));
  const withoutCrc = payloadFormat + merchantAccount + merchantCategory + currencyCode + transactionAmount + countryCode + merchantName + merchantCity + txId + "6304";
  return withoutCrc + crc16(withoutCrc);
}

function clearQrCanvas() {
  const ctx = pixCanvas.getContext("2d");
  ctx.clearRect(0, 0, pixCanvas.width, pixCanvas.height);
  ctx.fillStyle = "#ffffff";
  ctx.fillRect(0, 0, pixCanvas.width, pixCanvas.height);
}

async function generatePix() {
  const total = getTotal();
  const pixKey = document.getElementById("pixKey").value.trim();
  const merchantName = document.getElementById("merchantName").value.trim();
  const merchantCity = document.getElementById("merchantCity").value.trim();

  if (!cart.length || total <= 0) {
    pixStatus.textContent = "Adicione pelo menos um produto ao carrinho antes de gerar o Pix.";
    return;
  }

  if (!pixKey) {
    pixStatus.textContent = "Informe a chave Pix da loja para gerar o QR Code.";
    return;
  }

  const description = cart.map(item => `${item.qty}x ${item.name}`).join(" | ");
  const payload = buildPixPayload({
    key: pixKey,
    name: merchantName,
    city: merchantCity,
    amount: total,
    description
  });

  pixPayloadInput.value = payload;

  try {
    if (!window.QRCode) {
      throw new Error("Biblioteca de QR Code não carregou.");
    }

    await window.QRCode.toCanvas(pixCanvas, payload, {
      width: 220,
      margin: 2,
      errorCorrectionLevel: "M"
    });

    pixStatus.textContent = `QR Code gerado para ${currency.format(total)}.`;
    saveSale(payload);
  } catch (error) {
    pixStatus.textContent = "Pix copia e cola gerado. Não foi possível desenhar o QR Code agora.";
  }
}

function saveSale(payload) {
  const sales = JSON.parse(localStorage.getItem("misticaSales")) || [];
  sales.unshift({
    date: new Date().toISOString(),
    total: getTotal(),
    items: cart,
    pixPayload: payload
  });
  localStorage.setItem("misticaSales", JSON.stringify(sales.slice(0, 50)));
}

async function copyPix() {
  const payload = pixPayloadInput.value;
  if (!payload) {
    pixStatus.textContent = "Gere o Pix antes de copiar.";
    return;
  }

  try {
    await navigator.clipboard.writeText(payload);
    pixStatus.textContent = "Pix copia e cola copiado.";
  } catch {
    pixPayloadInput.select();
    document.execCommand("copy");
    pixStatus.textContent = "Pix copia e cola selecionado para copiar.";
  }
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

  clients.unshift(client);
  clients = clients.slice(0, 20);
  saveState();
  renderClients();

  clientSaved.hidden = false;
  clientSaved.innerHTML = `<strong>Cliente salvo:</strong> ${client.name} • ${client.whatsapp}`;
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

document.querySelector("[data-menu-toggle]").addEventListener("click", () => {
  document.querySelector("[data-nav-links]").classList.toggle("open");
});

renderProducts();
renderCart();
renderClients();
clearQrCanvas();
