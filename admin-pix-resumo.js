(() => {
  const config = window.misticaSiteConfig || {};
  const API_BASE = String(config.apiBaseUrl || "https://api.misticaesotericos.com.br").replace(/\/$/, "");
  const POLL_INTERVAL_MS = 15000;
  const LIMITE_RESUMO = 8;
  const SOM_PREF_KEY = "misticaAdminPixSomAtivo";

  const currency = new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" });

  let elementos = null;
  let pollTimer = null;
  let requisicaoEmAndamento = false;
  // IDs já vistos NESTA sessão de navegador, só em memória (nunca
  // localStorage) -- serve apenas para decidir quando tocar o aviso sonoro
  // de "pedido novo", nunca é dado administrativo persistido.
  let idsConhecidos = null;
  let ativo = false;

  function $(id) { return document.getElementById(id); }

  function garantirElementos() {
    if (elementos) return elementos;
    const painel = $("pedidosPixResumo");
    if (!painel) return null;
    elementos = {
      painel,
      lista: $("pixResumoLista"),
      contadorPendentes: $("pixResumoContadorPendentes"),
      contadorNovos: $("pixResumoContadorNovos"),
      avisoNovo: $("pixResumoAvisoNovo"),
      atualizadoEm: $("pixResumoAtualizadoEm"),
      somToggle: $("pixResumoSomToggle"),
      btnAtualizar: $("pixResumoAtualizar"),
      badgeHeader: $("badgeHeaderPixPedidos"),
    };
    return elementos;
  }

  function escapeHtml(value) {
    return String(value == null ? "" : value)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  function lerPreferenciaSom() {
    try {
      const valor = localStorage.getItem(SOM_PREF_KEY);
      return valor === null ? true : valor === "1";
    } catch {
      return true;
    }
  }

  function salvarPreferenciaSom(ativo) {
    try { localStorage.setItem(SOM_PREF_KEY, ativo ? "1" : "0"); } catch {}
  }

  // Bip curto via WebAudio, no máximo uma vez por atualização, nunca em loop.
  function tocarAvisoSonoro() {
    const els = garantirElementos();
    if (!els || !els.somToggle?.checked) return;
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
      // Ambiente sem WebAudio (raro): o aviso visual continua funcionando.
    }
  }

  function telefoneMascarado(telefone) {
    const digits = String(telefone || "").replace(/\D/g, "");
    if (digits.length < 8) return digits ? "••••" : "Não informado";
    const inicio = digits.slice(0, 2);
    const fim = digits.slice(-4);
    return `(${inicio}) •••••-${fim}`;
  }

  function telefoneDigits(telefone) {
    return String(telefone || "").replace(/\D/g, "");
  }

  function whatsappUrlParaCliente(pedido) {
    const digits = telefoneDigits(pedido.telefone);
    if (!digits) return null;
    const numero = digits.length <= 11 ? `55${digits}` : digits;
    const mensagem = `Olá, ${pedido.cliente || ""}! Aqui é da Mística Presentes sobre o seu pedido #${pedido.id}.`;
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

  function comprovanteInformado(pedido) {
    return Boolean(pedido.comprovante_enviado_em);
  }

  function renderPedidos(pedidos) {
    const els = garantirElementos();
    if (!els) return;
    if (!pedidos.length) {
      els.lista.innerHTML = `<p class="admin-pix-vazio">Não há pedidos Pix aguardando atendimento.</p>`;
      return;
    }
    els.lista.innerHTML = pedidos.map(pedido => {
      const novo = !pedido.visualizado_admin_em;
      const waUrl = whatsappUrlParaCliente(pedido);
      const status = String(pedido.status || "");
      return `
        <article class="pedido-pix-resumo-card${novo ? " pedido-pix-novo" : ""}" data-pedido-id="${escapeHtml(pedido.id)}">
          <div class="pedido-pix-resumo-cabecalho">
            <div class="pedido-pix-resumo-titulo">
              <strong>Pedido #${escapeHtml(pedido.id)}</strong>
              ${novo ? '<span class="pedido-pix-badge-novo">Novo pedido Pix</span>' : ""}
              <span class="pedido-pix-resumo-status status-${statusClasse(status)}">${escapeHtml(status)}</span>
            </div>
            <span>${escapeHtml(pedido.data_venda || pedido.data_iso || "")}</span>
          </div>
          <div class="pedido-pix-resumo-info">
            <span><strong>Cliente:</strong> ${escapeHtml(pedido.cliente || "Não informado")}</span>
            <span><strong>Telefone:</strong> ${escapeHtml(telefoneMascarado(pedido.telefone))}</span>
            <span><strong>Valor:</strong> ${escapeHtml(currency.format(Number(pedido.total_final || 0)))}</span>
            <span><strong>Visualizado:</strong> ${novo ? "Não" : "Sim"}</span>
            <span><strong>Cliente informou pagamento:</strong> ${comprovanteInformado(pedido) ? "Sim" : "Não"}</span>
          </div>
          <p class="pedido-pix-resumo-itens"><strong>Itens:</strong> ${escapeHtml(formatarItens(pedido))}</p>
          <div class="pedido-pix-resumo-acoes">
            <button type="button" class="btn btn-small btn-ghost" data-acao="visualizar">Visualizar</button>
            ${waUrl ? `<a class="btn btn-small btn-ghost" href="${waUrl}" target="_blank" rel="noopener">Abrir WhatsApp do cliente</a>` : ""}
            <a class="btn btn-small btn-ghost" href="admin-pedidos-pix.html">Abrir painel completo</a>
          </div>
        </article>`;
    }).join("");
  }

  function atualizarBadgeHeader(totalNaoVisualizados) {
    const els = garantirElementos();
    const badge = els?.badgeHeader;
    if (!badge) return;
    if (totalNaoVisualizados > 0) {
      badge.hidden = false;
      badge.textContent = String(totalNaoVisualizados);
    } else {
      badge.hidden = true;
    }
  }

  async function carregarResumo() {
    const els = garantirElementos();
    if (!els || !ativo) return;
    if (requisicaoEmAndamento) return;
    requisicaoEmAndamento = true;
    try {
      const response = await fetch(`${API_BASE}/api/pedidos/pix/pendentes?limite=${LIMITE_RESUMO}`, {
        method: "GET",
        credentials: "include",
        cache: "no-store",
      });
      const dados = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(dados.detail || dados.message || `Erro (${response.status})`);

      const pedidos = Array.isArray(dados.pedidos) ? dados.pedidos : [];
      els.contadorPendentes.textContent = `${dados.total || 0} aguardando`;
      if (dados.total_nao_visualizados) {
        els.contadorNovos.hidden = false;
        els.contadorNovos.textContent = `${dados.total_nao_visualizados} novo(s)`;
      } else {
        els.contadorNovos.hidden = true;
      }
      atualizarBadgeHeader(dados.total_nao_visualizados || 0);

      const primeiraCarga = idsConhecidos === null;
      if (primeiraCarga) {
        idsConhecidos = new Set(pedidos.map(pedido => pedido.id));
      } else {
        const chegouNovo = pedidos.some(pedido => !idsConhecidos.has(pedido.id));
        pedidos.forEach(pedido => idsConhecidos.add(pedido.id));
        if (chegouNovo) {
          els.avisoNovo.hidden = false;
          tocarAvisoSonoro();
        }
      }

      renderPedidos(pedidos);
      els.atualizadoEm.textContent = `Última atualização: ${new Date().toLocaleString("pt-BR")}`;
    } catch (error) {
      els.lista.innerHTML = `<p class="admin-pix-vazio admin-pix-erro">Não foi possível atualizar os pedidos. Tentaremos novamente.</p>`;
    } finally {
      requisicaoEmAndamento = false;
    }
  }

  async function executarAcaoRapida(acao, pedidoId) {
    if (acao !== "visualizar") return;
    await fetch(`${API_BASE}/api/pedidos/${encodeURIComponent(pedidoId)}/visualizar`, {
      method: "POST",
      credentials: "include",
      cache: "no-store",
      headers: { "Content-Type": "application/json" },
    });
    await carregarResumo();
  }

  function pararPolling() {
    if (pollTimer) clearInterval(pollTimer);
    pollTimer = null;
  }

  function iniciarPollingTimer() {
    pararPolling();
    pollTimer = setInterval(carregarResumo, POLL_INTERVAL_MS);
  }

  function instalarEventosUmaVez() {
    const els = garantirElementos();
    if (!els || els.painel.dataset.pixResumoInstalado === "true") return;
    els.painel.dataset.pixResumoInstalado = "true";

    els.somToggle.checked = lerPreferenciaSom();
    els.somToggle.addEventListener("change", () => salvarPreferenciaSom(els.somToggle.checked));

    els.btnAtualizar.addEventListener("click", () => carregarResumo());

    els.lista.addEventListener("click", async event => {
      const botao = event.target.closest("[data-acao]");
      if (!botao) return;
      const card = botao.closest("[data-pedido-id]");
      if (!card) return;
      botao.disabled = true;
      try {
        await executarAcaoRapida(botao.dataset.acao, card.dataset.pedidoId);
      } finally {
        botao.disabled = false;
      }
    });

    document.addEventListener("visibilitychange", () => {
      if (!ativo) return;
      if (document.hidden) {
        pararPolling();
        return;
      }
      carregarResumo();
      iniciarPollingTimer();
    });
  }

  function iniciar() {
    const els = garantirElementos();
    if (!els) return;
    instalarEventosUmaVez();
    if (ativo) return; // já rodando: nunca cria um segundo timer.
    ativo = true;
    idsConhecidos = null;
    els.avisoNovo.hidden = true;
    carregarResumo();
    if (!document.hidden) iniciarPollingTimer();
  }

  function parar() {
    ativo = false;
    pararPolling();
    idsConhecidos = null;
    requisicaoEmAndamento = false;
    const els = garantirElementos();
    if (els) atualizarBadgeHeader(0);
  }

  window.misticaAdminPixResumo = { iniciar, parar };

  // O login/logout do painel principal é hoje resolvido por mais de um
  // script legado (painel-auth.js e o bloco de captura em site-config.js,
  // este último só ativo em modo produção) que alternam a visibilidade de
  // #adminContent de formas diferentes. Em vez de duplicar/acoplar a este
  // fluxo de autenticação já existente, observamos diretamente a
  // visibilidade de #adminContent (a mesma sessão de administrador,
  // revalidada pelo servidor em cada chamada) e ligamos/desligamos o
  // polling só a partir dela -- funciona com qualquer um dos fluxos, sem
  // criar um segundo login.
  function observarAdminContent() {
    const adminContent = document.getElementById("adminContent");
    if (!adminContent) return;
    const verificar = () => {
      const visivel = !adminContent.hidden && adminContent.style.display !== "none";
      if (visivel) iniciar();
      else parar();
    };
    verificar();
    new MutationObserver(verificar).observe(adminContent, { attributes: true, attributeFilter: ["hidden", "style"] });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", observarAdminContent, { once: true });
  } else {
    observarAdminContent();
  }
})();
