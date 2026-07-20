(() => {
  "use strict";

  const TIMEOUT_MS = 12000;
  const RETRY_DELAY_MS = 700;
  let tentativaEmAndamento = null;
  let funcaoOriginal = null;

  function esperar(ms) {
    return new Promise((resolve) => window.setTimeout(resolve, ms));
  }

  function comTimeout(promessa, ms) {
    let timer = null;
    const timeout = new Promise((_, reject) => {
      timer = window.setTimeout(() => {
        const erro = new Error("A conexão demorou mais que o esperado. Tentando recuperar o mesmo pedido com segurança...");
        erro.name = "CheckoutPixTimeoutError";
        erro.recuperavel = true;
        reject(erro);
      }, ms);
    });
    return Promise.race([promessa, timeout]).finally(() => {
      if (timer !== null) window.clearTimeout(timer);
    });
  }

  function erroRecuperavel(erro) {
    if (!erro) return true;
    if (erro.recuperavel || erro.name === "CheckoutPixTimeoutError" || erro.name === "TypeError") return true;
    const mensagem = String(erro.message || erro).toLowerCase();
    return /network|rede|fetch|conex|timeout|temporariamente|api 5\d\d/.test(mensagem);
  }

  function avisar(mensagem, etapa) {
    window.dispatchEvent(new CustomEvent("mistica:checkout-pix-recovery", {
      detail: { mensagem, etapa },
    }));
  }

  async function criarPedidoComRecuperacao(itens) {
    if (tentativaEmAndamento) return tentativaEmAndamento;
    tentativaEmAndamento = (async () => {
      avisar("Enviando o pedido com proteção contra falhas de conexão...", "iniciando");
      try {
        return await comTimeout(Promise.resolve().then(() => funcaoOriginal(itens)), TIMEOUT_MS);
      } catch (primeiroErro) {
        if (!erroRecuperavel(primeiroErro) || navigator.onLine === false) {
          if (navigator.onLine === false) {
            throw new Error("Sem conexão com a internet. O carrinho foi preservado; reconecte e toque em Gerar Pix novamente.");
          }
          throw primeiroErro;
        }

        avisar("A conexão oscilou. Recuperando o mesmo pedido sem duplicar a reserva...", "repetindo");
        await esperar(RETRY_DELAY_MS);
        try {
          return await comTimeout(Promise.resolve().then(() => funcaoOriginal(itens)), TIMEOUT_MS);
        } catch (segundoErro) {
          if (erroRecuperavel(segundoErro)) {
            throw new Error("Não foi possível confirmar a geração do Pix agora. O carrinho foi preservado e uma nova tentativa reutilizará a mesma chave de segurança.");
          }
          throw segundoErro;
        }
      }
    })().finally(() => {
      tentativaEmAndamento = null;
    });
    return tentativaEmAndamento;
  }

  function instalar() {
    if (typeof window.misticaCriarPedido !== "function") return false;
    if (window.misticaCriarPedido.__misticaRecoveryInstalled) return true;
    funcaoOriginal = window.misticaCriarPedido;
    criarPedidoComRecuperacao.__misticaRecoveryInstalled = true;
    window.misticaCriarPedido = criarPedidoComRecuperacao;
    return true;
  }

  function atualizarEstadoRede() {
    const botao = document.querySelector("[data-generate-pix]");
    if (!botao) return;
    if (navigator.onLine === false) {
      botao.dataset.networkOffline = "true";
      if (!window.misticaGerarPixBloqueado?.()) botao.disabled = true;
    } else {
      delete botao.dataset.networkOffline;
      if (!window.misticaGerarPixBloqueado?.() && window.misticaCatalogState === "ready") {
        botao.disabled = false;
      }
    }
  }

  const observer = window.setInterval(() => {
    if (instalar()) window.clearInterval(observer);
  }, 50);
  window.setTimeout(() => window.clearInterval(observer), 10000);

  window.addEventListener("online", atualizarEstadoRede);
  window.addEventListener("offline", atualizarEstadoRede);
  window.addEventListener("DOMContentLoaded", atualizarEstadoRede, { once: true });
})();