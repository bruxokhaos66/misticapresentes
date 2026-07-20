(() => {
  "use strict";

  const config = window.misticaSiteConfig || {};
  const API_BASE = String(config.apiBaseUrl || "https://api.misticaesotericos.com.br").replace(/\/$/, "");
  const POLL_VISIBLE_MS = 15000;
  const POLL_HIDDEN_MS = 60000;
  const currency = new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" });
  const dateTime = new Intl.DateTimeFormat("pt-BR", { dateStyle: "short", timeStyle: "short" });

  const loginPanel = document.getElementById("loginPanelOperacoes");
  const loginForm = document.getElementById("loginFormOperacoes");
  const loginUser = document.getElementById("loginUserOperacoes");
  const loginSenha = document.getElementById("loginSenhaOperacoes");
  const loginStatus = document.getElementById("loginStatusOperacoes");
  const painel = document.getElementById("painelOperacoes");
  const grade = document.getElementById("gradeOperacoes");
  const alertasBox = document.getElementById("alertasOperacoes");
  const ultimaAtualizacao = document.getElementById("ultimaAtualizacaoOperacoes");
  const btnAtualizar = document.getElementById("btnAtualizarOperacoes");
  const btnSair = document.getElementById("btnSairOperacoes");

  let pollTimer = null;
  let carregando = false;

  const CARDS = [
    { chave: "pedidos_aguardando_pagamento", titulo: "Aguardando pagamento", tipo: "int" },
    { chave: "pedidos_pagos_aguardando_envio", titulo: "Pagos aguardando envio", tipo: "int" },
    { chave: "pedidos_enviados_hoje", titulo: "Enviados hoje", tipo: "int" },
    { chave: "faturamento_hoje", titulo: "Faturamento hoje", tipo: "moeda", destaque: true },
    { chave: "faturamento_mes", titulo: "Faturamento do mês", tipo: "moeda", destaque: true },
    { chave: "ticket_medio_mes", titulo: "Ticket médio do mês", tipo: "moeda" },
    { chave: "produtos_sem_estoque", titulo: "Produtos sem estoque", tipo: "int" },
    { chave: "produtos_estoque_critico", titulo: "Estoque crítico", tipo: "int" },
    { chave: "novos_clientes_hoje", titulo: "Novos clientes hoje", tipo: "int" },
    { chave: "cursos_vendidos_mes", titulo: "Cursos vendidos no mês", tipo: "int" },
    { chave: "pedidos_pix_mes", titulo: "Pedidos Pix (mês)", tipo: "int" },
    { chave: "pedidos_cartao_mes", titulo: "Pedidos Cartão (mês)", tipo: "int" },
    { chave: "campanhas_ativas", titulo: "Campanhas ativas", tipo: "int" },
  ];

  const NIVEL_ROTULO = { alerta: "Alerta", atencao: "Atenção", info: "Info" };

  function elemento(tag, classe, texto) {
    const node = document.createElement(tag);
    if (classe) node.className = classe;
    if (texto !== undefined && texto !== null) node.textContent = String(texto);
    return node;
  }

  function formatarValor(valor, tipo) {
    if (tipo === "moeda") return currency.format(Number(valor || 0));
    return String(Number(valor || 0));
  }

  async function apiFetch(path, options = {}) {
    const response = await fetch(`${API_BASE}${path}`, {
      credentials: "include",
      cache: "no-store",
      ...options,
      headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    });
    if (response.status === 401 || response.status === 403) {
      mostrarLogin();
      throw new Error("Sessão expirada");
    }
    const texto = await response.text();
    if (!response.ok) throw new Error(texto || `HTTP ${response.status}`);
    try { return JSON.parse(texto); } catch { return texto; }
  }

  function mostrarLogin() {
    pararPolling();
    painel.hidden = true;
    loginPanel.hidden = false;
  }

  function mostrarPainel() {
    loginPanel.hidden = true;
    painel.hidden = false;
  }

  function renderAlertas(alertas) {
    alertasBox.replaceChildren();
    if (!Array.isArray(alertas) || !alertas.length) return;
    alertas.forEach((alerta) => {
      const nivel = alerta.nivel || "info";
      const item = elemento("div", `admin-operacoes-alerta nivel-${nivel}`);
      item.append(elemento("span", "", `[${NIVEL_ROTULO[nivel] || nivel}]`), elemento("span", "", alerta.mensagem));
      alertasBox.appendChild(item);
    });
  }

  function renderGrade(dados) {
    grade.replaceChildren();
    CARDS.forEach((card) => {
      const el = elemento("article", `admin-operacoes-card${card.destaque ? " destaque" : ""}`);
      el.append(
        elemento("small", "", card.titulo),
        elemento("strong", "", formatarValor(dados[card.chave], card.tipo))
      );
      grade.appendChild(el);
    });
  }

  async function carregar() {
    if (carregando) return;
    carregando = true;
    try {
      const dados = await apiFetch("/api/painel/operacoes/dashboard");
      renderGrade(dados);
      renderAlertas(dados.alertas);
      ultimaAtualizacao.textContent = `Última atualização: ${dateTime.format(new Date())}`;
    } catch (erro) {
      ultimaAtualizacao.textContent = `Última atualização: falhou (${String(erro.message || erro).slice(0, 90)})`;
    } finally {
      carregando = false;
    }
  }

  function agendarPolling() {
    pararPolling();
    const intervalo = document.hidden ? POLL_HIDDEN_MS : POLL_VISIBLE_MS;
    pollTimer = setTimeout(async () => {
      await carregar();
      agendarPolling();
    }, intervalo);
  }

  function pararPolling() {
    if (pollTimer) clearTimeout(pollTimer);
    pollTimer = null;
  }

  document.addEventListener("visibilitychange", () => {
    if (!painel.hidden) agendarPolling();
  });

  loginForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    loginStatus.hidden = false;
    loginStatus.textContent = "Entrando...";
    try {
      await apiFetch("/api/auth/login", {
        method: "POST",
        body: JSON.stringify({ login: loginUser.value.trim(), senha: loginSenha.value }),
      });
      loginStatus.hidden = true;
      mostrarPainel();
      await carregar();
      agendarPolling();
    } catch (erro) {
      loginStatus.textContent = `Falha no login: ${String(erro.message || erro).slice(0, 100)}`;
    }
  });

  btnAtualizar.addEventListener("click", () => { carregar(); });

  btnSair.addEventListener("click", async () => {
    pararPolling();
    try { await apiFetch("/api/auth/logout", { method: "POST" }); } catch {}
    mostrarLogin();
  });

  (async () => {
    try {
      await apiFetch("/api/auth/me", { method: "GET" });
      mostrarPainel();
      await carregar();
      agendarPolling();
    } catch {
      mostrarLogin();
    }
  })();
})();
