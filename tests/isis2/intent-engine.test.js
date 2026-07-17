"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");
const { loadIsis2, SAMPLE_PRODUCTS } = require("./helpers/load-isis2");

test("IntentEngine detecta intenção de calma/ansiedade", () => {
  const Isis2 = loadIsis2({ products: SAMPLE_PRODUCTS });
  const detection = Isis2.IntentEngine.detect("Tenho ansiedade.");
  assert.equal(detection.primaryIntent.id, "calma");
});

test("IntentEngine detecta intenção de proteção", () => {
  const Isis2 = loadIsis2({ products: SAMPLE_PRODUCTS });
  const detection = Isis2.IntentEngine.detect("Qual pedra ajuda na proteção?");
  assert.equal(detection.primaryIntent.id, "protecao");
});

test("IntentEngine extrai orçamento de 'até R$100'", () => {
  const Isis2 = loadIsis2({ products: SAMPLE_PRODUCTS });
  const detection = Isis2.IntentEngine.detect("Quero um presente até R$100.");
  assert.equal(detection.budget, 100);
  assert.equal(detection.primaryIntent.id, "presente");
});

test("IntentEngine reconhece saudação", () => {
  const Isis2 = loadIsis2({ products: SAMPLE_PRODUCTS });
  const detection = Isis2.IntentEngine.detect("Oi");
  assert.equal(detection.isGreeting, true);
});

test("IntentEngine reconhece agradecimento", () => {
  const Isis2 = loadIsis2({ products: SAMPLE_PRODUCTS });
  const detection = Isis2.IntentEngine.detect("Muito obrigada!");
  assert.equal(detection.isThanks, true);
});

test("IntentEngine detecta intenção de montar altar", () => {
  const Isis2 = loadIsis2({ products: SAMPLE_PRODUCTS });
  const detection = Isis2.IntentEngine.detect("Quero montar um altar.");
  assert.equal(detection.primaryIntent.id, "altar");
});

test("IntentEngine cai em busca por termos livres quando não há intenção mapeada", () => {
  const Isis2 = loadIsis2({ products: SAMPLE_PRODUCTS });
  const detection = Isis2.IntentEngine.detect("Qual essência combina com lavanda?");
  assert.ok(detection.searchTerms.length > 0);
});
