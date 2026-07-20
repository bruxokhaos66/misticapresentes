const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const vm = require("node:vm");

const guardSource = fs.readFileSync(
  path.join(__dirname, "..", "site-production-guard.js"),
  "utf8",
);

function createHarness({ production = true, createOrder } = {}) {
  const listeners = new Map();
  const elements = new Map();
  const statusElement = { id: "pixStatus", textContent: "", style: {} };
  const pixButton = {
    disabled: false,
    attributes: {},
    setAttribute(name, value) {
      this.attributes[name] = value;
    },
  };
  elements.set("pixStatus", statusElement);

  const document = {
    readyState: "complete",
    querySelector(selector) {
      if (selector === "[data-generate-pix]") return pixButton;
      return null;
    },
    getElementById(id) {
      return elements.get(id) || null;
    },
    addEventListener(type, callback) {
      listeners.set(type, callback);
    },
  };

  let scrubCalls = 0;
  const window = {
    misticaSiteConfig: production
      ? { serverMode: "production", apiBaseUrl: "https://api.example.test/" }
      : {},
    misticaSecureStorage: {
      removeForbiddenKeys() {
        scrubCalls += 1;
      },
    },
    misticaCatalogState: "ready",
    misticaCriarPedido: createOrder,
  };

  const context = {
    window,
    document,
    console,
    cart: [{ id: 1, qty: 1, price: 10 }],
    products: [{ id: 1, apiId: 101, codigo: "P-1" }],
    clients: [{ nome: "Cliente" }],
    sales: [{ id: 1 }],
    suppliers: [{ id: 1 }],
    getTotal: () => 10,
    hasEnoughStockForCart: () => true,
    setTimeout,
    clearTimeout,
    Promise,
  };
  context.globalThis = context;

  vm.createContext(context);
  vm.runInContext(guardSource, context, { filename: "site-production-guard.js" });

  return {
    context,
    window,
    statusElement,
    pixButton,
    get scrubCalls() {
      return scrubCalls;
    },
  };
}

test("guard de produção instala limpeza e remove coleções locais sensíveis", () => {
  const harness = createHarness({ production: true });

  assert.equal(harness.window.misticaProductionGuard.enabled, true);
  assert.equal(harness.window.misticaProductionGuard.apiBase, "https://api.example.test");
  assert.equal(harness.scrubCalls, 1);
  assert.deepEqual(harness.context.clients, []);
  assert.deepEqual(harness.context.sales, []);
  assert.deepEqual(harness.context.suppliers, []);
});

test("guard não é instalado fora do modo de produção", () => {
  const harness = createHarness({ production: false });

  assert.equal(harness.window.misticaProductionGuard, undefined);
  assert.equal(harness.scrubCalls, 0);
  assert.equal(harness.context.cart.length, 1);
});

test("falha ao gerar Pix preserva carrinho e libera o botão", async () => {
  const harness = createHarness({
    production: true,
    createOrder: async () => {
      throw new Error("falha temporária");
    },
  });
  const event = {
    preventDefault() {},
    stopImmediatePropagation() {},
  };

  await harness.window.misticaProductionGuard.checkout(event);

  assert.equal(harness.context.cart.length, 1);
  assert.equal(harness.window.misticaProductionGuard.pendingOrderId, null);
  assert.equal(harness.pixButton.disabled, false);
  assert.match(harness.statusElement.textContent, /falha temporária/i);
});

test("Pix válido mantém carrinho e registra pedido somente em memória", async () => {
  const harness = createHarness({
    production: true,
    createOrder: async () => ({ id: 42, pixPayload: "000201", pixInfo: {} }),
  });
  const event = {
    preventDefault() {},
    stopImmediatePropagation() {},
  };

  await harness.window.misticaProductionGuard.checkout(event);

  assert.equal(harness.context.cart.length, 1);
  assert.equal(harness.window.misticaProductionGuard.pendingOrderId, 42);
  assert.match(harness.statusElement.textContent, /pedido #42 criado/i);
});
