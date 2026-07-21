"use strict";
// Testes das duas correções aplicadas em v2-mercadopago-checkout.js:
//
// 1) normalizarMensagemErro() -- nunca deixa "[object Object]"/JSON bruto
//    chegar à tela do cliente, qualquer que seja o formato do erro (string,
//    Error, objeto do backend, array de erros de validação do FastAPI).
// 2) definirEstadoParcelas() -- o <select id="mpInstallments"> sempre tem um
//    estado visível e coerente (placeholder desabilitado antes do cartão
//    ser identificado, "carregando", erro, vazio, ou habilitado com as
//    opções que o próprio SDK oficial inseriu).
//
// Mesmo ambiente Node mínimo de tests/mercadopago-cardform-config.test.js
// (sem depender de rede nem de navegador real).

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

function makeOption() {
  const attrs = {};
  return {
    tagName: "OPTION",
    value: "",
    textContent: "",
    disabled: false,
    selected: false,
    setAttribute(k, v) { attrs[k] = v; },
    getAttribute(k) { return attrs[k] ?? null; },
  };
}

function makeSelectElement() {
  let children = [];
  return {
    tagName: "SELECT",
    disabled: false,
    attrs: {},
    setAttribute(k, v) { this.attrs[k] = v; },
    getAttribute(k) { return this.attrs[k] ?? null; },
    appendChild(child) {
      children.push(child);
      child.remove = () => { children = children.filter((c) => c !== child); };
    },
    querySelectorAll(selector) {
      if (selector === 'option[data-placeholder="true"]') {
        return children.filter((c) => c.getAttribute("data-placeholder") === "true");
      }
      return [];
    },
    get options() { return children; },
    set innerHTML(_v) { children = []; },
    get innerHTML() { return ""; },
  };
}

function loadCheckout({ enabled = true, publicKey = "TEST-PUBLIC-KEY" } = {}) {
  delete require.cache[require.resolve("../v2-mercadopago-checkout.js")];

  const mpInstallmentsEl = makeSelectElement();
  const elementsById = {
    mpCardStatus: makeElement(),
    mpInstallmentsNote: makeElement(),
    mpCardSubmit: makeElement(),
    pixPaymentPanel: makeElement(),
    cardPaymentPanel: makeElement(),
    mpInstallments: mpInstallmentsEl,
  };

  global.window = global;
  global.window.misticaSiteConfig = { apiBaseUrl: "https://api.example.invalid" };
  global.window.misticaGetCart = () => [{ id: "produto-teste", qty: 1 }];
  global.window.misticaCriarPedido = async () => ({ id: 42, pixTxid: "txid-teste", totalFinal: 199.9 });

  const capturedConfigs = [];
  global.window.MercadoPago = function MockMercadoPago() {
    this.cardForm = (config) => {
      capturedConfigs.push(config);
      return { getCardFormData: () => ({}), unmount() {} };
    };
  };

  global.fetch = async () => ({ json: async () => ({ enabled, public_key: publicKey }) });

  global.document = {
    readyState: "complete",
    createElement: (tag) => (tag === "option" ? makeOption() : makeElement()),
    getElementById: (id) => elementsById[id] || null,
    querySelector: () => null,
    querySelectorAll: () => [],
    addEventListener: () => {},
  };
  global.getComputedStyle = () => ({ display: "block", visibility: "visible" });
  global.requestAnimationFrame = (callback) => setTimeout(callback, 0);

  require("../v2-mercadopago-checkout.js");
  return {
    checkout: global.window.misticaMercadoPagoCheckout,
    capturedConfigs,
    mpInstallmentsEl,
    elementsById,
  };
}

// ---------------------------------------------------------------------
// normalizarMensagemErro
// ---------------------------------------------------------------------

test("normalizarMensagemErro: string é preservada como está", () => {
  const { checkout } = loadCheckout();
  assert.equal(checkout.normalizarMensagemErro("Falha de conexão."), "Falha de conexão.");
});

test("normalizarMensagemErro: objeto Error vira mensagem amigável (usa .message)", () => {
  const { checkout } = loadCheckout();
  const erro = new Error("Não foi possível gerar o token do cartão.");
  assert.equal(checkout.normalizarMensagemErro(erro), "Não foi possível gerar o token do cartão.");
});

test("normalizarMensagemErro: objeto do backend ({detail: string}) vira a mensagem do backend", () => {
  const { checkout } = loadCheckout();
  assert.equal(checkout.normalizarMensagemErro({ detail: "Cabeçalho Idempotency-Key obrigatório." }), "Cabeçalho Idempotency-Key obrigatório.");
});

test("normalizarMensagemErro: array de erros de validação do FastAPI/Pydantic NUNCA vira [object Object]", () => {
  const { checkout } = loadCheckout();
  // Formato real de uma resposta 422 do FastAPI: detail é um array de
  // objetos {loc, msg, type}. new Error(array).message costumava virar
  // "[object Object]" -- esta é a origem confirmada do bug reportado.
  const respostaComoSeriaNoFrontend = {
    detail: [
      { loc: ["body", "payer", "endereco_cobranca", "uf"], msg: "Value error, UF inválida.", type: "value_error" },
    ],
  };
  const mensagem = checkout.normalizarMensagemErro(respostaComoSeriaNoFrontend);
  assert.equal(mensagem, "UF inválida.");
  assert.notEqual(mensagem, "[object Object]");
});

test("normalizarMensagemErro: array com múltiplos erros pega a primeira mensagem aproveitável", () => {
  const { checkout } = loadCheckout();
  const mensagem = checkout.normalizarMensagemErro({
    detail: [
      { msg: "Value error, CEP inválido: informe 8 dígitos." },
      { msg: "Value error, UF inválida." },
    ],
  });
  assert.equal(mensagem, "CEP inválido: informe 8 dígitos.");
});

test("normalizarMensagemErro: cause aninhado é seguido", () => {
  const { checkout } = loadCheckout();
  const mensagem = checkout.normalizarMensagemErro({ error: { cause: { message: "Pagamento recusado pelo emissor." } } });
  assert.equal(mensagem, "Pagamento recusado pelo emissor.");
});

test("normalizarMensagemErro: objeto vazio usa o fallback genérico", () => {
  const { checkout } = loadCheckout();
  assert.equal(
    checkout.normalizarMensagemErro({}),
    "Não foi possível processar o pagamento. Revise os dados e tente novamente ou escolha Pix.",
  );
});

test("normalizarMensagemErro: null/undefined usam o fallback (ou o fallback customizado quando informado)", () => {
  const { checkout } = loadCheckout();
  assert.equal(
    checkout.normalizarMensagemErro(null),
    "Não foi possível processar o pagamento. Revise os dados e tente novamente ou escolha Pix.",
  );
  assert.equal(checkout.normalizarMensagemErro(undefined, "Falha de conexão. Verifique sua internet e tente novamente."), "Falha de conexão. Verifique sua internet e tente novamente.");
});

test("normalizarMensagemErro: nunca deixa passar algo com cara de token/segredo do Mercado Pago", () => {
  const { checkout } = loadCheckout();
  const mensagem = checkout.normalizarMensagemErro({ detail: "Erro ao autenticar com APP_USR-1234567890abcdef-teste" });
  assert.equal(mensagem, "Não foi possível processar o pagamento. Revise os dados e tente novamente ou escolha Pix.");
  assert.doesNotMatch(mensagem, /APP_USR-/);
});

test("normalizarMensagemErro: nunca deixa passar uma sequência de dígitos com cara de número de cartão", () => {
  const { checkout } = loadCheckout();
  const mensagem = checkout.normalizarMensagemErro({ message: "Cartão 4111111111111111 recusado" });
  assert.doesNotMatch(mensagem, /4111111111111111/);
});

test("normalizarMensagemErro: erro técnico de rede (TypeError do fetch) não aparece em inglês", () => {
  const { checkout } = loadCheckout();
  const mensagem = checkout.normalizarMensagemErro(new TypeError("Failed to fetch"));
  assert.doesNotMatch(mensagem, /failed to fetch/i);
});

test("normalizarMensagemErro: JSON bruto (string começando com { ou [) cai no fallback", () => {
  const { checkout } = loadCheckout();
  const mensagem = checkout.normalizarMensagemErro('{"status_detail":"cc_rejected_other_reason"}');
  assert.equal(
    mensagem,
    "Não foi possível processar o pagamento. Revise os dados e tente novamente ou escolha Pix.",
  );
});

test("normalizarMensagemErro: código técnico conhecido (status_detail) é traduzido para PT-BR", () => {
  const { checkout } = loadCheckout();
  assert.equal(
    checkout.normalizarMensagemErro({ status_detail: "cc_rejected_high_risk" }),
    "Pagamento não autorizado por critérios de segurança.",
  );
});

// ---------------------------------------------------------------------
// definirEstadoParcelas / seletor de parcelas
// ---------------------------------------------------------------------

test("parcelas: estado inicial deixa o campo desabilitado com o texto 'Informe o cartão para ver as parcelas'", () => {
  const { checkout, mpInstallmentsEl, elementsById } = loadCheckout();
  checkout.definirEstadoParcelas("inicial");
  assert.equal(mpInstallmentsEl.disabled, true);
  assert.equal(mpInstallmentsEl.options.length, 1);
  assert.equal(mpInstallmentsEl.options[0].textContent, "Informe o cartão para ver as parcelas");
  assert.equal(elementsById.mpInstallmentsNote.textContent, "Informe o cartão para ver as parcelas");
});

test("parcelas: estado 'carregando' mostra mensagem de carregamento e mantém desabilitado", () => {
  const { checkout, mpInstallmentsEl, elementsById } = loadCheckout();
  checkout.definirEstadoParcelas("carregando");
  assert.equal(mpInstallmentsEl.disabled, true);
  assert.equal(mpInstallmentsEl.getAttribute("aria-busy"), "true");
  assert.equal(elementsById.mpInstallmentsNote.textContent, "Consultando parcelas…");
});

test("parcelas: erro na consulta mostra mensagem amigável (nunca [object Object]) e mantém bloqueado", () => {
  const { checkout, mpInstallmentsEl, elementsById } = loadCheckout();
  checkout.definirEstadoParcelas("erro");
  assert.equal(mpInstallmentsEl.disabled, true);
  assert.equal(
    elementsById.mpInstallmentsNote.textContent,
    "Não foi possível consultar as opções de parcelamento. Verifique os dados do cartão ou tente novamente.",
  );
});

test("parcelas: nenhuma opção disponível mantém o campo bloqueado com mensagem específica", () => {
  const { checkout, mpInstallmentsEl, elementsById } = loadCheckout();
  checkout.definirEstadoParcelas("vazio");
  assert.equal(mpInstallmentsEl.disabled, true);
  assert.equal(elementsById.mpInstallmentsNote.textContent, "Este cartão não possui opções de parcelamento disponíveis para esta compra.");
});

test("parcelas: quando o SDK já inseriu opções reais, o estado 'opcoes' libera o campo e remove o placeholder", () => {
  const { checkout, mpInstallmentsEl, elementsById } = loadCheckout();
  checkout.definirEstadoParcelas("inicial"); // placeholder presente
  // Simula o SDK oficial inserindo a(s) opção(ões) reais de parcelamento
  // (é isso que o CardForm faz sozinho -- nunca inventamos essas opções).
  const opcaoReal = makeOption();
  opcaoReal.value = "1";
  opcaoReal.textContent = "1x de R$ 18,00";
  mpInstallmentsEl.appendChild(opcaoReal);

  checkout.definirEstadoParcelas("opcoes");

  assert.equal(mpInstallmentsEl.disabled, false);
  assert.equal(mpInstallmentsEl.options.length, 1, "o placeholder deveria ter sido removido, só a opção real permanece");
  assert.equal(mpInstallmentsEl.options[0].textContent, "1x de R$ 18,00");
  assert.equal(elementsById.mpInstallmentsNote.textContent, "Parcelamento sujeito a juros conforme exibido no seletor acima.");
});

test("parcelas: uma única opção real (1x) continua sendo exibida, nunca escondida silenciosamente", () => {
  const { checkout, mpInstallmentsEl } = loadCheckout();
  const unica = makeOption();
  unica.value = "1";
  unica.textContent = "1x de R$ 18,00";
  mpInstallmentsEl.appendChild(unica);

  checkout.definirEstadoParcelas("opcoes");

  assert.equal(mpInstallmentsEl.hidden, undefined); // nunca setamos hidden neste fluxo
  assert.equal(mpInstallmentsEl.disabled, false);
  assert.equal(mpInstallmentsEl.options.length, 1);
});

test("parcelas: onBinChange (callback oficial do SDK para 'o número do cartão mudou') reseta parcelas antigas", async () => {
  const { checkout, capturedConfigs, mpInstallmentsEl } = loadCheckout();

  checkout.alternarFormaPagamento("cartao");
  let tentativas = 0;
  while (capturedConfigs.length === 0 && tentativas < 50) {
    await new Promise((resolve) => setTimeout(resolve, 5));
    tentativas += 1;
  }
  assert.equal(capturedConfigs.length, 1);
  const { callbacks } = capturedConfigs[0];
  assert.equal(typeof callbacks.onBinChange, "function", "cardForm() deveria configurar onBinChange (docs/card-form.md do mercadopago/sdk-js)");

  // Deixa o campo com uma opção "de uma bandeira anterior" antes de simular
  // a digitação de um novo número de cartão.
  const antiga = makeOption();
  antiga.textContent = "1x de R$ 18,00";
  mpInstallmentsEl.appendChild(antiga);
  checkout.definirEstadoParcelas("opcoes");
  assert.equal(mpInstallmentsEl.disabled, false);

  // BIN completo (6+ dígitos) de uma bandeira nova -- nunca reaproveita as
  // parcelas da bandeira anterior enquanto a nova consulta não responde.
  callbacks.onBinChange("511111");

  assert.equal(mpInstallmentsEl.disabled, true, "parcelas antigas não podem continuar selecionáveis após trocar de cartão");
});

test("parcelas: onBinChange com BIN incompleto (cartão ainda sendo digitado) volta ao estado inicial", async () => {
  const { checkout, capturedConfigs, mpInstallmentsEl, elementsById } = loadCheckout();

  checkout.alternarFormaPagamento("cartao");
  let tentativas = 0;
  while (capturedConfigs.length === 0 && tentativas < 50) {
    await new Promise((resolve) => setTimeout(resolve, 5));
    tentativas += 1;
  }
  const { callbacks } = capturedConfigs[0];

  callbacks.onBinChange("41");

  assert.equal(mpInstallmentsEl.disabled, true);
  assert.equal(elementsById.mpInstallmentsNote.textContent, "Informe o cartão para ver as parcelas");
});

test("parcelas: onPaymentMethodsReceived com data.results (formato real do SDK, não array solto) nunca quebra e reseta em caso de erro/vazio", async () => {
  const { checkout, capturedConfigs, mpInstallmentsEl } = loadCheckout();

  checkout.alternarFormaPagamento("cartao");
  let tentativas = 0;
  while (capturedConfigs.length === 0 && tentativas < 50) {
    await new Promise((resolve) => setTimeout(resolve, 5));
    tentativas += 1;
  }
  const { callbacks } = capturedConfigs[0];

  const antiga = makeOption();
  antiga.textContent = "1x de R$ 18,00";
  mpInstallmentsEl.appendChild(antiga);
  checkout.definirEstadoParcelas("opcoes");
  assert.equal(mpInstallmentsEl.disabled, false);

  // Formato real (mercadopago/sdk-js, docs/card-form.md): { paging, results }.
  callbacks.onPaymentMethodsReceived(null, { paging: { total: 0 }, results: [] });
  assert.equal(mpInstallmentsEl.disabled, true, "bandeira não reconhecida (results vazio) deveria voltar ao estado inicial");
});

test("parcelas: onInstallmentsReceived com erro do SDK nunca mostra [object Object] e desabilita o campo", async () => {
  const { checkout, capturedConfigs, mpInstallmentsEl, elementsById } = loadCheckout();

  checkout.alternarFormaPagamento("cartao");
  let tentativas = 0;
  while (capturedConfigs.length === 0 && tentativas < 50) {
    await new Promise((resolve) => setTimeout(resolve, 5));
    tentativas += 1;
  }

  const { callbacks } = capturedConfigs[0];
  // Formato real de erro que o SDK pode devolver -- um objeto, não uma
  // string (é exatamente o que, sem normalizar, vira [object Object]).
  callbacks.onInstallmentsReceived({ message: "installments_error", cause: {} }, null);

  assert.equal(mpInstallmentsEl.disabled, true);
  assert.notEqual(elementsById.mpInstallmentsNote.textContent, "[object Object]");
  assert.equal(
    elementsById.mpInstallmentsNote.textContent,
    "Não foi possível consultar as opções de parcelamento. Verifique os dados do cartão ou tente novamente.",
  );
});

test("parcelas: botão de pagar fica bloqueado enquanto as parcelas ainda estão carregando", async () => {
  const { checkout, capturedConfigs, elementsById } = loadCheckout();

  checkout.alternarFormaPagamento("cartao");
  let tentativas = 0;
  while (capturedConfigs.length === 0 && tentativas < 50) {
    await new Promise((resolve) => setTimeout(resolve, 5));
    tentativas += 1;
  }

  checkout.definirEstadoParcelas("carregando");
  assert.equal(elementsById.mpCardSubmit.disabled, true, "botão não pode ficar clicável com parcelas ainda carregando");
  assert.equal(elementsById.mpCardSubmit.textContent, "Carregando opções de parcelamento…");
});

test("parcelas: botão de pagar libera assim que uma opção válida existe", async () => {
  const { checkout, capturedConfigs, mpInstallmentsEl, elementsById } = loadCheckout();

  checkout.alternarFormaPagamento("cartao");
  let tentativas = 0;
  while (capturedConfigs.length === 0 && tentativas < 50) {
    await new Promise((resolve) => setTimeout(resolve, 5));
    tentativas += 1;
  }

  const opcao = makeOption();
  opcao.textContent = "1x de R$ 199,90";
  mpInstallmentsEl.appendChild(opcao);
  checkout.definirEstadoParcelas("opcoes");

  assert.equal(elementsById.mpCardSubmit.disabled, false);
  assert.match(elementsById.mpCardSubmit.textContent, /^Pagar/);
});
