(() => {
  "use strict";

  const config = window.misticaSiteConfig || {};
  const API_BASE = String(config.apiBaseUrl || "https://api.misticaesotericos.com.br").replace(/\/$/, "");
  const POLL_LISTA_MS = 8000;
  const POLL_MENSAGENS_MS = 6000;

  const loginPanel = document.getElementById("loginPanelCentral");
  const loginForm = document.getElementById("loginFormCentral");
  const loginUser = document.getElementById("loginUserCentral");
  const loginSenha = document.getElementById("loginSenhaCentral");
  const loginStatus = document.getElementById("loginStatusCentral");

  const appEl = document.getElementById("appCentral");
  const statusPill = document.getElementById("statusPill");
  const btnSair = document.getElementById("btnSair");
  const btnAtivarNotificacoes = document.getElementById("btnAtivarNotificacoes");

  const buscaConversas = document.getElementById("buscaConversas");
  const filtrosStatusBtns = Array.from(document.querySelectorAll(".filtro-btn[data-status], .filtro-btn[data-unread]"));
  const listaConversas = document.getElementById("listaConversas");
  const statusListaConversas = document.getElementById("statusListaConversas");

  const semConversa = document.getElementById("semConversa");
  const painelConversa = document.getElementById("painelConversa");
  const conversaNome = document.getElementById("conversaNome");
  const conversaTelefone = document.getElementById("conversaTelefone");
  const selectStatusConversa = document.getElementById("selectStatusConversa");
  const listaMensagens = document.getElementById("listaMensagens");
  const formEnviarMensagem = document.getElementById("formEnviarMensagem");
  const selectTemplate = document.getElementById("selectTemplate");
  const campoTexto = document.getElementById("campoTexto");
  const btnEnviarMensagem = document.getElementById("btnEnviarMensagem");
  const statusEnvio = document.getElementById("statusEnvio");

  const colLateral = document.getElementById("colLateral");
  const clienteInfo = document.getElementById("clienteInfo");
  const formVincularCliente = document.getElementById("formVincularCliente");
  const campoClienteId = document.getElementById("campoClienteId");
  const formVincularPedido = document.getElementById("formVincularPedido");
  const campoPedidoId = document.getElementById("campoPedidoId");
  const statusVinculo = document.getElementById("statusVinculo");

  let filtroStatusAtual = "";
  let apenasNaoLidas = false;
  let conversaSelecionadaId = null;
  let ultimoMessageIdConhecido = 0;
  let idsConversasConhecidos = new Set();
  let notificacaoSonoraHabilitada = true;
  let pollListaTimer = null;
  let pollMensagensTimer = null;

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
    if (response.status === 401 || response.status === 403) {
      pararPolling();
      mostrarLogin();
      const erro = new Error("Sessão expirada. Faça login novamente.");
      erro.status = response.status;
      throw erro;
    }
    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
      const erro = new Error(data.detail || "Não foi possível concluir esta operação.");
      erro.status = response.status;
      throw erro;
    }
    return data;
  }

  const dateTime = new Intl.DateTimeFormat("pt-BR", { dateStyle: "short", timeStyle: "short" });
  function formatarData(valor) {
    if (!valor) return "";
    const data = new Date(valor);
    return Number.isNaN(data.getTime()) ? "" : dateTime.format(data);
  }

  function mostrarLogin() {
    loginPanel.hidden = false;
    appEl.hidden = true;
  }

  function mostrarApp() {
    loginPanel.hidden = true;
    appEl.hidden = false;
  }

  // ---------------------------------------------------------------------
  // Login
  // ---------------------------------------------------------------------
  loginForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    loginStatus.hidden = false;
    loginStatus.textContent = "Entrando…";
    try {
      await apiFetch("/api/auth/login", {
        method: "POST",
        body: JSON.stringify({ login: loginUser.value.trim(), senha: loginSenha.value }),
      });
      loginForm.reset();
      loginStatus.hidden = true;
      mostrarApp();
      iniciar();
    } catch (erro) {
      loginStatus.textContent = erro.message || "Login ou senha inválidos.";
    }
  });

  btnSair.addEventListener("click", async () => {
    try { await apiFetch("/api/auth/logout", { method: "POST", body: "{}" }); } catch { /* ignora falha de logout */ }
    pararPolling();
    mostrarLogin();
  });

  // ---------------------------------------------------------------------
  // Notificações (só após clique explícito -- nunca solicitado automaticamente)
  // ---------------------------------------------------------------------
  btnAtivarNotificacoes.addEventListener("click", async () => {
    if (!("Notification" in window)) {
      btnAtivarNotificacoes.textContent = "Notificações indisponíveis neste navegador";
      btnAtivarNotificacoes.disabled = true;
      return;
    }
    const permissao = await Notification.requestPermission();
    btnAtivarNotificacoes.textContent = permissao === "granted" ? "Notificações ativadas" : "Notificações negadas";
    if (permissao === "granted") btnAtivarNotificacoes.disabled = true;
  });

  function notificarNovaMensagem(conversa) {
    if ("Notification" in window && Notification.permission === "granted") {
      const nome = (conversa && conversa.contact && conversa.contact.profile_name) || "Novo contato";
      new Notification("Nova mensagem no WhatsApp", { body: `${nome} enviou uma mensagem.` });
    }
  }

  // ---------------------------------------------------------------------
  // Status
  // ---------------------------------------------------------------------
  async function atualizarStatus() {
    try {
      const dados = await apiFetch("/api/admin/whatsapp/status");
      notificacaoSonoraHabilitada = dados.notification_sound_enabled !== false;
      if (dados.webhook_ready) {
        statusPill.textContent = "Central de Atendimento ativa";
        statusPill.className = "pill ok";
      } else {
        statusPill.textContent = "Central de Atendimento desativada/não configurada";
        statusPill.className = "pill erro";
      }
    } catch {
      statusPill.textContent = "Falha ao consultar status";
      statusPill.className = "pill erro";
    }
  }

  // ---------------------------------------------------------------------
  // Lista de conversas
  // ---------------------------------------------------------------------
  filtrosStatusBtns.forEach((botao) => {
    botao.addEventListener("click", () => {
      filtrosStatusBtns.forEach((b) => b.classList.remove("is-active"));
      botao.classList.add("is-active");
      if (botao.dataset.unread) {
        apenasNaoLidas = true;
        filtroStatusAtual = "";
      } else {
        apenasNaoLidas = false;
        filtroStatusAtual = botao.dataset.status || "";
      }
      carregarConversas();
    });
  });

  let buscaTimer = null;
  buscaConversas.addEventListener("input", () => {
    clearTimeout(buscaTimer);
    buscaTimer = setTimeout(carregarConversas, 300);
  });

  function montarItemConversa(conversa) {
    const item = elemento("li");
    const botao = elemento("button", "item-conversa");
    botao.type = "button";
    botao.dataset.id = String(conversa.id);
    if (conversa.id === conversaSelecionadaId) botao.classList.add("is-selected");

    const topo = elemento("div", "linha-topo");
    topo.append(elemento("span", "nome", (conversa.contact && conversa.contact.profile_name) || "Contato sem nome"));
    topo.append(elemento("span", "hora", formatarData(conversa.last_message_at)));
    botao.append(topo);

    const linha2 = elemento("div", "linha-topo");
    linha2.append(elemento("span", "preview", `•••${(conversa.contact && conversa.contact.phone_last4) || "----"}`));
    if (conversa.unread_count > 0) linha2.append(elemento("span", "badge-nao-lida", String(conversa.unread_count)));
    botao.append(linha2);

    if (conversa.order_id || conversa.customer_id) {
      const vinculo = elemento("span", "badge-vinculo", conversa.order_id ? `Pedido #${conversa.order_id}` : `Cliente #${conversa.customer_id}`);
      botao.append(vinculo);
    }

    botao.addEventListener("click", () => abrirConversa(conversa.id));
    item.append(botao);
    return item;
  }

  async function carregarConversas() {
    try {
      const params = new URLSearchParams();
      if (filtroStatusAtual) params.set("status", filtroStatusAtual);
      if (apenasNaoLidas) params.set("unread_only", "true");
      if (buscaConversas.value.trim()) params.set("q", buscaConversas.value.trim());
      params.set("page_size", "50");

      const dados = await apiFetch(`/api/admin/whatsapp/conversations?${params.toString()}`);
      listaConversas.textContent = "";
      const idsAtuais = new Set(dados.conversations.map((c) => c.id));
      for (const conversa of dados.conversations) {
        listaConversas.append(montarItemConversa(conversa));
        if (!idsConversasConhecidos.has(conversa.id) && idsConversasConhecidos.size > 0 && conversa.unread_count > 0) {
          notificarNovaMensagem(conversa);
        }
      }
      idsConversasConhecidos = idsAtuais;
      statusListaConversas.textContent = dados.conversations.length ? "" : "Nenhuma conversa encontrada.";
    } catch (erro) {
      if (erro.status !== 401 && erro.status !== 403) {
        statusListaConversas.textContent = "Falha ao carregar conversas.";
      }
    }
  }

  // ---------------------------------------------------------------------
  // Conversa selecionada / mensagens
  // ---------------------------------------------------------------------
  async function abrirConversa(id) {
    conversaSelecionadaId = id;
    semConversa.hidden = true;
    painelConversa.hidden = false;
    colLateral.hidden = false;
    ultimoMessageIdConhecido = 0;
    listaMensagens.textContent = "";

    try {
      const detalhe = await apiFetch(`/api/admin/whatsapp/conversations/${id}`);
      preencherCabecalhoConversa(detalhe.conversation);
      await carregarMensagens();
      await apiFetch(`/api/admin/whatsapp/conversations/${id}/read`, { method: "POST" });
      carregarConversas();
    } catch {
      statusEnvio.textContent = "Falha ao abrir a conversa.";
    }

    reiniciarPollMensagens();
  }

  function preencherCabecalhoConversa(conversa) {
    conversaNome.textContent = (conversa.contact && conversa.contact.profile_name) || "Contato sem nome";
    conversaTelefone.textContent = `•••${(conversa.contact && conversa.contact.phone_last4) || "----"}`;
    selectStatusConversa.value = conversa.status || "open";

    clienteInfo.textContent = "";
    if (conversa.customer_id) {
      const dl = elemento("dl");
      dl.append(elemento("dt", "", "Cliente vinculado"));
      dl.append(elemento("dd", "", `#${conversa.customer_id}`));
      if (conversa.order_id) {
        dl.append(elemento("dt", "", "Pedido vinculado"));
        dl.append(elemento("dd", "", `#${conversa.order_id}`));
      }
      clienteInfo.append(dl);
    } else {
      clienteInfo.append(elemento("p", "hint", "Nenhum cliente vinculado a esta conversa."));
    }
  }

  function montarBolhaMensagem(mensagem) {
    const bolha = elemento("div", `bolha ${mensagem.direction}`);
    let corpo = mensagem.text_body;
    if (!corpo && mensagem.media_id) corpo = `[${mensagem.message_type}] mídia recebida`;
    if (!corpo) corpo = "[Tipo de mensagem ainda não suportado]";
    bolha.append(elemento("span", "", corpo));

    if (mensagem.media_id) {
      const botao = document.createElement("button");
      botao.type = "button";
      botao.className = "midia-link";
      botao.textContent = "Abrir mídia";
      botao.addEventListener("click", () => abrirMidia(mensagem.id, botao));
      bolha.append(document.createElement("br"), botao);
    }

    const rotuloStatus = { queued: "enviando…", sent: "enviado", delivered: "entregue", read: "lido", failed: "falhou", received: "recebido" }[mensagem.status] || mensagem.status;
    const meta = elemento("small", "meta", `${formatarData(mensagem.created_at)} · ${rotuloStatus}`);
    bolha.append(meta);
    return bolha;
  }

  // ---------------------------------------------------------------------
  // Mídia recebida: preview seguro em modal + download com extensão correta
  //
  // Nunca usa <a target="_blank"> direto para a API: sempre passa por
  // fetch() autenticado, confere response.ok e Content-Type ANTES de criar
  // qualquer Blob (uma resposta de erro em JSON nunca vira "imagem"), e
  // revoga o Object URL assim que o modal fecha ou uma nova mídia é aberta.
  // ---------------------------------------------------------------------
  const modalMidia = document.getElementById("modalMidia");
  const modalMidiaCorpo = document.getElementById("modalMidiaCorpo");
  const btnFecharModalMidia = document.getElementById("btnFecharModalMidia");
  const linkBaixarMidia = document.getElementById("linkBaixarMidia");
  let objectUrlAtual = null;
  let elementoComFocoAntesDoModal = null;

  const EXTENSOES_POR_MIME = {
    "image/jpeg": "jpg",
    "image/png": "png",
    "image/webp": "webp",
    "application/pdf": "pdf",
    "audio/ogg": "ogg",
    "audio/mpeg": "mp3",
    "video/mp4": "mp4",
    "audio/mp4": "m4a",
    "video/3gpp": "3gp",
  };

  function revogarObjectUrlAtual() {
    if (objectUrlAtual) {
      URL.revokeObjectURL(objectUrlAtual);
      objectUrlAtual = null;
    }
  }

  function fecharModalMidia() {
    modalMidia.hidden = true;
    modalMidiaCorpo.textContent = "";
    linkBaixarMidia.hidden = true;
    linkBaixarMidia.removeAttribute("href");
    revogarObjectUrlAtual();
    if (elementoComFocoAntesDoModal) {
      elementoComFocoAntesDoModal.focus();
      elementoComFocoAntesDoModal = null;
    }
  }

  btnFecharModalMidia.addEventListener("click", fecharModalMidia);
  modalMidia.addEventListener("click", (event) => {
    if (event.target === modalMidia) fecharModalMidia();
  });
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && !modalMidia.hidden) fecharModalMidia();
  });

  function abrirModalComConteudo(nodo) {
    modalMidiaCorpo.textContent = "";
    modalMidiaCorpo.append(nodo);
    elementoComFocoAntesDoModal = document.activeElement;
    modalMidia.hidden = false;
    btnFecharModalMidia.focus();
  }

  async function abrirMidia(messageId, botaoOrigem) {
    const rotuloOriginal = botaoOrigem.textContent;
    botaoOrigem.disabled = true;
    botaoOrigem.textContent = "Carregando…";
    try {
      const resposta = await fetch(`${API_BASE}/api/admin/whatsapp/media/${messageId}`, {
        credentials: "include",
        cache: "no-store",
      });

      if (resposta.status === 401 || resposta.status === 403) {
        pararPolling();
        mostrarLogin();
        return;
      }

      const tipoConteudo = (resposta.headers.get("content-type") || "").split(";")[0].trim().toLowerCase();

      if (!resposta.ok) {
        // Uma falha (404/409/502) nunca é tratada como mídia -- lê a
        // mensagem de erro (se houver) e mostra em texto simples, nunca
        // cria um Blob/objectURL a partir do corpo de erro.
        let detalhe = "Não foi possível carregar esta mídia.";
        if (tipoConteudo === "application/json") {
          const corpoErro = await resposta.json().catch(() => null);
          if (corpoErro && corpoErro.detail) detalhe = corpoErro.detail;
        }
        abrirModalComConteudo(elemento("p", "hint", detalhe));
        return;
      }

      if (!tipoConteudo || tipoConteudo === "application/json" || tipoConteudo === "text/html") {
        abrirModalComConteudo(elemento("p", "hint", "Tipo de arquivo não suportado para preview."));
        return;
      }

      const blob = await resposta.blob();
      revogarObjectUrlAtual();
      objectUrlAtual = URL.createObjectURL(blob);

      const extensao = EXTENSOES_POR_MIME[tipoConteudo] || "bin";
      linkBaixarMidia.href = objectUrlAtual;
      linkBaixarMidia.download = `midia-${messageId}.${extensao}`;
      linkBaixarMidia.hidden = false;

      if (tipoConteudo.startsWith("image/")) {
        const img = document.createElement("img");
        img.src = objectUrlAtual;
        img.alt = "Imagem recebida do cliente";
        abrirModalComConteudo(img);
      } else if (tipoConteudo === "application/pdf") {
        abrirModalComConteudo(elemento("p", "hint", "PDF pronto -- use o botão \"Baixar arquivo\" para abrir."));
      } else if (tipoConteudo.startsWith("audio/")) {
        const audio = document.createElement("audio");
        audio.controls = true;
        audio.src = objectUrlAtual;
        abrirModalComConteudo(audio);
      } else if (tipoConteudo.startsWith("video/")) {
        const video = document.createElement("video");
        video.controls = true;
        video.src = objectUrlAtual;
        abrirModalComConteudo(video);
      } else {
        abrirModalComConteudo(elemento("p", "hint", "Tipo de arquivo não suportado para preview -- use o botão \"Baixar arquivo\"."));
      }
    } catch {
      abrirModalComConteudo(elemento("p", "hint", "Falha ao carregar a mídia."));
    } finally {
      botaoOrigem.disabled = false;
      botaoOrigem.textContent = rotuloOriginal;
    }
  }

  async function carregarMensagens() {
    if (!conversaSelecionadaId) return;
    try {
      const dados = await apiFetch(`/api/admin/whatsapp/conversations/${conversaSelecionadaId}/messages?limit=100`);
      listaMensagens.textContent = "";
      let ultimoId = 0;
      for (const mensagem of dados.messages) {
        listaMensagens.append(montarBolhaMensagem(mensagem));
        ultimoId = Math.max(ultimoId, mensagem.id);
      }
      ultimoMessageIdConhecido = ultimoId;
      listaMensagens.scrollTop = listaMensagens.scrollHeight;
    } catch {
      /* silencioso: próxima atualização tenta de novo */
    }
  }

  function reiniciarPollMensagens() {
    if (pollMensagensTimer) clearInterval(pollMensagensTimer);
    pollMensagensTimer = setInterval(carregarMensagens, POLL_MENSAGENS_MS);
  }

  selectStatusConversa.addEventListener("change", async () => {
    if (!conversaSelecionadaId) return;
    try {
      await apiFetch(`/api/admin/whatsapp/conversations/${conversaSelecionadaId}`, {
        method: "PATCH",
        body: JSON.stringify({ status: selectStatusConversa.value }),
      });
      carregarConversas();
    } catch {
      statusEnvio.textContent = "Falha ao atualizar status da conversa.";
    }
  });

  formEnviarMensagem.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (!conversaSelecionadaId) return;
    const texto = campoTexto.value.trim();
    const template = selectTemplate.value;
    if (!texto && !template) {
      statusEnvio.textContent = "Escreva uma mensagem ou selecione um template.";
      return;
    }
    btnEnviarMensagem.disabled = true;
    statusEnvio.textContent = "Enviando…";
    try {
      const corpo = template ? { template_name: template } : { text: texto };
      await apiFetch(`/api/admin/whatsapp/conversations/${conversaSelecionadaId}/messages`, {
        method: "POST",
        headers: { "Idempotency-Key": crypto.randomUUID() },
        body: JSON.stringify(corpo),
      });
      campoTexto.value = "";
      statusEnvio.textContent = "";
      await carregarMensagens();
    } catch (erro) {
      statusEnvio.textContent = erro.message || "Falha ao enviar mensagem.";
    } finally {
      btnEnviarMensagem.disabled = false;
    }
  });

  formVincularCliente.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (!conversaSelecionadaId || !campoClienteId.value) return;
    try {
      await apiFetch(`/api/admin/whatsapp/conversations/${conversaSelecionadaId}/link-customer`, {
        method: "POST",
        body: JSON.stringify({ customer_id: Number(campoClienteId.value) }),
      });
      statusVinculo.textContent = "Cliente vinculado.";
      await abrirConversa(conversaSelecionadaId);
    } catch (erro) {
      statusVinculo.textContent = erro.message || "Falha ao vincular cliente.";
    }
  });

  formVincularPedido.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (!conversaSelecionadaId || !campoPedidoId.value) return;
    try {
      await apiFetch(`/api/admin/whatsapp/conversations/${conversaSelecionadaId}/link-order`, {
        method: "POST",
        body: JSON.stringify({ order_id: Number(campoPedidoId.value) }),
      });
      statusVinculo.textContent = "Pedido vinculado.";
      await abrirConversa(conversaSelecionadaId);
    } catch (erro) {
      statusVinculo.textContent = erro.message || "Falha ao vincular pedido.";
    }
  });

  // ---------------------------------------------------------------------
  // Templates disponíveis
  // ---------------------------------------------------------------------
  async function carregarTemplates() {
    try {
      const dados = await apiFetch("/api/admin/whatsapp/templates");
      for (const template of dados.templates || []) {
        const opcao = elemento("option", "", `${template.name} (${template.language})`);
        opcao.value = template.name;
        selectTemplate.append(opcao);
      }
    } catch {
      /* lista de templates é apenas conveniência -- falha não bloqueia o painel */
    }
  }

  // ---------------------------------------------------------------------
  // Ciclo de vida
  // ---------------------------------------------------------------------
  function pararPolling() {
    if (pollListaTimer) clearInterval(pollListaTimer);
    if (pollMensagensTimer) clearInterval(pollMensagensTimer);
    pollListaTimer = null;
    pollMensagensTimer = null;
  }

  function iniciar() {
    atualizarStatus();
    carregarConversas();
    carregarTemplates();
    pollListaTimer = setInterval(() => {
      atualizarStatus();
      carregarConversas();
    }, POLL_LISTA_MS);
  }

  apiFetch("/api/auth/me")
    .then(() => { mostrarApp(); iniciar(); })
    .catch(() => mostrarLogin());
})();
