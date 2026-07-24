// Testes das funções puras do compose avançado da Central de Atendimento
// (backend-agnósticas: Enter-para-enviar, validade de texto/arquivo,
// limites de gravação de áudio) -- mesma técnica de
// tests/site-production-guard.test.js: carrega o script real via
// fs.readFileSync + vm.runInContext contra um DOM/harness fabricado, sem
// jsdom. Os hooks só são expostos quando window.__MISTICA_TEST__ === true
// (nunca em produção -- ver o fim de central-atendimento.js).
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const test = require("node:test");
const vm = require("node:vm");

const scriptSource = fs.readFileSync(
  path.join(__dirname, "..", "central-atendimento.js"),
  "utf8",
);

function createFakeElement(id) {
  const listeners = new Map();
  const el = {
    id,
    hidden: false,
    disabled: false,
    value: "",
    textContent: "",
    className: "",
    classList: {
      add() {},
      remove() {},
      toggle() {},
      contains() { return false; },
    },
    dataset: {},
    style: {},
    attributes: {},
    files: null,
    scrollTop: 0,
    scrollHeight: 0,
    addEventListener(type, callback) { listeners.set(type, callback); },
    removeEventListener(type) { listeners.delete(type); },
    dispatchEvent() { return true; },
    append() {},
    appendChild() {},
    remove() {},
    setAttribute(name, value) { el.attributes[name] = value; },
    getAttribute(name) { return el.attributes[name]; },
    removeAttribute(name) { delete el.attributes[name]; },
    querySelectorAll() { return []; },
    querySelector() { return null; },
    focus() {},
    click() {},
    reset() {},
    requestSubmit() {
      const callback = listeners.get("submit");
      if (callback) callback({ preventDefault() {} });
    },
    get _listeners() { return listeners; },
  };
  return el;
}

function createHarness() {
  const elements = new Map();
  const documentListeners = new Map();

  const document = {
    readyState: "complete",
    activeElement: null,
    getElementById(id) {
      if (!elements.has(id)) elements.set(id, createFakeElement(id));
      return elements.get(id);
    },
    querySelectorAll() { return []; },
    querySelector() { return null; },
    createElement(tag) { return createFakeElement(`<${tag}>`); },
    createTextNode(text) { return { text }; },
    addEventListener(type, callback) { documentListeners.set(type, callback); },
    removeEventListener(type) { documentListeners.delete(type); },
  };

  const window = {
    __MISTICA_TEST__: true,
    misticaSiteConfig: { apiBaseUrl: "https://api.example.test" },
  };

  const context = {
    window,
    document,
    console,
    Set,
    Map,
    Intl,
    Promise,
    setTimeout,
    clearTimeout,
    setInterval,
    clearInterval,
    // Nunca chamada de verdade nos testes (só usada dentro de handlers de
    // evento, não durante o carregamento do script) -- fornecida só para
    // que a chamada de bootstrap no fim do arquivo (apiFetch("/api/auth/me"))
    // não gere uma rejeição de promise não tratada durante o require().
    fetch: () => Promise.reject(new Error("rede desabilitada nos testes")),
  };
  context.globalThis = context;

  vm.createContext(context);
  vm.runInContext(scriptSource, context, { filename: "central-atendimento.js" });

  return { context, window, hooks: window.__misticaCentralAtendimentoTestHooks };
}

const { hooks } = createHarness();

test("hooks de teste são expostos quando __MISTICA_TEST__ está ligado", () => {
  assert.ok(hooks, "window.__misticaCentralAtendimentoTestHooks deveria existir");
  assert.equal(typeof hooks.decidirEnviarPorTecla, "function");
  assert.equal(typeof hooks.textoEhValidoParaEnvio, "function");
  assert.equal(typeof hooks.arquivoImagemEhValido, "function");
  assert.equal(typeof hooks.blobAudioEhValido, "function");
  assert.equal(typeof hooks.duracaoGravacaoExcedeuLimite, "function");
});

test("hooks de teste NÃO são expostos sem a flag __MISTICA_TEST__", () => {
  const elements = new Map();
  const document = {
    getElementById(id) {
      if (!elements.has(id)) elements.set(id, createFakeElement(id));
      return elements.get(id);
    },
    querySelectorAll() { return []; },
    createElement(tag) { return createFakeElement(`<${tag}>`); },
    addEventListener() {},
  };
  const window = { misticaSiteConfig: {} }; // __MISTICA_TEST__ ausente
  const context = { window, document, console, Set, Map, Intl, Promise, setTimeout, clearTimeout, setInterval, clearInterval, fetch: () => Promise.reject(new Error("nope")) };
  context.globalThis = context;
  vm.createContext(context);
  vm.runInContext(scriptSource, context, { filename: "central-atendimento.js" });
  assert.equal(window.__misticaCentralAtendimentoTestHooks, undefined);
});

// ---------------------------------------------------------------------------
// Enter envia / Shift+Enter quebra linha
// ---------------------------------------------------------------------------

test("Enter sem modificadores decide enviar", () => {
  assert.equal(hooks.decidirEnviarPorTecla({ key: "Enter" }), true);
});

test("Shift+Enter nunca decide enviar (quebra de linha)", () => {
  assert.equal(hooks.decidirEnviarPorTecla({ key: "Enter", shiftKey: true }), false);
});

test("Ctrl/Cmd/Alt+Enter também não decide enviar", () => {
  assert.equal(hooks.decidirEnviarPorTecla({ key: "Enter", ctrlKey: true }), false);
  assert.equal(hooks.decidirEnviarPorTecla({ key: "Enter", metaKey: true }), false);
  assert.equal(hooks.decidirEnviarPorTecla({ key: "Enter", altKey: true }), false);
});

test("Enter durante composição de IME nunca decide enviar", () => {
  assert.equal(hooks.decidirEnviarPorTecla({ key: "Enter", isComposing: true }), false);
});

test("outras teclas nunca decidem enviar", () => {
  assert.equal(hooks.decidirEnviarPorTecla({ key: "a" }), false);
  assert.equal(hooks.decidirEnviarPorTecla({ key: "Tab" }), false);
  assert.equal(hooks.decidirEnviarPorTecla(null), false);
});

// ---------------------------------------------------------------------------
// Texto vazio/whitespace nunca é válido para envio
// ---------------------------------------------------------------------------

test("texto vazio é rejeitado", () => {
  assert.equal(hooks.textoEhValidoParaEnvio(""), false);
});

test("texto só com espaços/quebras de linha é rejeitado", () => {
  assert.equal(hooks.textoEhValidoParaEnvio("   \n\t  "), false);
});

test("texto não-vazio (com espaços nas bordas) é aceito", () => {
  assert.equal(hooks.textoEhValidoParaEnvio("  Olá, tudo bem?  "), true);
});

// ---------------------------------------------------------------------------
// Validador de arquivo de imagem: tipo (magic-type do navegador) + tamanho
// ---------------------------------------------------------------------------

function arquivoFalso({ type, size }) {
  return { type, size };
}

test("imagem JPEG dentro do limite é aceita", () => {
  const resultado = hooks.arquivoImagemEhValido(arquivoFalso({ type: "image/jpeg", size: 1024 }));
  assert.equal(resultado.valido, true);
});

test("imagem PNG e WEBP dentro do limite são aceitas", () => {
  assert.equal(hooks.arquivoImagemEhValido(arquivoFalso({ type: "image/png", size: 1024 })).valido, true);
  assert.equal(hooks.arquivoImagemEhValido(arquivoFalso({ type: "image/webp", size: 1024 })).valido, true);
});

test("SVG é rejeitado mesmo se pequeno", () => {
  const resultado = hooks.arquivoImagemEhValido(arquivoFalso({ type: "image/svg+xml", size: 200 }));
  assert.equal(resultado.valido, false);
});

test("HTML disfarçado de imagem é rejeitado", () => {
  const resultado = hooks.arquivoImagemEhValido(arquivoFalso({ type: "text/html", size: 200 }));
  assert.equal(resultado.valido, false);
});

test("JavaScript é rejeitado", () => {
  const resultado = hooks.arquivoImagemEhValido(arquivoFalso({ type: "application/javascript", size: 200 }));
  assert.equal(resultado.valido, false);
});

test("arquivo de imagem maior que o limite é rejeitado", () => {
  const resultado = hooks.arquivoImagemEhValido(arquivoFalso({ type: "image/jpeg", size: 50 * 1024 * 1024 }), { maxBytes: 5 * 1024 * 1024 });
  assert.equal(resultado.valido, false);
});

test("arquivo vazio é rejeitado", () => {
  const resultado = hooks.arquivoImagemEhValido(arquivoFalso({ type: "image/jpeg", size: 0 }));
  assert.equal(resultado.valido, false);
});

test("nenhum arquivo selecionado é rejeitado", () => {
  const resultado = hooks.arquivoImagemEhValido(null);
  assert.equal(resultado.valido, false);
});

// ---------------------------------------------------------------------------
// Validador de blob de áudio gravado
// ---------------------------------------------------------------------------

test("blob de áudio válido dentro do limite é aceito", () => {
  const resultado = hooks.blobAudioEhValido({ size: 2048 });
  assert.equal(resultado.valido, true);
});

test("blob de áudio vazio é rejeitado", () => {
  const resultado = hooks.blobAudioEhValido({ size: 0 });
  assert.equal(resultado.valido, false);
});

test("blob de áudio maior que o limite é rejeitado", () => {
  const resultado = hooks.blobAudioEhValido({ size: 30 * 1024 * 1024 }, { maxBytes: 16 * 1024 * 1024 });
  assert.equal(resultado.valido, false);
});

test("blob ausente é rejeitado", () => {
  assert.equal(hooks.blobAudioEhValido(null).valido, false);
});

// ---------------------------------------------------------------------------
// Duração máxima de gravação
// ---------------------------------------------------------------------------

test("duração abaixo do limite não excede", () => {
  assert.equal(hooks.duracaoGravacaoExcedeuLimite(30, 120), false);
});

test("duração igual ou acima do limite excede", () => {
  assert.equal(hooks.duracaoGravacaoExcedeuLimite(120, 120), true);
  assert.equal(hooks.duracaoGravacaoExcedeuLimite(121, 120), true);
});
