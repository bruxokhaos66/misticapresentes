"use strict";
// Teste estrutural: confirma que v2-mercadopago-checkout.js monta o
// CardForm do Mercado Pago com `iframe: true`. Sem isso, o SDK espera
// <input> em cardNumber/securityCode/expirationDate (default iframe:
// false) e nunca monta os Secure Fields dentro dos <div> reais do
// checkout -- causa raiz do bug "campos de cartão não aceitam clique nem
// digitação" (ver docs oficiais mercadopago/sdk-js, card-form.md).
//
// Roda num ambiente Node mínimo (mesmo padrão de tests/isis2/helpers/
// load-isis2.js): simula window/document/fetch/MercadoPago o suficiente
// para o script carregar e chamar mpInstance.cardForm(config), sem
// depender de rede nem de um navegador real. Validações que precisam de
// layout real (iframe único por campo, bounding box, ausência de camada
// por cima) ficam em tests/e2e/mercadopago-cardform-mount.spec.js.

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
    ...overrides,
  };
}

function loadCheckout({ enabled = true, publicKey = "TEST-PUBLIC-KEY" } = {}) {
  delete require.cache[require.resolve("../v2-mercadopago-checkout.js")];

  const elementsById = {
    mpCardStatus: makeElement(),
    mpInstallmentsNote: makeElement(),
    mpCardSubmit: makeElement(),
    pixPaymentPanel: makeElement(),
    cardPaymentPanel: makeElement(),
  };

  global.window = global;
  global.window.misticaSiteConfig = { apiBaseUrl: "https://api.example.invalid" };
  global.window.misticaGetCart = () => [{ id: "produto-teste", qty: 1 }];
  global.window.misticaCriarPedido = async () => ({ id: 42, pixTxid: "txid-teste", totalFinal: 199.9 });

  const capturedConfigs = [];
  global.window.MercadoPago = function MockMercadoPago() {
    this.cardForm = (config) => {
      capturedConfigs.push(config);
      return { getCardFormData: () => ({}) };
    };
  };

  global.fetch = async () => ({
    json: async () => ({ enabled, public_key: publicKey }),
  });

  global.document = {
    readyState: "complete",
    getElementById: (id) => elementsById[id] || null,
    querySelector: () => null,
    querySelectorAll: () => [],
    addEventListener: () => {},
  };

  require("../v2-mercadopago-checkout.js");
  return { checkout: global.window.misticaMercadoPagoCheckout, capturedConfigs };
}

test("cardForm() é chamado com iframe: true (Secure Fields exigem isso quando os campos são <div>)", async () => {
  const { checkout, capturedConfigs } = loadCheckout();

  checkout.alternarFormaPagamento("cartao");

  let tentativas = 0;
  while (capturedConfigs.length === 0 && tentativas < 50) {
    await new Promise((resolve) => setTimeout(resolve, 5));
    tentativas += 1;
  }

  assert.equal(capturedConfigs.length, 1, "cardForm() deveria ter sido chamado exatamente uma vez");
  const config = capturedConfigs[0];
  assert.equal(config.iframe, true, "cardForm({ iframe }) deveria ser true");
  assert.equal(config.autoMount, true);
  assert.equal(config.form.cardNumber.id, "mpCardNumber");
  assert.equal(config.form.expirationDate.id, "mpExpirationDate");
  assert.equal(config.form.securityCode.id, "mpSecurityCode");
  assert.equal(config.form.identificationType.id, "mpIdentificationType");
});

test("integração desabilitada: cardForm() nunca é chamado", async () => {
  const { checkout, capturedConfigs } = loadCheckout({ enabled: false });

  checkout.alternarFormaPagamento("cartao");
  await new Promise((resolve) => setTimeout(resolve, 50));

  assert.equal(capturedConfigs.length, 0);
});

test("index.html: cardNumber/expirationDate/securityCode são <div> e identificationType é <select> (contrato exigido pelo SDK)", () => {
  const fs = require("node:fs");
  const path = require("node:path");
  const html = fs.readFileSync(path.join(__dirname, "..", "index.html"), "utf8");

  for (const id of ["mpCardNumber", "mpExpirationDate", "mpSecurityCode"]) {
    const match = html.match(new RegExp(`<div id="${id}"[^>]*>`));
    assert.ok(match, `#${id} deveria ser um <div> (contêiner de iframe do Secure Fields)`);
  }

  const identMatch = html.match(/<select id="mpIdentificationType"[^>]*>/);
  assert.ok(identMatch, "#mpIdentificationType deveria ser um <select> (exigido pela SDK, ver docs card-form.md)");
});
