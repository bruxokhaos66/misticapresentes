(() => {
  "use strict";

  const config = window.misticaSiteConfig || {};
  const API_BASE = String(config.apiBaseUrl || "https://api.misticaesotericos.com.br").replace(/\/$/, "");
  const dialog = document.getElementById("detalhePedidoDialog");
  const titulo = document.getElementById("detalhePedidoTitulo");
  const conteudo = document.getElementById("detalhePedidoConteudo");
  const operacoes = new Set();
  const carregamentos = new Set();

  if (!dialog || !titulo || !conteudo) return;

  function elemento(tag, classe, texto) {
    const node = document.createElement(tag);
    if (classe) node.className = classe;
    if (texto !== undefined && texto !== null) node.textContent = String(texto);
    return node;
  }

  async function apiFetch(path, options = {}) {
    const response = await fetch(`${API_BASE}${path}`, {
      credentials: "include",
      cache: "no-store",
      ...options,
      headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
      const error = new Error(data.detail || data.message || "Não foi possível concluir esta operação.");
      error.status = response.status;
      throw error;
    }
    return data;
  }

  function pedidoIdAtual() {
    const match = String(titulo.textContent || "").match(/#(\d+)/);
    return match ? Number(match[1]) : null;
  }

  function criarCampo(rotulo, controle) {
    const label = elemento("label", "admin-logistica-campo");
    label.append(elemento("span", "", rotulo), controle);
    return label;
  }

  function atualizarVisibilidadeRastreio(select, campoRastreio, aviso) {
    const retirada = select.value === "retirada";
    campoRastreio.disabled = retirada;
    campoRastreio.required = false;
    if (retirada) campoRastreio.value = "";
    aviso.hidden = !retirada;
  }

  function criarModulo(pedidoId, dados) {
    const secao = elemento("section", "admin-detalhe-secao admin-logistica-secao");
    secao.dataset.moduloLogistica = String(pedidoId);
    secao.append(elemento("h3", "", "Logística de retirada ou entrega"));
    secao.append(elemento("p", "admin-logistica-ajuda", "Atualize somente a operação logística. O pagamento e a situação financeira não são alterados."));

    const form = elemento("form", "admin-logistica-form");
    const forma = elemento("select", "admin-logistica-select");
    forma.name = "forma_recebimento";
    forma.required = true;
    forma.append(
      new Option("Selecione", ""),
      new Option("Retirada na loja", "retirada"),
      new Option("Entrega", "entrega")
    );
    forma.value = String(dados.forma_recebimento || "").toLowerCase();

    const rastreio = elemento("input", "admin-logistica-rastreio");
    rastreio.name = "codigo_rastreio";
    rastreio.maxLength = 120;
    rastreio.autocomplete = "off";
    rastreio.placeholder = "Código fornecido pela transportadora";
    rastreio.value = dados.codigo_rastreio || "";

    const observacao = elemento("textarea", "admin-logistica-observacao");
    observacao.name = "observacao";
    observacao.maxLength = 280;
    observacao.rows = 3;
    observacao.placeholder = "Ex.: cliente avisado, embalagem pronta ou instrução de entrega";
    observacao.value = dados.observacao_pedido || "";

    const aviso = elemento("p", "admin-logistica-aviso", "Pedidos para retirada não usam código de rastreio.");
    aviso.hidden = true;
    forma.addEventListener("change", () => atualizarVisibilidadeRastreio(forma, rastreio, aviso));
    atualizarVisibilidadeRastreio(forma, rastreio, aviso);

    const status = elemento("p", "admin-logistica-status");
    status.hidden = true;
    status.setAttribute("role", "status");

    const salvar = elemento("button", "btn", "Salvar logística");
    salvar.type = "submit";

    form.append(
      criarCampo("Forma de recebimento", forma),
      criarCampo("Código de rastreio", rastreio),
      aviso,
      criarCampo("Observação logística", observacao),
      salvar,
      status
    );

    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      const chave = `logistica-${pedidoId}`;
      if (operacoes.has(chave)) return;
      if (!forma.value) {
        status.hidden = false;
        status.textContent = "Selecione retirada ou entrega.";
        forma.focus();
        return;
      }

      operacoes.add(chave);
      salvar.disabled = true;
      status.hidden = false;
      status.textContent = "Salvando logística...";
      try {
        const resposta = await apiFetch(`/api/pedidos/${pedidoId}/logistica`, {
          method: "PATCH",
          body: JSON.stringify({
            forma_recebimento: forma.value,
            codigo_rastreio: rastreio.value.trim() || null,
            observacao: observacao.value.trim() || null,
          }),
        });
        rastreio.value = resposta.codigo_rastreio || "";
        status.textContent = "Logística atualizada com segurança.";
      } catch (error) {
        status.textContent = error.message || "Não foi possível salvar a logística.";
      } finally {
        salvar.disabled = false;
        operacoes.delete(chave);
      }
    });

    secao.append(form);
    return secao;
  }

  async function montarLogistica() {
    const pedidoId = pedidoIdAtual();
    if (!pedidoId) return;
    if (!conteudo.querySelector(".admin-detalhe-secao")) return;
    if (conteudo.querySelector(`[data-modulo-logistica='${pedidoId}']`)) return;
    if (carregamentos.has(pedidoId)) return;

    carregamentos.add(pedidoId);
    const placeholder = elemento("section", "admin-detalhe-secao admin-logistica-secao");
    placeholder.dataset.moduloLogistica = String(pedidoId);
    placeholder.append(elemento("h3", "", "Logística de retirada ou entrega"));
    placeholder.append(elemento("p", "admin-logistica-ajuda", "Carregando dados logísticos..."));
    conteudo.append(placeholder);

    try {
      const dados = await apiFetch(`/api/pedidos/${pedidoId}/logistica`);
      if (placeholder.isConnected) placeholder.replaceWith(criarModulo(pedidoId, dados));
    } catch (error) {
      if (placeholder.isConnected) {
        placeholder.replaceChildren(
          elemento("h3", "", "Logística de retirada ou entrega"),
          elemento("p", "admin-logistica-status", error.message || "Não foi possível carregar a logística.")
        );
      }
    } finally {
      carregamentos.delete(pedidoId);
    }
  }

  const observer = new MutationObserver(() => {
    if (!dialog.open) return;
    window.requestAnimationFrame(montarLogistica);
  });
  observer.observe(conteudo, { childList: true });
})();
