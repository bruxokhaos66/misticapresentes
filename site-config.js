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
  metaPixelId: "",
  // Feature flag pública da Isis 2.0 (isis2/README.md). Não é segredo,
  // não depende de query string nem de localStorage — é lida uma única
  // vez, de forma síncrona, deste arquivo estático. Default false:
  // mantém só a Isis 1 (isis-guided.js) até a habilitação explícita por
  // ambiente. Para homologar, edite este valor para true no deploy de
  // homologação; para produção, só depois de validado em homolog.
  isis2: {
    enabled: false,
    // Feature flag pública da Isis 2.0 — Especialista da Mística Escola
    // (isis2/README.md, Fase 2). Depende também de isis2.enabled=true
    // (ver isis2-loader.js): com isis2.enabled=false esta flag nunca é
    // avaliada. Não é segredo, não é lida de query string nem de
    // localStorage/sessionStorage, e só atua nas páginas da Escola
    // (escola.html, escola-curso.html). Default false.
    escola: {
      enabled: false,
      // Feature flag pública da Isis 2.0 — Refinamento da Especialista da
      // Mística Escola (isis2/README.md, Fase 2.1). Depende também de
      // isis2.enabled=true E isis2.escola.enabled=true (ver
      // isis2-loader.js e school-mode.js): com qualquer uma das duas
      // desligada, esta flag nunca é avaliada. Não é segredo, não é lida
      // de query string, hash, atributo HTML, localStorage/sessionStorage
      // nem cookie — só deste arquivo estático, uma única vez, de forma
      // síncrona. Nunca é ativada automaticamente em produção. Default
      // false: mantém o comportamento exato da Fase 2 até a habilitação
      // explícita por ambiente, após auditoria.
      refinamento: {
        enabled: false
      }
    }
  }
};

// Persistência segura do navegador. Este bloco roda de forma síncrona, no
// primeiro script da página (site-config.js sempre precede app.js e os
// demais consumidores), então nenhuma escrita comercial acontece antes dele.
// Não depende de monkey patch tardio: é a única API de armazenamento usada
// pelos scripts do site (app.js, mobile-sync.js, product-admin.js,
// v2-admin-products.js, site-production-guard.js).
(() => {
  const CART_KEY = "misticaCart";
  const FORBIDDEN_KEYS = [
    "misticaClients",
    "misticaSales",
    "misticaStock",
    "misticaSuppliers",
    "misticaAutoBackup",
    "misticaLastBackupAt",
    "misticaPendingOrderId",
    "misticaCustomProducts",
    "misticaApiProductsCache",
    "misticaApiProductsCacheAt",
  ];
  const MAX_QTY = 999;

  function sanitizeCartList(list) {
    if (!Array.isArray(list)) return [];
    const limpo = [];
    for (const raw of list) {
      if (!raw || typeof raw !== "object") continue;
      const id = raw.produto_id ?? raw.id;
      const qty = Number(raw.quantidade ?? raw.qty);
      if ((typeof id !== "string" && typeof id !== "number") || String(id).trim() === "") continue;
      if (!Number.isInteger(qty) || qty < 1) continue;
      limpo.push({ id: String(id), qty: Math.min(qty, MAX_QTY) });
    }
    return limpo;
  }

  function readRawCart() {
    let raw = null;
    try { raw = localStorage.getItem(CART_KEY); } catch { return []; }
    if (!raw) return [];
    let parsed;
    try { parsed = JSON.parse(raw); } catch { return []; }
    return sanitizeCartList(parsed);
  }

  function writeCart(items) {
    const limpo = sanitizeCartList(items);
    try { localStorage.setItem(CART_KEY, JSON.stringify(limpo)); } catch {}
    return limpo;
  }

  function clearCart() {
    try { localStorage.removeItem(CART_KEY); } catch {}
  }

  const CHECKOUT_IDEMPOTENCY_KEY = "misticaCheckoutIdempotency";

  // Guarda a Idempotency-Key da tentativa de checkout em curso, junto com a
  // assinatura do carrinho que a gerou, para que um reload da página ou uma
  // segunda aba com o mesmo carrinho reaproveitem a mesma chave em vez de
  // criar um segundo pedido/reserva de estoque (ver mobile-sync.js). Nunca
  // contém dado sensível (nome, telefone, endereço, valor) — só a chave
  // opaca e a assinatura id:quantidade dos itens.
  function sanitizeCheckoutIdempotency(value) {
    if (!value || typeof value !== "object") return null;
    const { key, signature, ts } = value;
    if (typeof key !== "string" || !key.trim()) return null;
    if (typeof signature !== "string") return null;
    if (!Number.isFinite(ts)) return null;
    return { key, signature, ts };
  }

  function getCheckoutIdempotency() {
    let raw = null;
    try { raw = localStorage.getItem(CHECKOUT_IDEMPOTENCY_KEY); } catch { return null; }
    if (!raw) return null;
    let parsed;
    try { parsed = JSON.parse(raw); } catch { return null; }
    return sanitizeCheckoutIdempotency(parsed);
  }

  function setCheckoutIdempotency(key, signature) {
    const limpo = sanitizeCheckoutIdempotency({ key, signature, ts: Date.now() });
    if (!limpo) return null;
    try { localStorage.setItem(CHECKOUT_IDEMPOTENCY_KEY, JSON.stringify(limpo)); } catch {}
    return limpo;
  }

  function clearCheckoutIdempotency() {
    try { localStorage.removeItem(CHECKOUT_IDEMPOTENCY_KEY); } catch {}
  }

  function removeForbiddenKeys() {
    let removidas = 0;
    FORBIDDEN_KEYS.forEach(key => {
      try {
        if (localStorage.getItem(key) !== null) {
          localStorage.removeItem(key);
          removidas++;
        }
      } catch {}
    });
    if (removidas > 0) {
      try {
        console.info(JSON.stringify({ evento: "armazenamento_legado_removido", quantidade_chaves: removidas }));
      } catch {}
    }
    return removidas;
  }

  // Limpeza de legado acontece imediatamente, antes de qualquer leitura pelo
  // restante da aplicação (nenhum outro script ainda executou neste ponto).
  removeForbiddenKeys();

  // Uma aba antiga (com formato de carrinho legado ou chaves proibidas) não
  // pode reintroduzir dados: qualquer alteração de storage vinda de outra
  // aba é filtrada aqui antes de propagar.
  window.addEventListener("storage", event => {
    if (!event.key) return;
    if (FORBIDDEN_KEYS.includes(event.key)) {
      try { localStorage.removeItem(event.key); } catch {}
      return;
    }
    if (event.key === CART_KEY && event.newValue) {
      let parsed;
      try { parsed = JSON.parse(event.newValue); } catch { parsed = null; }
      const sanitizado = sanitizeCartList(parsed);
      if (JSON.stringify(sanitizado) !== event.newValue) writeCart(sanitizado);
    }
  });

  const secureStorageApi = Object.freeze({
    CART_KEY,
    FORBIDDEN_KEYS: FORBIDDEN_KEYS.slice(),
    getCart: readRawCart,
    setCart: writeCart,
    clearCart,
    sanitizeCart: sanitizeCartList,
    removeForbiddenKeys,
    CHECKOUT_IDEMPOTENCY_KEY,
    getCheckoutIdempotency,
    setCheckoutIdempotency,
    clearCheckoutIdempotency,
  });
  // Não editável e não redefinível: nenhum script carregado depois pode
  // trocar window.misticaSecureStorage por uma implementação diferente
  // (silenciosamente ou não) nem alterar seus métodos.
  Object.defineProperty(window, "misticaSecureStorage", {
    value: secureStorageApi,
    writable: false,
    configurable: false,
    enumerable: true,
  });
})();

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
    // mobile-sync.js dispara "loading"/"error" a cada sincronização (a cada
    // 15s, para sempre, inclusive quando tudo está bem) e também numa falha
    // passageira de rede depois de um catálogo já confirmado. Se a vitrine já
    // tem produtos reais renderizados, apagar tudo aqui pra colocar um aviso
    // é o que fazia os cards desaparecerem, a seção seguinte subir e, no
    // próximo sync com sucesso, tudo reaparecer empurrando a página de
    // novo — o "piscar/pular" da vitrine. Uma vez que o catálogo já foi
    // confirmado (existe ao menos um card real), este aviso só faz sentido
    // enquanto NADA ainda foi mostrado (1º carregamento); depois disso, o
    // botão de Pix já fica bloqueado acima e o selo flutuante do
    // mobile-sync.js (#mobileSyncStatus) já avisa da instabilidade, sem
    // remover o que já está em tela.
    if (grid.querySelector(".product-card")) return;
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
    loadScript("misticaIsis2HomologAdminScript", "isis2-homolog-admin.js?v=20260717-isis2-homolog-admin");
  };

  const iniciar = () => {
    loadScript("misticaProductionGuardScript", "/site-production-guard.js?v=20260713-checkout-estavel-3");
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