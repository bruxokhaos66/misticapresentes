// Isis 2.0 — Cart Assistant.
//
// Nunca implementa carrinho próprio: apenas orquestra as funções e o
// estado globais já usados pelo site (app.js — window.addToCart,
// window.setCartQty, window.removeFromCart, `cart`, `products`,
// `currency`). Isso garante que preço, estoque e regras de negócio
// (encomenda, limites de quantidade, desconto de estoque) continuam
// sendo decididas por um único lugar (app.js) — a Isis nunca calcula
// preço/estoque por conta própria nem confia em números ditos na
// conversa sem checar o catálogo.
//
// window.addToCart(id) (app.js) sempre adiciona 1 unidade -- a vitrine
// não tem mais campo de quantidade (produto pode estar "esgotado" ou não
// disponível na página atual). Este módulo só chama addToCart quando o
// botão "Adicionar ao carrinho" (`[data-add-to-cart]`) do produto está
// de fato renderizado na página atual -- em produto.html/kit.html esse
// botão só existe para o(s) produto(s) atualmente exibidos, então um
// produto recomendado pela Isis que não está na página não pode ser
// adicionado "no escuro". Quando é pedida mais de 1 unidade, o ajuste
// depois do primeiro clique usa window.setCartQty (o mesmo stepper do
// carrinho), com o estoque disponível checado ANTES de tocar no
// carrinho, para nunca aceitar parcialmente um pedido acima do estoque.
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

  // Encontra o botão "Adicionar ao carrinho" do produto na página atual
  // (iterando em vez de montar um seletor CSS com o id do produto, para
  // não depender de escapar caracteres especiais no valor do atributo).
  function addButtonFor(productId) {
    try {
      const buttons = document.querySelectorAll("[data-add-to-cart]");
      for (const button of buttons) {
        const value = button.dataset ? button.dataset.addToCart : button.getAttribute?.("data-add-to-cart");
        if (String(value) === String(productId)) return button;
      }
      return null;
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
    return typeof window.addToCart === "function" && Boolean(addButtonFor(productId));
  }

  function add(productId, requestedQty = 1) {
    if (typeof window.addToCart !== "function") return { ok: false, reason: "unavailable" };
    if (!findProduct(productId)) return { ok: false, reason: "not_found" };

    if (!addButtonFor(productId)) return { ok: false, reason: "not_addable_here" };

    const qty = normalizeQty(requestedQty);
    const before = cartQtyOf(productId);

    // Checa o estoque disponível ANTES de tocar no carrinho: um pedido
    // acima do estoque deve ser recusado por inteiro (nunca adicionar
    // parcialmente o quanto couber) -- mesma regra que validateQuantity
    // já aplica em app.js.
    const available = typeof window.getStock === "function"
      ? window.getStock(productId)
      : (typeof getStock === "function" ? getStock(productId) : Infinity);
    if (qty + before > available) return { ok: false, reason: "rejected_by_store" };

    window.addToCart(productId);
    if (qty > 1 && typeof window.setCartQty === "function") {
      window.setCartQty(productId, before + qty);
    }
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
