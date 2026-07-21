"use strict";
// Nome/sobrenome do COMPRADOR (payer.first_name/last_name) -- campos
// próprios do checkout (#mpBuyerFirstName/#mpBuyerLastName), nunca a partir
// de cardholderName ("Nome impresso no cartão", o titular do cartão -- pode
// ser outra pessoa). normalizarNomeComprador()/nomeCompradorValido() são
// funções puras: normaliza espaços e valida o conjunto de caracteres
// aceitos (letras Unicode, espaço, apóstrofo, hífen), sem inventar nem
// dividir nome nenhum.
//
// Roda num ambiente Node mínimo (mesmo padrão de
// tests/mercadopago-device-id.test.js), sem depender de rede nem de um
// navegador real.

const test = require("node:test");
const assert = require("node:assert/strict");

function makeElement(overrides = {}) {
  return {
    hidden: false,
    disabled: false,
    textContent: "",
    attrs: {},
    setAttribute(k, v) { this.attrs[k] = v; },
    getAttribute(k) { return this.attrs[k] ?? null; },
    removeAttribute(k) { delete this.attrs[k]; },
    addEventListener() {},
    classList: { toggle() {} },
    getBoundingClientRect: () => ({ width: 300, height: 44, top: 100, left: 20 }),
    ...overrides,
  };
}

function loadCheckout() {
  delete require.cache[require.resolve("../v2-mercadopago-checkout.js")];

  const elementsById = {
    mpCardStatus: makeElement(),
    mpInstallmentsNote: makeElement(),
    mpCardSubmit: makeElement(),
    pixPaymentPanel: makeElement(),
    cardPaymentPanel: makeElement(),
  };

  global.window = global;
  delete global.window.MP_DEVICE_SESSION_ID;
  global.window.misticaSiteConfig = { apiBaseUrl: "https://api.example.invalid" };
  global.window.misticaGetCart = () => [{ id: "produto-teste", qty: 1 }];
  global.window.misticaCriarPedido = async () => ({ id: 42, pixTxid: "txid-teste", totalFinal: 199.9 });
  global.window.MercadoPago = function MockMercadoPago() {
    this.cardForm = () => ({ getCardFormData: () => ({}) });
  };
  global.fetch = async () => ({ json: async () => ({ enabled: true, public_key: "TEST-PUBLIC-KEY" }) });
  global.document = {
    readyState: "complete",
    getElementById: (id) => elementsById[id] || null,
    querySelector: () => null,
    querySelectorAll: () => [],
    addEventListener: () => {},
  };
  global.getComputedStyle = () => ({ display: "block", visibility: "visible" });
  global.requestAnimationFrame = (callback) => setTimeout(callback, 0);

  require("../v2-mercadopago-checkout.js");
  return global.window.misticaMercadoPagoCheckout;
}

test("normalizarNomeComprador() colapsa espaços excessivos e remove espaços nas pontas", () => {
  const checkout = loadCheckout();
  assert.equal(checkout.normalizarNomeComprador("  Ana   Maria  "), "Ana Maria");
});

test("normalizarNomeComprador() trata valor ausente/undefined como string vazia", () => {
  const checkout = loadCheckout();
  assert.equal(checkout.normalizarNomeComprador(undefined), "");
  assert.equal(checkout.normalizarNomeComprador(null), "");
});

test("nomeCompradorValido() aceita nome de uma única palavra", () => {
  const checkout = loadCheckout();
  assert.equal(checkout.nomeCompradorValido("Madonna"), true);
});

test("nomeCompradorValido() aceita nome composto com partícula", () => {
  const checkout = loadCheckout();
  assert.equal(checkout.nomeCompradorValido("Maria da Silva"), true);
});

test("nomeCompradorValido() aceita acentos", () => {
  const checkout = loadCheckout();
  assert.equal(checkout.nomeCompradorValido("José Ápice"), true);
});

test("nomeCompradorValido() aceita hífen e apóstrofo", () => {
  const checkout = loadCheckout();
  assert.equal(checkout.nomeCompradorValido("O'Brien-Souza"), true);
});

test("nomeCompradorValido() rejeita números", () => {
  const checkout = loadCheckout();
  assert.equal(checkout.nomeCompradorValido("Ana123"), false);
});

test("nomeCompradorValido() rejeita HTML/tags", () => {
  const checkout = loadCheckout();
  assert.equal(checkout.nomeCompradorValido("<script>alert(1)</script>"), false);
});

test("nomeCompradorValido() rejeita string vazia", () => {
  const checkout = loadCheckout();
  assert.equal(checkout.nomeCompradorValido(""), false);
});

test("nomeCompradorValido() rejeita valor acima de 60 caracteres", () => {
  const checkout = loadCheckout();
  assert.equal(checkout.nomeCompradorValido("a".repeat(61)), false);
});

test("nomeCompradorValido() aceita exatamente 60 caracteres", () => {
  const checkout = loadCheckout();
  assert.equal(checkout.nomeCompradorValido("a".repeat(60)), true);
});
