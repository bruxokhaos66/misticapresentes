(() => {
  "use strict";

  const config = window.misticaSiteConfig || {};
  const API_BASE = String(config.apiBaseUrl || "https://api.misticaesotericos.com.br").replace(/\/$/, "");
  const POLL_VISIBLE_MS = 15000;
  const POLL_HIDDEN_MS = 60000;
  const currency = new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" });
  const dateTime = new Intl.DateTimeFormat("pt-BR", { dateStyle: "short", timeStyle: "short" });

  const loginPanel = document.getElementById("loginPanelPedidos");
  const loginForm = document.getElementById("loginFormPedidos");
  const loginUser = document.getElementById("loginUserPedidos");
  const loginSenha = document.getElementById("loginSenhaPedidos");
  const loginStatus = document.getElementById("loginStatusPedidos");
  const painel = document.getElementById("painelPedidos");
  const lista = document.getElementById("listaPedidosUnificados");
  const statusLista = document.getElementById("statusListaPedidos");
  const contador = document.getElementById("contadorPedidos");
  const contadorNovos = document.getElementById("contadorNovosPedidos");
  const somToggle = document.getElementById("somPedidosToggle");
  const dialog = document.getElementById("detalhePedidoDialog");
  const detalheTitulo = document.getElementById("detalhePedidoTitulo");
  const detalheConteudo = document.getElementById("detalhePedidoConteudo");

  const filtros = {
    busca: document.getElementById("filtroBuscaPedidos"),
    pagamento: document.getElementById("filtroPagamentoPedidos"),
    financeiro: document.getElementById("filtroFinanceiroPedidos"),
    comercial: document.getElementById("filtroComercialPedidos"),
    inicio: document.getElementById("filtroDataInicioPedidos"),
    fim: document.getElementById("filtroDataFimPedidos"),
    novos: document.getElementById("filtroSomenteNovosPedidos"),
  };

  let pedidos = [];
  let idsNotificacaoConhecidos = null;
  let pollTimer = null;
  let carregando = false;
  const operacoesEmAndamento = new Set();
  let filtroRapidoEstado = null;

  function inicioDoDia(offsetDias = 0) {
    const data = new Date();
    data.setDate(data.getDate() + offsetDias);
    data.setHours(0, 0, 0, 0);
    return data;
  }

  function fimDoDia(offsetDias = 0) {
    const data = inicioDoDia(offsetDias);
    data.setHours(23, 59, 59, 999);
    return data;
  }

  function aplicarFiltroPeriodo(chave) {
    const formatarDataInput = (data) => `${data.getFullYear()}-${String(data.getMonth() + 1).padStart(2, "0")}-${String(data.getDate()).padStart(2, "0")}`;
    const mapa = {
      hoje: [inicioDoDia(0), fimDoDia(0)],
      ontem: [inicioDoDia(-1), fimDoDia(-1)],
      "7dias": [inicioDoDia(-6), fimDoDia(0)],
      "30dias": [inicioDoDia(-29), fimDoDia(0)],
    };
    const [inicio, fim] = mapa[chave] || [];
    filtros.inicio.value = inicio ? formatarDataInput(inicio) : "";
    filtros.fim.value = fim ? formatarDataInput(fim) : "";
  }

  function pedidoAtendeFiltroRapido(pedido) {
    if (!filtroRapidoEstado) return true;
    const financeiro = String(pedido.status || "");
    if (filtroRapidoEstado === "pendente") return financeiro === "Aguardando pagamento" || financeiro === "Pagamento divergente";
    if (filtroRapidoEstado === "cancelado") return financeiro === "Cancelado" || pedido.status_pedido === "cancelado";
    if (filtroRapidoEstado === "pago") return financeiro !== "Aguardando pagamento" && financeiro !== "Pagamento divergente" && financeiro !== "Cancelado";
    if (filtroRapidoEstado === "enviado") return pedido.status_pedido === "enviado";
    if (filtroRapidoEstado === "pix") return tipoPagamento(pedido) === "pix";
    if (filtroRapidoEstado === "cartao") return tipoPagamento(pedido) === "credit_card" || tipoPagamento(pedido) === "debit_card";
    return true;
  }

  const ROTULOS_COMERCIAIS = {
    novo: "Novo",
    confirmado: "Confirmado",
    em_preparacao: "Em preparação",
    pronto_retirada: "Pronto para retirada",
    enviado: "Enviado",
    concluido: "Concluído",
    cancelado: "Cancelado",
  };

  const TRANSICOES = {
    novo: ["confirmado", "cancelado"],
    confirmado: ["em_preparacao", "cancelado"],
    em_preparacao: ["pronto_retirada", "enviado", "cancelado"],
    pronto_retirada: ["concluido", "cancelado"],
    enviado: ["concluido", "cancelado"],
    concluido: [],
    cancelado: [],
  };

  const ENDERECO_LOJA = "Mística Presentes — Galeria Ody, nº 2400, sala 07, Centro, Pinhalzinho/SC";

  function rotuloRecebimento(pedido) {
    const forma = String(pedido.forma_recebimento || "").toLowerCase();
    if (forma === "retirada") return "Retirada na loja";
    if (forma === "entrega") return "Entrega";
    return "Forma de recebimento não definida";
  }

  function enderecoTexto(pedido) {
    const forma = String(pedido.forma_recebimento || "").toLowerCase();
    if (forma === "retirada") return ENDERECO_LOJA;
    if (forma !== "entrega") return "—";
    const partes = [
      [pedido.endereco_rua, pedido.endereco_numero].filter(Boolean).join(", "),
      pedido.endereco_complemento,
      pedido.endereco_bairro,
      [pedido.endereco_cidade, pedido.endereco_uf].filter(Boolean).join("/"),
      pedido.endereco_cep,
    ].filter(Boolean);
    return partes.length ? partes.join(" — ") : "Endereço não informado";
  }

  function elemento(tag, classe, texto) {
    const node = document.createElement(tag);
    if (classe) node.className = classe;
    if (texto !== undefined && texto !== null) node.textContent = String(texto);
    return node;
  }

  function campo(rotulo, valor) {
    const box = elemento("div", "admin-pedido-campo");
    box.append(elemento("small", "", rotulo), elemento("strong", "", valor || "—"));
    return box;
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

  function dataPedido(pedido) {
    const valor = pedido.data_iso || pedido.data_venda || "";
    const data = new Date(valor);
    return Number.isNaN(data.getTime()) ? null : data;
  }

  function formatarData(valor) {
    const data = new Date(valor || "");
    return Number.isNaN(data.getTime()) ? (valor || "—") : dateTime.format(data);
  }

  function rotuloParcelas(parcelas) {
    const n = Number(parcelas || 1);
    return n <= 1 ? "À vista" : `${n}x`;
  }

  function tipoPagamento(pedido) {
    const tipo = String(pedido.payment_type_id || "").toLowerCase();
    const forma = String(pedido.forma_pagamento || "").toLowerCase();
    if (tipo === "credit_card" || forma.includes("crédito") || forma.includes("credito")) return "credit_card";
    if (tipo === "debit_card" || forma.includes("débito") || forma.includes("debito")) return "debit_card";
    if (tipo === "pix" || forma.includes("pix") || pedido.payment_provider === "manual_pix") return "pix";
    return tipo || "outro";
  }

  function rotuloPagamento(pedido) {
    const tipo = tipoPagamento(pedido);
    const base = tipo === "credit_card" ? "Crédito" : tipo === "debit_card" ? "Débito" : tipo === "pix" ? "Pix" : (pedido.forma_pagamento || "Não identificado");
    const bandeira = pedido.payment_method_id && pedido.payment_method_id !== "pix" ? ` · ${pedido.payment_method_id}` : "";
    return `${base}${bandeira} · ${rotuloParcelas(pedido.parcelas)}`;
  }

  function normalizar(valor) {
    return String(valor || "").normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase();
  }

  function pedidosFiltrados() {
    const busca = normalizar(filtros.busca.value).trim();
    const inicio = filtros.inicio.value ? new Date(`${filtros.inicio.value}T00:00:00`) : null;
    const fim = filtros.fim.value ? new Date(`${filtros.fim.value}T23:59:59`) : null;
    return pedidos.filter((pedido) => {
      const texto = normalizar(`${pedido.id} ${pedido.cliente} ${pedido.telefone} ${pedido.email}`);
      const data = dataPedido(pedido);
      return (!busca || texto.includes(busca))
        && (!filtros.pagamento.value || tipoPagamento(pedido) === filtros.pagamento.value)
        && (!filtros.financeiro.value || String(pedido.status || "") === filtros.financeiro.value)
        && (!filtros.comercial.value || String(pedido.status_pedido || "novo") === filtros.comercial.value)
        && (!filtros.novos.checked || !pedido.visualizado_admin_em)
        && (!inicio || (data && data >= inicio))
        && (!fim || (data && data <= fim))
        && pedidoAtendeFiltroRapido(pedido);
    }).sort((a, b) => {
      const da = dataPedido(a)?.getTime() || Number(a.id) || 0;
      const db = dataPedido(b)?.getTime() || Number(b.id) || 0;
      return db - da;
    });
  }

  function atualizarFiltroFinanceiro() {
    const atual = filtros.financeiro.value;
    const valores = [...new Set(pedidos.map((p) => String(p.status || "")).filter(Boolean))].sort();
    filtros.financeiro.replaceChildren(new Option("Todos", ""), ...valores.map((v) => new Option(v, v)));
    if (valores.includes(atual)) filtros.financeiro.value = atual;
  }

  function criarCard(pedido) {
    const novo = !pedido.visualizado_admin_em;
    const card = elemento("article", `admin-pedido-card${novo ? " novo" : ""}`);
    card.dataset.pedidoId = String(pedido.id);

    const top = elemento("div", "admin-pedido-card-top");
    const identificacao = elemento("div", "admin-pedido-identificacao");
    identificacao.append(elemento("strong", "", `Pedido #${pedido.id}`));
    if (novo) identificacao.append(elemento("span", "admin-pedido-badge novo", "Novo"));
    identificacao.append(elemento("span", "admin-pedido-badge", ROTULOS_COMERCIAIS[pedido.status_pedido || "novo"] || pedido.status_pedido || "Novo"));
    top.append(identificacao, elemento("span", "", formatarData(pedido.data_iso || pedido.data_venda)));

    const grid = elemento("div", "admin-pedido-grid");
    grid.append(
      campo("Cliente", pedido.cliente || "Não informado"),
      campo("Telefone", pedido.telefone || "Não informado"),
      campo("E-mail", pedido.email || "Não informado"),
      campo("Total", currency.format(Number(pedido.total_final || 0))),
      campo("Pagamento", rotuloPagamento(pedido)),
      campo("Financeiro", pedido.status || "Não informado"),
      campo("Comercial", ROTULOS_COMERCIAIS[pedido.status_pedido || "novo"] || pedido.status_pedido),
      campo("Recebimento", rotuloRecebimento(pedido)),
      campo("Endereço/Retirada", enderecoTexto(pedido)),
      campo("Frete", currency.format(Number(pedido.frete || 0))),
      campo("Rastreio", pedido.codigo_rastreio || "—"),
      campo("Aprovação", formatarData(pedido.data_aprovacao)),
    );

    const acoes = elemento("div", "admin-pedido-acoes");
    const abrir = elemento("button", "btn btn-small", "Abrir detalhes");
    abrir.type = "button";
    abrir.dataset.acao = "detalhes";
    acoes.append(abrir);
    card.append(top, grid, acoes);
    return card;
  }

  function renderizar() {
    const filtrados = pedidosFiltrados();
    lista.replaceChildren();
    filtrados.forEach((pedido) => lista.append(criarCard(pedido)));
    if (!filtrados.length) lista.append(elemento("p", "admin-vazio", "Nenhum pedido corresponde aos filtros atuais."));
    contador.textContent = `${filtrados.length} pedido(s)`;
    const novos = pedidos.filter((p) => !p.visualizado_admin_em).length;
    contadorNovos.hidden = novos === 0;
    contadorNovos.textContent = `${novos} novo(s)`;
    statusLista.textContent = `Última atualização: ${dateTime.format(new Date())}`;
  }

  function tocarAviso() {
    if (!somToggle.checked) return;
    try {
      const AudioCtx = window.AudioContext || window.webkitAudioContext;
      if (!AudioCtx) return;
      const ctx = new AudioCtx();
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.frequency.value = 880;
      gain.gain.setValueAtTime(0.0001, ctx.currentTime);
      gain.gain.exponentialRampToValueAtTime(0.12, ctx.currentTime + 0.02);
      gain.gain.exponentialRampToValueAtTime(0.0001, ctx.currentTime + 0.3);
      osc.connect(gain).connect(ctx.destination);
      osc.start();
      osc.stop(ctx.currentTime + 0.32);
      osc.onended = () => ctx.close().catch(() => {});
    } catch {}
  }

  async function carregarPedidos({ silencioso = false } = {}) {
    if (carregando || painel.hidden) return;
    carregando = true;
    if (!silencioso) statusLista.textContent = "Carregando pedidos...";
    try {
      const [listaPedidos, notificacoes] = await Promise.all([
        apiFetch("/api/pedidos?limite=500"),
        apiFetch("/api/pedidos/notificacoes/pendentes?limite=500"),
      ]);
      pedidos = Array.isArray(listaPedidos) ? listaPedidos : [];
      const idsAtuais = new Set((notificacoes.pedidos || []).filter((p) => !p.visualizado_admin_em).map((p) => Number(p.id)));
      if (idsNotificacaoConhecidos === null) {
        idsNotificacaoConhecidos = idsAtuais;
      } else {
        const realmenteNovo = [...idsAtuais].some((id) => !idsNotificacaoConhecidos.has(id));
        idsNotificacaoConhecidos = idsAtuais;
        if (realmenteNovo) tocarAviso();
      }
      atualizarFiltroFinanceiro();
      renderizar();
    } catch (error) {
      if (error.status === 401 || error.status === 403) mostrarLogin();
      else statusLista.textContent = "Não foi possível atualizar os pedidos agora. Uma nova tentativa será feita automaticamente.";
    } finally {
      carregando = false;
    }
  }

  function agendarPolling() {
    if (pollTimer) clearTimeout(pollTimer);
    if (painel.hidden) return;
    pollTimer = setTimeout(async () => {
      await carregarPedidos({ silencioso: true });
      agendarPolling();
    }, document.hidden ? POLL_HIDDEN_MS : POLL_VISIBLE_MS);
  }

  function secaoDetalhe(titulo) {
    const secao = elemento("section", "admin-detalhe-secao");
    secao.append(elemento("h3", "", titulo));
    return secao;
  }

  function linhaDetalhe(textos) {
    const item = elemento("div", "admin-detalhe-item");
    textos.forEach((texto) => item.append(elemento("div", "", texto || "—")));
    return item;
  }

  function renderDetalhe(pedido) {
    detalheConteudo.replaceChildren();
    detalheTitulo.textContent = `Pedido #${pedido.id}`;

    const resumo = secaoDetalhe("Resumo");
    const grid = elemento("div", "admin-detalhe-grid");
    grid.append(
      campo("Cliente", pedido.cliente), campo("Telefone", pedido.telefone), campo("E-mail", pedido.email),
      campo("Data", formatarData(pedido.data_iso || pedido.data_venda)), campo("Pagamento", rotuloPagamento(pedido)),
      campo("Financeiro", pedido.status), campo("Comercial", ROTULOS_COMERCIAIS[pedido.status_pedido || "novo"]),
      campo("Recebimento", rotuloRecebimento(pedido)), campo("Rastreio", pedido.codigo_rastreio),
      campo("Endereço/Retirada", enderecoTexto(pedido)),
      campo("Subtotal", currency.format(Number(pedido.subtotal || 0))), campo("Desconto", currency.format(Number(pedido.desconto || 0))),
      campo("Frete", currency.format(Number(pedido.frete || 0))), campo("Total", currency.format(Number(pedido.total_final || 0)))
    );
    resumo.append(grid);

    const itens = secaoDetalhe("Itens");
    const itensLista = elemento("div", "admin-detalhe-lista");
    (pedido.itens || []).forEach((item) => itensLista.append(linhaDetalhe([
      `${Number(item.quantidade || 0)}x ${item.nome_p || "Item"}`,
      `${currency.format(Number(item.valor_unitario || 0))} cada · ${currency.format(Number(item.valor_total || 0))}`,
    ])));
    if (!itensLista.children.length) itensLista.append(linhaDetalhe(["Nenhum item registrado."]));
    itens.append(itensLista);

    const pagamentos = secaoDetalhe("Histórico de pagamento e tentativas");
    const pagamentosLista = elemento("div", "admin-detalhe-lista");
    (pedido.historico_pagamentos || []).forEach((pagamento) => pagamentosLista.append(linhaDetalhe([
      `${pagamento.forma || "Pagamento"} · ${currency.format(Number(pagamento.valor || 0))} · ${pagamento.status || ""}`,
      `${formatarData(pagamento.data_hora)} · ${pagamento.usuario || "Sistema"}`,
      pagamento.observacao || "",
    ])));
    (pedido.tentativas_pagamento || []).forEach((tentativa) => pagamentosLista.append(linhaDetalhe([
      `Tentativa ${tentativa.provedor || ""} · ${tentativa.status_interno || tentativa.status_externo || ""}`,
      `${tentativa.payment_type_id || "Método não identificado"} · ${rotuloParcelas(tentativa.parcelas)} · ${tentativa.bandeira || ""}`,
      formatarData(tentativa.atualizado_em || tentativa.criado_em),
    ])));
    if (!pagamentosLista.children.length) pagamentosLista.append(linhaDetalhe(["Nenhum pagamento ou tentativa registrado."]));
    pagamentos.append(pagamentosLista);

    const historico = secaoDetalhe("Histórico do pedido");
    const historicoLista = elemento("div", "admin-detalhe-lista");
    (pedido.historico_status || []).forEach((registro) => historicoLista.append(linhaDetalhe([
      `${ROTULOS_COMERCIAIS[registro.status] || registro.status || "Atualização"} · ${registro.tipo || "pedido"}`,
      `${formatarData(registro.data_hora)} · ${registro.usuario || "Sistema"} · ${registro.origem || ""}`,
      registro.observacao || "",
    ])));
    if (!historicoLista.children.length) historicoLista.append(linhaDetalhe(["Nenhuma atualização registrada."]));
    historico.append(historicoLista);

    const statusSecao = secaoDetalhe("Atualizar situação comercial");
    const form = elemento("form", "admin-status-form");
    const selectLabel = elemento("label", "", "Nova situação");
    const select = elemento("select", "admin-status-select");
    select.name = "status_pedido";
    const atual = pedido.status_pedido || "novo";
    select.append(new Option(ROTULOS_COMERCIAIS[atual] || atual, atual));
    (TRANSICOES[atual] || []).forEach((status) => select.append(new Option(ROTULOS_COMERCIAIS[status], status)));
    selectLabel.append(select);
    const obsLabel = elemento("label", "", "Observação permitida");
    const observacao = elemento("input", "admin-status-observacao");
    observacao.name = "observacao";
    observacao.maxLength = 280;
    observacao.placeholder = "Opcional";
    obsLabel.append(observacao);
    const salvar = elemento("button", "btn", "Salvar situação");
    salvar.type = "submit";
    salvar.disabled = !(TRANSICOES[atual] || []).length;
    form.append(selectLabel, obsLabel, salvar);
    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      const destino = select.value;
      if (destino === atual) return;
      if (destino === "cancelado" && !window.confirm("Cancelar comercialmente este pedido? Esta tela não estorna nem altera o pagamento.")) return;
      await atualizarStatusComercial(pedido.id, destino, observacao.value, salvar);
    });
    statusSecao.append(form);

    const observacoes = secaoDetalhe("Observações");
    observacoes.append(linhaDetalhe([pedido.observacao_pedido || "Nenhuma observação registrada."]));
    detalheConteudo.append(resumo, itens, pagamentos, historico, statusSecao, observacoes);
  }

  async function abrirDetalhes(id) {
    if (operacoesEmAndamento.has(`detalhe-${id}`)) return;
    operacoesEmAndamento.add(`detalhe-${id}`);
    detalheTitulo.textContent = `Pedido #${id}`;
    detalheConteudo.replaceChildren(elemento("p", "admin-vazio", "Carregando detalhes..."));
    if (!dialog.open) dialog.showModal();
    try {
      const pedido = await apiFetch(`/api/pedidos/${id}/detalhes-admin`);
      renderDetalhe(pedido);
      if (!pedido.visualizado_admin_em) {
        await apiFetch(`/api/pedidos/${id}/visualizar`, { method: "POST", body: "{}" });
        const local = pedidos.find((p) => Number(p.id) === Number(id));
        if (local) local.visualizado_admin_em = new Date().toISOString();
        renderizar();
      }
    } catch (error) {
      detalheConteudo.replaceChildren(elemento("p", "admin-vazio", error.message || "Não foi possível abrir o pedido."));
    } finally {
      operacoesEmAndamento.delete(`detalhe-${id}`);
    }
  }

  async function atualizarStatusComercial(id, destino, observacao, botao) {
    const chave = `status-${id}`;
    if (operacoesEmAndamento.has(chave)) return;
    operacoesEmAndamento.add(chave);
    botao.disabled = true;
    try {
      await apiFetch(`/api/pedidos/${id}/status-comercial`, {
        method: "PATCH",
        body: JSON.stringify({ status_pedido: destino, observacao }),
      });
      await carregarPedidos();
      await abrirDetalhes(id);
    } catch (error) {
      window.alert(error.message || "Não foi possível atualizar a situação comercial.");
    } finally {
      botao.disabled = false;
      operacoesEmAndamento.delete(chave);
    }
  }

  function mostrarPainel() {
    loginPanel.hidden = true;
    painel.hidden = false;
    idsNotificacaoConhecidos = null;
    carregarPedidos().finally(agendarPolling);
  }

  function mostrarLogin() {
    if (pollTimer) clearTimeout(pollTimer);
    pollTimer = null;
    painel.hidden = true;
    loginPanel.hidden = false;
    pedidos = [];
    lista.replaceChildren();
  }

  lista.addEventListener("click", (event) => {
    const botao = event.target.closest("[data-acao='detalhes']");
    const card = botao?.closest("[data-pedido-id]");
    if (card) abrirDetalhes(Number(card.dataset.pedidoId));
  });

  Object.values(filtros).forEach((controle) => controle.addEventListener("input", renderizar));

  document.querySelectorAll(".admin-pedido-chip[data-periodo]").forEach((chip) => {
    chip.addEventListener("click", () => {
      const ativo = chip.classList.contains("ativo");
      document.querySelectorAll(".admin-pedido-chip[data-periodo]").forEach((outro) => outro.classList.remove("ativo"));
      if (ativo) {
        filtros.inicio.value = "";
        filtros.fim.value = "";
      } else {
        chip.classList.add("ativo");
        aplicarFiltroPeriodo(chip.dataset.periodo);
      }
      renderizar();
    });
  });

  document.querySelectorAll(".admin-pedido-chip[data-estado]").forEach((chip) => {
    chip.addEventListener("click", () => {
      const ativo = chip.classList.contains("ativo");
      document.querySelectorAll(".admin-pedido-chip[data-estado]").forEach((outro) => outro.classList.remove("ativo"));
      filtroRapidoEstado = ativo ? null : chip.dataset.estado;
      if (!ativo) chip.classList.add("ativo");
      renderizar();
    });
  });

  document.getElementById("btnLimparFiltrosPedidos").addEventListener("click", () => {
    Object.values(filtros).forEach((controle) => { if (controle.type === "checkbox") controle.checked = false; else controle.value = ""; });
    filtroRapidoEstado = null;
    document.querySelectorAll(".admin-pedido-chip.ativo").forEach((chip) => chip.classList.remove("ativo"));
    renderizar();
  });
  document.getElementById("btnAtualizarPedidos").addEventListener("click", () => carregarPedidos());

  loginForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    loginStatus.hidden = false;
    loginStatus.textContent = "Entrando...";
    try {
      await apiFetch("/api/auth/login", { method: "POST", body: JSON.stringify({ login: loginUser.value.trim(), senha: loginSenha.value }) });
      loginForm.reset();
      loginStatus.hidden = true;
      mostrarPainel();
    } catch (error) {
      loginStatus.textContent = error.message || "Login ou senha inválidos.";
    }
  });

  document.getElementById("btnSairPedidos").addEventListener("click", async () => {
    try { await apiFetch("/api/auth/logout", { method: "POST", body: "{}" }); } catch {}
    mostrarLogin();
  });

  document.addEventListener("visibilitychange", () => {
    if (painel.hidden) return;
    if (pollTimer) clearTimeout(pollTimer);
    if (!document.hidden) carregarPedidos({ silencioso: true });
    agendarPolling();
  });

  apiFetch("/api/auth/me").then(mostrarPainel).catch(mostrarLogin);
})();
