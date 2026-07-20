(() => {
  "use strict";

  const config = window.misticaSiteConfig || {};
  const API_BASE = String(config.apiBaseUrl || "https://api.misticaesotericos.com.br").replace(/\/$/, "");
  const dateTime = new Intl.DateTimeFormat("pt-BR", { dateStyle: "short", timeStyle: "short" });

  const loginPanel = document.getElementById("loginPanelHomolog");
  const loginForm = document.getElementById("loginFormHomolog");
  const loginUser = document.getElementById("loginUserHomolog");
  const loginSenha = document.getElementById("loginSenhaHomolog");
  const loginStatus = document.getElementById("loginStatusHomolog");
  const painel = document.getElementById("painelHomolog");
  const lista = document.getElementById("listaHomolog");
  const ultimaAtualizacao = document.getElementById("ultimaAtualizacaoHomolog");
  const btnAtualizar = document.getElementById("btnAtualizarHomolog");
  const btnSair = document.getElementById("btnSairHomolog");

  const SELO = { verde: "Aprovado", amarelo: "Atenção", vermelho: "Bloqueante", info: "Verificação manual" };

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
      mostrarLogin();
      throw new Error("Sessão expirada ou sem perfil de administrador");
    }
    const texto = await response.text();
    if (!response.ok) throw new Error(texto || `HTTP ${response.status}`);
    try { return JSON.parse(texto); } catch { return texto; }
  }

  function mostrarLogin() {
    painel.hidden = true;
    loginPanel.hidden = false;
  }

  function mostrarPainel() {
    loginPanel.hidden = true;
    painel.hidden = false;
  }

  function renderLista(itens) {
    lista.replaceChildren();
    if (!Array.isArray(itens) || !itens.length) {
      lista.append(elemento("p", "admin-operacoes-note", "Nenhum item de homologação disponível."));
      return;
    }
    itens.forEach((item) => {
      const card = elemento("article", "admin-homologacao-item");
      const luz = elemento("span", `admin-homologacao-luz ${item.status}`);
      const texto = elemento("div", "admin-homologacao-texto");
      texto.append(
        elemento("h3", "", item.titulo),
        elemento("p", "", item.detalhe),
        elemento("span", "admin-homologacao-selo", SELO[item.status] || item.status)
      );
      card.append(luz, texto);
      lista.appendChild(card);
    });
  }

  async function carregar() {
    ultimaAtualizacao.textContent = "Verificando checklist...";
    try {
      const dados = await apiFetch("/api/painel/operacoes/homologacao");
      renderLista(dados.itens);
      ultimaAtualizacao.textContent = `Última verificação: ${dateTime.format(new Date())}`;
    } catch (erro) {
      ultimaAtualizacao.textContent = `Última verificação: falhou (${String(erro.message || erro).slice(0, 90)})`;
    }
  }

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
    } catch (erro) {
      loginStatus.textContent = `Falha no login: ${String(erro.message || erro).slice(0, 100)}`;
    }
  });

  btnAtualizar.addEventListener("click", () => { carregar(); });

  btnSair.addEventListener("click", async () => {
    try { await apiFetch("/api/auth/logout", { method: "POST" }); } catch {}
    mostrarLogin();
  });

  (async () => {
    try {
      await apiFetch("/api/auth/me", { method: "GET" });
      mostrarPainel();
      await carregar();
    } catch {
      mostrarLogin();
    }
  })();
})();
