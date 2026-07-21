"use strict";
// Device ID (antifraude) -- coletado pelo script oficial do Mercado Pago
// (https://www.mercadopago.com/v2/security.js, ver index.html), que expõe
// window.MP_DEVICE_SESSION_ID de forma assíncrona. obterDeviceId() é o único
// ponto do frontend que lê essa variável: nunca gera um identificador
// próprio, nunca usa fingerprinting externo, nunca grava em
// localStorage/sessionStorage, nunca loga no console, e nunca trava o
// checkout indefinidamente (timeout curto e controlado).
//
// Roda num ambiente Node mínimo (mesmo padrão de
// tests/mercadopago-cardform-config.test.js), sem depender de rede nem de
// um navegador real.

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

test("obterDeviceId() resolve com o valor já disponível em MP_DEVICE_SESSION_ID", async () => {
  const checkout = loadCheckout();
  global.window.MP_DEVICE_SESSION_ID = "abc123-device-session";
  const deviceId = await checkout.obterDeviceId();
  assert.equal(deviceId, "abc123-device-session");
});

test("obterDeviceId() espera o script oficial terminar de coletar (variável aparece depois de um instante)", async () => {
  const checkout = loadCheckout();
  setTimeout(() => {
    global.window.MP_DEVICE_SESSION_ID = "device-tardio";
  }, 50);
  const deviceId = await checkout.obterDeviceId();
  assert.equal(deviceId, "device-tardio");
});

test("obterDeviceId() nunca trava o checkout: resolve null após o timeout se a variável nunca aparecer", async () => {
  const checkout = loadCheckout();
  const inicio = Date.now();
  const deviceId = await checkout.obterDeviceId();
  const decorrido = Date.now() - inicio;
  assert.equal(deviceId, null);
  assert.ok(decorrido < 3000, "obterDeviceId() não deveria demorar mais que um timeout curto e controlado");
});

test("obterDeviceId() ignora valor vazio/em branco (trata como indisponível, nunca envia string vazia)", async () => {
  const checkout = loadCheckout();
  global.window.MP_DEVICE_SESSION_ID = "   ";
  const deviceId = await checkout.obterDeviceId();
  assert.equal(deviceId, null);
});

test("obterDeviceId() nunca loga no console (nem em sucesso, nem em timeout)", async () => {
  const originalLog = console.log;
  const originalWarn = console.warn;
  const originalError = console.error;
  const chamadas = [];
  console.log = (...args) => chamadas.push(args);
  console.warn = (...args) => chamadas.push(args);
  console.error = (...args) => chamadas.push(args);
  try {
    const checkout = loadCheckout();
    global.window.MP_DEVICE_SESSION_ID = "device-nao-deve-logar";
    await checkout.obterDeviceId();
    const checkoutSemDevice = loadCheckout();
    await checkoutSemDevice.obterDeviceId();
  } finally {
    console.log = originalLog;
    console.warn = originalWarn;
    console.error = originalError;
  }
  assert.equal(chamadas.length, 0, "obterDeviceId() nunca deveria logar nada no console");
});

test("obterDeviceId() nunca grava em localStorage/sessionStorage", async () => {
  const chamadasStorage = [];
  global.localStorage = {
    setItem: (...args) => chamadasStorage.push(["localStorage", ...args]),
    getItem: () => null,
    removeItem: () => {},
  };
  global.sessionStorage = {
    setItem: (...args) => chamadasStorage.push(["sessionStorage", ...args]),
    getItem: () => null,
    removeItem: () => {},
  };
  const checkout = loadCheckout();
  global.window.MP_DEVICE_SESSION_ID = "device-nao-deve-persistir";
  await checkout.obterDeviceId();
  const chamadasComDeviceId = chamadasStorage.filter((chamada) =>
    chamada.some((arg) => typeof arg === "string" && arg.includes("device-nao-deve-persistir")),
  );
  assert.equal(chamadasComDeviceId.length, 0, "o valor do Device ID nunca deveria ser gravado em Web Storage");
});
