"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");
const { loadIsis2, SAMPLE_PRODUCTS } = require("./helpers/load-isis2");

// Cobre a matriz de casos de borda do carrinho pedida na auditoria da
// Isis 2.0: nunca duplica lógica de negócio (só usa window.addToCart /
// removeFromCart já existentes), nunca finge sucesso quando a loja
// recusou a ação, e nunca aceita quantidade inválida.

test("Adicione 2 unidades: respeita a quantidade pedida (dentro do estoque)", () => {
  const Isis2 = loadIsis2({ products: SAMPLE_PRODUCTS });
  const result = Isis2.CartAssistant.add("incenso-natural", 2);
  assert.equal(result.ok, true);
  assert.equal(Isis2.CartAssistant.itemCount(), 2);
});

test("Adicione 999 unidades: recusado pela loja (acima do estoque real)", () => {
  const Isis2 = loadIsis2({ products: SAMPLE_PRODUCTS });
  const result = Isis2.CartAssistant.add("incenso-natural", 999);
  assert.equal(result.ok, false);
  assert.equal(result.reason, "rejected_by_store");
  assert.equal(Isis2.CartAssistant.itemCount(), 0);
});

test("Adicione -1: quantidade negativa nunca é usada como está (normalizada para um mínimo seguro)", () => {
  const Isis2 = loadIsis2({ products: SAMPLE_PRODUCTS });
  const result = Isis2.CartAssistant.add("incenso-natural", -1);
  assert.equal(result.ok, true);
  assert.equal(result.added, 1);
});

test("Adicione um produto inexistente: nunca chama addToCart para ID fora do catálogo", () => {
  const Isis2 = loadIsis2({ products: SAMPLE_PRODUCTS });
  const result = Isis2.CartAssistant.add("produto-fantasma", 1);
  assert.equal(result.ok, false);
  assert.equal(result.reason, "not_found");
  assert.equal(Isis2.CartAssistant.itemCount(), 0);
});

test("Produto esgotou entre a recomendação e o clique em adicionar", () => {
  const zeroed = SAMPLE_PRODUCTS.map(p => (p.id === "incenso-natural" ? { ...p, stock: 0 } : p));
  const Isis2 = loadIsis2({ products: zeroed });
  const result = Isis2.CartAssistant.add("incenso-natural", 1);
  assert.equal(result.ok, false);
  assert.equal(result.reason, "rejected_by_store");
});

test("Produto recomendado sem botão 'Adicionar ao carrinho' renderizado na página atual não crasha, devolve motivo claro", () => {
  // Reproduz produto.html/kit.html: só o produto em foco tem o botão de
  // adicionar renderizado. Um produto recomendado pela Isis que não é o
  // produto da página não deve ser adicionado "no escuro".
  const Isis2 = loadIsis2({ products: SAMPLE_PRODUCTS, addButtonsFor: ["vela-ritualistica"] });
  const result = Isis2.CartAssistant.add("incenso-natural", 1);
  assert.equal(result.ok, false);
  assert.equal(result.reason, "not_addable_here");
  assert.equal(Isis2.CartAssistant.canAddDirectly("incenso-natural"), false);
  assert.equal(Isis2.CartAssistant.canAddDirectly("vela-ritualistica"), true);
});

test("Clique duplo rápido no mesmo botão soma corretamente (sem duplicar por engano)", () => {
  const Isis2 = loadIsis2({ products: SAMPLE_PRODUCTS });
  const first = Isis2.CartAssistant.add("incenso-natural", 1);
  const second = Isis2.CartAssistant.add("incenso-natural", 1);
  assert.equal(first.ok, true);
  assert.equal(second.ok, true);
  assert.equal(Isis2.CartAssistant.itemCount(), 2);
});

test("CartAssistant.remove nunca remove item que não está no carrinho", () => {
  const Isis2 = loadIsis2({ products: SAMPLE_PRODUCTS });
  const result = Isis2.CartAssistant.remove("incenso-natural");
  assert.equal(result.ok, false);
  assert.equal(result.reason, "not_in_cart");
});

test("CartAssistant.subtotal nunca calcula preço a partir de texto da conversa, só do catálogo real", () => {
  const Isis2 = loadIsis2({ products: SAMPLE_PRODUCTS });
  Isis2.CartAssistant.add("incenso-natural", 3);
  assert.equal(Isis2.CartAssistant.subtotal(), 12.9 * 3);
});

test("Adicione 0 unidades: normalizado para o mínimo seguro (1), nunca vira item de quantidade zero", () => {
  const Isis2 = loadIsis2({ products: SAMPLE_PRODUCTS });
  const result = Isis2.CartAssistant.add("incenso-natural", 0);
  assert.equal(result.ok, true);
  assert.equal(result.added, 1);
});

test("Adicione 2.7 unidades (decimal): arredonda para baixo, nunca fraciona um item físico", () => {
  const Isis2 = loadIsis2({ products: SAMPLE_PRODUCTS });
  const result = Isis2.CartAssistant.add("incenso-natural", 2.7);
  assert.equal(result.ok, true);
  assert.equal(result.added, 2);
});

test("Adicione NaN unidades: normalizado para o mínimo seguro, nunca propaga NaN ao carrinho", () => {
  const Isis2 = loadIsis2({ products: SAMPLE_PRODUCTS });
  const result = Isis2.CartAssistant.add("incenso-natural", NaN);
  assert.equal(result.ok, true);
  assert.equal(result.added, 1);
  assert.equal(Number.isNaN(Isis2.CartAssistant.subtotal()), false);
});

test("Adicione Infinity unidades: nunca aceito ao pé da letra (valor não-finito cai no mínimo seguro, não vira pedido infinito)", () => {
  const Isis2 = loadIsis2({ products: SAMPLE_PRODUCTS });
  const result = Isis2.CartAssistant.add("incenso-natural", Infinity);
  // Infinity não é um inteiro finito válido: normalizeQty() trata como
  // entrada inválida e cai no mínimo seguro (1) — nunca tenta pedir uma
  // quantidade infinita ao carrinho real.
  assert.equal(result.ok, true);
  assert.equal(result.added, 1);
});

test("ID malformado (objeto, undefined, string vazia) nunca chega a window.addToCart", () => {
  const Isis2 = loadIsis2({ products: SAMPLE_PRODUCTS });
  [undefined, null, "", {}, ["incenso-natural"]].forEach(idRuim => {
    const result = Isis2.CartAssistant.add(idRuim, 1);
    assert.equal(result.ok, false);
  });
  assert.equal(Isis2.CartAssistant.itemCount(), 0);
});
