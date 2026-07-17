"use strict";
// Isis 2.0 — testes unitários do portão de homologação
// (isis2/isis2-homolog-gate.js). Ambiente mínimo simulado (sem jsdom),
// no mesmo espírito de tests/isis2/helpers/load-isis2.js: stubs de
// document/window/fetch suficientes para observar o comportamento real
// do script (quais scripts/CSS ele injeta, o que ele nunca lê).
const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("fs");
const path = require("path");

const GATE_PATH = path.resolve(__dirname, "..", "..", "isis2", "isis2-homolog-gate.js");
const GATE_SOURCE = fs.readFileSync(GATE_PATH, "utf8");

function createElementStub() {
  const created = [];
  const elementFactory = () => {
    const el = {
      id: "",
      rel: "",
      href: "",
      src: "",
      defer: false,
      textContent: "",
      attrs: {},
      setAttribute(name, value) { this.attrs[name] = value; },
      getAttribute(name) { return this.attrs[name]; },
    };
    created.push(el);
    return el;
  };
  return { created, elementFactory };
}

function loadGate({
  siteConfig = {},
  fetchImpl = null,
  existingIds = [],
} = {}) {
  delete require.cache[GATE_PATH];

  const { created, elementFactory } = createElementStub();
  const headAppended = [];
  const bodyAppended = [];
  const byId = new Map(existingIds.map(id => [id, {}]));
  const listeners = {};

  global.window = global;
  global.__MISTICA_ISIS2_HOMOLOG_GATE__ = undefined;
  global.__MISTICA_ISIS2_HOMOLOG_ATIVO__ = undefined;
  global.misticaSiteConfig = siteConfig;
  global.fetch = fetchImpl;
  global.document = {
    getElementById: id => byId.get(id) || null,
    createElement: () => elementFactory(),
    head: { appendChild: el => headAppended.push(el) },
    body: { appendChild: el => bodyAppended.push(el) },
    addEventListener: (evt, cb) => { listeners[evt] = cb; },
  };

  require(GATE_PATH);

  return { headAppended, bodyAppended, created, GATE_SOURCE };
}

test("com a flag estática já true (nunca deveria acontecer em produção), injeta o loader sem chamar fetch", () => {
  let fetchChamado = false;
  const fetchImpl = async () => { fetchChamado = true; return { ok: false }; };
  const { headAppended } = loadGate({
    siteConfig: { isis2: { enabled: true } },
    fetchImpl,
  });
  assert.equal(fetchChamado, false);
  const loaderScript = headAppended.find(el => String(el.src || "").includes("isis2-loader.js"));
  assert.ok(loaderScript, "deveria ter injetado isis2-loader.js");
});

test("sem apiBaseUrl configurado, não chama fetch e não injeta nada (fail-safe)", () => {
  let fetchChamado = false;
  const fetchImpl = async () => { fetchChamado = true; return { ok: true, json: async () => ({}) }; };
  const { headAppended } = loadGate({
    siteConfig: { isis2: { enabled: false }, apiBaseUrl: "" },
    fetchImpl,
  });
  assert.equal(fetchChamado, false);
  assert.equal(headAppended.length, 0);
});

test("backend autoriza (enabled+homologacao true): injeta loader, aplica flags e mostra indicador", async () => {
  const chamadas = [];
  const fetchImpl = async (url, opts) => {
    chamadas.push({ url, opts });
    return {
      ok: true,
      json: async () => ({ enabled: true, escola: true, refinamento: true, homologacao: true }),
    };
  };
  const { headAppended, bodyAppended } = loadGate({
    siteConfig: { isis2: { enabled: false }, apiBaseUrl: "https://api.exemplo.com.br" },
    fetchImpl,
  });

  // A chamada é assíncrona (fetch real); espera a fila de microtasks correr.
  await new Promise(resolve => setImmediate(resolve));
  await new Promise(resolve => setImmediate(resolve));
  await new Promise(resolve => setImmediate(resolve));

  assert.equal(chamadas.length, 1);
  assert.equal(chamadas[0].url, "https://api.exemplo.com.br/api/isis2/homolog-config");
  assert.equal(chamadas[0].opts.credentials, "include");
  assert.equal(chamadas[0].opts.method, "GET");

  assert.equal(global.misticaSiteConfig.isis2.enabled, true);
  assert.equal(global.misticaSiteConfig.isis2.escola.enabled, true);
  assert.equal(global.misticaSiteConfig.isis2.escola.refinamento.enabled, true);
  assert.equal(global.__MISTICA_ISIS2_HOMOLOG_ATIVO__, true);

  const loaderScript = headAppended.find(el => String(el.src || "").includes("isis2-loader.js"));
  assert.ok(loaderScript, "deveria ter injetado isis2-loader.js");
  const badgeCss = headAppended.find(el => String(el.href || "").includes("isis2-homolog-badge.css"));
  assert.ok(badgeCss, "deveria ter injetado o CSS do indicador");
  assert.equal(bodyAppended.length, 1);
  assert.equal(bodyAppended[0].textContent, "Isis em homologação");
  assert.equal(bodyAppended[0].attrs["role"], "status");
  assert.equal(bodyAppended[0].attrs["aria-live"], "polite");
});

test("backend nega (enabled false): não injeta nada, nunca ativa por padrão", async () => {
  const fetchImpl = async () => ({
    ok: true,
    json: async () => ({ enabled: false, escola: false, refinamento: false, homologacao: false }),
  });
  const { headAppended, bodyAppended } = loadGate({
    siteConfig: { isis2: { enabled: false }, apiBaseUrl: "https://api.exemplo.com.br" },
    fetchImpl,
  });
  await new Promise(resolve => setImmediate(resolve));
  await new Promise(resolve => setImmediate(resolve));
  await new Promise(resolve => setImmediate(resolve));

  assert.equal(headAppended.length, 0);
  assert.equal(bodyAppended.length, 0);
  assert.notEqual(global.misticaSiteConfig.isis2.enabled, true);
});

test("resposta parcial (homologacao true mas enabled ausente) não ativa nada -- exige os dois campos", async () => {
  const fetchImpl = async () => ({
    ok: true,
    json: async () => ({ homologacao: true, escola: true, refinamento: true }),
  });
  const { headAppended } = loadGate({
    siteConfig: { isis2: { enabled: false }, apiBaseUrl: "https://api.exemplo.com.br" },
    fetchImpl,
  });
  await new Promise(resolve => setImmediate(resolve));
  await new Promise(resolve => setImmediate(resolve));
  assert.equal(headAppended.length, 0);
});

test("resposta HTTP não-ok (ex.: 500/403) mantém desligado", async () => {
  const fetchImpl = async () => ({ ok: false, json: async () => ({ enabled: true, homologacao: true }) });
  const { headAppended } = loadGate({
    siteConfig: { isis2: { enabled: false }, apiBaseUrl: "https://api.exemplo.com.br" },
    fetchImpl,
  });
  await new Promise(resolve => setImmediate(resolve));
  await new Promise(resolve => setImmediate(resolve));
  assert.equal(headAppended.length, 0);
});

test("falha de rede (fetch rejeita) nunca lança exceção e mantém desligado", async () => {
  const fetchImpl = async () => { throw new Error("network offline"); };
  let lancou = false;
  try {
    const { headAppended } = loadGate({
      siteConfig: { isis2: { enabled: false }, apiBaseUrl: "https://api.exemplo.com.br" },
      fetchImpl,
    });
    await new Promise(resolve => setImmediate(resolve));
    await new Promise(resolve => setImmediate(resolve));
    assert.equal(headAppended.length, 0);
  } catch {
    lancou = true;
  }
  assert.equal(lancou, false);
});

test("JSON inesperado (não é objeto) não ativa nada", async () => {
  const fetchImpl = async () => ({ ok: true, json: async () => null });
  const { headAppended } = loadGate({
    siteConfig: { isis2: { enabled: false }, apiBaseUrl: "https://api.exemplo.com.br" },
    fetchImpl,
  });
  await new Promise(resolve => setImmediate(resolve));
  await new Promise(resolve => setImmediate(resolve));
  assert.equal(headAppended.length, 0);
});

test("execução dupla é ignorada (guarda __MISTICA_ISIS2_HOMOLOG_GATE__)", () => {
  let chamadas = 0;
  const fetchImpl = async () => { chamadas += 1; return { ok: false }; };
  loadGate({ siteConfig: { isis2: { enabled: false }, apiBaseUrl: "https://api.exemplo.com.br" }, fetchImpl });
  // Segunda "carga" no mesmo processo sem limpar o cache nem a guarda:
  // simula o script sendo incluído duas vezes na mesma página.
  delete require.cache[GATE_PATH];
  require(GATE_PATH);
  assert.equal(chamadas, 1);
});

// ---------------------------------------------------------------------------
// Checagem estática: o portão nunca lê query string, hash, localStorage,
// sessionStorage nem um segredo embutido no bundle -- a única fonte de
// autorização é a resposta do backend (fetch + cookie HttpOnly existente).
// ---------------------------------------------------------------------------

test("o código-fonte do portão nunca LÊ query string/hash/localStorage/sessionStorage como fonte de autorização (só comenta que não usa)", () => {
  // Remove comentários antes de checar uso real -- o cabeçalho do arquivo
  // documenta em prosa, de propósito, que essas fontes NÃO são usadas.
  const semComentarios = GATE_SOURCE
    .replace(/\/\/.*$/gm, "")
    .replace(/\/\*[\s\S]*?\*\//g, "");
  assert.doesNotMatch(semComentarios, /location\.search/);
  assert.doesNotMatch(semComentarios, /location\.hash/);
  assert.doesNotMatch(semComentarios, /localStorage/);
  assert.doesNotMatch(semComentarios, /sessionStorage/);
  assert.doesNotMatch(semComentarios, /URLSearchParams/);
});

test("a chamada ao backend usa credentials:'include' (cookie HttpOnly) e nunca acrescenta headers com segredo", () => {
  assert.match(GATE_SOURCE, /credentials:\s*"include"/);
  assert.doesNotMatch(GATE_SOURCE, /X-Mistica-Api-Key/);
  assert.doesNotMatch(GATE_SOURCE, /Authorization/);
});
