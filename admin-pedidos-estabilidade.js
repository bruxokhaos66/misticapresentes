(() => {
  "use strict";

  function assinaturaNos(nos) {
    return nos.map((node) => {
      if (node.nodeType === Node.ELEMENT_NODE) return node.outerHTML;
      return `${node.nodeType}:${node.textContent || ""}`;
    }).join("\n");
  }

  function instalarListaEstavel(lista) {
    if (!lista || lista.dataset.renderEstavel === "1") return;
    lista.dataset.renderEstavel = "1";

    const replaceChildrenNativo = lista.replaceChildren.bind(lista);
    const appendNativo = lista.append.bind(lista);
    let buffer = null;
    let commitAgendado = false;

    function agendarCommit() {
      if (commitAgendado) return;
      commitAgendado = true;
      queueMicrotask(() => {
        commitAgendado = false;
        if (!buffer) return;

        const novosNos = buffer;
        buffer = null;
        const atuais = Array.from(lista.childNodes);
        if (assinaturaNos(atuais) === assinaturaNos(novosNos)) return;

        const ativo = document.activeElement;
        const cardAtivo = ativo?.closest?.("[data-pedido-id]");
        const pedidoId = cardAtivo?.dataset.pedidoId || null;
        const acao = ativo?.dataset?.acao || null;

        replaceChildrenNativo(...novosNos);

        if (pedidoId && acao) {
          lista.querySelector(`[data-pedido-id='${CSS.escape(pedidoId)}'] [data-acao='${CSS.escape(acao)}']`)?.focus({ preventScroll: true });
        }
      });
    }

    lista.replaceChildren = (...nos) => {
      if (nos.length) {
        buffer = null;
        return replaceChildrenNativo(...nos);
      }
      buffer = [];
      agendarCommit();
    };

    lista.append = (...nos) => {
      if (buffer) {
        buffer.push(...nos);
        agendarCommit();
        return;
      }
      appendNativo(...nos);
    };
  }

  function instalarSelectEstavel(select) {
    if (!select || select.dataset.renderEstavel === "1") return;
    select.dataset.renderEstavel = "1";
    const replaceChildrenNativo = select.replaceChildren.bind(select);

    select.replaceChildren = (...nos) => {
      const assinaturaAtual = Array.from(select.childNodes).map((node) => `${node.nodeName}:${node.value || ""}:${node.textContent || ""}`).join("|");
      const assinaturaNova = nos.map((node) => `${node.nodeName}:${node.value || ""}:${node.textContent || ""}`).join("|");
      if (assinaturaAtual === assinaturaNova) return;
      const valor = select.value;
      replaceChildrenNativo(...nos);
      if (Array.from(select.options).some((option) => option.value === valor)) select.value = valor;
    };
  }

  instalarListaEstavel(document.getElementById("listaPedidosUnificados"));
  instalarSelectEstavel(document.getElementById("filtroFinanceiroPedidos"));
})();
