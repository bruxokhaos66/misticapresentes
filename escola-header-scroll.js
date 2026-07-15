(() => {
  "use strict";

  // Sentinela estrutural do header compacto. Este módulo não sobrescreve APIs
  // nativas nem registra listeners de scroll. O controlador legado do player
  // permanece como único escritor da classe; aqui apenas validamos o limite e
  // expomos diagnóstico, evitando dois controladores concorrentes.
  const CLASSE = "is-leitura-compacta";
  const SELETOR_SENTINELA = "[data-header-sentinel]";
  const TOPO_SENTINELA = 118; // rootMargin -8px => transição efetiva em 110px.

  const diagnostico = {
    controlador: "single-writer-with-sentinel-audit",
    alteracoes: 0,
    ativacoes: 0,
    desativacoes: 0,
    observersCriados: 0,
    reinicializacoes: 0,
    interceptacoesGlobais: 0,
    desalinhamentos: 0,
    estado: document.body.classList.contains(CLASSE),
    estadoEsperado: false,
  };
  window.__escolaHeaderDiagnostics = diagnostico;

  let observer = null;
  let sentinel = null;
  let shellObserver = null;
  let classObserver = null;
  let estadoCompacto = diagnostico.estado;

  function registrarEstadoReal() {
    const proximoEstado = document.body.classList.contains(CLASSE);
    if (proximoEstado === estadoCompacto) return;
    estadoCompacto = proximoEstado;
    diagnostico.estado = proximoEstado;
    diagnostico.alteracoes += 1;
    if (proximoEstado) diagnostico.ativacoes += 1;
    else diagnostico.desativacoes += 1;
    if (proximoEstado !== diagnostico.estadoEsperado) diagnostico.desalinhamentos += 1;
    document.body.dispatchEvent(new CustomEvent("escola:header-compacto", {
      detail: { compacto: proximoEstado, alteracoes: diagnostico.alteracoes },
    }));
  }

  function destruirObserver() {
    observer?.disconnect();
    observer = null;
  }

  function garantirSentinela() {
    const main = document.querySelector(".plataforma-main");
    if (!main) return false;

    const existentes = [...document.querySelectorAll(SELETOR_SENTINELA)];
    if (!sentinel || !sentinel.isConnected) {
      sentinel = existentes.shift() || document.createElement("span");
      sentinel.className = "plataforma-header-sentinel";
      sentinel.setAttribute("data-header-sentinel", "");
      sentinel.setAttribute("aria-hidden", "true");
    }
    existentes.forEach(elemento => elemento.remove());

    sentinel.style.setProperty("--sentinel-top", `${TOPO_SENTINELA}px`);
    if (main.previousElementSibling !== sentinel) main.before(sentinel);
    return true;
  }

  function iniciarObserver() {
    if (!garantirSentinela()) return false;
    destruirObserver();

    observer = new IntersectionObserver(([entry]) => {
      diagnostico.estadoEsperado = !entry.isIntersecting;
      if (diagnostico.estado !== diagnostico.estadoEsperado) diagnostico.desalinhamentos += 1;
    }, {
      threshold: 0,
      rootMargin: "-8px 0px 0px 0px",
    });
    observer.observe(sentinel);
    diagnostico.observersCriados += 1;
    diagnostico.reinicializacoes += 1;
    return true;
  }

  // Registra as mudanças feitas pelo único escritor real sem reescrever a classe.
  classObserver = new MutationObserver(mudancas => {
    if (mudancas.some(mudanca => mudanca.attributeName === "class")) registrarEstadoReal();
  });
  classObserver.observe(document.body, { attributes: true, attributeFilter: ["class"] });

  // O player é renderizado depois do fetch. Observa apenas criação/substituição
  // do layout e recria exatamente um IntersectionObserver.
  const shell = document.querySelector("[data-plataforma]");
  if (shell) {
    shellObserver = new MutationObserver(() => {
      if (document.querySelector("[data-layout]") && (!observer || !sentinel?.isConnected)) {
        iniciarObserver();
      }
    });
    shellObserver.observe(shell, { childList: true, subtree: false });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", iniciarObserver, { once: true });
  } else {
    iniciarObserver();
  }

  window.__escolaHeaderScroll = {
    reiniciar: iniciarObserver,
    destruir() {
      destruirObserver();
      shellObserver?.disconnect();
      shellObserver = null;
      classObserver?.disconnect();
      classObserver = null;
      sentinel?.remove();
      sentinel = null;
    },
  };
})();
