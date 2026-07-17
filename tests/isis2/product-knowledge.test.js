"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");
const { loadIsis2, SAMPLE_PRODUCTS } = require("./helpers/load-isis2");

test("ProductKnowledge nunca inventa produtos: só retorna o catálogo real", () => {
  const Isis2 = loadIsis2({ products: SAMPLE_PRODUCTS });
  const all = Isis2.ProductKnowledge.listAll();
  assert.equal(all.length, SAMPLE_PRODUCTS.length);
  assert.equal(Isis2.ProductKnowledge.byId("produto-inexistente"), null);
});

test("ProductKnowledge.listAll respeita estoque zerado", () => {
  const zeroed = SAMPLE_PRODUCTS.map(p => (p.id === "incenso-natural" ? { ...p, stock: 0 } : p));
  const Isis2 = loadIsis2({ products: zeroed });
  const all = Isis2.ProductKnowledge.listAll({ onlyInStock: true });
  assert.ok(!all.some(p => p.id === "incenso-natural"));
});

test("ProductKnowledge.searchByTerms ranqueia por relevância textual", () => {
  const Isis2 = loadIsis2({ products: SAMPLE_PRODUCTS });
  const found = Isis2.ProductKnowledge.searchByTerms(["incenso"]);
  assert.ok(found.length >= 1);
  assert.equal(found[0].id, "incenso-natural");
});

test("ProductKnowledge.byBudget filtra por orçamento", () => {
  const Isis2 = loadIsis2({ products: SAMPLE_PRODUCTS });
  const found = Isis2.ProductKnowledge.byBudget(20);
  assert.ok(found.every(p => p.price <= 20));
  assert.ok(found.some(p => p.id === "incenso-natural"));
  assert.ok(!found.some(p => p.id === "presente-mistico"));
});

test("ProductKnowledge.getComplements só sugere itens em estoque", () => {
  const Isis2 = loadIsis2({ products: SAMPLE_PRODUCTS });
  const complements = Isis2.ProductKnowledge.getComplements("incenso-natural");
  assert.ok(complements.length > 0);
  assert.equal(complements[0].product.id, "incensario");
});

test("ProductKnowledge.formatPrice usa formatação em reais", () => {
  const Isis2 = loadIsis2({ products: SAMPLE_PRODUCTS });
  assert.match(Isis2.ProductKnowledge.formatPrice(12.9), /R\$/);
});
