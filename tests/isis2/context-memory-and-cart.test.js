"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");
const { loadIsis2, SAMPLE_PRODUCTS } = require("./helpers/load-isis2");

test("ContextMemory nunca guarda campos fora da lista permitida (sem dados pessoais)", () => {
  const Isis2 = loadIsis2({ products: SAMPLE_PRODUCTS });
  Isis2.ContextMemory.reset();
  const detection = Isis2.IntentEngine.detect("Tenho ansiedade.");
  const state = Isis2.ContextMemory.registerMessage(detection);
  const allowedKeys = new Set([
    "startedAt", "messageCount", "lastIntentId", "categoryOfInterest",
    "budget", "viewedProductIds", "cartAddedIds", "school",
  ]);
  Object.keys(state).forEach(key => assert.ok(allowedKeys.has(key), `campo inesperado: ${key}`));
  assert.equal(state.lastIntentId, "calma");

  // "school" (Fase 2 — Escola) também é uma lista fechada, sem dado
  // pessoal, nota de avaliação ou texto de conversa.
  const allowedSchoolKeys = new Set([
    "updatedAt", "courseOfInterest", "studentLevel", "viewedCourseSlug",
    "currentModuleId", "currentLessonId", "educationalIntent", "presentedCourseIds",
  ]);
  Object.keys(state.school).forEach(key => assert.ok(allowedSchoolKeys.has(key), `campo inesperado em school: ${key}`));
});

test("ContextMemory.addViewedProduct e addCartAdd deduplicam e persistem", () => {
  const Isis2 = loadIsis2({ products: SAMPLE_PRODUCTS });
  Isis2.ContextMemory.reset();
  Isis2.ContextMemory.addViewedProduct("incenso-natural");
  Isis2.ContextMemory.addViewedProduct("incenso-natural");
  Isis2.ContextMemory.addCartAdd("incenso-natural");
  const state = Isis2.ContextMemory.get();
  assert.deepEqual(state.viewedProductIds, ["incenso-natural"]);
  assert.deepEqual(state.cartAddedIds, ["incenso-natural"]);
});

test("CartAssistant.add usa window.addToCart existente (não duplica lógica de carrinho)", () => {
  const Isis2 = loadIsis2({ products: SAMPLE_PRODUCTS });
  const result = Isis2.CartAssistant.add("incenso-natural");
  assert.equal(result.ok, true);
  assert.equal(Isis2.CartAssistant.itemCount(), 1);
});

test("CartAssistant.subtotal reflete preços reais do catálogo", () => {
  const Isis2 = loadIsis2({ products: SAMPLE_PRODUCTS });
  Isis2.CartAssistant.add("incenso-natural");
  Isis2.CartAssistant.add("vela-ritualistica");
  const subtotal = Isis2.CartAssistant.subtotal();
  assert.equal(subtotal, 12.9 + 18.0);
});

test("CartAssistant.available retorna false quando app.js não carregou", () => {
  const Isis2 = loadIsis2({ products: SAMPLE_PRODUCTS });
  global.window.addToCart = undefined;
  assert.equal(Isis2.CartAssistant.available(), false);
});
