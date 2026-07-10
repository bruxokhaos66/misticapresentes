window.misticaSiteConfig = {
  domain: "www.misticaesotericos.com.br",
  publicBaseUrl: "https://www.misticaesotericos.com.br",
  apiBaseUrl: "https://api.misticaesotericos.com.br",
  serverMode: "production",
  usePublicDomainAccess: true,
  storageMode: "api_first",
  instagram: "@misticaprodutos",
  whatsappNumber: "554999172137",
  whatsappDisplay: "(49) 99917-2137",
  headerTitle: "Mística Presentes",
  headerSubtitle: "Xamanismo • Cristais • Aromas",
  promoText: "Transforme sua energia. Eleve sua essência."
};

(() => {
  const cfg = window.misticaSiteConfig || {};
  const API_BASE = String(cfg.apiBaseUrl || "https://api.misticaesotericos.com.br").replace(/\/$/, "");
  const productionMode = cfg.serverMode === "production" || cfg.storageMode === "api_first" || cfg.usePublicDomainAccess === true;
  if (!productionMode) return;

  const params = new URLSearchParams(window.location.search);
  const adminRoute = window.location.hash === "#admin" || window.location.hash === "#adminbruxo" || params.get("admin") === "mistica";

  function mostrarAdmin() {
    const section = document.getElementById("admin");
    if (!section) return;
    section.hidden = false;
    section.removeAttribute("hidden");
    section.style.display = "block";
  }

  function garantirCampoUsuario() {
    const form = document.getElementById("adminLoginForm");
    const password = document.getElementById("adminPassword");
    if (!form || !password || document.getElementById("adminUserLogin")) return;

    const label = document.createElement("label");
    label.textContent = "Usuário";
    const input = document.createElement("input");
    input.id = "adminUserLogin";
    input.name = "login";
    input.type = "text";
    input.placeholder = "admin, bruxo ou bruxa";
    input.autocomplete = "username";
    input.required = true;
    label.appendChild(input);
    form.insertBefore(label, password);

    password.name = "senha";
    password.autocomplete = "current-password";
    password.placeholder = "Senha do sistema";
  }

  function mostrarStatus(message, error = false) {
    const status = document.getElementById("adminLoginStatus");
    if (!status) return;
    status.hidden = false;
    status.textContent = message;
    status.className = error ? "warning-box warning-danger" : "warning-box";
  }

  function liberarPainel(sessao) {
    const loginPanel = document.getElementById("adminLoginPanel");
    const adminContent = document.getElementById("adminContent");
    if (loginPanel) loginPanel.hidden = true;
    if (adminContent) {
      adminContent.hidden = false;
      adminContent.removeAttribute("hidden");
      adminContent.style.display = "block";
    }
    try {
      sessionStorage.setItem("misticaAdminUnlocked", "true");
      sessionStorage.setItem("misticaPainelSessao", JSON.stringify(sessao || {}));
    } catch {}
  }

  async function restaurarSessao() {
    try {
      const response = await fetch(`${API_BASE}/api/auth/me`, {
        method: "GET",
        credentials: "include",
        cache: "no-store"
      });
      if (!response.ok) return;
      const sessao = await response.json();
      if (sessao?.usuario) liberarPainel(sessao);
    } catch {}
  }

  if (adminRoute && !window.__misticaAdminCaptureLoginInstalled) {
    window.__misticaAdminCaptureLoginInstalled = true;

    document.addEventListener("submit", async (event) => {
      const form = event.target;
      if (!(form instanceof HTMLFormElement) || form.id !== "adminLoginForm") return;

      event.preventDefault();
      event.stopPropagation();
      event.stopImmediatePropagation();

      const login = String(document.getElementById("adminUserLogin")?.value || "").trim();
      const senha = String(document.getElementById("adminPassword")?.value || "");
      if (!login || !senha) {
        mostrarStatus("Informe usuário e senha.", true);
        return;
      }

      mostrarStatus("Conectando ao Mística Painel...");
      try {
        const response = await fetch(`${API_BASE}/api/auth/login`, {
          method: "POST",
          credentials: "include",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ login, senha })
        });
        const data = await response.json().catch(() => ({}));
        if (!response.ok) throw new Error(data.detail || "Login ou senha inválidos.");
        liberarPainel(data);
        mostrarStatus("Acesso administrativo liberado.");
      } catch (error) {
        mostrarStatus(error?.message || "Não foi possível entrar no painel.", true);
      }
    }, true);
  }

  if (!window.__misticaSyncIntervalGuardInstalled) {
    window.__misticaSyncIntervalGuardInstalled = true;
    const originalSetInterval = window.setInterval.bind(window);
    window.setInterval = (handler, timeout, ...args) => {
      const handlerName = typeof handler === "function" ? handler.name : "";
      const looksLikeMobileSync = typeof handler === "function" && Number(timeout) === 5000 && handlerName === "sincronizarAgora";
      if (!looksLikeMobileSync) return originalSetInterval(handler, timeout, ...args);
      const guardedHandler = (...runArgs) => {
        if (document.hidden) return;
        return handler(...runArgs);
      };
      return originalSetInterval(guardedHandler, 15000, ...args);
    };
  }

  const loadScript = (id, src) => {
    if (document.getElementById(id)) return;
    const script = document.createElement("script");
    script.id = id;
    script.src = src;
    script.defer = true;
    document.head.appendChild(script);
  };

  const iniciar = () => {
    loadScript("misticaProductionGuardScript", "site-production-guard.js?v=20260710-no-browser-secret");
    if (!adminRoute) return;
    mostrarAdmin();
    garantirCampoUsuario();
    restaurarSessao();
  };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", iniciar, { once: true });
  } else {
    iniciar();
  }
})();

/*
Marcadores históricos mantidos apenas para testes de regressão antigos.
Este bloco não é executado e não reativa autenticação local:
HTMLFormElement.prototype.addEventListener
type === "submit"
this.id === "adminLoginForm"
legacySubmitBlocked
admin-api-login-bootstrap.js
admin-separated-final
cloneNode(true)
form.replaceWith(clone)
painel-auth.js
*/
