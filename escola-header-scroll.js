(() => {
  "use strict";

  // Sentinela estrutural do header compacto. Este módulo não sobrescreve APIs
  // nativas nem registra listeners de scroll: o IntersectionObserver acompanha
  // um ponto absoluto e estável, independente da altura visual do header.
  const CLASSE = "is-leitura-compacta";
  const SELETOR_SENTINELA = "[data-header-sentinel]";
  const TOPO_SENTINELA = 118; // rootMargin -8px => transição efetiva em 110px.

  const diagnostico = {
    controlador: "intersection-observer-sentinel",
    alteracoes: 0,
    ativacoes: 0,
    desativacoes: 0,
    observersCriados: 0,
    reinicializacoes: 0,
    interceptacoesGlobais: 0,
    estado: false,
  };
  window.__escolaHeaderDiagnostics = diagnostico;

  let observer = null;
  let sentinel = null;
  let estadoCompacto = document.body.classList.contains(CLASSE);
  let shellObserver = null;

  function aplicarEstado(proximoEstado) {
    if (proximoEstado === estadoCompacto) return;
    estadoCompacto = proximoEstado;
    diagnostico.estado = proximoEstado;
    diagnostico.alteracoes += 1;
    if (proximoEstado) diagnostico.ativacoes += 1;
    else diagnostico.desativacoes += 1;
    document.body.classList.toggle(CLASSE, proximoEstado);
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
      aplicarEstado(!entry.isIntersecting);
    }, {
      threshold: 0,
      rootMargin: "-8px 0px 0px 0px",
    });
    observer.observe(sentinel);
    diagnostico.observersCriados += 1;
    diagnostico.reinicializacoes += 1;
    return true;
  }

  // O player é renderizado depois do fetch. O MutationObserver observa apenas a
  // criação/substituição do layout e recria exatamente um IntersectionObserver.
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
      aplicarEstado(false);
      sentinel?.remove();
      sentinel = null;
    },
  };
})();