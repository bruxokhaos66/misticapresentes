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
  const blocoBuscaFiltros = document.getElementById("blocoBuscaFiltros");
  const contadorAtivas = document.getElementById("contadorAtivas");

  const abasBtns = Array.from(document.querySelectorAll(".aba-btn"));
  const abaTodas = document.getElementById("abaTodas");
  const abaVendedores = document.getElementById("abaVendedores");
  const secaoVendedores = document.getElementById("secaoVendedores");
  const secaoMensagens = document.getElementById("secaoMensagens");
  const listaAgentes = document.getElementById("listaAgentes");
  const statusAgentes = document.getElementById("statusAgentes");

  const semConversa = document.getElementById("semConversa");
  const painelConversa = document.getElementById("painelConversa");
  const conversaNome = document.getElementById("conversaNome");
  const conversaTelefone = document.getElementById("conversaTelefone");
  const badgeFila = document.getElementById("badgeFila");
  const badgeAtendente = document.getElementById("badgeAtendente");
  const selectStatusConversa = document.getElementById("selectStatusConversa");
  const listaMensagens = document.getElementById("listaMensagens");
  const formEnviarMensagem = document.getElementById("formEnviarMensagem");
  const selectTemplate = document.getElementById("selectTemplate");
  const campoTexto = document.getElementById("campoTexto");
  const btnEnviarMensagem = document.getElementById("btnEnviarMensagem");
  const statusEnvio = document.getElementById("statusEnvio");

  const btnAssumir = document.getElementById("btnAssumir");
  const btnLiberar = document.getElementById("btnLiberar");
  const btnTransferir = document.getElementById("btnTransferir");
  const btnFinalizar = document.getElementById("btnFinalizar");
  const btnReabrir = document.getElementById("btnReabrir");
  const statusFilaAcao = document.getElementById("statusFilaAcao");

  const modalTransferir = document.getElementById("modalTransferir");
  const btnFecharModalTransferir = document.getElementById("btnFecharModalTransferir");
  const formTransferir = document.getElementById("formTransferir");
  const selectVendedorDestino = document.getElementById("selectVendedorDestino");
  const campoMotivoTransferencia = document.getElementById("campoMotivoTransferencia");
  const statusTransferencia = document.getElementById("statusTransferencia");

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

  let sessaoUsuario = { id: null, perfil: null };
  let abaAtual = "fila";
  let conversaAtual = null; // detalhe completo (com queue_status/assigned_user_id/assignment_version)
  const ROTULO_FILA = { waiting: "Na fila", assigned: "Em atendimento", resolved: "Encerrada" };

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
    if (response.status === 401) {
      // Só 401 (sessão inválida/expirada) desloga. 403 agora também
      // representa negação de autorização por linha (ex.: vendedor tentando
      // ver/responder conversa de outro, ou ação restrita a adm/supervisor)
      // -- nunca deve derrubar a sessão inteira nem trocar a tela para
      // login; cada chamador trata erro.status === 403 com uma mensagem
      // própria, mantendo o app funcionando.
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
    // /status é restrito a adm/supervisor_atendimento -- vendedor nunca vê
    // este diagnóstico (nem precisa dele para atender), então simplesmente
    // não exibimos a pill de erro para esse perfil em vez de mostrar um
    // "falha" enganoso a cada consulta.
    if (sessaoUsuario.perfil === "vendedor") {
      statusPill.hidden = true;
      return;
    }
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
    } catch (erro) {
      if (erro.status === 403) { statusPill.hidden = true; return; }
      statusPill.textContent = "Falha ao consultar status";
      statusPill.className = "pill erro";
    }
  }

  // ---------------------------------------------------------------------
  // Abas (Fila / Minhas conversas / Todas / Vendedores)
  // ---------------------------------------------------------------------
  abasBtns.forEach((botao) => {
    botao.addEventListener("click", () => selecionarAba(botao.dataset.aba));
  });

  function selecionarAba(aba) {
    abaAtual = aba;
    abasBtns.forEach((b) => {
      const ativa = b.dataset.aba === aba;
      b.classList.toggle("is-active", ativa);
      b.setAttribute("aria-selected", ativa ? "true" : "false");
    });
    const ehTodas = aba === "todas";
    const ehVendedores = aba === "vendedores";
    blocoBuscaFiltros.hidden = !ehTodas;
    listaConversas.hidden = ehVendedores;
    statusListaConversas.hidden = ehVendedores;
    secaoVendedores.hidden = !ehVendedores;
    secaoMensagens.hidden = ehVendedores;
    colLateral.hidden = ehVendedores || !conversaSelecionadaId;
    if (ehVendedores) {
      carregarAgentes();
    } else {
      carregarConversas();
    }
  }

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

    if (conversa.queue_status) {
      botao.append(elemento("span", `badge-fila ${conversa.queue_status}`, ROTULO_FILA[conversa.queue_status] || conversa.queue_status));
    }

    if (conversa.order_id || conversa.customer_id) {
      const vinculo = elemento("span", "badge-vinculo", conversa.order_id ? `Pedido #${conversa.order_id}` : `Cliente #${conversa.customer_id}`);
      botao.append(vinculo);
    }

    botao.addEventListener("click", () => abrirConversa(conversa.id));
    item.append(botao);
    return item;
  }

  function endpointDaAba() {
    if (abaAtual === "fila") return "/api/admin/whatsapp/queue";
    if (abaAtual === "minhas") return "/api/admin/whatsapp/my-conversations";
    return "/api/admin/whatsapp/conversations";
  }

  async function carregarConversas() {
    try {
      const params = new URLSearchParams();
      if (abaAtual === "todas") {
        if (filtroStatusAtual) params.set("status", filtroStatusAtual);
        if (apenasNaoLidas) params.set("unread_only", "true");
        if (buscaConversas.value.trim()) params.set("q", buscaConversas.value.trim());
      }
      params.set("page_size", "50");

      const dados = await apiFetch(`${endpointDaAba()}?${params.toString()}`);
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
      if (erro.status === 401) {
        // sessão expirada -- apiFetch já trocou a tela para login.
      } else if (erro.status === 403) {
        statusListaConversas.textContent = erro.message || "Você não tem acesso a esta lista.";
      } else {
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
      conversaAtual = detalhe.conversation;
      preencherCabecalhoConversa(conversaAtual);
      atualizarBotoesFila(conversaAtual);
      await carregarMensagens();
      await apiFetch(`/api/admin/whatsapp/conversations/${id}/read`, { method: "POST" });
      carregarConversas();
    } catch (erro) {
      if (erro.status === 403) {
        statusEnvio.textContent = "Você não tem acesso a esta conversa.";
      } else {
        statusEnvio.textContent = "Falha ao abrir a conversa.";
      }
    }

    reiniciarPollMensagens();
  }

  function preencherCabecalhoConversa(conversa) {
    conversaNome.textContent = (conversa.contact && conversa.contact.profile_name) || "Contato sem nome";
    conversaTelefone.textContent = `•••${(conversa.contact && conversa.contact.phone_last4) || "----"}`;
    selectStatusConversa.value = conversa.status || "open";

    const fila = conversa.queue_status || "waiting";
    badgeFila.textContent = ROTULO_FILA[fila] || fila;
    badgeFila.className = `badge-fila ${fila}`;

    if (conversa.assigned_user_id) {
      const nomeAgente = nomeDoAgente(conversa.assigned_user_id);
      badgeAtendente.textContent = conversa.assigned_user_id === sessaoUsuario.id ? "Você" : (nomeAgente || `Atendente #${conversa.assigned_user_id}`);
      badgeAtendente.hidden = false;
    } else {
      badgeAtendente.hidden = true;
    }

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

  // ---------------------------------------------------------------------
  // Fila multiatendente: assumir / liberar / transferir / finalizar / reabrir
  // ---------------------------------------------------------------------
  const ehGestao = () => sessaoUsuario.perfil === "adm" || sessaoUsuario.perfil === "supervisor_atendimento";
  const ehDono = (conversa) => conversa.assigned_user_id != null && conversa.assigned_user_id === sessaoUsuario.id;

  function atualizarBotoesFila(conversa) {
    const fila = conversa.queue_status || "waiting";
    const dono = ehDono(conversa);
    const gestao = ehGestao();

    btnAssumir.hidden = !(fila === "waiting");
    btnLiberar.hidden = !(fila === "assigned" && (dono || gestao));
    btnTransferir.hidden = !(fila === "assigned" && (dono || gestao));
    btnFinalizar.hidden = !(fila === "assigned" && (dono || gestao));
    btnReabrir.hidden = !(fila === "resolved" && gestao);
    btnAbrirProdutos.hidden = !catalogoHabilitado;
    statusFilaAcao.textContent = "";
  }

  async function executarAcaoFila(caminho, opcoes, mensagemSucesso) {
    if (!conversaSelecionadaId) return;
    statusFilaAcao.textContent = "Processando…";
    try {
      const resposta = await apiFetch(`/api/admin/whatsapp/conversations/${conversaSelecionadaId}${caminho}`, opcoes);
      conversaAtual = resposta.conversation || conversaAtual;
      preencherCabecalhoConversa(conversaAtual);
      atualizarBotoesFila(conversaAtual);
      statusFilaAcao.textContent = mensagemSucesso;
      carregarConversas();
    } catch (erro) {
      if (erro.status === 409) {
        statusFilaAcao.textContent = erro.message || "Esta conversa foi alterada por outra ação; recarregando…";
        // 409/412 de corrida de claim ou assignment_version desatualizada:
        // recarrega o estado real da conversa em vez de deixar o painel
        // mostrando um estado que não existe mais no servidor.
        try {
          const atualizado = await apiFetch(`/api/admin/whatsapp/conversations/${conversaSelecionadaId}`);
          conversaAtual = atualizado.conversation;
          preencherCabecalhoConversa(conversaAtual);
          atualizarBotoesFila(conversaAtual);
        } catch { /* mantém a mensagem de erro acima */ }
      } else if (erro.status === 403) {
        statusFilaAcao.textContent = erro.message || "Você não tem permissão para esta ação.";
      } else {
        statusFilaAcao.textContent = erro.message || "Falha ao executar esta ação.";
      }
    }
  }

  btnAssumir.addEventListener("click", () => executarAcaoFila("/claim", { method: "POST", body: "{}" }, "Conversa assumida."));
  btnLiberar.addEventListener("click", () => executarAcaoFila("/release", { method: "POST", body: JSON.stringify({}) }, "Conversa liberada."));
  btnFinalizar.addEventListener("click", () => executarAcaoFila("/resolve", { method: "POST", body: JSON.stringify({ assignment_version: conversaAtual ? conversaAtual.assignment_version : null }) }, "Conversa finalizada."));
  btnReabrir.addEventListener("click", () => executarAcaoFila("/reopen", { method: "POST", body: "{}" }, "Conversa reaberta."));

  // Transferência: abre modal, carrega lista de agentes elegíveis.
  let agentesCache = [];

  function nomeDoAgente(id) {
    const agente = agentesCache.find((a) => a.id === id);
    return agente ? (agente.nome || agente.login) : null;
  }

  async function carregarAgentesParaTransferencia() {
    try {
      const dados = await apiFetch("/api/admin/whatsapp/agents");
      agentesCache = dados.agents || [];
    } catch {
      agentesCache = [];
    }
    selectVendedorDestino.textContent = "";
    for (const agente of agentesCache) {
      if (agente.id === sessaoUsuario.id) continue;
      if (!agente.atendimento_enabled) continue;
      const opcao = elemento("option", "", `${agente.nome || agente.login} (${agente.perfil}) — ${agente.active_conversations || 0} ativa(s)`);
      opcao.value = String(agente.id);
      selectVendedorDestino.append(opcao);
    }
  }

  btnTransferir.addEventListener("click", async () => {
    if (!conversaSelecionadaId) return;
    campoMotivoTransferencia.value = "";
    statusTransferencia.textContent = "";
    await carregarAgentesParaTransferencia();
    modalTransferir.hidden = false;
    selectVendedorDestino.focus();
  });

  btnFecharModalTransferir.addEventListener("click", () => { modalTransferir.hidden = true; });
  modalTransferir.addEventListener("click", (event) => { if (event.target === modalTransferir) modalTransferir.hidden = true; });

  formTransferir.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (!conversaSelecionadaId || !selectVendedorDestino.value) return;
    statusTransferencia.textContent = "Transferindo…";
    try {
      const resposta = await apiFetch(`/api/admin/whatsapp/conversations/${conversaSelecionadaId}/transfer`, {
        method: "POST",
        body: JSON.stringify({
          target_user_id: Number(selectVendedorDestino.value),
          reason: campoMotivoTransferencia.value.trim() || undefined,
          assignment_version: conversaAtual ? conversaAtual.assignment_version : undefined,
        }),
      });
      conversaAtual = resposta.conversation || conversaAtual;
      preencherCabecalhoConversa(conversaAtual);
      atualizarBotoesFila(conversaAtual);
      modalTransferir.hidden = true;
      carregarConversas();
    } catch (erro) {
      statusTransferencia.textContent = erro.message || "Falha ao transferir.";
    }
  });

  // ---------------------------------------------------------------------
  // Gestão de vendedores (aba Vendedores -- só adm/supervisor)
  // ---------------------------------------------------------------------
  function montarCartaoAgente(agente) {
    const cartao = elemento("div", "cartao-agente");
    const topo = elemento("div", "linha-topo");
    topo.append(elemento("strong", "", `${agente.nome || agente.login} (${agente.perfil})`));
    topo.append(elemento("span", "hint", `${agente.active_conversations || 0} conversa(s) ativa(s)`));
    cartao.append(topo);

    const campos = elemento("div", "campos-agente");

    const labelHabilitado = elemento("label");
    const chkHabilitado = document.createElement("input");
    chkHabilitado.type = "checkbox";
    chkHabilitado.checked = !!agente.atendimento_enabled;
    labelHabilitado.append(chkHabilitado, document.createTextNode(" Atendimento habilitado"));
    campos.append(labelHabilitado);

    const labelSuspenso = elemento("label");
    const chkSuspenso = document.createElement("input");
    chkSuspenso.type = "checkbox";
    chkSuspenso.checked = !!agente.atendimento_suspended_at;
    labelSuspenso.append(chkSuspenso, document.createTextNode(" Suspenso"));
    campos.append(labelSuspenso);

    const labelLimite = elemento("label");
    const campoLimite = document.createElement("input");
    campoLimite.type = "number";
    campoLimite.min = "1";
    campoLimite.max = "1000";
    campoLimite.placeholder = "padrão";
    if (agente.atendimento_max_active_conversations) campoLimite.value = String(agente.atendimento_max_active_conversations);
    labelLimite.append(document.createTextNode("Limite:"), campoLimite);
    campos.append(labelLimite);

    let selectPerfil = null;
    if (agente.perfil !== "adm") {
      const labelPerfil = elemento("label");
      selectPerfil = document.createElement("select");
      for (const valor of ["vendedor", "supervisor_atendimento"]) {
        const opcao = elemento("option", "", valor);
        opcao.value = valor;
        if (agente.perfil === valor) opcao.selected = true;
        selectPerfil.append(opcao);
      }
      labelPerfil.append(document.createTextNode("Perfil:"), selectPerfil);
      campos.append(labelPerfil);
    }

    const btnSalvar = document.createElement("button");
    btnSalvar.type = "button";
    btnSalvar.className = "btn-secondary";
    btnSalvar.textContent = "Salvar";
    btnSalvar.addEventListener("click", async () => {
      btnSalvar.disabled = true;
      try {
        const corpo = {
          atendimento_enabled: chkHabilitado.checked,
          suspender: chkSuspenso.checked,
          atendimento_max_active_conversations: campoLimite.value ? Number(campoLimite.value) : null,
        };
        if (selectPerfil) corpo.perfil = selectPerfil.value;
        await apiFetch(`/api/admin/whatsapp/agents/${agente.id}`, { method: "PATCH", body: JSON.stringify(corpo) });
        statusAgentes.textContent = "Alterações salvas.";
        carregarAgentes();
      } catch (erro) {
        statusAgentes.textContent = erro.message || "Falha ao salvar alterações.";
      } finally {
        btnSalvar.disabled = false;
      }
    });
    campos.append(btnSalvar);
    cartao.append(campos);
    return cartao;
  }

  async function carregarAgentes() {
    try {
      const dados = await apiFetch("/api/admin/whatsapp/agents");
      agentesCache = dados.agents || [];
      listaAgentes.textContent = "";
      for (const agente of agentesCache) {
        listaAgentes.append(montarCartaoAgente(agente));
      }
      statusAgentes.textContent = agentesCache.length ? "" : "Nenhum atendente cadastrado.";
    } catch (erro) {
      statusAgentes.textContent = erro.message || "Falha ao carregar vendedores.";
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
    if (event.key !== "Escape") return;
    if (!modalMidia.hidden) fecharModalMidia();
    if (!modalTransferir.hidden) modalTransferir.hidden = true;
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

  // ---------------------------------------------------------------------
  // Catálogo Comercial: painel Produtos -- busca, seleção múltipla, envio
  // (único e em lote) e recentes. Some inteiramente da tela quando
  // ATENDIMENTO_CATALOG_ENABLED estiver desligada no backend (nunca decide
  // isso sozinho: sempre a partir da resposta real do endpoint).
  // ---------------------------------------------------------------------
  const btnAbrirProdutos = document.getElementById("btnAbrirProdutos");
  const modalProdutos = document.getElementById("modalProdutos");
  const btnFecharModalProdutos = document.getElementById("btnFecharModalProdutos");
  const formBuscaProdutos = document.getElementById("formBuscaProdutos");
  const campoBuscaProduto = document.getElementById("campoBuscaProduto");
  const campoFiltroCategoria = document.getElementById("campoFiltroCategoria");
  const chkSomenteEstoque = document.getElementById("chkSomenteEstoque");
  const statusProdutos = document.getElementById("statusProdutos");
  const secaoRecentesProdutos = document.getElementById("secaoRecentesProdutos");
  const listaProdutosRecentes = document.getElementById("listaProdutosRecentes");
  const listaProdutosCatalogo = document.getElementById("listaProdutosCatalogo");
  const btnProdutosPaginaAnterior = document.getElementById("btnProdutosPaginaAnterior");
  const btnProdutosProximaPagina = document.getElementById("btnProdutosProximaPagina");
  const produtosPaginaAtual = document.getElementById("produtosPaginaAtual");
  const contadorSelecionados = document.getElementById("contadorSelecionados");
  const btnLimparSelecaoProdutos = document.getElementById("btnLimparSelecaoProdutos");
  const btnEnviarProdutosSelecionados = document.getElementById("btnEnviarProdutosSelecionados");

  let catalogoHabilitado = false;
  let elementoComFocoAntesDoModalProdutos = null;
  let paginaProdutosAtual = 1;
  let totalProdutosAtual = 0;
  const PRODUTOS_PAGE_SIZE = 12;
  const produtosSelecionados = new Map(); // id -> produto

  const ROTULO_ESTOQUE = { available: "Disponível", low_stock: "Estoque baixo", unavailable: "Indisponível" };

  function formatarPrecoBRL(valor) {
    return new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" }).format(Number(valor) || 0);
  }

  function montarCartaoProduto(produto, { compacto = false } = {}) {
    const cartao = elemento("div", "cartao-produto");
    if (produtosSelecionados.has(produto.id)) cartao.classList.add("is-selecionado");

    const imagemBox = elemento("div", "cartao-produto-imagem");
    if (produto.imagem_url) {
      const img = document.createElement("img");
      img.src = produto.imagem_url;
      img.alt = produto.nome || "Produto";
      img.loading = "lazy";
      img.addEventListener("error", () => {
        imagemBox.textContent = "";
        imagemBox.append(elemento("span", "sem-imagem", "Sem imagem"));
      });
      imagemBox.append(img);
    } else {
      imagemBox.append(elemento("span", "sem-imagem", "Sem imagem"));
    }
    cartao.append(imagemBox);

    cartao.append(elemento("div", "cartao-produto-nome", produto.nome));

    const preco = elemento("div", "cartao-produto-preco");
    if (produto.preco_promocional != null && produto.preco_promocional < produto.preco) {
      preco.append(elemento("span", "preco-original", formatarPrecoBRL(produto.preco)));
      preco.append(elemento("span", "preco-promocional", formatarPrecoBRL(produto.preco_promocional)));
    } else {
      preco.append(document.createTextNode(formatarPrecoBRL(produto.preco)));
    }
    cartao.append(preco);

    cartao.append(elemento("span", `badge-estoque ${produto.estoque_status}`, ROTULO_ESTOQUE[produto.estoque_status] || produto.estoque_status));

    const acoes = elemento("div", "cartao-produto-acoes");

    if (produto.url_publica) {
      const link = document.createElement("a");
      link.href = produto.url_publica;
      link.target = "_blank";
      link.rel = "noopener noreferrer";
      link.className = "btn-secondary";
      link.textContent = "Ver no site";
      acoes.append(link);
    }

    const labelSelecionar = elemento("label");
    const chk = document.createElement("input");
    chk.type = "checkbox";
    chk.checked = produtosSelecionados.has(produto.id);
    chk.disabled = !produto.disponivel;
    chk.setAttribute("aria-label", `Selecionar ${produto.nome}`);
    chk.addEventListener("change", () => {
      if (chk.checked) {
        produtosSelecionados.set(produto.id, produto);
      } else {
        produtosSelecionados.delete(produto.id);
      }
      cartao.classList.toggle("is-selecionado", chk.checked);
      atualizarContadorSelecionados();
    });
    labelSelecionar.append(chk, document.createTextNode(" Selecionar"));
    acoes.append(labelSelecionar);

    if (compacto) {
      const btnReenviar = document.createElement("button");
      btnReenviar.type = "button";
      btnReenviar.className = "btn-secondary";
      btnReenviar.textContent = "Reenviar";
      btnReenviar.disabled = !produto.disponivel;
      btnReenviar.addEventListener("click", () => enviarProdutoUnico(produto, btnReenviar));
      acoes.append(btnReenviar);
    }

    cartao.append(acoes);
    return cartao;
  }

  function atualizarContadorSelecionados() {
    const total = produtosSelecionados.size;
    contadorSelecionados.textContent = total === 0 ? "Nenhum produto selecionado" : `${total} produto(s) selecionado(s)`;
    btnEnviarProdutosSelecionados.disabled = total === 0;
  }

  btnLimparSelecaoProdutos.addEventListener("click", () => {
    produtosSelecionados.clear();
    atualizarContadorSelecionados();
    listaProdutosCatalogo.querySelectorAll(".cartao-produto.is-selecionado").forEach((el) => el.classList.remove("is-selecionado"));
    listaProdutosCatalogo.querySelectorAll('input[type="checkbox"]').forEach((el) => { el.checked = false; });
  });

  async function pesquisarProdutos(pagina = 1) {
    if (!conversaSelecionadaId) return;
    statusProdutos.textContent = "Pesquisando…";
    try {
      const parametros = new URLSearchParams();
      if (campoBuscaProduto.value.trim()) parametros.set("q", campoBuscaProduto.value.trim());
      if (campoFiltroCategoria.value.trim()) parametros.set("categoria", campoFiltroCategoria.value.trim());
      if (chkSomenteEstoque.checked) parametros.set("em_estoque", "true");
      parametros.set("page", String(pagina));
      parametros.set("page_size", String(PRODUTOS_PAGE_SIZE));

      const dados = await apiFetch(`/api/admin/whatsapp/catalog/products?${parametros.toString()}`);
      paginaProdutosAtual = dados.page;
      totalProdutosAtual = dados.total;
      listaProdutosCatalogo.textContent = "";
      for (const produto of dados.products) {
        const li = document.createElement("li");
        li.append(montarCartaoProduto(produto));
        listaProdutosCatalogo.append(li);
      }
      const totalPaginas = Math.max(1, Math.ceil(totalProdutosAtual / PRODUTOS_PAGE_SIZE));
      produtosPaginaAtual.textContent = `Página ${paginaProdutosAtual} de ${totalPaginas}`;
      btnProdutosPaginaAnterior.disabled = paginaProdutosAtual <= 1;
      btnProdutosProximaPagina.disabled = paginaProdutosAtual >= totalPaginas;
      statusProdutos.textContent = dados.products.length ? "" : "Nenhum produto encontrado.";
    } catch (erro) {
      if (erro.status === 403) {
        statusProdutos.textContent = erro.message || "Você não tem acesso ao catálogo.";
      } else {
        statusProdutos.textContent = erro.message || "Falha ao pesquisar produtos.";
      }
    }
  }

  async function carregarProdutosRecentes() {
    try {
      const dados = await apiFetch("/api/admin/whatsapp/catalog/recent-products?limit=10");
      listaProdutosRecentes.textContent = "";
      for (const produto of dados.products || []) {
        const li = document.createElement("li");
        li.append(montarCartaoProduto(produto, { compacto: true }));
        listaProdutosRecentes.append(li);
      }
      secaoRecentesProdutos.hidden = !(dados.products || []).length;
    } catch {
      secaoRecentesProdutos.hidden = true;
    }
  }

  async function enviarProdutoUnico(produto, botao) {
    if (!conversaSelecionadaId) return;
    const rotuloOriginal = botao.textContent;
    botao.disabled = true;
    botao.textContent = "Enviando…";
    try {
      const corpo = { product_id: produto.id };
      if (conversaAtual && conversaAtual.assignment_version != null) corpo.assignment_version = conversaAtual.assignment_version;
      await apiFetch(`/api/admin/whatsapp/conversations/${conversaSelecionadaId}/send-product`, {
        method: "POST",
        headers: { "Idempotency-Key": crypto.randomUUID() },
        body: JSON.stringify(corpo),
      });
      statusProdutos.textContent = "Produto enviado.";
      await carregarMensagens();
    } catch (erro) {
      statusProdutos.textContent = erro.message || "Falha ao enviar produto.";
    } finally {
      botao.disabled = false;
      botao.textContent = rotuloOriginal;
    }
  }

  btnEnviarProdutosSelecionados.addEventListener("click", async () => {
    if (!conversaSelecionadaId || produtosSelecionados.size === 0) return;
    btnEnviarProdutosSelecionados.disabled = true;
    statusProdutos.textContent = "Enviando…";
    try {
      const ids = Array.from(produtosSelecionados.keys());
      const corpo = { product_ids: ids };
      if (conversaAtual && conversaAtual.assignment_version != null) corpo.assignment_version = conversaAtual.assignment_version;
      await apiFetch(`/api/admin/whatsapp/conversations/${conversaSelecionadaId}/send-products`, {
        method: "POST",
        headers: { "Idempotency-Key": crypto.randomUUID() },
        body: JSON.stringify(corpo),
      });
      statusProdutos.textContent = "Produtos enviados.";
      produtosSelecionados.clear();
      atualizarContadorSelecionados();
      listaProdutosCatalogo.querySelectorAll(".cartao-produto.is-selecionado").forEach((el) => el.classList.remove("is-selecionado"));
      listaProdutosCatalogo.querySelectorAll('input[type="checkbox"]').forEach((el) => { el.checked = false; });
      await carregarMensagens();
      await carregarProdutosRecentes();
    } catch (erro) {
      if (erro.status === 409) {
        statusProdutos.textContent = "Esta conversa foi alterada por outra ação; recarregue e tente novamente.";
      } else if (erro.status === 422) {
        statusProdutos.textContent = erro.message || "Lote inválido -- nenhum produto foi enviado.";
      } else {
        statusProdutos.textContent = erro.message || "Falha ao enviar produtos.";
      }
    } finally {
      btnEnviarProdutosSelecionados.disabled = produtosSelecionados.size === 0;
    }
  });

  btnProdutosPaginaAnterior.addEventListener("click", () => pesquisarProdutos(Math.max(1, paginaProdutosAtual - 1)));
  btnProdutosProximaPagina.addEventListener("click", () => pesquisarProdutos(paginaProdutosAtual + 1));

  formBuscaProdutos.addEventListener("submit", (event) => {
    event.preventDefault();
    pesquisarProdutos(1);
  });

  function fecharModalProdutos() {
    modalProdutos.hidden = true;
    if (elementoComFocoAntesDoModalProdutos) {
      elementoComFocoAntesDoModalProdutos.focus();
      elementoComFocoAntesDoModalProdutos = null;
    }
  }

  btnFecharModalProdutos.addEventListener("click", fecharModalProdutos);
  modalProdutos.addEventListener("click", (event) => { if (event.target === modalProdutos) fecharModalProdutos(); });
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && !modalProdutos.hidden) fecharModalProdutos();
  });

  btnAbrirProdutos.addEventListener("click", async () => {
    if (!conversaSelecionadaId) return;
    elementoComFocoAntesDoModalProdutos = document.activeElement;
    modalProdutos.hidden = false;
    campoBuscaProduto.value = "";
    campoFiltroCategoria.value = "";
    chkSomenteEstoque.checked = false;
    statusProdutos.textContent = "";
    campoBuscaProduto.focus();
    await carregarProdutosRecentes();
    await pesquisarProdutos(1);
  });

  async function verificarCatalogoHabilitado() {
    try {
      await apiFetch("/api/admin/whatsapp/catalog/products?page_size=1");
      catalogoHabilitado = true;
    } catch {
      // 503 (flag desligada), 403 (sem acesso) ou qualquer outra falha:
      // o botão Produtos simplesmente não aparece -- nunca decide isso
      // sozinho no frontend, só reflete a resposta real do backend.
      catalogoHabilitado = false;
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
      if (conversaAtual && conversaAtual.assignment_version != null) corpo.assignment_version = conversaAtual.assignment_version;
      await apiFetch(`/api/admin/whatsapp/conversations/${conversaSelecionadaId}/messages`, {
        method: "POST",
        headers: { "Idempotency-Key": crypto.randomUUID() },
        body: JSON.stringify(corpo),
      });
      campoTexto.value = "";
      statusEnvio.textContent = "";
      await carregarMensagens();
    } catch (erro) {
      if (erro.status === 403) {
        statusEnvio.textContent = erro.message || "Assuma esta conversa antes de responder.";
      } else if (erro.status === 409) {
        statusEnvio.textContent = "Esta conversa foi alterada por outra ação; recarregando…";
        await abrirConversa(conversaSelecionadaId);
      } else {
        statusEnvio.textContent = erro.message || "Falha ao enviar mensagem.";
      }
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
    const gestao = ehGestao();
    abaTodas.hidden = !gestao;
    abaVendedores.hidden = !gestao;
    selecionarAba("fila");
    atualizarStatus();
    carregarTemplates();
    verificarCatalogoHabilitado().then(() => {
      if (conversaAtual) atualizarBotoesFila(conversaAtual);
    });
    pollListaTimer = setInterval(() => {
      atualizarStatus();
      if (abaAtual !== "vendedores") carregarConversas();
    }, POLL_LISTA_MS);
  }

  apiFetch("/api/auth/me")
    .then((dados) => {
      const usuario = dados.usuario || {};
      sessaoUsuario = { id: usuario.id != null ? Number(usuario.id) : null, perfil: usuario.perfil || null };
      mostrarApp();
      iniciar();
    })
    .catch(() => mostrarLogin());
})();
