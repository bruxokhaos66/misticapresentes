const storeConfig = {
  name: "Mística Presentes",
  whatsappNumber: "554999172137",
  instagram: "@misticaeso",
  minStock: 3
};

const PLACEHOLDER_WHATSAPP = "5549999999999";

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

// O navegador só persiste o carrinho mínimo (id + quantidade), via
// window.misticaSecureStorage (site-config.js, carregado antes deste
// script). Nome, preço e classificação de encomenda são recompostos a
// partir do catálogo oficial em reconcileCartWithCatalog().
let cart = (window.misticaSecureStorage ? window.misticaSecureStorage.getCart() : [])
  .map(entry => ({ id: entry.id, qty: entry.qty }));
// Dados pessoais de clientes (nome, CPF, endereço, WhatsApp), vendas,
// estoque e fornecedores nunca são persistidos no navegador: ficam só em
// memória durante a sessão da página. Estoque e catálogo vêm sempre do
// servidor (mobile-sync.js).
let clients = [];
let sales = [];
let stock = createInitialStock();
let suppliers = [];
let lastBackupAt = null;
// O carrinho carregado do navegador só tem id+quantidade: até o catálogo
// oficial confirmar esses produtos (mobile-sync.js), a UI mostra um estado
// de carregamento em vez de itens com nome/preço incompletos ou confiar no
// catálogo estático de fallback acima.
let cartReady = false;

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
const storeNameInput = $("#storeName");
const merchantCityInput = $("#merchantCity");
const publishWarning = $("#publishWarning");
const pixCopyFeedback = $("#pixCopyFeedback");
const pixComprovanteFeedback = $("#pixComprovanteFeedback");
const pixKeyToggleBtn = $("[data-toggle-pix-key]");
const generatePixBtn = $("[data-generate-pix]");
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

function createInitialStock() { return products.reduce((map, product) => { map[product.id] = product.stock; return map; }, {}); }
// Única gravação no navegador: o carrinho mínimo (id + quantidade). Vendas,
// estoque, fornecedores e clientes nunca tocam localStorage.
function saveState() { if (window.misticaSecureStorage) window.misticaSecureStorage.setCart(cart.map(item => ({ id: item.id, qty: item.qty }))); }
function createBackupPayload() { return { store: storeConfig.name, createdAt: new Date().toISOString(), products, sales, stock, suppliers }; }
// Reconstrói o carrinho a partir do catálogo oficial atual: descarta
// produtos inexistentes/inativos, aplica preço e estoque vigentes e
// recalcula a classificação de encomenda. Nunca confia em dados antigos do
// navegador (preço, nome e sob-encomenda salvos localmente).
function reconcileCartWithCatalog() {
  cartReady = true;
  const minimal = cart.map(item => ({ id: item.id, qty: item.qty }));
  cart = minimal.reduce((acc, entry) => {
    const product = products.find(p => p.id === entry.id);
    if (!product) return acc;
    const available = getStock(product.id);
    const qty = Math.max(0, Math.min(Math.floor(Number(entry.qty) || 0), available));
    if (qty < 1) return acc;
    const sob = Boolean(window.misticaEncomenda && window.misticaEncomenda.isSobEncomenda(product));
    acc.push({ id: product.id, name: product.name, price: product.price, qty, sob });
    return acc;
  }, []);
  saveState();
  renderCart();
  renderProducts();
}
window.misticaReconcileCart = reconcileCartWithCatalog;
// Leitura do carrinho atual para outros módulos (ex.: v2-mercadopago-checkout.js)
// sem duplicar o estado do carrinho em outro arquivo. Nunca usado para
// escrita: quem precisa alterar o carrinho usa addToCart/removeFromCart/clearCart.
window.misticaGetCart = () => cart.slice();
window.addEventListener("storage", event => {
  if (window.misticaSecureStorage && event.key === window.misticaSecureStorage.CART_KEY) {
    cart = window.misticaSecureStorage.getCart().map(entry => ({ id: entry.id, qty: entry.qty }));
    reconcileCartWithCatalog();
  }
});
function text(value) { return String(value ?? ""); }
function onlyDigits(value) { return text(value).replace(/\D/g, ""); }
function getStock(productId) { return Number(stock[productId] ?? 0); }
// products[] guarda texto puro (não escapado) vindo do catálogo oficial
// (mobile-sync.js). Todo trecho que injeta esses campos via innerHTML deve
// passar por escapeHtml() antes; quem usa textContent pode usar o valor bruto.
const PRODUCT_FALLBACK_IMAGE = "/assets/images/produto-sem-imagem.webp";
function escapeHtml(value) { return text(value).replace(/[&<>"']/g, char => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[char])); }
window.escapeHtml = escapeHtml;
window.PRODUCT_FALLBACK_IMAGE = PRODUCT_FALLBACK_IMAGE;
function setStatus(message) { if (pixStatus) pixStatus.textContent = message; }
function escapeCsv(value) { return `"${text(value).replace(/"/g, '""')}"`; }
function safeId(value) { return text(value).replace(/[^a-zA-Z0-9_-]/g, ""); }
function buildWhatsappUrl(message) { return `https://wa.me/${storeConfig.whatsappNumber}?text=${encodeURIComponent(message)}`; }

function setupConfig() { const pendente = "Disponível após confirmar o pedido"; if (pixKeyInput) { pixKeyInput.value = pendente; delete pixKeyInput.dataset.valorMascarado; } if (pixKeyToggleBtn) pixKeyToggleBtn.disabled = true; if (merchantNameInput) merchantNameInput.value = pendente; if (storeNameInput) storeNameInput.value = pendente; if (merchantCityInput) merchantCityInput.value = pendente; $$('[data-whatsapp-link]').forEach(link => { link.href = buildWhatsappUrl("Olá, vim pelo site da Mística Presentes e gostaria de atendimento."); }); const warnings = []; if (storeConfig.whatsappNumber === PLACEHOLDER_WHATSAPP) warnings.push("WhatsApp ainda está com número de exemplo."); if (warnings.length && publishWarning) { publishWarning.hidden = false; publishWarning.innerHTML = `<strong>Atenção:</strong> ${warnings.join(" ")}`; } }
function setupFloatingWhatsapp() { if (document.querySelector(".floating-whatsapp")) return; const link = document.createElement("a"); link.className = "floating-whatsapp"; link.href = buildWhatsappUrl("Olá, vim pelo site da Mística Presentes e gostaria de atendimento."); link.target = "_blank"; link.rel = "noopener"; link.setAttribute("aria-label", "Chamar Mística Presentes no WhatsApp"); link.textContent = "☘ WhatsApp"; document.body.appendChild(link); }

// Carrinho flutuante com contador de itens, presente em todas as páginas. Dá
// visibilidade constante ao carrinho (reduz abandono) e leva direto ao
// checkout. Em páginas que não são a home, aponta para index.html#checkout.
function cartItemCount() { return cart.reduce((sum, item) => sum + Number(item.qty || 0), 0); }
function checkoutHref() { const onIndex = /(^|\/)(index\.html)?$/.test(window.location.pathname); return onIndex ? "#checkout" : "index.html#checkout"; }
function setupFloatingCart() {
  if (document.querySelector(".floating-cart")) return;
  const link = document.createElement("a");
  link.className = "floating-cart";
  link.href = checkoutHref();
  link.setAttribute("aria-label", "Abrir carrinho");
  link.innerHTML = `<span class="floating-cart-icon" aria-hidden="true">🛒</span><span class="floating-cart-count" data-cart-count>0</span>`;
  document.body.appendChild(link);
  updateCartCount();
}
function updateCartCount() {
  const badge = document.querySelector("[data-cart-count]");
  const link = document.querySelector(".floating-cart");
  if (!badge || !link) return;
  const count = cartItemCount();
  badge.textContent = String(count);
  link.classList.toggle("has-items", count > 0);
}

function productBadgeText(product) { return String(product.selo || product.tag || ""); }
function isBestSeller(product) { return /mais vendid/i.test(productBadgeText(product)); }
function socialProofHtml(product) {
  const total = Number(product.avaliacoesTotal || 0);
  if (!total) return "";
  const media = Number(product.avaliacoesMedia || 0);
  const cheias = Math.max(0, Math.min(5, Math.round(media)));
  const estrelas = "★★★★★".slice(0, cheias) + "☆☆☆☆☆".slice(cheias);
  return `<div class="product-rating" aria-label="Nota média ${media.toFixed(1)} de 5, ${total} avaliaç${total === 1 ? "ão" : "ões"}"><span class="product-rating-stars" aria-hidden="true">${estrelas}</span><span class="product-rating-count">${media.toFixed(1).replace(".", ",")} (${total})</span></div>`;
}
function productCardHtml(product) {
  const available = getStock(product.id);
  const disabled = available <= 0 ? "disabled" : "";
  const id = safeId(product.id);
  const name = escapeHtml(product.name);
  const imgSrc = escapeHtml(product.imageUrl || PRODUCT_FALLBACK_IMAGE);
  const media = `<div class="product-media-frame"><img class="product-photo" src="${imgSrc}" alt="${name}" loading="lazy" decoding="async" onerror="this.onerror=null;this.src='${PRODUCT_FALLBACK_IMAGE}';this.classList.add('is-fallback');">${isBestSeller(product) ? `<span class="product-badge-best">${escapeHtml(productBadgeText(product))}</span>` : ""}</div>`;
  const descId = `desc-${id}`;
  return `<article class="product-card" data-category="${escapeHtml(product.category || "")}" data-best-seller="${isBestSeller(product)}">${media}<div class="product-card-body"><p class="eyebrow">${escapeHtml(product.category)}</p><h3>${name}</h3>${socialProofHtml(product)}<strong class="product-price">${currency.format(product.price)}</strong><span class="stock-badge ${available <= storeConfig.minStock ? "stock-low" : ""}">Estoque: ${available}</span><div class="qty-row"><input id="qty-${id}" type="number" min="1" max="${available}" step="1" value="1" aria-label="Quantidade de ${name}" ${disabled} /><button class="btn" type="button" onclick="addToCart('${product.id}')" ${disabled}>Adicionar</button></div><button class="btn btn-ghost btn-full" type="button" onclick="buyProductWhatsapp('${product.id}')">Comprar pelo WhatsApp</button><button class="product-desc-toggle" type="button" aria-expanded="${openProductDrawers.has(product.id)}" aria-controls="${descId}" onclick="toggleProductDescription('${product.id}')"><span>Ver descrição</span><svg class="product-desc-chevron" viewBox="0 0 20 20" aria-hidden="true"><path d="M5 7l5 5 5-5" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg></button><div class="product-desc-drawer${openProductDrawers.has(product.id) ? " is-open" : ""}" id="${descId}"${openProductDrawers.has(product.id) ? "" : ' aria-hidden="true"'}><div class="product-desc-drawer-inner"><p>${escapeHtml(product.description)}</p></div></div></div></article>`;
}
const openProductDrawers = new Set();
function toggleProductDescription(productId) {
  // Sem escopo em [data-product-grid]: o mesmo productCardHtml() é usado na
  // vitrine principal (com data-product-grid) e em kit.html (kit-page.js),
  // cujo grid só tem a classe .product-grid, sem esse atributo.
  const card = document.querySelector(`[aria-controls="desc-${safeId(productId)}"]`)?.closest(".product-card");
  if (!card) return;
  const drawer = card.querySelector(".product-desc-drawer");
  const toggle = card.querySelector(".product-desc-toggle");
  const willOpen = !drawer.classList.contains("is-open");
  drawer.classList.toggle("is-open", willOpen);
  toggle.setAttribute("aria-expanded", String(willOpen));
  if (willOpen) drawer.removeAttribute("aria-hidden"); else drawer.setAttribute("aria-hidden", "true");
  if (willOpen) openProductDrawers.add(productId); else openProductDrawers.delete(productId);
}
window.toggleProductDescription = toggleProductDescription;
window.openProductDrawers = openProductDrawers;
function renderProducts() { if (!productGrid) return; productGrid.innerHTML = products.map(productCardHtml).join(""); }
function validateQuantity(rawQty, productId) { const qty = Number.parseInt(rawQty, 10); const available = getStock(productId); const inCart = cart.find(item => item.id === productId)?.qty || 0; if (!Number.isInteger(qty) || qty < 1) return { ok: false, message: "Informe uma quantidade inteira maior que zero." }; if (qty + inCart > available) return { ok: false, message: `Estoque insuficiente. Disponível: ${Math.max(available - inCart, 0)}.` }; return { ok: true, qty }; }
function addToCart(productId) { const product = products.find(item => item.id === productId); if (!product) return; const qtyInput = document.getElementById(`qty-${safeId(productId)}`); const validation = validateQuantity(qtyInput.value, productId); if (!validation.ok) return setStatus(validation.message); const existing = cart.find(item => item.id === productId); const sob = Boolean(window.misticaEncomenda && window.misticaEncomenda.isSobEncomenda(product)); if (existing) { existing.qty += validation.qty; existing.sob = sob; } else cart.push({ id: product.id, name: product.name, price: product.price, qty: validation.qty, sob }); window.misticaResetIdempotencyKey?.(); resetGerarPixStateOnCartChange(); saveState(); renderCart(); renderProducts(); setStatus(`${product.name} adicionado ao carrinho.`); window.misticaTrack?.("add_to_cart", { currency: "BRL", value: product.price * validation.qty, items: [{ item_id: product.id, item_name: product.name, price: product.price, quantity: validation.qty }] }); }
function removeFromCart(productId) { cart = cart.filter(item => item.id !== productId); window.misticaResetIdempotencyKey?.(); resetGerarPixStateOnCartChange(); saveState(); renderCart(); renderProducts(); }
function clearCart() { cart = []; window.misticaCupomAtivo = null; window.misticaResetIdempotencyKey?.(); resetGerarPixStateOnCartChange(); const cupomInput = document.getElementById("cartCoupon"); if (cupomInput) cupomInput.value = ""; const cupomStatus = document.getElementById("couponStatus"); if (cupomStatus) cupomStatus.hidden = true; pixPayloadInput.value = ""; setStatus("Carrinho limpo. Adicione produtos para gerar um novo Pix."); clearQrCanvas(); pararAcompanhamentoPedido(); const el = reservaStatusEl(); if (el) { el.textContent = ""; el.hidden = true; } const statusEl = document.getElementById("pixPedidoStatus"); if (statusEl) statusEl.hidden = true; setCheckoutStep("carrinho"); saveState(); renderCart(); renderProducts(); }
// Identifica itens sob encomenda no carrinho. Prioriza o marcador salvo no
// próprio item (definido no addToCart), com fallback para a regra central caso
// o produto ainda esteja no catálogo carregado.
function cartItemIsEncomenda(item) {
  if (item && typeof item.sob === "boolean") return item.sob;
  const product = products.find(p => p.id === item.id);
  return Boolean(window.misticaEncomenda && window.misticaEncomenda.isSobEncomenda(product || item));
}
function cartHasEncomenda() { return cart.some(cartItemIsEncomenda); }
function updateCheckoutEncomendaBox() {
  const box = document.getElementById("encomendaCheckoutBox");
  if (!box) return;
  const show = cartHasEncomenda();
  box.hidden = !show;
  const check = document.getElementById("encomendaConfirm");
  if (check && !show) check.checked = false;
}
function updatePixPanelVisibility() {
  const panel = document.querySelector(".pix-panel");
  if (panel) panel.hidden = !cart.length;
  const generateBtn = document.querySelector("[data-generate-pix]");
  // Só a ausência de itens no carrinho decide o estado "idle" aqui; os
  // estados "busy" (requisição em curso) e "gerado" (Pix já emitido para
  // este pedido) são controlados por setGerarPixVisualState() e não podem
  // ser reabertos só porque o carrinho foi re-renderizado.
  if (generateBtn && gerarPixEstadoAtual === "idle") generateBtn.disabled = !cart.length;
  const whatsappBtn = document.querySelector("[data-send-sale-whatsapp]");
  if (whatsappBtn) whatsappBtn.disabled = !cart.length;
}
function cartItemLineHtml(item) {
  const subtotal = item.price * item.qty;
  return `<div class="cart-item"><div class="cart-item-detail"><span class="cart-item-name">${escapeHtml(item.name)}</span><span class="cart-item-line"><span>${item.qty} × ${currency.format(item.price)}</span><span class="cart-item-subtotal">Subtotal: ${currency.format(subtotal)}</span></span>${cartItemIsEncomenda(item) ? `<span class="cart-encomenda-tag">${escapeHtml((window.misticaEncomenda && window.misticaEncomenda.BADGE) || "Sob encomenda")}</span>` : ""}</div><button class="cart-remove" type="button" aria-label="Remover ${escapeHtml(item.name)} do carrinho" onclick="removeFromCart('${item.id}')">Remover</button></div>`;
}
function renderCart() { updateCartCount(); renderCrossSell(); updateCheckoutEncomendaBox(); updatePixPanelVisibility(); if (!cartList || !cartTotal) return; if (!cartReady) { cartList.innerHTML = `<div class="cart-item"><span>Carregando catálogo oficial para exibir seu carrinho...</span></div>`; cartTotal.textContent = currency.format(0); return; } if (!cart.length) cartList.innerHTML = `<div class="cart-empty"><p>Seu carrinho está vazio. Explore nossos produtos e encontre algo especial para sua intenção.</p><a class="btn btn-small" href="#produtos">Ver produtos</a></div>`; else cartList.innerHTML = cart.map(cartItemLineHtml).join(""); cartTotal.textContent = currency.format(getTotal()); }

// Cross-sell no carrinho: sugere até 4 produtos disponíveis que ainda não
// estão no carrinho, priorizando categorias diferentes das já escolhidas
// (para compor um "kit"). Aumenta o ticket médio sem pressão nem escassez
// falsa. Só aparece quando há itens no carrinho.
function renderCrossSell() {
  const checkout = document.querySelector("#checkout .checkout-grid");
  if (!checkout) return;
  let box = document.getElementById("cartCrossSell");
  if (!cartReady || !cart.length) { if (box) box.remove(); return; }
  const noCarrinho = new Set(cart.map(item => item.id));
  const sugestoes = products
    .filter(product => !noCarrinho.has(product.id) && getStock(product.id) > 0)
    .slice(0, 4);
  if (!sugestoes.length) { if (box) box.remove(); return; }
  if (!box) {
    box = document.createElement("div");
    box.id = "cartCrossSell";
    box.className = "cross-sell";
    checkout.appendChild(box);
  }
  box.innerHTML = `<p class="eyebrow">Combine seu ritual</p><h3>Quem levou esses, também gostou de</h3><div class="cross-sell-grid">${sugestoes.map(product => `<div class="cross-sell-card"><span aria-hidden="true">${escapeHtml(product.icon || "✨")}</span><strong>${escapeHtml(product.name)}</strong><small>${currency.format(product.price)}</small><button class="btn btn-ghost btn-full" type="button" onclick="addToCart('${product.id}')">Adicionar</button></div>`).join("")}</div>`;
}
function getTotal() { return cart.reduce((sum, item) => sum + item.price * item.qty, 0); }
function renderClients() { if (!clientList) return; if (!clients.length) { clientList.innerHTML = `<div class="client-item"><span>Nenhum cliente cadastrado ainda.</span></div>`; return; } clientList.replaceChildren(); clients.slice(0, 5).forEach(client => { const item = document.createElement("div"); item.className = "client-item"; const name = document.createElement("strong"); name.textContent = client.name; const cpf = document.createElement("span"); cpf.textContent = `CPF: ${client.cpf}`; const whatsapp = document.createElement("span"); whatsapp.textContent = `WhatsApp: ${client.whatsapp}`; const address = document.createElement("span"); address.textContent = client.address; item.append(name, cpf, document.createElement("br"), whatsapp, document.createElement("br"), address); clientList.appendChild(item); }); }
function renderHistory() { if (!salesHistory) return; if (!sales.length) { salesHistory.innerHTML = `<div class="history-item"><span>Nenhuma venda registrada ainda.</span></div>`; return; } salesHistory.innerHTML = sales.slice(0, 10).map(sale => `<div class="history-item"><strong>${currency.format(sale.total)} • ${new Date(sale.date).toLocaleString("pt-BR")}</strong><span>${sale.items.map(item => `${item.qty}x ${item.name}`).join(" | ")}</span><span>Status: ${sale.status}</span></div>`).join(""); }
function renderStock() { if (!stockList) return renderAdminDashboard(); stockList.innerHTML = products.map(product => { const current = getStock(product.id); const low = current <= storeConfig.minStock; return `<div class="stock-item"><div><strong>${escapeHtml(product.name)}</strong><span>${escapeHtml(product.category)}</span></div><span class="stock-badge ${low ? "stock-low" : ""}">${current} un.</span></div>`; }).join(""); renderAdminDashboard(); }

function maskCpf(value) { return onlyDigits(value).slice(0, 11).replace(/(\d{3})(\d)/, "$1.$2").replace(/(\d{3})(\d)/, "$1.$2").replace(/(\d{3})(\d{1,2})$/, "$1-$2"); }
function maskWhatsapp(value) { const digits = onlyDigits(value).slice(0, 11); if (digits.length <= 10) return digits.replace(/(\d{2})(\d)/, "($1) $2").replace(/(\d{4})(\d)/, "$1-$2"); return digits.replace(/(\d{2})(\d)/, "($1) $2").replace(/(\d{5})(\d)/, "$1-$2"); }
function isValidCpf(cpf) { const digits = onlyDigits(cpf); if (digits.length !== 11 || /^(\d)\1{10}$/.test(digits)) return false; let sum = 0; for (let i = 0; i < 9; i++) sum += Number(digits[i]) * (10 - i); let first = (sum * 10) % 11; if (first === 10) first = 0; if (first !== Number(digits[9])) return false; sum = 0; for (let i = 0; i < 10; i++) sum += Number(digits[i]) * (11 - i); let second = (sum * 10) % 11; if (second === 10) second = 0; return second === Number(digits[10]); }
function isValidWhatsapp(value) { const digits = onlyDigits(value); return digits.length === 10 || digits.length === 11; }
function clearQrCanvas() { if (!pixCanvas) return; const ctx = pixCanvas.getContext("2d"); ctx.clearRect(0, 0, pixCanvas.width, pixCanvas.height); ctx.fillStyle = "#ffffff"; ctx.fillRect(0, 0, pixCanvas.width, pixCanvas.height); }
function hasEnoughStockForCart() { return cart.every(item => item.qty <= getStock(item.id)); }
function reduceStockFromCart() { cart.forEach(item => { stock[item.id] = Math.max(0, getStock(item.id) - item.qty); }); }

let reservaTimerInterval = null;
let pedidoStatusPollInterval = null;
// Guarda só o necessário para montar a mensagem do WhatsApp e chamar o
// endpoint de comprovante (id + txid do pedido atual, nunca dado sensível
// de outro cliente): nunca persistido em localStorage/sessionStorage.
let pedidoAtualParaComprovante = null;

// ---------------------------------------------------------------------
// Estado visual do botão "Gerar Pix": puramente de UI (não mexe em regra
// de negócio/backend). "gerado" trava o botão para não recriar o mesmo
// pedido por engano; volta a ficar livre quando o carrinho muda (o Pix
// gerado passa a valer para um pedido diferente), a reserva expira ou o
// pedido é cancelado — os únicos casos em que gerar de novo faz sentido.
let gerarPixEstadoAtual = "idle"; // "idle" | "busy" | "gerado"
function setGerarPixVisualState(state) {
  gerarPixEstadoAtual = state;
  const botao = generatePixBtn || document.querySelector("[data-generate-pix]");
  if (!botao) return;
  botao.dataset.state = state;
  if (state === "busy") {
    botao.disabled = true;
    botao.setAttribute("aria-busy", "true");
    botao.textContent = "Gerando Pix...";
  } else if (state === "gerado") {
    botao.disabled = true;
    botao.setAttribute("aria-busy", "false");
    botao.textContent = "Pix gerado";
  } else {
    botao.disabled = !cart.length;
    botao.setAttribute("aria-busy", "false");
    botao.textContent = "Gerar Pix";
  }
}
window.misticaSetGerarPixVisualState = setGerarPixVisualState;
window.misticaGerarPixBloqueado = () => gerarPixEstadoAtual !== "idle";
// Cart mudou depois do Pix gerado: o Pix exibido não representa mais esse
// carrinho, então destrava o botão para permitir gerar um novo.
function resetGerarPixStateOnCartChange() {
  if (gerarPixEstadoAtual === "gerado") setGerarPixVisualState("idle");
}

// Reabilita "Copiar Pix" e limpa o feedback de cópia da geração anterior
// (ex.: reserva expirada, que via desabilitarAcoesPixInvalido() havia
// desabilitado o botão). Chamada no início de toda nova tentativa de gerar
// Pix, nas duas rotas de checkout (app.js e site-production-guard.js), para
// que o botão nunca fique preso desabilitado sobre um payload novo e válido.
function resetCopyPixButtonState() {
  const copyBtn = document.querySelector("[data-copy-pix]");
  if (copyBtn) copyBtn.disabled = false;
  if (pixCopyFeedback) { pixCopyFeedback.hidden = true; pixCopyFeedback.textContent = ""; }
}
window.misticaResetCopyPixButtonState = resetCopyPixButtonState;

const STEP_LABELS = { carrinho: 1, pagamento: 2, comprovante: 3, confirmacao: 4 };
function setCheckoutStep(stepName) {
  const steps = document.querySelectorAll("#checkoutSteps .checkout-step");
  const alvo = STEP_LABELS[stepName] || 1;
  steps.forEach(step => {
    const ordem = STEP_LABELS[step.dataset.step] || 1;
    step.removeAttribute("aria-current");
    step.removeAttribute("data-done");
    if (ordem === alvo) step.setAttribute("aria-current", "step");
    else if (ordem < alvo) step.setAttribute("data-done", "true");
  });
}
window.misticaSetCheckoutStep = setCheckoutStep;

const PEDIDO_STATUS_LABELS = {
  "Aguardando pagamento": { texto: "Aguardando pagamento", tom: "aguardando" },
  "Pagamento divergente": { texto: "Aguardando pagamento", tom: "aguardando" },
  "Comprovante enviado": { texto: "Pagamento informado — aguardando conferência da loja", tom: "informado" },
  "Pagamento em análise": { texto: "Pagamento informado — aguardando conferência da loja", tom: "informado" },
  "Pagamento confirmado": { texto: "Pagamento confirmado — seu pedido está sendo preparado", tom: "confirmado" },
  "Aguardando encomenda": { texto: "Pagamento confirmado — seu pedido está sendo preparado", tom: "confirmado" },
  "Cancelado": { texto: "Pix expirado — gere um novo pagamento", tom: "expirado" },
};
function pedidoStatusEl() {
  let el = document.getElementById("pixPedidoStatus");
  if (!el && pixStatus) {
    el = document.createElement("p");
    el.id = "pixPedidoStatus";
    el.className = "pix-pedido-status";
    el.setAttribute("role", "status");
    el.setAttribute("aria-live", "polite");
    pixStatus.insertAdjacentElement("afterend", el);
  }
  return el;
}
function setPedidoStatusLabel(statusBackend) {
  const el = pedidoStatusEl();
  if (!el) return;
  const info = PEDIDO_STATUS_LABELS[statusBackend] || { texto: statusBackend || "", tom: "aguardando" };
  el.textContent = info.texto;
  el.dataset.tone = info.tom;
  if (info.tom === "confirmado") setCheckoutStep("confirmacao");
  else if (info.tom === "informado") setCheckoutStep("comprovante");
}
window.misticaSetPedidoStatusLabel = setPedidoStatusLabel;

function reservaStatusEl() {
  let el = document.getElementById("pixReservaStatus");
  if (!el && pixStatus) {
    el = document.createElement("p");
    el.id = "pixReservaStatus";
    el.className = "pix-reserva-status";
    el.setAttribute("role", "status");
    el.setAttribute("aria-live", "polite");
    pixStatus.insertAdjacentElement("afterend", el);
  }
  return el;
}

// Desabilita ações que não fazem mais sentido quando a reserva expira ou o
// pedido é cancelado (copiar Pix, avisar pagamento): o Pix mostrado na tela
// não deve mais ser pago nesse estado. O prazo em si vem sempre do backend
// (pedido.expiraEm) — este relógio só exibe a contagem, nunca a define.
function desabilitarAcoesPixInvalido() {
  const copyBtn = document.querySelector("[data-copy-pix]");
  if (copyBtn) copyBtn.disabled = true;
  const comprovanteBtn = document.querySelector("[data-send-pix-comprovante]");
  if (comprovanteBtn) comprovanteBtn.disabled = true;
  setGerarPixVisualState("idle");
}

function pararAcompanhamentoPedido() {
  if (reservaTimerInterval) clearInterval(reservaTimerInterval);
  if (pedidoStatusPollInterval) clearInterval(pedidoStatusPollInterval);
  reservaTimerInterval = null;
  pedidoStatusPollInterval = null;
}

function iniciarAcompanhamentoPedido(pedido) {
  pararAcompanhamentoPedido();
  const el = reservaStatusEl();
  if (!el) return;
  el.hidden = false;
  el.removeAttribute("data-urgent");
  el.removeAttribute("data-expired");

  if (pedido.expiraEm) {
    const expiraEm = new Date(pedido.expiraEm).getTime();
    const CINCO_MINUTOS_MS = 5 * 60000;
    const atualizarContagem = () => {
      const restanteMs = expiraEm - Date.now();
      if (restanteMs <= 0) {
        el.textContent = "Reserva expirada — o Pix acima não deve mais ser pago. Gere um novo Pix para reservar os produtos novamente.";
        el.dataset.expired = "true";
        el.removeAttribute("data-urgent");
        clearInterval(reservaTimerInterval);
        reservaTimerInterval = null;
        desabilitarAcoesPixInvalido();
        return;
      }
      const minutos = String(Math.floor(restanteMs / 60000)).padStart(2, "0");
      const segundos = String(Math.floor((restanteMs % 60000) / 1000)).padStart(2, "0");
      const urgente = restanteMs < CINCO_MINUTOS_MS;
      el.dataset.urgent = urgente ? "true" : "false";
      el.textContent = urgente
        ? `Atenção: reserva expira em ${minutos}:${segundos}. Pague agora para garantir os produtos.`
        : `Reserva expira em ${minutos}:${segundos}`;
    };
    atualizarContagem();
    reservaTimerInterval = setInterval(atualizarContagem, 1000);
  }

  if (pedido.id && typeof window.misticaConsultarStatusPedido === "function") {
    pedidoStatusPollInterval = setInterval(async () => {
      try {
        const { status } = await window.misticaConsultarStatusPedido(pedido.id, pedido.pixTxid);
        if (status && status !== "Aguardando pagamento") {
          setPedidoStatusLabel(status);
          const cancelado = /cancel/i.test(status);
          if (cancelado) {
            pararAcompanhamentoPedido();
            el.textContent = "Este pedido foi cancelado e o estoque reservado foi liberado.";
            el.dataset.expired = "true";
            el.removeAttribute("data-urgent");
            desabilitarAcoesPixInvalido();
          } else if (/confirmad|encomenda/i.test(status)) {
            pararAcompanhamentoPedido();
          }
        }
      } catch {
        // Falha de rede ao consultar status não deve interromper o checkout;
        // a próxima verificação tenta de novo.
      }
    }, 20000);
  }
}

async function generatePix() {
  // Trava contra clique duplo/geração concorrente: enquanto uma requisição
  // está em andamento ou já existe um Pix gerado válido para este carrinho,
  // um novo clique não deve disparar outro pedido.
  if (gerarPixEstadoAtual === "busy" || gerarPixEstadoAtual === "gerado") return;
  const total = getTotal();
  if (!cart.length || total <= 0) return setStatus("Adicione pelo menos um produto ao carrinho antes de gerar o Pix.");
  if (!hasEnoughStockForCart()) return setStatus("Existe produto no carrinho acima do estoque disponível. Ajuste antes de gerar o Pix.");
  // Só exige a confirmação quando há item sob encomenda; pedidos formados
  // apenas por produtos em estoque seguem o fluxo normal, sem alteração.
  if (cartHasEncomenda()) {
    const check = document.getElementById("encomendaConfirm");
    if (check && !check.checked) {
      const box = document.getElementById("encomendaCheckoutBox");
      if (box) box.hidden = false;
      return setStatus("Confirme que está ciente do produto sob encomenda para continuar.");
    }
  }
  if (typeof window.misticaCriarPedido !== "function") return setStatus("Não foi possível conectar ao servidor para gerar o Pix. Tente novamente em instantes ou fale pelo WhatsApp.");
  window.misticaTrack?.("begin_checkout", { currency: "BRL", value: total, items: cart.map(item => ({ item_id: item.id, item_name: item.name, price: item.price, quantity: item.qty })) });
  pararAcompanhamentoPedido();
  clearQrCanvas();
  pixPayloadInput.value = "";
  resetCopyPixButtonState();
  setGerarPixVisualState("busy");
  setStatus("Enviando pedido e gerando o Pix com o servidor...");
  let pedido;
  try {
    pedido = await window.misticaCriarPedido(cart);
  } catch (error) {
    setGerarPixVisualState("idle");
    return setStatus(error.message || "Não foi possível gerar o Pix agora. Tente novamente ou fale pelo WhatsApp.");
  }
  pixPayloadInput.value = pedido.pixPayload;
  if (pedido.pixInfo) {
    if (pixKeyInput) pixKeyInput.dataset.valorMascarado = pedido.pixInfo.chave_mascarada || "";
    if (merchantNameInput) merchantNameInput.value = pedido.pixInfo.recebedor || "";
    if (storeNameInput) storeNameInput.value = pedido.pixInfo.nome_loja || "";
    if (merchantCityInput) merchantCityInput.value = pedido.pixInfo.cidade || "";
  }
  setPixKeyRevealed(false);
  try {
    if (!window.QRCode) throw new Error("Biblioteca de QR Code não carregou.");
    await window.QRCode.toCanvas(pixCanvas, pedido.pixPayload, { width: 220, margin: 2, errorCorrectionLevel: "M" });
    setStatus(`QR Code gerado para ${currency.format(total)}. Confira valor e recebedor no banco antes de pagar.`);
  } catch {
    setStatus("Pix copia e cola gerado. Não foi possível desenhar o QR Code agora.");
  }
  setGerarPixVisualState("gerado");
  setPedidoStatusLabel("Aguardando pagamento");
  setCheckoutStep("pagamento");
  mostrarBotaoComprovanteWhatsapp(pedido, total);
  iniciarAcompanhamentoPedido(pedido);
  saveSale(pedido);
  window.misticaMobileSync?.syncNow?.();
}

function mostrarBotaoComprovanteWhatsapp(pedido, total) {
  pedidoAtualParaComprovante = { id: pedido.id, pixTxid: pedido.pixTxid || null, total, dataIso: pedido.dataIso };
  comprovanteEnviadoAtual = false;
  const botao = document.querySelector("[data-send-pix-comprovante]");
  const nota = document.getElementById("comprovanteWhatsappNote");
  if (botao) { botao.hidden = false; botao.disabled = false; botao.dataset.state = ""; botao.textContent = "Já realizei o pagamento"; }
  if (nota) nota.hidden = false;
  if (pixComprovanteFeedback) { pixComprovanteFeedback.hidden = true; pixComprovanteFeedback.textContent = ""; }
}

// "Já realizei o pagamento": nunca marca o pedido como pago. Apenas
// registra no servidor (idempotente) que o cliente indicou ter pago e abre
// o WhatsApp da loja com uma mensagem pré-preenchida — sem a chave Pix
// completa, só os dados já públicos do próprio pedido do cliente. A
// confirmação real do pagamento é sempre feita por um administrador.
let comprovanteEnviadoAtual = false;
let comprovanteEnviandoAgora = false;
async function enviarComprovantePixWhatsapp() {
  const pedido = pedidoAtualParaComprovante;
  if (!pedido || !pedido.id) return setStatus("Gere o Pix antes de enviar o comprovante.");
  // Evita clique duplo/envio duplicado: uma vez informado, o botão fica
  // travado até um novo Pix ser gerado (mostrarBotaoComprovanteWhatsapp
  // reseta esse estado).
  if (comprovanteEnviandoAgora || comprovanteEnviadoAtual) return;
  comprovanteEnviandoAgora = true;

  const botao = document.querySelector("[data-send-pix-comprovante]");
  if (botao) botao.disabled = true;

  const dataHora = new Date(pedido.dataIso || Date.now()).toLocaleString("pt-BR");
  const mensagem = `Olá, ${storeConfig.name}! Realizei o pagamento Pix do pedido #${pedido.id}.\n\nValor: ${currency.format(pedido.total)}\nData: ${dataHora}\n\nVou anexar o comprovante nesta conversa.`;

  window.misticaTrack?.("contact_whatsapp", { method: "comprovante_pix", pedido_id: pedido.id, value: pedido.total });

  try {
    if (typeof window.misticaRegistrarComprovanteEnviado === "function") {
      await window.misticaRegistrarComprovanteEnviado(pedido.id, pedido.pixTxid);
    }
  } catch {
    // Falha ao registrar no servidor não deve impedir o cliente de enviar o
    // comprovante pelo WhatsApp; o administrador ainda vê o pedido no painel
    // mesmo sem esse registro (ex.: pedido segue "Aguardando pagamento").
  }

  comprovanteEnviadoAtual = true;
  comprovanteEnviandoAgora = false;
  if (botao) { botao.dataset.state = "enviado"; botao.textContent = "Pagamento informado ✓"; }
  if (pixComprovanteFeedback) {
    pixComprovanteFeedback.hidden = false;
    pixComprovanteFeedback.textContent = "Pagamento informado. Seu pedido será conferido pela loja.";
  }
  setPedidoStatusLabel("Comprovante enviado");
  setCheckoutStep("comprovante");

  window.open(buildWhatsappUrl(mensagem), "_blank", "noopener");
}
// O pix_txid não entra no objeto salvo em `sales`/localStorage: ele já cumpriu
// seu papel (acompanhar o pedido nesta sessão, via `pedido.pixTxid` em
// memória) e não deve ficar persistido permanentemente no navegador.
function saveSale(pedido) { const saleItems = cart.map(item => ({ ...item })); const total = getTotal(); reduceStockFromCart(); sales.unshift({ date: pedido.dataIso || new Date().toISOString(), id: pedido.id, pedidoBackendId: pedido.id, total, items: saleItems, pixPayload: pedido.pixPayload, status: "Aguardando pagamento", estoqueReposto: false }); sales = sales.slice(0, 50); cart = []; saveState(); renderAll(); }
function showPixCopyFeedback(message, tone = "ok") {
  if (!pixCopyFeedback) return setStatus(message);
  pixCopyFeedback.hidden = false;
  pixCopyFeedback.textContent = message;
  pixCopyFeedback.dataset.tone = tone;
}
async function copyPix() {
  const payload = pixPayloadInput.value;
  if (!payload) return setStatus("Gere o Pix antes de copiar.");
  try {
    await navigator.clipboard.writeText(payload);
    showPixCopyFeedback("Código Pix copiado com sucesso! Cole no aplicativo do seu banco para concluir o pagamento.");
  } catch {
    pixPayloadInput.select();
    document.execCommand("copy");
    showPixCopyFeedback("Código Pix selecionado. Copie com Ctrl+C (ou Cmd+C) e cole no aplicativo do seu banco.", "warn");
  }
}
function buildSaleSummary() { if (!cart.length) return ""; const items = cart.map(item => `• ${item.qty}x ${item.name} - ${currency.format(item.price * item.qty)}`).join("\n"); return `Olá, quero finalizar um pedido na ${storeConfig.name}:\n\n${items}\n\nTotal: ${currency.format(getTotal())}`; }
function sendSaleWhatsapp() { if (!cart.length) return setStatus("Adicione produtos ao carrinho para enviar o resumo pelo WhatsApp."); window.misticaTrack?.("contact_whatsapp", { method: "carrinho", currency: "BRL", value: getTotal() }); window.open(buildWhatsappUrl(buildSaleSummary()), "_blank", "noopener"); }
function buyProductWhatsapp(productId) { const product = products.find(item => item.id === productId); if (!product) return; const message = `Olá, tenho interesse neste produto da ${storeConfig.name}:\n\n${product.name}\nValor: ${currency.format(product.price)}\nCategoria: ${product.category}\n\nGostaria de saber disponibilidade e opções parecidas.`; window.misticaTrack?.("contact_whatsapp", { method: "produto", item_id: product.id, item_name: product.name }); window.open(buildWhatsappUrl(message), "_blank", "noopener"); }
function exportCsv(filename, rows) { if (!rows.length) return alert("Não há dados para exportar."); const csv = rows.map(row => row.map(escapeCsv).join(";")).join("\n"); downloadFile(filename, "\ufeff" + csv, "text/csv;charset=utf-8;"); }
function downloadFile(filename, content, type) { const blob = new Blob([content], { type }); const url = URL.createObjectURL(blob); const link = document.createElement("a"); link.href = url; link.download = filename; link.click(); URL.revokeObjectURL(url); }
function exportClients() { const rows = [["Nome", "CPF", "Endereco", "WhatsApp", "Cadastro"]].concat(clients.map(client => [client.name, client.cpf, client.address, client.whatsapp, client.createdAt])); exportCsv("mistica-clientes.csv", rows); }
function exportSales() { const rows = [["ID", "Data", "Itens", "Total", "Status"]].concat(sales.map(sale => [sale.id, sale.date, sale.items.map(item => `${item.qty}x ${item.name}`).join(" | "), sale.total.toFixed(2).replace(".", ","), sale.status])); exportCsv("mistica-vendas.csv", rows); }
function renderAdminDashboard() { const today = new Date(); const startDay = new Date(today.getFullYear(), today.getMonth(), today.getDate()); const startWeek = new Date(startDay); startWeek.setDate(startDay.getDate() - startDay.getDay()); const startMonth = new Date(today.getFullYear(), today.getMonth(), 1); const totalSince = date => sales.filter(s => new Date(s.date) >= date).reduce((sum, s) => sum + Number(s.total || 0), 0); const setText = (id, value) => { const el = document.getElementById(id); if (el) el.textContent = value; }; setText("revenueToday", currency.format(totalSince(startDay))); setText("revenueWeek", currency.format(totalSince(startWeek))); setText("revenueMonth", currency.format(totalSince(startMonth))); setText("salesCount", String(sales.length)); const lowStock = products.filter(product => getStock(product.id) <= storeConfig.minStock); const alerts = document.getElementById("lowStockAlerts"); if (alerts) alerts.innerHTML = lowStock.length ? lowStock.map(product => `<div class="history-item"><strong>${escapeHtml(product.name)}</strong><span>Estoque atual: ${getStock(product.id)} un. Reposição recomendada.</span></div>`).join("") : `<div class="history-item"><span>Nenhum alerta de estoque mínimo.</span></div>`; if (backupStatus) { backupStatus.textContent = lastBackupAt ? `Último backup baixado nesta sessão: ${new Date(lastBackupAt).toLocaleString("pt-BR")}` : "Nenhum backup baixado nesta sessão."; } }
function downloadBackup() { lastBackupAt = new Date().toISOString(); downloadFile(`mistica-backup-${new Date().toISOString().slice(0, 10)}.json`, JSON.stringify(createBackupPayload(), null, 2), "application/json;charset=utf-8;"); renderAdminDashboard(); }
function restoreBackupInfo() { alert("Para restaurar um backup real, será necessário adicionar upload de arquivo JSON ou backend. O backup automático local já está salvo neste navegador."); }
function printReceipt(sale = sales[0]) { if (!sale) return alert("Nenhuma venda para imprimir."); const items = sale.items.map(item => `<tr><td>${item.qty}x ${item.name}</td><td>${currency.format(item.price * item.qty)}</td></tr>`).join(""); const win = window.open("", "_blank", "width=420,height=620"); win.document.write(`<html><head><title>Cupom ${sale.id}</title><style>body{font-family:Arial,sans-serif;padding:18px;color:#111}h1{font-size:20px}table{width:100%;border-collapse:collapse}td{border-bottom:1px dashed #999;padding:8px 0}.total{font-size:20px;font-weight:bold;text-align:right}.small{font-size:12px;color:#555}</style></head><body><h1>${storeConfig.name}</h1><p class="small">Cupom: ${sale.id}<br>${new Date(sale.date).toLocaleString("pt-BR")}</p><table>${items}</table><p class="total">Total: ${currency.format(sale.total)}</p><p>Status: ${sale.status}</p><p class="small">Obrigado pela preferência.</p></body></html>`); win.document.close(); win.focus(); win.print(); }
function sendLastReceiptWhatsapp() { const sale = sales[0]; if (!sale) return alert("Nenhuma venda para enviar."); const items = sale.items.map(item => `• ${item.qty}x ${item.name} - ${currency.format(item.price * item.qty)}`).join("\n"); const message = `Comprovante/Pedido - ${storeConfig.name}\n\nVenda: ${sale.id}\nData: ${new Date(sale.date).toLocaleString("pt-BR")}\n\n${items}\n\nTotal: ${currency.format(sale.total)}\nStatus: ${sale.status}`; window.open(buildWhatsappUrl(message), "_blank", "noopener"); }
function renderSuppliers() { if (!supplierList) return; if (!suppliers.length) { supplierList.innerHTML = `<div class="history-item"><span>Nenhum fornecedor cadastrado ainda.</span></div>`; return; } supplierList.innerHTML = suppliers.map(supplier => `<div class="history-item"><strong>${supplier.name}</strong><span>${supplier.category}</span><span>WhatsApp: ${supplier.whatsapp || "não informado"}</span><span>${supplier.notes || "Sem observação"}</span></div>`).join(""); }
function handleSupplierSubmit(event) { event.preventDefault(); const supplier = { id: `FORN${Date.now()}`, name: $("#supplierName").value.trim(), category: $("#supplierCategory").value.trim(), whatsapp: maskWhatsapp($("#supplierWhatsapp").value.trim()), notes: $("#supplierNotes").value.trim(), createdAt: new Date().toISOString() }; suppliers.unshift(supplier); suppliers = suppliers.slice(0, 100); saveState(); renderSuppliers(); supplierForm.reset(); }
// Cupom de desconto: o código é validado no servidor (POST /api/cupons/validar)
// e o desconto real é sempre recalculado no backend ao gerar o Pix. Aqui só
// guardamos o código aplicado e mostramos uma prévia; o navegador nunca define
// o valor do desconto.
window.misticaCupomAtivo = null;
function couponApiBase() { return String((window.misticaSiteConfig || {}).apiBaseUrl || "https://api.misticaesotericos.com.br").replace(/\/$/, ""); }
function setCouponStatus(message, error = false) {
  const el = document.getElementById("couponStatus");
  if (!el) return;
  el.hidden = false;
  el.textContent = message;
  el.classList.toggle("coupon-status-error", Boolean(error));
  el.classList.toggle("coupon-status-ok", !error);
}
async function applyCoupon() {
  const input = document.getElementById("cartCoupon");
  const codigo = String(input?.value || "").trim().toUpperCase();
  if (!codigo) { window.misticaCupomAtivo = null; setCouponStatus("Digite um código de cupom.", true); return; }
  const subtotal = getTotal();
  if (subtotal <= 0) { setCouponStatus("Adicione produtos ao carrinho antes de aplicar o cupom.", true); return; }
  setCouponStatus("Validando cupom...");
  try {
    const response = await fetch(`${couponApiBase()}/api/cupons/validar`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ codigo, subtotal })
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok || !data.valido) {
      window.misticaCupomAtivo = null;
      setCouponStatus(data.motivo || "Cupom inválido ou expirado.", true);
      return;
    }
    window.misticaCupomAtivo = codigo;
    if (data.frete_gratis) {
      setCouponStatus(`Cupom ${codigo} aplicado: frete grátis. Confirmado ao gerar o Pix.`);
    } else {
      setCouponStatus(`Cupom ${codigo} aplicado: -${currency.format(data.desconto || 0)}. Total: ${currency.format(data.total_com_desconto ?? subtotal)} (confirmado ao gerar o Pix).`);
    }
  } catch {
    window.misticaCupomAtivo = null;
    setCouponStatus("Não foi possível validar o cupom agora. Tente novamente.", true);
  }
}

function unlockAdmin() { adminLoginStatus.hidden = false; adminLoginStatus.textContent = "Use o login do Mística Painel. A senha local foi removida por segurança."; }
function appendIsis(role, message) { const box = document.createElement("div"); box.className = `isis-message ${role}`; box.textContent = message; isisChat.appendChild(box); isisChat.scrollTop = isisChat.scrollHeight; }
function answerIsis() { return "A Isis comercial está carregando. Use os botões de kits e produtos para receber sugestões conectadas ao catálogo."; }
function handleIsisSubmit(event) { if (isisForm?.dataset?.isisCommerce === "1") return; event.preventDefault(); const message = isisInput.value.trim(); if (!message) return; appendIsis("user", message); appendIsis("bot", answerIsis(message)); isisForm.reset(); }

if (clientForm) clientForm.addEventListener("submit", event => { event.preventDefault(); const client = { name: $("#clientName").value.trim(), cpf: $("#clientCpf").value.trim(), address: $("#clientAddress").value.trim(), whatsapp: $("#clientWhatsapp").value.trim(), createdAt: new Date().toISOString() }; if (!isValidCpf(client.cpf)) { clientSaved.hidden = false; clientSaved.textContent = "CPF inválido. Confira os números digitados."; return; } if (!isValidWhatsapp(client.whatsapp)) { clientSaved.hidden = false; clientSaved.textContent = "WhatsApp inválido. Use DDD + número."; return; } clients.unshift(client); clients = clients.slice(0, 20); saveState(); renderClients(); clientSaved.hidden = false; clientSaved.textContent = `Cliente salvo: ${client.name} • ${client.whatsapp}`; clientForm.reset(); });
function renderAll() { renderProducts(); renderCart(); renderClients(); renderHistory(); renderStock(); renderSuppliers(); renderAdminDashboard(); }

// A chave Pix chega do backend já mascarada (nunca a chave completa: ver
// backend/pix.py, info_publica_pix). Este toggle só alterna a EXIBIÇÃO
// dessa versão já mascarada — não existe chave completa no navegador para
// revelar, então o payload do Pix e o backend não são tocados.
let pixKeyRevelada = false;
function setPixKeyRevealed(revelar) {
  pixKeyRevelada = Boolean(revelar);
  if (!pixKeyInput || !pixKeyToggleBtn) return;
  const mascarada = pixKeyInput.dataset.valorMascarado || "";
  pixKeyToggleBtn.disabled = !mascarada;
  pixKeyInput.value = pixKeyRevelada ? mascarada : "•••• (oculta)";
  pixKeyToggleBtn.textContent = pixKeyRevelada ? "Ocultar chave" : "Mostrar chave";
  pixKeyToggleBtn.setAttribute("aria-pressed", String(pixKeyRevelada));
}
function togglePixKeyReveal() { setPixKeyRevealed(!pixKeyRevelada); }
window.misticaSetPixKeyRevealed = setPixKeyRevealed;

$("#clientCpf")?.addEventListener("input", event => { event.target.value = maskCpf(event.target.value); });
$("#clientWhatsapp")?.addEventListener("input", event => { event.target.value = maskWhatsapp(event.target.value); });
$("[data-apply-coupon]")?.addEventListener("click", applyCoupon);
$("[data-clear-cart]")?.addEventListener("click", clearCart);
$("[data-generate-pix]")?.addEventListener("click", generatePix);
$("[data-copy-pix]")?.addEventListener("click", copyPix);
$("[data-send-pix-comprovante]")?.addEventListener("click", enviarComprovantePixWhatsapp);
$("[data-toggle-pix-key]")?.addEventListener("click", togglePixKeyReveal);
$("[data-send-sale-whatsapp]")?.addEventListener("click", sendSaleWhatsapp);
$("[data-export-clients]")?.addEventListener("click", exportClients);
$("[data-export-sales]")?.addEventListener("click", exportSales);
$("[data-print-last-receipt]")?.addEventListener("click", () => printReceipt());
$("[data-send-last-receipt-whatsapp]")?.addEventListener("click", sendLastReceiptWhatsapp);
$("[data-download-backup]")?.addEventListener("click", downloadBackup);
$("[data-restore-backup]")?.addEventListener("click", restoreBackupInfo);
(() => {
  const toggleBtn = $("[data-menu-toggle]");
  const navLinks = $("[data-nav-links]");
  const header = $(".site-header");
  if (!toggleBtn || !navLinks) return;
  const setMenuOpen = open => {
    navLinks.classList.toggle("open", open);
    header?.classList.toggle("menu-open", open);
    toggleBtn.setAttribute("aria-expanded", String(open));
    toggleBtn.setAttribute("aria-label", open ? "Fechar menu" : "Abrir menu");
    document.body.style.overflow = open ? "hidden" : "";
  };
  toggleBtn.addEventListener("click", () => setMenuOpen(!navLinks.classList.contains("open")));
  document.addEventListener("keydown", event => {
    if (event.key === "Escape" && navLinks.classList.contains("open")) setMenuOpen(false);
  });
  document.addEventListener("click", event => {
    if (!navLinks.classList.contains("open")) return;
    if (navLinks.contains(event.target) || toggleBtn.contains(event.target)) return;
    setMenuOpen(false);
  });
  navLinks.addEventListener("click", event => {
    if (event.target.closest("a")) setMenuOpen(false);
  });
})();
if (supplierForm) supplierForm.addEventListener("submit", handleSupplierSubmit);
if (adminLoginForm) adminLoginForm.addEventListener("submit", event => { event.preventDefault(); unlockAdmin(); });
if (isisForm) isisForm.addEventListener("submit", handleIsisSubmit);

setupConfig();
setupFloatingWhatsapp();
setupFloatingCart();
renderAll();
clearQrCanvas();
setCheckoutStep("carrinho");
setGerarPixVisualState("idle");
