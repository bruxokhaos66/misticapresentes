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

test("'Até R$20' admite quando nenhum produto cabe (não força acima do orçamento)", () => {
  const Isis2 = loadIsis2({ products: SAMPLE_PRODUCTS });
  // menor preço do catálogo de teste é 12,90 (incenso-natural) — sobe o
  // piso pra garantir um caso realmente vazio.
  const semNada = SAMPLE_PRODUCTS.map(p => ({ ...p, price: p.price + 100 }));
  const Isis2b = loadIsis2({ products: semNada });
  const detection = Isis2b.IntentEngine.detect("Quero algo até R$20.");
  const { products, note } = Isis2b.RecommendationEngine.recommend(detection);
  assert.equal(products.length, 0);
  assert.equal(note, "no_match");
});

test("'Até R$20' recomenda quando existe produto elegível mais barato (regressão do bug de orçamento)", () => {
  const Isis2 = loadIsis2({ products: SAMPLE_PRODUCTS });
  const detection = Isis2.IntentEngine.detect("Quero algo até R$20.");
  const { products } = Isis2.RecommendationEngine.recommend(detection);
  assert.ok(products.length > 0, "deveria achar incenso-natural (12,9) ou banho-ervas (16,5)");
  assert.ok(products.every(p => p.price <= 20));
});

test("Produto mais barato do catálogo, mas esgotado: nunca é recomendado", () => {
  const semEstoque = SAMPLE_PRODUCTS.map(p => (p.id === "incenso-natural" ? { ...p, stock: 0 } : p));
  const Isis2 = loadIsis2({ products: semEstoque });
  const detection = Isis2.IntentEngine.detect("Quero um produto barato.");
  const { products } = Isis2.RecommendationEngine.recommend(detection);
  assert.ok(!products.some(p => p.id === "incenso-natural"));
});

test("Produto mais barato do catálogo, mas excluído pelo usuário: nunca é recomendado", () => {
  const Isis2 = loadIsis2({ products: SAMPLE_PRODUCTS });
  const detection = Isis2.IntentEngine.detect("Quero um produto barato, mas não quero incenso.");
  const { products } = Isis2.RecommendationEngine.recommend(detection);
  assert.ok(!products.some(p => p.id === "incenso-natural"));
});

test("Preço inválido/ausente no catálogo nunca quebra a recomendação nem gera NaN no orçamento", () => {
  const comPrecoRuim = [
    { id: "sem-preco", name: "Sem preço", category: "Teste", description: "algo para relaxar", stock: 5 },
    ...SAMPLE_PRODUCTS,
  ];
  const Isis2 = loadIsis2({ products: comPrecoRuim });
  const detection = Isis2.IntentEngine.detect("Quero um presente até R$50.");
  const { products } = Isis2.RecommendationEngine.recommend(detection);
  products.forEach(p => assert.equal(Number.isNaN(Number(p.price)), false));
});

test("Recomendação nunca usa preço extraído do texto da conversa — só o preço real do catálogo", () => {
  const Isis2 = loadIsis2({ products: SAMPLE_PRODUCTS });
  // O usuário "mente" um preço que não existe no catálogo (R$1); a Isis
  // deve continuar respondendo com preços reais, nunca inventar um
  // produto de R$1.
  const detection = Isis2.IntentEngine.detect("Esse incenso não custava R$1?");
  const { products } = Isis2.RecommendationEngine.recommend(detection);
  products.forEach(p => {
    const real = SAMPLE_PRODUCTS.find(sp => sp.id === p.id);
    assert.equal(p.price, real.price);
  });
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

test("'Quero um presente entre R$50 e R$100' respeita a faixa de preço (min e max)", () => {
  const Isis2 = loadIsis2({ products: SAMPLE_PRODUCTS });
  const detection = Isis2.IntentEngine.detect("Quero um presente entre R$50 e R$100.");
  assert.equal(detection.budgetMin, 50);
  assert.equal(detection.budget, 100);
  const { products } = Isis2.RecommendationEngine.recommend(detection);
  products.forEach(p => {
    assert.ok(p.price >= 50 && p.price <= 100, `${p.id} custa ${p.price}, fora da faixa 50-100`);
  });
});

test("'Quero um produto barato' ordena por menor preço primeiro", () => {
  const Isis2 = loadIsis2({ products: SAMPLE_PRODUCTS });
  const detection = Isis2.IntentEngine.detect("Quero um produto barato.");
  const { products } = Isis2.RecommendationEngine.recommend(detection);
  const cheapest = SAMPLE_PRODUCTS.slice().sort((a, b) => a.price - b.price)[0];
  assert.equal(products[0].id, cheapest.id);
});

test("'Quero o produto mais caro' ordena por maior preço primeiro", () => {
  const Isis2 = loadIsis2({ products: SAMPLE_PRODUCTS });
  const detection = Isis2.IntentEngine.detect("Quero o produto mais caro.");
  const { products } = Isis2.RecommendationEngine.recommend(detection);
  const priciest = SAMPLE_PRODUCTS.slice().sort((a, b) => b.price - a.price)[0];
  assert.equal(products[0].id, priciest.id);
});

test("'Não quero lavanda' exclui produtos cujo texto menciona o termo negado", () => {
  const withLavanda = SAMPLE_PRODUCTS.map(p => (p.id === "aromatizador" ? { ...p, description: `${p.description} Aroma de lavanda disponível.` } : p));
  const Isis2 = loadIsis2({ products: withLavanda });
  const detection = Isis2.IntentEngine.detect("Quero uma essência floral, mas não quero lavanda.");
  assert.ok(detection.excludeTerms.includes("lavanda"));
  const { products } = Isis2.RecommendationEngine.recommend(detection);
  assert.ok(!products.some(p => p.id === "aromatizador"));
});

test("'Quero um incenso, mas não tenho incensário' não sugere incensário como complemento", () => {
  const Isis2 = loadIsis2({ products: SAMPLE_PRODUCTS });
  const detection = Isis2.IntentEngine.detect("Quero um incenso, mas já tenho incensario.");
  assert.ok(detection.excludeTerms.includes("incensario"));
  const { complements } = Isis2.RecommendationEngine.recommend(detection);
  assert.ok(!complements.some(c => c.product.id === "incensario"));
});

test("'Já tenho aromatizador' não recomenda outro aromatizador", () => {
  const Isis2 = loadIsis2({ products: SAMPLE_PRODUCTS });
  const detection = Isis2.IntentEngine.detect("Já tenho aromatizador, quero outra coisa para casa perfumada.");
  const { products } = Isis2.RecommendationEngine.recommend(detection);
  assert.ok(!products.some(p => p.id === "aromatizador"));
});

test("'Três produtos com total máximo de R$120' monta uma combinação real dentro do orçamento", () => {
  const Isis2 = loadIsis2({ products: SAMPLE_PRODUCTS });
  const detection = Isis2.IntentEngine.detect("Quero três produtos com total máximo de R$120.");
  assert.deepEqual(detection.combo, { count: 3, budget: 120 });
  const { products, total } = Isis2.RecommendationEngine.recommendCombo(detection);
  assert.ok(products.length <= 3);
  assert.ok(total <= 120, `total ${total} excede 120`);
  const validIds = new Set(SAMPLE_PRODUCTS.map(p => p.id));
  products.forEach(p => assert.ok(validIds.has(p.id)));
});

test("Combo nunca inventa produto: se não achar combinação viável, devolve lista vazia (não força acima do orçamento)", () => {
  const expensive = [{ id: "caro-1", name: "Caro 1", category: "Teste", description: "x", price: 200, stock: 5 }];
  const Isis2 = loadIsis2({ products: expensive });
  const detection = Isis2.IntentEngine.detect("Quero três produtos com total máximo de R$120.");
  const { products, note } = Isis2.RecommendationEngine.recommendCombo(detection);
  assert.equal(products.length, 0);
  assert.equal(note, "no_match");
});
