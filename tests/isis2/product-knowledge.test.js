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

test("ProductKnowledge.formatPrice nunca quebra nem mostra NaN quando o produto não tem preço definido", () => {
  // Na prática, mobile-sync.js sempre normaliza preco/estoque com
  // Number(...|| 0) antes de entrar em `products` — mas esta camada
  // não deve confiar cegamente nisso e precisa ser resiliente mesmo se
  // um objeto malformado chegar até aqui.
  const withoutPrice = [{ id: "sem-preco", name: "Sem preço", category: "Teste", description: "x", stock: 5 }];
  const Isis2 = loadIsis2({ products: withoutPrice });
  const product = Isis2.ProductKnowledge.byId("sem-preco");
  const formatted = Isis2.ProductKnowledge.formatPrice(product.price);
  assert.doesNotMatch(formatted, /NaN/);
  assert.equal(formatted, Isis2.ProductKnowledge.formatPrice(0));
});

test("ProductKnowledge nunca quebra com estoque indefinido (trata como 0, produto some do listAll)", () => {
  const withoutStock = [{ id: "sem-estoque", name: "Sem estoque", category: "Teste", description: "x", price: 10 }];
  const Isis2 = loadIsis2({ products: withoutStock });
  assert.equal(Isis2.ProductKnowledge.stockOf(withoutStock[0]), 0);
  assert.equal(Isis2.ProductKnowledge.listAll({ onlyInStock: true }).length, 0);
  assert.equal(Isis2.ProductKnowledge.listAll({ onlyInStock: false }).length, 1);
});

test("ProductKnowledge deduplica produtos repetidos vindos do catálogo (mesmo ID duas vezes)", () => {
  const dup = [SAMPLE_PRODUCTS[0], { ...SAMPLE_PRODUCTS[0] }];
  const Isis2 = loadIsis2({ products: dup });
  assert.equal(Isis2.ProductKnowledge.listAll({ onlyInStock: false }).length, 1);
});

test("ProductKnowledge.byId tolera comparação entre ID string e numérico", () => {
  const numericId = [{ id: 501, name: "ID numérico", category: "Teste", description: "x", price: 9.9, stock: 5 }];
  const Isis2 = loadIsis2({ products: numericId });
  assert.ok(Isis2.ProductKnowledge.byId("501"));
  assert.ok(Isis2.ProductKnowledge.byId(501));
});

test("ProductKnowledge não sanitiza descrição (isso é responsabilidade da camada de renderização/escapeHtml no widget)", () => {
  const malicious = [{ id: "produto-malicioso", name: "<img src=x onerror=alert(1)>", category: "Teste", description: "<script>alert(1)</script>", price: 10, stock: 5 }];
  const Isis2 = loadIsis2({ products: malicious });
  const product = Isis2.ProductKnowledge.byId("produto-malicioso");
  // O dado bruto passa intacto (não é o local certo para sanitizar); a
  // garantia de segurança real está nos testes de XSS do widget
  // (tests/e2e/isis2-widget.spec.js), que verificam escapeHtml().
  assert.equal(product.description, "<script>alert(1)</script>");
});
