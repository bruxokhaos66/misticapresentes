window.misticaSiteConfig = {
  domain: "www.misticaesotericos.com.br",
  publicBaseUrl: "https://www.misticaesotericos.com.br",
  apiBaseUrl: "https://api.misticaesotericos.com.br",
  serverMode: "production",
  usePublicDomainAccess: true,
  storageMode: "api_first",
  instagram: "@misticaeso",
  whatsappNumber: "554999172137",
  whatsappDisplay: "(49) 99917-2137",
  headerTitle: "Mística Presentes",
  headerSubtitle: "Xamanismo • Cristais • Aromas",
  promoText: "Transforme sua energia. Eleve sua essência.",
  // Deixe em branco para manter o analytics público desativado. Preencha
  // com o ID real (ex.: "G-XXXXXXX" e "000000000000000") para ativar.
  gaMeasurementId: "",
  metaPixelId: ""
};

(() => {
  const cfg = window.misticaSiteConfig || {};
  const productionMode = cfg.serverMode === "production" || cfg.storageMode === "api_first" || cfg.usePublicDomainAccess === true;
  if (!productionMode) return;

  window.misticaCatalogState = "loading";
  document.documentElement.dataset.catalogState = "loading";

  function updateCatalogUi(state) {
    const grid = document.querySelector("[data-product-grid]");
    const pixButton = document.querySelector("[data-generate-pix]");
    const blocked = state !== "ready";

    if (pixButton) {
      pixButton.disabled = blocked;
      pixButton.setAttribute("aria-disabled", blocked ? "true" : "false");
    }

    if (!grid || state === "ready") return;
    grid.replaceChildren();
    const notice = document.createElement("div");
    notice.className = "warning-box";
    notice.setAttribute("role", "status");
    notice.textContent = state === "error"
      ? "Catálogo indisponível no momento. As compras estão temporariamente bloqueadas."
      : "Carregando catálogo oficial da Mística...";
    grid.appendChild(notice);
  }

  document.addEventListener("click", event => {
    if (window.misticaCatalogState === "ready") return;
    const target = event.target?.closest?.("button, a");
    if (!target) return;
    const onclick = target.getAttribute("onclick") || "";
    if (target.matches("[data-generate-pix]") || onclick.includes("addToCart(")) {
      event.preventDefault();
      event.stopImmediatePropagation();
      if (typeof window.setStatus === "function") {
        window.setStatus("Compra temporariamente indisponível até o catálogo oficial carregar.");
      }
    }
  }, true);

  window.addEventListener("mistica:catalog-state", event => {
    updateCatalogUi(event.detail?.state || window.misticaCatalogState || "error");
  });

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", () => updateCatalogUi(window.misticaCatalogState), { once: true });
  } else {
    updateCatalogUi(window.misticaCatalogState);
  }
})();

(() => {
  const cfg = window.misticaSiteConfig || {};
  const API_BASE = String(cfg.apiBaseUrl || "https://api.misticaesotericos.com.br").replace(/\/$/, "");
  const productionMode = cfg.serverMode === "production" || cfg.storageMode === "api_first" || cfg.usePublicDomainAccess === true;
  if (!productionMode) return;

  const params = new URLSearchParams(window.location.search);
  const onAdminPage = /(^|\/)admin\.html$/.test(window.location.pathname);
  const adminRoute = onAdminPage || window.location.hash === "#admin" || window.location.hash === "#adminbruxo" || params.get("admin") === "mistica";

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

  function liberarPainel() {
    const loginPanel = document.getElementById("adminLoginPanel");
    const adminContent = document.getElementById("adminContent");
    if (loginPanel) loginPanel.hidden = true;
    if (adminContent) {
      adminContent.hidden = false;
      adminContent.removeAttribute("hidden");
      adminContent.style.display = "block";
    }
    try { sessionStorage.setItem("misticaAdminUnlocked", "true"); } catch {}
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
      if (sessao?.usuario) liberarPainel();
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
        liberarPainel();
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

  const loadStyle = (id, href) => {
    if (document.getElementById(id)) return;
    const link = document.createElement("link");
    link.id = id;
    link.rel = "stylesheet";
    link.href = href;
    document.head.appendChild(link);
  };

  const carregarPainelAdmin = () => {
    loadStyle("misticaAdminProductsStyle", "v2-admin-products.css?v=20260708-admin-products");
    loadStyle("misticaCoursesStyle", "v2-courses.css?v=20260710-cursos");
    loadScript("misticaAdminProductsScript", "v2-admin-products.js?v=20260708-admin-products");
    loadScript("misticaCoursesScript", "v2-courses.js?v=20260711-convite");
    loadScript("misticaCampaignAdminScript", "campaign-admin.js?v=20260711-campanhas");
  };

  const iniciar = () => {
    loadScript("misticaProductionGuardScript", "site-production-guard.js?v=20260713-checkout-estavel-2");
    if (!adminRoute) return;
    if (!onAdminPage) {
      window.location.replace("admin.html");
      return;
    }
    carregarPainelAdmin();
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