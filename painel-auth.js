(() => {
  const config = window.misticaSiteConfig || {};
  const API_BASE = (config.apiBaseUrl || "https://api.misticaesotericos.com.br").replace(/\/$/, "");
  const ADMIN_HASHES = ["#admin", "#adminbruxo"];

  function $(selector) { return document.querySelector(selector); }

  function isAdminRoute() {
    return ADMIN_HASHES.includes(window.location.hash);
  }

  function temSessaoAtiva() {
    try { return sessionStorage.getItem("misticaAdminUnlocked") === "true"; } catch { return false; }
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
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ login, senha }),
    });
    if (!response.ok) throw new Error("Login ou senha inválidos.");
    return response.json();
  }

  function sairDoAdmin() {
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
    const titulo = adminContent.querySelector(".container.form-panel h2, h2");
    const aviso = document.createElement("div");
    aviso.className = "saved-box";
    aviso.textContent = `Acesso liberado para ${sessao.usuario.nome} • Perfil: ${perfil === "adm" ? "Administrador" : "Vendedor"}`;
    aviso.style.marginBottom = "14px";
    adminContent.prepend(aviso);

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
    if (!form || !loginInput || !senhaInput || !loginPanel || !adminContent) return;

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

  function restaurarSessao() {
    try {
      const sessao = JSON.parse(sessionStorage.getItem("misticaPainelSessao") || "null");
      if (!sessao?.usuario) return;
      const loginPanel = document.getElementById("adminLoginPanel");
      const adminContent = document.getElementById("adminContent");
      if (loginPanel && adminContent) {
        loginPanel.hidden = true;
        adminContent.hidden = false;
        aplicarPermissoes(sessao);
        carregarPainelTempoReal();
      }
    } catch {}
  }

  window.addEventListener("load", () => {
    garantirCampoLogin();
    instalarLoginApi();
    sincronizarRotaAdmin();
  });
  window.addEventListener("hashchange", sincronizarRotaAdmin);
})();
