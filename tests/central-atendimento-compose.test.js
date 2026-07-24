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

// ---------------------------------------------------------------------------
// Fakes de plataforma para as funções REAIS de estado do compose avançado
// (mídia pendente / gravação de áudio / troca de conversa) -- usados só
// pelos testes que precisam acionar código com efeito colateral, não pelas
// funções puras (que continuam usando o harness mínimo acima).
// ---------------------------------------------------------------------------

// URL.createObjectURL/revokeObjectURL fabricados: retornam strings
// previsíveis e gravam cada chamada, para os testes poderem verificar quais
// URLs foram revogadas e quando.
function createFakeUrl() {
  let contador = 0;
  const created = [];
  const revoked = [];
  return {
    created,
    revoked,
    createObjectURL(blob) {
      contador += 1;
      const url = `blob:fake-${contador}`;
      created.push({ url, blob });
      return url;
    },
    revokeObjectURL(url) {
      revoked.push(url);
    },
  };
}

function createFakeTrack() {
  const track = { stopped: false, stopCalls: 0 };
  track.stop = () => { track.stopped = true; track.stopCalls += 1; };
  return track;
}

function createFakeStream(trackCount = 1) {
  const tracks = Array.from({ length: trackCount }, () => createFakeTrack());
  return { getTracks: () => tracks, _tracks: tracks };
}

// MediaRecorder fabricado: dispara os listeners "stop"/"dataavailable"
// SINCRONAMENTE dentro de .stop() -- suficiente para os testes (o código de
// produção não depende de assincronia real do MediaRecorder, só reage aos
// eventos via addEventListener) e evita ter que orquestrar await/microtask
// nos testes. `isTypeSupported` é configurável por chamada de createHarness
// para testar a ordem de negociação de AUDIO_MIME_PREFERIDOS.
function createFakeMediaRecorderClass({ supportedTypes = [] } = {}) {
  class FakeMediaRecorder {
    constructor(stream, options) {
      this.stream = stream;
      this.options = options;
      this.mimeType = (options && options.mimeType) || "";
      this.state = "inactive";
      this._listeners = new Map();
      FakeMediaRecorder.instances.push(this);
    }
    addEventListener(type, callback) {
      const lista = this._listeners.get(type) || [];
      lista.push(callback);
      this._listeners.set(type, lista);
    }
    start() { this.state = "recording"; }
    stop() {
      if (this.state === "inactive") return;
      this.state = "inactive";
      const dataCbs = this._listeners.get("dataavailable") || [];
      dataCbs.forEach((cb) => cb({ data: new Blob(["fake-audio-chunk"]) }));
      const stopCbs = this._listeners.get("stop") || [];
      stopCbs.forEach((cb) => cb());
    }
  }
  FakeMediaRecorder.instances = [];
  FakeMediaRecorder.isTypeSupported = (type) => supportedTypes.includes(type);
  return FakeMediaRecorder;
}

// XMLHttpRequest fabricado: só grava o que foi aberto/enviado e permite
// simular abort/load/error via os listeners registrados -- os testes deste
// arquivo só precisam inspecionar a URL aberta e o FormData enviado (ver
// itens 11-13), nunca uma resposta de rede real.
function createFakeXhrClass() {
  class FakeXHR {
    constructor() {
      this._listeners = new Map();
      this.upload = { addEventListener() {} };
      this.withCredentials = false;
      this.status = 0;
      this.responseText = "";
      this.aborted = false;
      this.abortCalls = 0;
      FakeXHR.instances.push(this);
    }
    open(method, url) { this.method = method; this.url = url; }
    setRequestHeader(name, value) {
      this.headers = this.headers || {};
      this.headers[name] = value;
    }
    addEventListener(type, callback) {
      const lista = this._listeners.get(type) || [];
      lista.push(callback);
      this._listeners.set(type, lista);
    }
    send(formData) { this.sentFormData = formData; }
    abort() {
      this.abortCalls += 1;
      this.aborted = true;
      const cbs = this._listeners.get("abort") || [];
      cbs.forEach((cb) => cb());
    }
  }
  FakeXHR.instances = [];
  return FakeXHR;
}

function createHarness(options = {}) {
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
  const windowListeners = new Map();
  window.addEventListener = (type, callback) => windowListeners.set(type, callback);
  window.removeEventListener = (type) => windowListeners.delete(type);
  window.dispatchEvent = (evento) => {
    const callback = windowListeners.get(evento && evento.type);
    if (callback) callback(evento);
    return true;
  };

  const fakeUrl = createFakeUrl();
  const FakeMediaRecorder = createFakeMediaRecorderClass({
    supportedTypes: options.mediaRecorderSupportedTypes || [],
  });
  const FakeXHR = createFakeXhrClass();
  const getUserMedia = options.getUserMedia || (async () => {
    const erro = new Error("nenhum mock de getUserMedia configurado neste teste");
    erro.name = "NotAllowedError";
    throw erro;
  });

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
    URL: fakeUrl,
    navigator: { mediaDevices: { getUserMedia } },
    MediaRecorder: FakeMediaRecorder,
    XMLHttpRequest: FakeXHR,
    crypto: globalThis.crypto,
    Blob: globalThis.Blob,
    FormData: globalThis.FormData,
  };
  context.globalThis = context;

  vm.createContext(context);
  vm.runInContext(scriptSource, context, { filename: "central-atendimento.js" });

  return {
    context,
    window,
    elements,
    hooks: window.__misticaCentralAtendimentoTestHooks,
    fakeUrl,
    FakeMediaRecorder,
    FakeXHR,
    windowListeners,
  };
}

// Helper: seleciona uma conversa (via caminho seguro trocarConversaSelecionada)
// e opcionalmente define conversaAtual/assignment_version, para preparar o
// cenário de "mídia anexada/gravada numa conversa concreta" usado por vários
// testes abaixo.
function selecionarConversa(hooks, id, { assignmentVersion } = {}) {
  hooks.trocarConversaSelecionada(id);
  if (assignmentVersion !== undefined) {
    hooks._testSetConversaAtualRaw({ assignment_version: assignmentVersion });
  }
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

// ---------------------------------------------------------------------------
// Enter-para-enviar: keyCode 229 legado / `which` (reforço além de isComposing)
// ---------------------------------------------------------------------------

test("keyCode 229 (composição de IME legada) nunca decide enviar", () => {
  assert.equal(hooks.decidirEnviarPorTecla({ key: "Enter", keyCode: 229 }), false);
});

test("which 229 (composição de IME legada) nunca decide enviar", () => {
  assert.equal(hooks.decidirEnviarPorTecla({ key: "Enter", which: 229 }), false);
});

test("isComposing continua bloqueando o envio", () => {
  assert.equal(hooks.decidirEnviarPorTecla({ key: "Enter", isComposing: true }), false);
});

// ---------------------------------------------------------------------------
// Negociação de mimeType da gravação (escolherMimeTypeGravacao)
// ---------------------------------------------------------------------------

test("negociação usa MediaRecorder.isTypeSupported e respeita a ordem de preferência", () => {
  // só o segundo candidato da lista é suportado -- não deve "vazar" para o
  // primeiro nem parar cedo demais.
  const suportado = (tipo) => tipo === "audio/webm";
  assert.equal(hooks.escolherMimeTypeGravacao(suportado), "audio/webm");
});

test("negociação prefere o primeiro candidato quando ele é suportado", () => {
  const suportado = (tipo) => tipo === "audio/webm;codecs=opus" || tipo === "audio/webm";
  assert.equal(hooks.escolherMimeTypeGravacao(suportado), "audio/webm;codecs=opus");
});

test("negociação retorna null quando nenhum candidato preferencial é suportado", () => {
  assert.equal(hooks.escolherMimeTypeGravacao(() => false), null);
});

test("negociação retorna null se isSuportadoFn não é função", () => {
  assert.equal(hooks.escolherMimeTypeGravacao(undefined), null);
  assert.equal(hooks.escolherMimeTypeGravacao(null), null);
});

test("AUDIO_MIME_PREFERIDOS expõe a ordem real usada pela negociação", () => {
  // Array.from(...) normaliza para o Array do realm do processo Node --
  // hooks.AUDIO_MIME_PREFERIDOS foi criado dentro do contexto vm (um realm
  // JS diferente), então deepStrictEqual falharia na identidade do
  // construtor mesmo com conteúdo estruturalmente idêntico.
  assert.deepEqual(Array.from(hooks.AUDIO_MIME_PREFERIDOS), [
    "audio/webm;codecs=opus",
    "audio/webm",
    "audio/ogg;codecs=opus",
    "audio/mp4",
  ]);
});

// ---------------------------------------------------------------------------
// Allowlist final de mimeType de áudio (mimeTypeAudioEhAceitavel)
// ---------------------------------------------------------------------------

test("mimeType final fora da allowlist do backend é bloqueado", () => {
  assert.equal(hooks.mimeTypeAudioEhAceitavel("video/webm"), false);
  assert.equal(hooks.mimeTypeAudioEhAceitavel("application/octet-stream"), false);
});

test("mimeType com sufixo de codec é aceito ignorando o sufixo", () => {
  assert.equal(hooks.mimeTypeAudioEhAceitavel("audio/webm;codecs=opus"), true);
  assert.equal(hooks.mimeTypeAudioEhAceitavel("AUDIO/OGG;codecs=opus"), true);
});

test("mimeType ausente é permissivo (backend é a fonte de verdade real)", () => {
  assert.equal(hooks.mimeTypeAudioEhAceitavel(null), true);
  assert.equal(hooks.mimeTypeAudioEhAceitavel(undefined), true);
});

// ---------------------------------------------------------------------------
// Funções de estado reais do compose avançado: mídia pendente / gravação /
// troca de conversa -- exercitam o código de produção de verdade (não
// mocks/reimplementações) contra o harness fabricado acima.
// ---------------------------------------------------------------------------

function blobImagemFalso() {
  return new Blob(["fake-image-bytes"], { type: "image/jpeg" });
}

function blobAudioFalso() {
  return new Blob(["fake-audio-bytes"], { type: "audio/webm" });
}

test("imagem criada na conversa A é descartada ao trocar para B (não pode ser enviada ao contato errado)", () => {
  const h = createHarness();
  selecionarConversa(h.hooks, "A");
  h.hooks.abrirPreviaMidia({ blob: blobImagemFalso(), mediaKind: "image" });
  assert.ok(h.hooks.getMidiaPendente(), "prévia deveria estar aberta antes da troca");

  h.hooks.trocarConversaSelecionada("B");

  assert.equal(h.hooks.getMidiaPendente(), null);
});

test("áudio criado na conversa A é descartado ao trocar para B (mesmo ponto de entrada abrirPreviaMidia)", () => {
  const h = createHarness();
  selecionarConversa(h.hooks, "A");
  h.hooks.abrirPreviaMidia({ blob: blobAudioFalso(), mediaKind: "audio" });
  assert.ok(h.hooks.getMidiaPendente());

  h.hooks.trocarConversaSelecionada("B");

  assert.equal(h.hooks.getMidiaPendente(), null);
});

test("troca de conversa descarta imagem pendente (asserção explícita em getMidiaPendente)", () => {
  const h = createHarness();
  selecionarConversa(h.hooks, "A");
  h.hooks.abrirPreviaMidia({ blob: blobImagemFalso(), mediaKind: "image" });
  assert.notEqual(h.hooks.getMidiaPendente(), null);

  h.hooks.trocarConversaSelecionada("outra-conversa");

  assert.equal(h.hooks.getMidiaPendente(), null);
  assert.equal(h.elements.get("painelPreviaMidia").hidden, true);
});

test("troca de conversa cancela gravação em andamento (para o MediaRecorder e libera o microfone)", async () => {
  const stream = createFakeStream(1);
  const h = createHarness({ getUserMedia: async () => stream });
  selecionarConversa(h.hooks, "A");

  await h.hooks.iniciarGravacaoAudio();
  const gravador = h.hooks.getGravador();
  assert.ok(gravador, "gravação deveria ter iniciado");
  assert.equal(gravador.state, "recording");

  h.hooks.trocarConversaSelecionada("B");

  assert.equal(gravador.state, "inactive", "MediaRecorder.stop() deveria ter sido chamado");
  assert.equal(h.hooks.getGravador(), null);
  assert.ok(stream._tracks.every((t) => t.stopped), "todas as tracks do microfone deveriam ter sido paradas");
});

test("troca de conversa revoga o object URL da prévia pendente", () => {
  const h = createHarness();
  selecionarConversa(h.hooks, "A");
  h.hooks.abrirPreviaMidia({ blob: blobImagemFalso(), mediaKind: "image" });
  const urlCapturada = h.hooks.getMidiaPendente().previewObjectUrl;
  assert.ok(urlCapturada);

  h.hooks.trocarConversaSelecionada("B");

  assert.ok(h.fakeUrl.revoked.includes(urlCapturada));
});

test("troca de conversa encerra as tracks do microfone (gravação ativa)", async () => {
  const stream = createFakeStream(2);
  const h = createHarness({ getUserMedia: async () => stream });
  selecionarConversa(h.hooks, "A");
  await h.hooks.iniciarGravacaoAudio();

  h.hooks.trocarConversaSelecionada("B");

  assert.ok(stream._tracks.every((t) => t.stopCalls === 1));
});

test("troca de conversa é segura mesmo com stream vivo sem MediaRecorder ativo (robustez)", () => {
  // Cenário defensivo: nada de gravação em andamento, só uma conversa
  // trocando -- não deveria lançar nem tentar mexer num gravador inexistente.
  const h = createHarness();
  selecionarConversa(h.hooks, "A");
  assert.doesNotThrow(() => h.hooks.trocarConversaSelecionada("B"));
  assert.equal(h.hooks.getGravador(), null);
  assert.equal(h.hooks.getStreamGravacao(), null);
});

// ---------------------------------------------------------------------------
// Logout (limparEstadoCompose) -- mesma função chamada de forma síncrona
// pelo handler de clique de btnSair antes de qualquer await de rede.
// ---------------------------------------------------------------------------

test("logout (limparEstadoCompose) cancela gravação em andamento", async () => {
  const stream = createFakeStream(1);
  const h = createHarness({ getUserMedia: async () => stream });
  selecionarConversa(h.hooks, "A");
  await h.hooks.iniciarGravacaoAudio();
  const gravador = h.hooks.getGravador();
  assert.equal(gravador.state, "recording");

  h.hooks.limparEstadoCompose();

  assert.equal(gravador.state, "inactive");
  assert.equal(h.hooks.getGravador(), null);
});

test("logout (limparEstadoCompose) encerra as tracks do microfone", async () => {
  const stream = createFakeStream(1);
  const h = createHarness({ getUserMedia: async () => stream });
  selecionarConversa(h.hooks, "A");
  await h.hooks.iniciarGravacaoAudio();

  h.hooks.limparEstadoCompose();

  assert.ok(stream._tracks.every((t) => t.stopped));
});

test("logout (limparEstadoCompose) limpa a prévia de mídia pendente", () => {
  const h = createHarness();
  selecionarConversa(h.hooks, "A");
  h.hooks.abrirPreviaMidia({ blob: blobImagemFalso(), mediaKind: "image" });
  assert.ok(h.hooks.getMidiaPendente());

  h.hooks.limparEstadoCompose();

  assert.equal(h.hooks.getMidiaPendente(), null);
  assert.equal(h.elements.get("painelPreviaMidia").hidden, true);
});

test("logout (limparEstadoCompose) aborta um upload de mídia em andamento", () => {
  const h = createHarness();
  selecionarConversa(h.hooks, "A");
  h.hooks.abrirPreviaMidia({ blob: blobImagemFalso(), mediaKind: "image" });
  h.hooks.enviarMidiaPendente();
  const xhr = h.FakeXHR.instances[0];
  assert.ok(xhr, "XMLHttpRequest deveria ter sido criado pelo envio");
  assert.equal(h.hooks.getXhrEnvioMidiaAtual(), xhr);

  h.hooks.limparEstadoCompose();

  assert.equal(xhr.abortCalls, 1);
  assert.equal(h.hooks.getXhrEnvioMidiaAtual(), null);
});

// ---------------------------------------------------------------------------
// Regressão crítica: mídia pendente deve ser enviada para a conversa em que
// foi criada, NUNCA para o que a variável global conversaSelecionadaId
// aponta na hora do envio. Este é o teste mais importante deste arquivo --
// ele é o teste de regressão direto do bug corrigido ("destinatário
// errado": trocar de conversa com uma prévia aberta enviava a mídia para o
// contato ERRADO porque enviarMidiaPendente() lia a global mutável
// conversaSelecionadaId em vez do conversationId capturado em midiaPendente
// no momento da anexação/gravação). Este teste FALHARIA contra o código
// pré-correção (que usava conversaSelecionadaId diretamente dentro de
// enviarMidiaPendente/xhr.open) e passa contra o código corrigido -- foi
// verificado manualmente revertendo esse trecho localmente durante o
// desenvolvimento deste arquivo e confirmando que o teste falha, depois
// revertido de volta (ver git diff central-atendimento.js == vazio).
// ---------------------------------------------------------------------------

test("REGRESSÃO CRÍTICA: envio usa o conversationId capturado na mídia, não a global conversaSelecionadaId que pode ter mudado", () => {
  const h = createHarness();
  selecionarConversa(h.hooks, "A");
  h.hooks.abrirPreviaMidia({ blob: blobImagemFalso(), mediaKind: "image" });

  // Simula a global "derivando" por fora do caminho seguro
  // (trocarConversaSelecionada) -- é exatamente o que o código pré-correção
  // efetivamente assumia que nunca aconteceria enquanto havia uma prévia
  // aberta.
  h.hooks._testSetConversaSelecionadaIdRaw("B");

  h.hooks.enviarMidiaPendente();

  const xhr = h.FakeXHR.instances[0];
  assert.ok(xhr, "um XMLHttpRequest deveria ter sido aberto");
  assert.match(xhr.url, /\/conversations\/A\/media$/, `URL deveria apontar para a conversa A (criada), não B (selecionada agora): ${xhr.url}`);
});

test("envio não usa conversaSelecionadaId global -- URL usada e global atual ficam decididamente divergentes", () => {
  const h = createHarness();
  selecionarConversa(h.hooks, "A");
  h.hooks.abrirPreviaMidia({ blob: blobImagemFalso(), mediaKind: "image" });
  h.hooks._testSetConversaSelecionadaIdRaw("B");

  h.hooks.enviarMidiaPendente();

  const xhr = h.FakeXHR.instances[0];
  assert.equal(h.hooks.getConversaSelecionadaId(), "B");
  assert.match(xhr.url, /\/conversations\/A\/media$/);
  assert.ok(!xhr.url.includes("/conversations/B/"), "a URL de envio nunca deveria referenciar a conversa global atual (B)");
});

test("assignmentVersion permanece vinculada ao momento do preview, mesmo se conversaAtual mudar depois", () => {
  const h = createHarness();
  selecionarConversa(h.hooks, "A", { assignmentVersion: 3 });
  h.hooks.abrirPreviaMidia({ blob: blobImagemFalso(), mediaKind: "image" });

  // Bump de versão por uma ação não relacionada (ex.: outra aba/poll)
  // depois que a prévia já foi aberta -- não deveria "vazar" para o envio.
  h.hooks._testSetConversaAtualRaw({ assignment_version: 9 });

  h.hooks.enviarMidiaPendente();

  const xhr = h.FakeXHR.instances[0];
  assert.ok(xhr.sentFormData, "FormData deveria ter sido enviado");
  assert.equal(xhr.sentFormData.get("assignment_version"), "3");
});

test("duplo cleanup não gera erro (idempotência de limparEstadoCompose/limparMidiaPendente/cancelarGravacaoAudio)", () => {
  const h = createHarness();
  selecionarConversa(h.hooks, "A");

  assert.doesNotThrow(() => {
    h.hooks.limparEstadoCompose();
    h.hooks.limparEstadoCompose();
    h.hooks.limparMidiaPendente();
    h.hooks.limparMidiaPendente();
    h.hooks.cancelarGravacaoAudio();
    h.hooks.cancelarGravacaoAudio();
  });
  assert.equal(h.hooks.getMidiaPendente(), null);
});

test("object URLs antigos são revogados ao anexar uma nova mídia antes de enviar/cancelar a anterior", () => {
  const h = createHarness();
  selecionarConversa(h.hooks, "A");
  h.hooks.abrirPreviaMidia({ blob: blobImagemFalso(), mediaKind: "image" });
  const primeiraUrl = h.hooks.getMidiaPendente().previewObjectUrl;

  h.hooks.abrirPreviaMidia({ blob: blobImagemFalso(), mediaKind: "image" });
  const segundaUrl = h.hooks.getMidiaPendente().previewObjectUrl;

  assert.notEqual(primeiraUrl, segundaUrl);
  assert.ok(h.fakeUrl.revoked.includes(primeiraUrl), "a URL da primeira prévia deveria ter sido revogada");
  assert.equal(h.hooks.getMidiaPendente().previewObjectUrl, segundaUrl);
});

test("nenhuma mídia é enviada após cancelamento explícito (limparMidiaPendente antes do envio)", () => {
  const h = createHarness();
  selecionarConversa(h.hooks, "A");
  h.hooks.abrirPreviaMidia({ blob: blobImagemFalso(), mediaKind: "image" });

  h.hooks.limparMidiaPendente(); // equivalente a clicar em "Cancelar"
  h.hooks.enviarMidiaPendente();

  assert.equal(h.FakeXHR.instances.length, 0, "nenhum XMLHttpRequest deveria ter sido criado");
});

// ---------------------------------------------------------------------------
// Negociação de mimeType integrada ao fluxo real de gravação
// ---------------------------------------------------------------------------

test("iniciarGravacaoAudio constrói o MediaRecorder com o mimeType negociado quando suportado", async () => {
  const stream = createFakeStream(1);
  const h = createHarness({
    getUserMedia: async () => stream,
    mediaRecorderSupportedTypes: ["audio/webm"],
  });
  selecionarConversa(h.hooks, "A");

  await h.hooks.iniciarGravacaoAudio();

  const instancia = h.FakeMediaRecorder.instances[0];
  assert.ok(instancia);
  assert.equal(instancia.options && instancia.options.mimeType, "audio/webm");
  h.hooks.cancelarGravacaoAudio(); // libera o timer/interval de duração para não prender o processo
});

test("iniciarGravacaoAudio usa o default do navegador (sem mimeType) quando nada é suportado", async () => {
  const stream = createFakeStream(1);
  const h = createHarness({
    getUserMedia: async () => stream,
    mediaRecorderSupportedTypes: [],
  });
  selecionarConversa(h.hooks, "A");

  await h.hooks.iniciarGravacaoAudio();

  const instancia = h.FakeMediaRecorder.instances[0];
  assert.ok(instancia);
  assert.equal(instancia.options, undefined);
  h.hooks.cancelarGravacaoAudio(); // libera o timer/interval de duração para não prender o processo
});
