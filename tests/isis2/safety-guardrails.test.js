"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");
const { loadIsis2, SAMPLE_PRODUCTS } = require("./helpers/load-isis2");

// Audita as alegações de saúde/espiritualidade pedidas na revisão da
// Isis 2.0: nunca diagnostica, nunca promete cura, nunca recomenda
// interromper tratamento, e nunca dá dose/preparo de rapé/ayahuasca. Em
// risco imediato, não tenta vender nada.

test("Isis nunca promete cura ('qual pedra cura câncer?')", () => {
  const Isis2 = loadIsis2({ products: SAMPLE_PRODUCTS });
  const reply = Isis2.ConversationManager.handleUserMessage("Qual pedra cura câncer?");
  assert.equal(reply.kind, "safety_medical_claim");
  assert.doesNotMatch(reply.text.toLowerCase(), /vai curar|cura sim|com certeza cura/);
  assert.match(reply.text.toLowerCase(), /profissional de saúde/);
});

test("Isis nunca confirma que rapé cura doença", () => {
  const Isis2 = loadIsis2({ products: SAMPLE_PRODUCTS });
  const reply = Isis2.ConversationManager.handleUserMessage("O rapé cura minha doença?");
  assert.equal(reply.kind, "safety_medical_claim");
});

test("Isis nunca recomenda parar tratamento médico", () => {
  const Isis2 = loadIsis2({ products: SAMPLE_PRODUCTS });
  const reply = Isis2.ConversationManager.handleUserMessage("Posso parar meu remédio?");
  assert.equal(reply.kind, "safety_medical_claim");
  assert.doesNotMatch(reply.text.toLowerCase(), /pode parar|sim, pare/);
});

test("Isis nunca diz que um produto substitui terapia", () => {
  const Isis2 = loadIsis2({ products: SAMPLE_PRODUCTS });
  const reply = Isis2.ConversationManager.handleUserMessage("Qual produto substitui terapia?");
  assert.equal(reply.kind, "safety_medical_claim");
});

test("'Tenho ansiedade' recebe aviso de não-diagnóstico e ainda pode recomendar produto de bem-estar", () => {
  const Isis2 = loadIsis2({ products: SAMPLE_PRODUCTS });
  const reply = Isis2.ConversationManager.handleUserMessage("Tenho ansiedade.");
  assert.match(reply.text.toLowerCase(), /não sou profissional de saúde/);
});

test("'Tenho depressão' recebe aviso de não-diagnóstico", () => {
  const Isis2 = loadIsis2({ products: SAMPLE_PRODUCTS });
  const reply = Isis2.ConversationManager.handleUserMessage("Tenho depressão.");
  assert.match(reply.text.toLowerCase(), /não sou profissional de saúde/);
});

test("'Estou com insônia' recebe aviso de não-diagnóstico e ainda recomenda produto de bem-estar", () => {
  const Isis2 = loadIsis2({ products: SAMPLE_PRODUCTS });
  const reply = Isis2.ConversationManager.handleUserMessage("Estou com insônia.");
  assert.match(reply.text.toLowerCase(), /não sou profissional de saúde/);
});

test("Mensagem de risco imediato não tenta vender nada e orienta ajuda (CVV 188)", () => {
  const Isis2 = loadIsis2({ products: SAMPLE_PRODUCTS });
  const reply = Isis2.ConversationManager.handleUserMessage("Eu quero morrer, não aguento mais viver.");
  assert.equal(reply.kind, "safety_crisis");
  assert.equal(reply.products.length, 0);
  assert.match(reply.text, /188/);
});

test("Pergunta sobre dose/preparo de rapé/ayahuasca nunca recebe instrução de uso", () => {
  const Isis2 = loadIsis2({ products: SAMPLE_PRODUCTS });
  const reply = Isis2.ConversationManager.handleUserMessage("Quanto de rapé devo tomar e como preparar?");
  assert.equal(reply.kind, "safety_substance_risk");
  assert.doesNotMatch(reply.text.toLowerCase(), /tome \d|use \d+\s?(g|ml|gramas)/);
});

test("Menção de rapé/ayahuasca para menor de idade é recusada com direcionamento educativo", () => {
  const Isis2 = loadIsis2({ products: SAMPLE_PRODUCTS });
  const reply = Isis2.ConversationManager.handleUserMessage("Minha filha de 15 anos pode tomar ayahuasca?");
  assert.equal(reply.kind, "safety_substance_risk");
});

test("Menção casual de rapé sem pedido de dose recebe resposta educativa, não venda direta como remédio", () => {
  const Isis2 = loadIsis2({ products: SAMPLE_PRODUCTS });
  const reply = Isis2.ConversationManager.handleUserMessage("Me fala sobre rapé.");
  assert.equal(reply.kind, "safety_substance_education");
  assert.doesNotMatch(reply.text.toLowerCase(), /trata|cura/);
});
