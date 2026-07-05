(() => {
  function norm(value) {
    return String(value || "").normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase().trim();
  }

  function money(value) {
    return typeof currency !== "undefined" ? currency.format(Number(value || 0)) : `R$ ${Number(value || 0).toFixed(2).replace(".", ",")}`;
  }

  function listProducts() {
    return typeof products !== "undefined" && Array.isArray(products) ? products : [];
  }

  function findProduct(command) {
    const text = norm(command);
    return listProducts().find(product => {
      const name = norm(product.name);
      return text.includes(name) || name.split(" ").some(part => part.length > 3 && text.includes(part));
    });
  }

  function qty(command) {
    const match = norm(command).match(/(\d+)/);
    return match ? Math.max(1, Number.parseInt(match[1], 10)) : 1;
  }

  function totalCart() {
    return typeof getTotal === "function" ? getTotal() : 0;
  }

  function addToSale(command) {
    const product = findProduct(command);
    if (!product) return "Produto nao encontrado.";
    const amount = qty(command);
    const available = typeof getStock === "function" ? getStock(product.id) : Number(stock?.[product.id] || product.stock || 0);
    if (available < amount) return `Estoque insuficiente de ${product.name}. Disponivel: ${available}.`;
    const existing = cart.find(item => item.id === product.id);
    if (existing) existing.qty += amount;
    else cart.push({ id: product.id, name: product.name, price: product.price, qty: amount });
    if (typeof saveState === "function") saveState();
    if (typeof renderCart === "function") renderCart();
    if (typeof renderProducts === "function") renderProducts();
    return `${amount}x ${product.name} no carrinho. Total: ${money(totalCart())}.`;
  }

  function addStock(command) {
    const product = findProduct(command);
    if (!product) return "Produto nao encontrado no estoque.";
    const amount = qty(command);
    const current = typeof getStock === "function" ? getStock(product.id) : Number(stock?.[product.id] || product.stock || 0);
    const next = current + amount;
    if (typeof stock !== "undefined") stock[product.id] = next;
    product.stock = next;
    if (typeof saveState === "function") saveState();
    if (typeof renderAll === "function") renderAll();
    return `${product.name}: estoque atualizado para ${next}.`;
  }

  function cartText() {
    if (!Array.isArray(cart) || !cart.length) return "Carrinho vazio.";
    return `${cart.map(item => `${item.qty}x ${item.name}`).join(" | ")} Total: ${money(totalCart())}.`;
  }

  const oldAnswer = window.answerIsis;
  window.answerIsis = function answerIsisPlus(command) {
    const text = norm(command);
    if (text.includes("limpar carrinho")) {
      if (typeof clearCart === "function") clearCart();
      return "Carrinho limpo.";
    }
    if (text.includes("entrada estoque") || text.includes("adicionar estoque")) return addStock(command);
    if (text.includes("vender") || text.includes("vende") || text.includes("carrinho")) {
      if (text.includes("total") || text.includes("mostrar")) return cartText();
      return addToSale(command);
    }
    if (text.includes("clientes vip") && window.misticaCustomerVip?.message) return window.misticaCustomerVip.message();
    if (text.includes("produtos encalhados") && window.misticaSlowProducts?.message) return window.misticaSlowProducts.message();
    if (text.includes("fechamento") && window.misticaCashClosing?.message) return window.misticaCashClosing.message();
    if (text.includes("pagamento") && window.misticaPaymentReport?.message) return window.misticaPaymentReport.message();
    return typeof oldAnswer === "function" ? oldAnswer(command) : "Comando nao reconhecido.";
  };
})();
