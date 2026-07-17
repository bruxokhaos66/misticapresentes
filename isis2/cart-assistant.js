// Isis 2.0 — Cart Assistant.
//
// Nunca implementa carrinho próprio: apenas orquestra as funções e o
// estado globais já usados pelo site (app.js — window.addToCart,
// window.removeFromCart, `cart`, `products`, `currency`). Isso garante
// que preço, estoque e regras de negócio (encomenda, limites de
// quantidade) continuam sendo decididos por um único lugar (app.js).
(() => {
  window.Isis2 = window.Isis2 || {};
  if (window.Isis2.CartAssistant) return;

  function available() {
    return typeof window.addToCart === "function" && typeof window.products !== "undefined";
  }

  function currentCart() {
    // `cart` é uma variável top-level de app.js, exposta no escopo global
    // porque o script é clássico (não-módulo) — mesmo padrão usado pelo
    // restante do site.
    try {
      return Array.isArray(window.cart) ? window.cart : (typeof cart !== "undefined" ? cart : []);
    } catch {
      return [];
    }
  }

  function add(productId, qty = 1) {
    if (typeof window.addToCart !== "function") return { ok: false, reason: "unavailable" };
    for (let i = 0; i < qty; i += 1) window.addToCart(productId);
    window.Isis2.ContextMemory?.addCartAdd(productId);
    window.Isis2.Analytics?.track("product_added_to_cart", { item_id: productId });
    return { ok: true };
  }

  function remove(productId) {
    if (typeof window.removeFromCart !== "function") return { ok: false, reason: "unavailable" };
    window.removeFromCart(productId);
    return { ok: true };
  }

  function subtotal() {
    const items = currentCart();
    return items.reduce((total, item) => total + Number(item.price || 0) * Number(item.qty || 0), 0);
  }

  function itemCount() {
    return currentCart().reduce((total, item) => total + Number(item.qty || 0), 0);
  }

  function formattedSubtotal() {
    const knowledge = window.Isis2.ProductKnowledge;
    return knowledge ? knowledge.formatPrice(subtotal()) : `R$ ${subtotal().toFixed(2)}`;
  }

  function suggestCheckout() {
    window.Isis2.Analytics?.track("checkout_suggested", {});
    const checkoutSection = document.querySelector("#checkout");
    return {
      hasItems: itemCount() > 0,
      subtotal: formattedSubtotal(),
      scrollTo: () => checkoutSection?.scrollIntoView({ behavior: "smooth" }),
    };
  }

  window.Isis2.CartAssistant = {
    available,
    add,
    remove,
    subtotal,
    formattedSubtotal,
    itemCount,
    suggestCheckout,
  };
})();
