"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");
const { loadIsis2, SAMPLE_PRODUCTS } = require("./helpers/load-isis2");

test("RecommendationEngine recomenda incenso para pedido de relaxamento", () => {
  const Isis2 = loadIsis2({ products: SAMPLE_PRODUCTS });
  const detection = Isis2.IntentEngine.detect("Quero um incenso para relaxar.");
  const { products, reasons } = Isis2.RecommendationEngine.recommend(detection);
  assert.ok(products.length > 0);
  assert.ok(reasons[products[0].id]);
});

test("RecommendationEngine respeita orçamento informado", () => {
  const Isis2 = loadIsis2({ products: SAMPLE_PRODUCTS });
  const detection = Isis2.IntentEngine.detect("Quero um presente até R$100.");
  const { products } = Isis2.RecommendationEngine.recommend(detection);
  assert.ok(products.every(p => p.price <= 100));
});

test("RecommendationEngine sugere complementos coerentes", () => {
  const Isis2 = loadIsis2({ products: SAMPLE_PRODUCTS });
  const detection = Isis2.IntentEngine.detect("Quero um incenso para relaxar.");
  const { products, complements } = Isis2.RecommendationEngine.recommend(detection);
  if (products.length && products[0].id === "incenso-natural") {
    assert.ok(complements.some(c => c.product.id === "incensario"));
  }
});

test("RecommendationEngine admite quando não encontra nada (catálogo vazio)", () => {
  const Isis2 = loadIsis2({ products: [] });
  const detection = Isis2.IntentEngine.detect("Quero um incenso para relaxar.");
  const { note, products } = Isis2.RecommendationEngine.recommend(detection);
  assert.equal(note, "catalog_unavailable");
  assert.equal(products.length, 0);
});

test("RecommendationEngine nunca recomenda produto fora do catálogo", () => {
  const Isis2 = loadIsis2({ products: SAMPLE_PRODUCTS });
  const detection = Isis2.IntentEngine.detect("Quero algo místico qualquer.");
  const { products } = Isis2.RecommendationEngine.recommend(detection);
  const validIds = new Set(SAMPLE_PRODUCTS.map(p => p.id));
  products.forEach(p => assert.ok(validIds.has(p.id)));
});
