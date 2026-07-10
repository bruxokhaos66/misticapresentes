(() => {
  const config = window.misticaSiteConfig || {};
  const API_BASE = (config.apiBaseUrl || "https://api.misticaesotericos.com.br").replace(/\/$/, "");
  const ADMIN_HASHES = ["#admin", "#adminbruxo"];

  function $(selector) { return document.querySelector(selector); }

  function isAdminRoute() {
    const params = new URLSearchParams(window.location.search);
    return ADMIN_HASHES.includes(window.location.hash) || params.get("admin") === "mistica";
  }

  function temSessaoAtiva() {
    // Apenas um indício local para decidir se vale a pena perguntar ao servidor;
    // a autenticação de fato é sempre revalidada em /api/auth/me (cookie HttpOnly).
    try { return sessionStorage.getItem("misticaAdminUnlocked") === "true"; } catch { return false; }
  }

  async function apiMe() {
    const response = await fetch(`${API_BASE}/api/auth/me`, {
      method: "GET",
      credentials: "include",
      cache: "no-store",
    });
    if (!response.ok) return null;
    return response.json();
  }

  function mostrarSecaoAdmin() {
    const secao = document.getElementById("admin");
    if (!secao) return;
    secao.hidden = false;
    secao.removeAttribute("hidden");
    secao.style.display = "block";
    setTimeout(() => secao.scrollIntoView({ behavior: "smooth", block: "start" }), 80);
  }

  function esconderSecaoAdmin() {
    const secao = document.getElementById("admin");
    if (!secao) return;
    secao.hidden = true;
    secao.style.display = "none";
  }

  function sincronizarRotaAdmin() {
    if (!isAdminRoute()) return esconderSecaoAdmin();
    mostrarSecaoAdmin();
    if (temSessaoAtiva()) restaurarSessao();
  }

  function garantirCampoLogin() {
    const form = document.getElementById("adminLoginForm");
    const senha = document.getElementById("adminPassword");
    if (!form || !senha || document.getElementById("adminUserLogin")) return;

    const label = document.createElement("label");
    label.textContent = "Usuário";
    const input = document.createElement("input");
    input.id = "adminUserLogin";
    input.type = "text";
    input.placeholder = "admin ou login do vendedor";
    input.autocomplete = "username";
    input.required = true;
    label.appendChild(input);
    form.insertBefore(label, senha.closest("label"));

    senha.autocomplete = "current-password";
    senha.placeholder = "Senha do sistema";
  }

  async function apiLogin(login, senha) {
    const response = await fetch(`${API_BASE}/api/auth/login`, {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ login, senha }),
    });
    if (!response.ok) throw new Error("Login ou senha inválidos.");
    return response.json();
  }

  async function sairDoAdmin() {
    try {
      await fetch(`${API_BASE}/api/auth/logout`, { method: "POST", credentials: "include" });
    } catch {}
    try {
      sessionStorage.removeItem("misticaPainelSessao");
      sessionStorage.removeItem("misticaAdminUnlocked");
    } catch {}
    const loginPanel = document.getElementById("adminLoginPanel");
    const adminContent = document.getElementById("adminContent");
    const status = document.getElementById("adminLoginStatus");
    if (adminContent) adminContent.hidden = true;
    if (loginPanel) loginPanel.hidden = false;
    if (status) {
      status.hidden = false;
      status.textContent = "Sessão encerrada com segurança.";
    }
  }

  function garantirBotaoSaida(adminContent) {
    if (adminContent.querySelector("[data-admin-logout]")) return;
    const button = document.createElement("button");
    button.type = "button";
    button.className = "btn btn-ghost";
    button.setAttribute("data-admin-logout", "true");
    button.textContent = "Sair do admin";
    button.addEventListener("click", sairDoAdmin);
    adminContent.insertBefore(button, adminContent.firstChild);
  }

  function aplicarPermissoes(sessao) {
    const perfil = sessao?.usuario?.perfil || "vendedor";
    const permissoes = sessao?.permissoes || {};
    const adminContent = document.getElementById("adminContent");
    if (!adminContent) return;

    garantirBotaoSaida(adminContent);
    if (!adminContent.querySelector("[data-admin-session-notice]")) {
      const aviso = document.createElement("div");
      aviso.className = "saved-box";
      aviso.setAttribute("data-admin-session-notice", "true");
      aviso.textContent = `Acesso liberado para ${sessao.usuario.nome} • Perfil: ${perfil === "adm" ? "Administrador" : "Vendedor"}`;
      aviso.style.marginBottom = "14px";
      adminContent.prepend(aviso);
    }

    if (!permissoes.clientes) {
      const clientSection = document.getElementById("cliente");
      if (clientSection) clientSection.style.display = "none";
    }

    if (!permissoes.fornecedores && perfil !== "adm") {
      adminContent.querySelectorAll("form#supplierForm, #supplierList").forEach(el => {
        const panel = el.closest(".form-panel");
        if (panel) panel.style.display = "none";
      });
    }

    if (!permissoes.backup && perfil !== "adm") {
      adminContent.querySelectorAll("[data-download-backup], [data-restore-backup]").forEach(el => {
        const panel = el.closest(".form-panel");
        if (panel) panel.style.display = "none";
      });
    }
  }

  async function carregarPainelTempoReal() {
    try {
      if (window.misticaMobileSync?.syncNow) await window.misticaMobileSync.syncNow();
      if (typeof renderAdminDashboard === "function") renderAdminDashboard();
      if (typeof renderStock === "function") renderStock();
      if (typeof renderHistory === "function") renderHistory();
    } catch {}
  }

  function instalarLoginApi() {
    const form = document.getElementById("adminLoginForm");
    const loginInput = document.getElementById("adminUserLogin");
    const senhaInput = document.getElementById("adminPassword");
    const status = document.getElementById("adminLoginStatus");
    const loginPanel = document.getElementById("adminLoginPanel");
    const adminContent = document.getElementById("adminContent");
    if (!form || !loginInput || !senhaInput || !loginPanel || !adminContent || form.dataset.apiAuthInstalled === "true") return;
    form.dataset.apiAuthInstalled = "true";

    form.addEventListener("submit", async event => {
      event.preventDefault();
      event.stopImmediatePropagation();
      const login = loginInput.value.trim();
      const senha = senhaInput.value;
      if (!login || !senha) return;

      if (status) {
        status.hidden = false;
        status.textContent = "Conectando ao Mística Painel...";
      }

      try {
        const sessao = await apiLogin(login, senha);
        sessionStorage.setItem("misticaPainelSessao", JSON.stringify(sessao));
        sessionStorage.setItem("misticaAdminUnlocked", "true");
        loginPanel.hidden = true;
        adminContent.hidden = false;
        aplicarPermissoes(sessao);
        await carregarPainelTempoReal();
      } catch (error) {
        if (status) {
          status.hidden = false;
          status.textContent = error.message || "Erro ao entrar no painel.";
        }
      }
    }, true);
  }

  async function restaurarSessao() {
    // A sessão local é só um atalho de UI; a fonte da verdade é sempre o servidor.
    const sessao = await apiMe().catch(() => null);
    if (!sessao?.usuario) {
      try {
        sessionStorage.removeItem("misticaPainelSessao");
        sessionStorage.removeItem("misticaAdminUnlocked");
      } catch {}
      return;
    }
    try { sessionStorage.setItem("misticaPainelSessao", JSON.stringify(sessao)); } catch {}
    const loginPanel = document.getElementById("adminLoginPanel");
    const adminContent = document.getElementById("adminContent");
    if (loginPanel && adminContent) {
      loginPanel.hidden = true;
      adminContent.hidden = false;
      aplicarPermissoes(sessao);
      carregarPainelTempoReal();
    }
  }

  function inicializarAdmin() {
    garantirCampoLogin();
    instalarLoginApi();
    sincronizarRotaAdmin();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", inicializarAdmin, { once: true });
  } else {
    inicializarAdmin();
  }

  window.addEventListener("hashchange", sincronizarRotaAdmin);
  window.addEventListener("popstate", sincronizarRotaAdmin);
})();