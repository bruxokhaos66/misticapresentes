(() => {
  "use strict";

  // Controlador estrutural do header compacto da Escola Mística.
  //
  // O player anterior registrava o mesmo callback de scroll para progresso,
  // parallax e compactação. A compactação alterava o layout do próprio header
  // enquanto o scroll era medido, permitindo que a ancoragem do navegador
  // atravessasse repetidamente o limite de 110px. Este módulo substitui apenas
  // essa responsabilidade por uma sentinela estável; progresso e parallax
  // continuam no controlador original.
  const CLASSE = "is-leitura-compacta";
  const SELETOR_SENTINELA = "[data-header-sentinel]";
  const diagnostico = {
    controlador: "intersection-observer-sentinel",
    alteracoes: 0,
    ativacoes: 0,
    desativacoes: 0,
    listenersLegadosBloqueados: 0,
    observersCriados: 0,
    estado: false,
  };
  window.__escolaHeaderDiagnostics = diagnostico;

  let observer = null;
  let sentinel = null;
  let estadoCompacto = false;
  let controladorAtivo = true;

  const toggleNativo = DOMTokenList.prototype.toggle;
  const addEventListenerNativo = window.addEventListener.bind(window);
  const removeEventListenerNativo = window.removeEventListener.bind(window);

  // Impede somente o controlador legado de compactação de voltar a escrever a
  // classe. A identificação é restrita ao callback fechado sobre `agendado` e
  // `medir`, criado em escola-curso.js. Outros listeners de scroll permanecem
  // intocados.
  const addEventListenerInterceptado = function (tipo, listener, opcoes) {
    const fonte = typeof listener === "function" ? Function.prototype.toString.call(listener) : "";
    const controladorLegado = (tipo === "scroll" || tipo === "resize")
      && fonte.includes("requestAnimationFrame(medir)")
      && fonte.includes("agendado");

    if (controladorLegado) {
      diagnostico.listenersLegadosBloqueados += 1;
      return;
    }
    return addEventListenerNativo(tipo, listener, opcoes);
  };

  window.addEventListener = addEventListenerInterceptado;

  // O código legado ainda chama seu medidor diretamente na renderização e na
  // troca de aula. Bloqueamos exclusivamente a escrita antiga desta classe;
  // o observer abaixo usa o método nativo para aplicar o estado estável.
  DOMTokenList.prototype.toggle = function (token, force) {
    if (controladorAtivo && token === CLASSE && this === document.body.classList) {
      return this.contains(token);
    }
    return toggleNativo.call(this, token, force);
  };

  function aplicarEstado(proximoEstado) {
    if (proximoEstado === estadoCompacto) return;
    estadoCompacto = proximoEstado;
    diagnostico.estado = proximoEstado;
    diagnostico.alteracoes += 1;
    if (proximoEstado) diagnostico.ativacoes += 1;
    else diagnostico.desativacoes += 1;
    toggleNativo.call(document.body.classList, CLASSE, proximoEstado);
    document.body.dispatchEvent(new CustomEvent("escola:header-compacto", {
      detail: { compacto: proximoEstado, alteracoes: diagnostico.alteracoes },
    }));
  }

  function destruirObserver() {
    if (observer) observer.disconnect();
    observer = null;
  }

  function garantirSentinela() {
    const layout = document.querySelector("[data-layout]");
    if (!layout) return false;

    const existente = document.querySelector(SELETOR_SENTINELA);
    if (existente && existente !== sentinel) existente.remove();

    if (!sentinel || !sentinel.isConnected) {
      sentinel = document.createElement("span");
      sentinel.className = "plataforma-header-sentinel";
      sentinel.setAttribute("data-header-sentinel", "");
      sentinel.setAttribute("aria-hidden", "true");
    }

    if (layout.previousElementSibling !== sentinel) layout.before(sentinel);
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
    return true;
  }

  // O shell é preenchido depois do fetch. Observamos somente a troca estrutural
  // do player e recriamos um único observer quando [data-layout] nasce de novo.
  const shell = document.querySelector("[data-plataforma]");
  const shellObserver = shell ? new MutationObserver(() => {
    if (document.querySelector("[data-layout]") && (!sentinel || !sentinel.isConnected)) {
      iniciarObserver();
    }
  }) : null;

  if (shellObserver) shellObserver.observe(shell, { childList: true, subtree: true });

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", iniciarObserver, { once: true });
  } else {
    iniciarObserver();
  }

  // API mínima para testes e para reinicializações explícitas do player.
  window.__escolaHeaderScroll = {
    reiniciar: iniciarObserver,
    destruir() {
      destruirObserver();
      shellObserver?.disconnect();
      aplicarEstado(false);
      controladorAtivo = false;
      DOMTokenList.prototype.toggle = toggleNativo;
      window.addEventListener = addEventListenerNativo;
      window.removeEventListener = removeEventListenerNativo;
    },
  };
})();
