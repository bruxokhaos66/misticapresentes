(() => {
  const config = window.misticaSiteConfig || {};
  const API_BASE = String(config.apiBaseUrl || "https://api.misticaesotericos.com.br").replace(/\/$/, "");
  const POLL_INTERVAL_MS = 15000;
  const AVISO_CONFIRMAR_PAGAMENTO =
    "Confirme no aplicativo bancário que o valor foi creditado. Um comprovante isolado pode ser falso.";

  const currency = new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" });

  const loginPanel = document.getElementById("loginPanelPix");
  const loginForm = document.getElementById("loginFormPix");
  const loginUser = document.getElementById("loginUserPix");
  const loginSenha = document.getElementById("loginSenhaPix");
  const loginStatus = document.getElementById("loginStatusPix");
  const painel = document.getElementById("painelPix");
  const lista = document.getElementById("listaPedidosPix");
  const contadorPendentes = document.getElementById("contadorPendentes");
  const contadorNovos = document.getElementById("contadorNovos");
  const somToggle = document.getElementById("somToggle");
  const btnSair = document.getElementById("btnSairPix");

  // IDs de pedidos já vistos NESTA sessão de navegador (memória, nunca
  // localStorage/sessionStorage: é só para decidir quando tocar o som de
  // aviso, não é dado administrativo persistido).
  let idsConhecidos = null;
  let pollTimer = null;
  let usuarioAtual = null;

  function escapeHtml(value) {
    return String(value == null ? "" : value)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  async function apiFetch(path, options = {}) {
    const response = await fetch(`${API_BASE}${path}`, {
      credentials: "include",
      cache: "no-store",
      ...options,
      headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data.detail || data.message || `Erro (${response.status})`);
    return data;
  }

  // Bip curto e discreto via WebAudio (sem depender de arquivo de áudio),
  // tocado no máximo uma vez por atualização — nunca em loop/contínuo.
  function tocarAvisoSonoro() {
    if (!somToggle?.checked) return;
    try {
      const AudioCtx = window.AudioContext || window.webkitAudioContext;
      if (!AudioCtx) return;
      const ctx = new AudioCtx();
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.type = "sine";
      osc.frequency.value = 880;
      gain.gain.setValueAtTime(0.0001, ctx.currentTime);
      gain.gain.exponentialRampToValueAtTime(0.15, ctx.currentTime + 0.02);
      gain.gain.exponentialRampToValueAtTime(0.0001, ctx.currentTime + 0.32);
      osc.connect(gain).connect(ctx.destination);
      osc.start();
      osc.stop(ctx.currentTime + 0.35);
      osc.onended = () => ctx.close().catch(() => {});
    } catch {
      // Ambiente sem suporte a WebAudio (raro): silenciosamente ignora, o
      // aviso visual (contador/destaque) continua funcionando normalmente.
    }
  }

  function telefoneDigits(telefone) {
    return String(telefone || "").replace(/\D/g, "");
  }

  function whatsappUrlParaCliente(pedido) {
    const digits = telefoneDigits(pedido.telefone);
    if (!digits) return null;
    const numero = digits.length <= 11 ? `55${digits}` : digits;
    const mensagem = `Olá, ${escapeHtml(pedido.cliente || "")}! Aqui é da Mística Presentes sobre o seu pedido #${pedido.id}.`;
    return `https://wa.me/${numero}?text=${encodeURIComponent(mensagem)}`;
  }

  function formatarItens(pedido) {
    const itens = Array.isArray(pedido.itens) ? pedido.itens : [];
    if (!itens.length) return "Sem itens registrados.";
    return itens.map(item => `${item.quantidade}x ${item.nome_p}`).join(", ");
  }

  function statusClasse(status) {
    return String(status || "").toLowerCase().replace(/[^a-z0-9]+/g, "-");
  }

  function renderPedidos(pedidos) {
    if (!pedidos.length) {
      lista.innerHTML = `<p class="admin-pix-vazio">Nenhum pedido Pix aguardando confirmação no momento.</p>`;
      return;
    }
    lista.innerHTML = pedidos.map(pedido => {
      const novo = !pedido.visualizado_admin_em;
      const waUrl = whatsappUrlParaCliente(pedido);
      const status = String(pedido.status || "");
      const podeMarcarRecebido = status === "Comprovante enviado";
      const podeRejeitar = status === "Comprovante enviado" || status === "Pagamento em análise";
      const podeConfirmar = status !== "Cancelado";
      return `
        <article class="pedido-pix-card${novo ? " pedido-pix-novo" : ""}" data-pedido-id="${pedido.id}" data-total="${pedido.total_final}" data-status="${escapeHtml(status)}">
          <div class="pedido-pix-cabecalho">
            <div class="pedido-pix-titulo">
              <strong>Pedido #${pedido.id}</strong>
              ${novo ? '<span class="pedido-pix-badge-novo">Novo</span>' : ""}
              <span class="pedido-pix-status status-${statusClasse(status)}">${escapeHtml(status)}</span>
            </div>
            <span>${escapeHtml(pedido.data_venda || pedido.data_iso || "")}</span>
          </div>
          <div class="pedido-pix-info">
            <span><strong>Cliente:</strong> ${escapeHtml(pedido.cliente || "Não informado")}</span>
            <span><strong>Telefone:</strong> ${escapeHtml(pedido.telefone || "Não informado")}</span>
            <span><strong>Valor:</strong> ${currency.format(Number(pedido.total_final || 0))}</span>
            <span><strong>Pagamento:</strong> ${escapeHtml(pedido.forma_pagamento || "Pix")}</span>
            ${pedido.payment_provider && pedido.payment_provider !== "manual_pix" ? `<span><strong>Provedor:</strong> ${escapeHtml(pedido.payment_provider)}${pedido.provider_payment_id ? ` (#${escapeHtml(pedido.provider_payment_id)})` : ""}</span>` : ""}
          </div>
          <p class="pedido-pix-itens"><strong>Itens:</strong> ${escapeHtml(formatarItens(pedido))}</p>
          ${status === "Comprovante enviado" || status === "Pagamento em análise" ? `<p class="pedido-pix-aviso-comprovante">O cliente indicou ter enviado o comprovante pelo WhatsApp. O site não confirma automaticamente se o anexo foi de fato enviado — confira a conversa antes de aprovar.</p>` : ""}
          <div class="pedido-pix-tentativas" data-tentativas-pedido="${pedido.id}" hidden></div>
          <div class="pedido-pix-acoes">
            <button type="button" class="btn btn-small btn-ghost" data-acao="visualizar">Marcar como visto</button>
            <button type="button" class="btn btn-small btn-ghost" data-acao="ver-tentativas">Ver tentativas de pagamento</button>
            ${waUrl ? `<a class="btn btn-small btn-ghost" href="${waUrl}" target="_blank" rel="noopener">Abrir WhatsApp</a>` : ""}
            ${podeMarcarRecebido ? `<button type="button" class="btn btn-small btn-ghost" data-acao="comprovante-recebido">Marcar comprovante recebido</button>` : ""}
            ${podeConfirmar ? `<button type="button" class="btn btn-small" data-acao="confirmar-pagamento">Confirmar pagamento</button>` : ""}
            ${podeRejeitar ? `<button type="button" class="btn btn-small btn-ghost" data-acao="rejeitar-comprovante">Rejeitar comprovante</button>` : ""}
            <button type="button" class="btn btn-small btn-ghost" data-acao="cancelar">Cancelar pedido</button>
          </div>
        </article>`;
    }).join("");
  }

  async function carregarPedidos({ primeiraCarga = false } = {}) {
    let resposta;
    try {
      resposta = await apiFetch("/api/pedidos/pix/pendentes?limite=100");
    } catch (error) {
      lista.innerHTML = `<p class="admin-pix-vazio">Não foi possível carregar os pedidos agora: ${escapeHtml(error.message)}</p>`;
      return;
    }
    const pedidos = Array.isArray(resposta.pedidos) ? resposta.pedidos : [];
    contadorPendentes.textContent = `${resposta.total || 0} aguardando`;
    if (resposta.total_nao_visualizados) {
      contadorNovos.hidden = false;
      contadorNovos.textContent = `${resposta.total_nao_visualizados} novo(s)`;
    } else {
      contadorNovos.hidden = true;
    }

    if (idsConhecidos === null) {
      idsConhecidos = new Set(pedidos.map(pedido => pedido.id));
    } else {
      const chegouNovo = pedidos.some(pedido => !idsConhecidos.has(pedido.id));
      pedidos.forEach(pedido => idsConhecidos.add(pedido.id));
      if (chegouNovo && !primeiraCarga) tocarAvisoSonoro();
    }

    renderPedidos(pedidos);
  }

  function formatarTentativa(tentativa) {
    const dataFormatada = escapeHtml(tentativa.atualizado_em || tentativa.criado_em || "");
    const provedor = escapeHtml(tentativa.provedor || "");
    const statusBadge = escapeHtml(tentativa.status_interno || "");
    const parcelas = tentativa.parcelas ? `${tentativa.parcelas}x` : "";
    const providerId = tentativa.provider_payment_id ? `#${escapeHtml(tentativa.provider_payment_id)}` : "";
    const motivo = tentativa.motivo_recusa ? ` — ${escapeHtml(tentativa.motivo_recusa)}` : "";
    const podeReconsultar = tentativa.provedor === "mercadopago" && tentativa.provider_payment_id;
    return `<div class="pedido-pix-tentativa-item" data-tentativa-id="${tentativa.id}">
      <span class="pedido-pix-status status-${statusClasse(statusBadge)}">${statusBadge}</span>
      <span>${provedor} ${parcelas} ${providerId}</span>
      <span>${dataFormatada}</span>
      <span>${motivo}</span>
      ${podeReconsultar ? `<button type="button" class="btn btn-small btn-ghost" data-acao="reconsultar-tentativa" data-tentativa-id="${tentativa.id}">Consultar novamente no provedor</button>` : ""}
    </div>`;
  }

  async function alternarTentativas(pedidoId, container) {
    if (!container.hidden) {
      container.hidden = true;
      return;
    }
    container.hidden = false;
    container.innerHTML = "<p>Carregando tentativas...</p>";
    try {
      const tentativas = await apiFetch(`/api/payments/mercadopago/tentativas/${pedidoId}`);
      container.innerHTML = Array.isArray(tentativas) && tentativas.length
        ? tentativas.map(formatarTentativa).join("")
        : "<p>Nenhuma tentativa de pagamento por provedor externo registrada para este pedido.</p>";
    } catch (error) {
      container.innerHTML = `<p>Não foi possível carregar as tentativas: ${escapeHtml(error.message)}</p>`;
    }
  }

  async function executarAcao(acao, pedidoId, valorTotal) {
    if (acao === "visualizar") {
      await apiFetch(`/api/pedidos/${pedidoId}/visualizar`, { method: "POST" });
    } else if (acao === "comprovante-recebido") {
      await apiFetch(`/api/pedidos/${pedidoId}/comprovante/recebido`, { method: "POST", body: "{}" });
    } else if (acao === "rejeitar-comprovante") {
      const motivo = window.prompt("Motivo da rejeição (opcional):", "") || "";
      await apiFetch(`/api/pedidos/${pedidoId}/comprovante/rejeitar`, { method: "POST", body: JSON.stringify({ observacao: motivo }) });
    } else if (acao === "cancelar") {
      if (!window.confirm(`Cancelar o pedido #${pedidoId}? Essa ação não pode ser desfeita por aqui.`)) return;
      await apiFetch(`/api/pedidos/${pedidoId}/cancelar-painel`, { method: "POST", body: "{}" });
    } else if (acao === "confirmar-pagamento") {
      if (!window.confirm(AVISO_CONFIRMAR_PAGAMENTO)) return;
      const valorDigitado = window.prompt(
        "Valor recebido conforme o aplicativo bancário (R$):",
        Number(valorTotal || 0).toFixed(2).replace(".", ","),
      );
      if (valorDigitado === null) return;
      const valor = Number(String(valorDigitado).replace(/\./g, "").replace(",", "."));
      if (!Number.isFinite(valor) || valor <= 0) {
        window.alert("Valor inválido.");
        return;
      }
      await apiFetch(`/api/pedidos/${pedidoId}/confirmar-pagamento-painel`, {
        method: "POST",
        body: JSON.stringify({ valor }),
      });
    }
  }

  lista.addEventListener("click", async event => {
    const botao = event.target.closest("[data-acao]");
    if (!botao) return;
    const card = botao.closest("[data-pedido-id]");
    if (!card) return;
    const pedidoId = card.dataset.pedidoId;
    const total = card.dataset.total;

    if (botao.dataset.acao === "ver-tentativas") {
      const container = card.querySelector(`[data-tentativas-pedido="${pedidoId}"]`);
      if (container) await alternarTentativas(pedidoId, container);
      return;
    }
    if (botao.dataset.acao === "reconsultar-tentativa") {
      botao.disabled = true;
      try {
        await apiFetch(`/api/payments/mercadopago/tentativas/${botao.dataset.tentativaId}/consultar`, { method: "POST" });
        const container = card.querySelector(`[data-tentativas-pedido="${pedidoId}"]`);
        if (container) { container.hidden = true; await alternarTentativas(pedidoId, container); }
        await carregarPedidos();
      } catch (error) {
        window.alert(error.message || "Não foi possível reconsultar o provedor.");
      } finally {
        botao.disabled = false;
      }
      return;
    }

    botao.disabled = true;
    try {
      await executarAcao(botao.dataset.acao, pedidoId, total);
      await carregarPedidos();
    } catch (error) {
      window.alert(error.message || "Não foi possível concluir a ação.");
    } finally {
      botao.disabled = false;
    }
  });

  function pararPolling() {
    if (pollTimer) clearInterval(pollTimer);
    pollTimer = null;
  }

  function iniciarPolling() {
    pararPolling();
    carregarPedidos({ primeiraCarga: true });
    pollTimer = setInterval(() => carregarPedidos(), POLL_INTERVAL_MS);
  }

  function mostrarPainel(sessao) {
    usuarioAtual = sessao?.usuario?.nome || sessao?.usuario?.login || "Admin";
    loginPanel.hidden = true;
    painel.hidden = false;
    iniciarPolling();
  }

  function mostrarLogin() {
    pararPolling();
    idsConhecidos = null;
    painel.hidden = true;
    loginPanel.hidden = false;
  }

  async function verificarSessao() {
    try {
      const sessao = await apiFetch("/api/auth/me");
      mostrarPainel(sessao);
    } catch {
      mostrarLogin();
    }
  }

  loginForm.addEventListener("submit", async event => {
    event.preventDefault();
    loginStatus.hidden = false;
    loginStatus.textContent = "Entrando...";
    try {
      const sessao = await apiFetch("/api/auth/login", {
        method: "POST",
        body: JSON.stringify({ login: loginUser.value.trim(), senha: loginSenha.value }),
      });
      loginForm.reset();
      loginStatus.hidden = true;
      mostrarPainel(sessao);
    } catch (error) {
      loginStatus.textContent = error.message || "Login ou senha inválidos.";
    }
  });

  btnSair.addEventListener("click", async () => {
    try {
      await apiFetch("/api/auth/logout", { method: "POST" });
    } catch {}
    mostrarLogin();
  });

  document.addEventListener("visibilitychange", () => {
    if (document.hidden) return;
    if (!painel.hidden) carregarPedidos();
  });

  verificarSessao();
})();
