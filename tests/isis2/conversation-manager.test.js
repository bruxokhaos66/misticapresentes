"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");
const { loadIsis2, SAMPLE_PRODUCTS } = require("./helpers/load-isis2");

// Cobre literalmente os exemplos de conversa citados no briefing do
// Projeto Isis 2.0, garantindo que cada um produz uma resposta útil
// (recomendação, esclarecimento ou admissão de limite) sem travar.
const EXAMPLE_MESSAGES = [
  "Quero um incenso para relaxar.",
  "Qual pedra ajuda na proteção?",
  "Estou começando no xamanismo.",
  "Quero um presente até R$100.",
  "Tenho ansiedade.",
  "Quero montar um altar.",
  "Qual essência combina com lavanda?",
];

test("ConversationManager responde a todos os exemplos do briefing sem lançar exceção", () => {
  const Isis2 = loadIsis2({ products: SAMPLE_PRODUCTS });
  EXAMPLE_MESSAGES.forEach(message => {
    const reply = Isis2.ConversationManager.handleUserMessage(message);
    assert.ok(reply && typeof reply.text === "string" && reply.text.length > 0, `sem resposta para: ${message}`);
  });
});

test("ConversationManager responde a saudação com boas-vindas e sem produtos", () => {
  const Isis2 = loadIsis2({ products: SAMPLE_PRODUCTS });
  const reply = Isis2.ConversationManager.handleUserMessage("Olá");
  assert.equal(reply.kind, "greeting");
  assert.equal(reply.products.length, 0);
});

test("ConversationManager filtra por orçamento em 'presente até R$100'", () => {
  const Isis2 = loadIsis2({ products: SAMPLE_PRODUCTS });
  const reply = Isis2.ConversationManager.handleUserMessage("Quero um presente até R$100.");
  assert.ok(reply.products.every(p => p.price <= 100));
});

test("ConversationManager admite quando não sabe, em vez de inventar (catálogo vazio)", () => {
  const Isis2 = loadIsis2({ products: [] });
  const reply = Isis2.ConversationManager.handleUserMessage("Quero um incenso para relaxar.");
  assert.equal(reply.kind, "unavailable");
  assert.equal(reply.products.length, 0);
});

test("ConversationManager justifica cada recomendação (Escolhi porque...)", () => {
  const Isis2 = loadIsis2({ products: SAMPLE_PRODUCTS });
  const reply = Isis2.ConversationManager.handleUserMessage("Tenho ansiedade.");
  if (reply.products.length) {
    assert.ok(reply.reasons[reply.products[0].id]);
  }
});

test("ConversationManager.startConversation registra métrica de conversa iniciada", () => {
  const Isis2 = loadIsis2({ products: SAMPLE_PRODUCTS });
  Isis2.ConversationManager.startConversation();
  const metrics = Isis2.Analytics.getMetrics();
  assert.equal(metrics.conversation_started, 1);
});
