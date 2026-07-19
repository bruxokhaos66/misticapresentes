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
    // Este ambiente Node não tem layout real -- simula um painel já visível
    // e com tamanho (usado por aguardarPainelCartaoVisivel em
    // v2-mercadopago-checkout.js). Validações de layout/geometria real
    // ficam em tests/e2e/mercadopago-cardform-mount.spec.js e
    // tests/e2e/mercadopago-cardform-viewport.spec.js.
    getBoundingClientRect: () => ({ width: 300, height: 44, top: 100, left: 20 }),
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
  const capturedConstructorOptions = [];
  global.window.MercadoPago = function MockMercadoPago(_publicKey, options) {
    capturedConstructorOptions.push(options);
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
  global.getComputedStyle = () => ({ display: "block", visibility: "visible" });
  global.requestAnimationFrame = (callback) => setTimeout(callback, 0);

  require("../v2-mercadopago-checkout.js");
  return { checkout: global.window.misticaMercadoPagoCheckout, capturedConfigs, capturedConstructorOptions };
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

test("cardNumber/expirationDate/securityCode recebem style de alto contraste (texto claro sobre fundo escuro do tema)", async () => {
  const { checkout, capturedConfigs } = loadCheckout();

  checkout.alternarFormaPagamento("cartao");

  let tentativas = 0;
  while (capturedConfigs.length === 0 && tentativas < 50) {
    await new Promise((resolve) => setTimeout(resolve, 5));
    tentativas += 1;
  }

  assert.equal(capturedConfigs.length, 1);
  const { form } = capturedConfigs[0];

  for (const campo of ["cardNumber", "expirationDate", "securityCode"]) {
    const style = form[campo].style;
    assert.ok(style, `form.${campo}.style deveria existir`);
    // Só propriedades documentadas em
    // github.com/mercadopago/sdk-js/blob/main/docs/fields.md#style --
    // backgroundColor/caret/estados (:focus/:valid/:invalid) NÃO existem
    // nessa API (o iframe é de outra origem); quem resolve fundo/borda é
    // o wrapper .mp-secure-field em v2-mercadopago-checkout.css.
    assert.equal(style.color, "#F7E7BE", `form.${campo}.style.color`);
    assert.equal(style.placeholderColor, "rgba(247, 231, 190, 0.55)", `form.${campo}.style.placeholderColor`);
    assert.equal(style.fontSize, "16px", `form.${campo}.style.fontSize`);
    assert.equal(style.fontWeight, "500", `form.${campo}.style.fontWeight`);
    assert.ok(style.fontFamily, `form.${campo}.style.fontFamily`);
    assert.equal("backgroundColor" in style, false, `form.${campo}.style não deveria ter backgroundColor (não suportado pela API)`);
    // Texto preenchido precisa ser visualmente distinto do placeholder --
    // não pode ser a mesma cor (senão o campo preenchido pareceria vazio).
    assert.notEqual(style.color, style.placeholderColor, `form.${campo}: color e placeholderColor devem ser diferentes`);
  }

  // Os três campos usam exatamente o mesmo objeto de estilo (mesma
  // identidade) -- evita divergência acidental entre eles no futuro.
  assert.strictEqual(form.cardNumber.style, form.expirationDate.style);
  assert.strictEqual(form.cardNumber.style, form.securityCode.style);
});

test("new MercadoPago() é chamado com trackingDisabled: true e não desativa advancedFraudPrevention", async () => {
  const { checkout, capturedConstructorOptions } = loadCheckout();

  checkout.alternarFormaPagamento("cartao");

  let tentativas = 0;
  while (capturedConstructorOptions.length === 0 && tentativas < 50) {
    await new Promise((resolve) => setTimeout(resolve, 5));
    tentativas += 1;
  }

  assert.equal(capturedConstructorOptions.length, 1, "new MercadoPago() deveria ter sido chamado exatamente uma vez");
  const options = capturedConstructorOptions[0];
  // trackingDisabled: true -- opção oficial (ver README @mercadopago/sdk-js)
  // mais próxima do script inline de telemetria bloqueado pela CSP; ver
  // docs/admin/CSP.md para o que foi/não foi confirmado sobre o efeito real.
  assert.equal(options.trackingDisabled, true);
  // advancedFraudPrevention nunca deve ser passado como false por este
  // arquivo -- é uma opção de prevenção de fraude, não de telemetria, e
  // desativá-la tem impacto direto em aprovação/risco (não decidido aqui).
  assert.equal(Object.prototype.hasOwnProperty.call(options, "advancedFraudPrevention"), false);
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

test("v2-mercadopago-checkout.css: wrapper dos Secure Fields e <select> de parcelas usam o tema escuro sempre (sem depender do SO)", () => {
  const fs = require("node:fs");
  const path = require("node:path");
  const cssComComentarios = fs.readFileSync(path.join(__dirname, "..", "v2-mercadopago-checkout.css"), "utf8");
  // Remove comentários /* ... */ antes de checar uso real de CSS -- os
  // comentários deste arquivo explicam a mudança em prosa e citam os
  // próprios termos que este teste procura (ex.: "var(--border...)",
  // "prefers-color-scheme"), o que geraria falso-positivo se checássemos o
  // arquivo com comentários.
  const css = cssComComentarios.replace(/\/\*[\s\S]*?\*\//g, "");

  // O bug reportado (texto/campo claro destoando do checkout escuro) vinha
  // de var(--border, #d8d0ea) -- --border não existe em v2.css (só em
  // styles.css, que index.html não carrega), então sempre caía no fallback
  // claro -- e de depender de prefers-color-scheme (SO), quando o resto do
  // tema é sempre escuro (não muda com o SO em nenhum outro lugar do site).
  assert.equal(/@media[^{]*prefers-color-scheme/.test(css), false, "não deveria mais ter um @media prefers-color-scheme (comentários explicando o porquê são ok)");
  assert.equal(/var\(--border/.test(css), false, "--border não existe em v2.css -- não usar essa variável aqui");
  assert.equal(/\.mp-secure-field\s*\{[^}]*background:\s*#fff/.test(css), false, ".mp-secure-field não deveria ter fundo branco fixo");

  const wrapperMatch = css.match(/\.mp-secure-field\s*\{([^}]*)\}/);
  assert.ok(wrapperMatch, ".mp-secure-field deveria existir");
  assert.match(wrapperMatch[1], /background:\s*rgba\(0,\s*0,\s*0,\s*\.28\)/, ".mp-secure-field deveria usar o mesmo fundo escuro dos <input> do tema");

  const selectMatch = css.match(/\.card-panel select\s*\{([^}]*)\}/);
  assert.ok(selectMatch, ".card-panel select deveria existir (senão o <select id=\"mpInstallments\"> usa o combo box claro padrão do navegador)");
  assert.match(selectMatch[1], /background:\s*rgba\(0,\s*0,\s*0,\s*\.28\)/, ".card-panel select deveria ter fundo escuro");
  assert.match(selectMatch[1], /color:\s*var\(--cream/, ".card-panel select deveria ter texto claro");
});
