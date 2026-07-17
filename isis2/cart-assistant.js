// Isis 2.0 — Cart Assistant.
//
// Nunca implementa carrinho próprio: apenas orquestra as funções e o
// estado globais já usados pelo site (app.js — window.addToCart,
// window.removeFromCart, `cart`, `products`, `currency`). Isso garante
// que preço, estoque e regras de negócio (encomenda, limites de
// quantidade, desconto de estoque) continuam sendo decididas por um
// único lugar (app.js) — a Isis nunca calcula preço/estoque por conta
// própria nem confia em números ditos na conversa sem checar o catálogo.
//
// window.addToCart(id) (app.js) lê a quantidade de um <input
// id="qty-<id>"> renderizado na página para ESSE produto específico —
// não aceita quantidade por parâmetro. Em produto.html/kit.html esse
// input só existe para o(s) produto(s) atualmente exibidos: se a Isis
// recomendar um produto que não está com o input renderizado na página
// atual, chamar addToCart direto lançaria erro (leitura de `.value` em
// `null`). Por isso este módulo verifica a presença do input antes de
// agir e devolve um motivo explícito quando não é possível adicionar
// "no local" — nunca falha silenciosamente nem finge sucesso.
(() => {
  window.Isis2 = window.Isis2 || {};
  if (window.Isis2.CartAssistant) return;

  const MAX_QTY = 999;

  // `products` é `const` no topo de app.js: isso cria uma ligação no
  // escopo léxico do script, NÃO uma propriedade em `window` (diferente
  // de `var`). Por isso window.products é sempre undefined num
  // navegador real, mesmo com o catálogo carregado — é preciso checar o
  // identificador solto `products`, com try/catch para páginas onde
  // app.js não está presente.
  function catalog() {
    try {
      return Array.isArray(window.products) ? window.products : (typeof products !== "undefined" ? products : []);
    } catch {
      return [];
    }
  }

  function available() {
    return typeof window.addToCart === "function" && catalog().length > 0;
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

  function findProduct(productId) {
    return catalog().find(item => String(item.id) === String(productId)) || null;
  }

  function qtyInputFor(productId) {
    try {
      return document.getElementById(`qty-${productId}`);
    } catch {
      return null;
    }
  }

  function cartQtyOf(productId) {
    return currentCart().find(item => String(item.id) === String(productId))?.qty || 0;
  }

  // Normaliza a quantidade pedida: nunca negativa, decimal, NaN,
  // infinita ou absurdamente grande (protege contra "adicione 999999999
  // unidades" mesmo antes do estoque real decidir o limite).
  function normalizeQty(rawQty) {
    const value = Math.floor(Number(rawQty));
    if (!Number.isFinite(value) || value < 1) return 1;
    return Math.min(value, MAX_QTY);
  }

  function canAddDirectly(productId) {
    return typeof window.addToCart === "function" && Boolean(qtyInputFor(productId));
  }

  function add(productId, requestedQty = 1) {
    if (typeof window.addToCart !== "function") return { ok: false, reason: "unavailable" };
    if (!findProduct(productId)) return { ok: false, reason: "not_found" };

    const input = qtyInputFor(productId);
    if (!input) return { ok: false, reason: "not_addable_here" };

    const qty = normalizeQty(requestedQty);
    const before = cartQtyOf(productId);
    const previousValue = input.value;
    input.value = String(qty);
    window.addToCart(productId);
    input.value = previousValue;
    const after = cartQtyOf(productId);

    // window.addToCart não lança nem retorna status em caso de recusa
    // (estoque insuficiente, quantidade inválida): a única forma
    // confiável de saber se a ação realmente aconteceu é comparar o
    // carrinho antes/depois, em vez de assumir sucesso.
    if (after <= before) return { ok: false, reason: "rejected_by_store" };

    window.Isis2.ContextMemory?.addCartAdd(productId);
    window.Isis2.Analytics?.track("product_added_to_cart", { item_id: productId, qty: after - before });
    return { ok: true, added: after - before };
  }

  function remove(productId) {
    if (typeof window.removeFromCart !== "function") return { ok: false, reason: "unavailable" };
    if (!cartQtyOf(productId)) return { ok: false, reason: "not_in_cart" };
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
    let checkoutSection = null;
    try {
      checkoutSection = document.querySelector("#checkout");
    } catch {
      /* document indisponível (ambiente de teste sem DOM) */
    }
    return {
      hasItems: itemCount() > 0,
      subtotal: formattedSubtotal(),
      scrollTo: () => checkoutSection?.scrollIntoView({ behavior: "smooth" }),
    };
  }

  window.Isis2.CartAssistant = {
    available,
    canAddDirectly,
    add,
    remove,
    subtotal,
    formattedSubtotal,
    itemCount,
    suggestCheckout,
  };
})();
