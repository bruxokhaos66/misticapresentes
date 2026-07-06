(() => {
  const cfg = window.misticaSiteConfig || {};
  const productionMode = cfg.serverMode === "production" || cfg.storageMode === "api_first" || cfg.usePublicDomainAccess === true;
  const siteKey = String(cfg.siteApiKey || "").trim();
  if (!productionMode || siteKey) return;

  const WRITE_SELECTORS = [
    "[data-generate-pix]",
    "#clientForm",
    "#productAdminForm",
    "#supplierForm",
    "[data-download-backup]",
    "[data-export-clients]",
    "[data-export-sales]",
  ];

  function message() {
    return "Ação bloqueada em produção: configure a chave da API do site antes de gravar vendas, clientes ou dados administrativos.";
  }

  function showStatus(text) {
    const pix = document.getElementById("pixStatus");
    if (pix) pix.textContent = text;
    const admin = document.getElementById("adminLoginStatus") || document.getElementById("productAdminStatus") || document.getElementById("clientSaved");
    if (admin) {
      admin.hidden = false;
      admin.textContent = text;
    }
    const sync = document.getElementById("mobileSyncStatus");
    if (sync) {
      sync.textContent = text;
      sync.style.background = "#3b1c1c";
      sync.style.color = "#ffd7d7";
    }
  }

  function block(event) {
    event.preventDefault();
    event.stopImmediatePropagation();
    showStatus(message());
    return false;
  }

  document.addEventListener("click", event => {
    const target = event.target?.closest?.("button, a");
    if (!target) return;
    if (WRITE_SELECTORS.some(selector => target.matches(selector) || target.closest(selector))) block(event);
    const inline = target.getAttribute("onclick") || "";
    if (/cancelSale|updateSaleStatus/.test(inline)) block(event);
  }, true);

  document.addEventListener("submit", event => {
    const form = event.target;
    if (!form) return;
    if (WRITE_SELECTORS.some(selector => form.matches(selector))) block(event);
  }, true);

  window.misticaWriteKeyGuard = { enabled: true, reason: "missing_site_api_key" };
})();
