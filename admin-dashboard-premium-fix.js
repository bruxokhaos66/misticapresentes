(() => {
  const styleId = "misticaAdminDashboardPremiumStyle";
  const summaryId = "adminPremiumSummary";

  function installStyle() {
    if (document.getElementById(styleId)) return;

    const style = document.createElement("style");
    style.id = styleId;
    style.textContent = `
      #admin .admin-content {
        position: relative;
      }

      #admin .dashboard-grid {
        gap: clamp(12px, 2vw, 18px);
      }

      #admin .metric-card {
        position: relative;
        overflow: hidden;
        border: 1px solid rgba(240,197,106,.24) !important;
        border-radius: 26px !important;
        padding: clamp(18px, 2.4vw, 24px) !important;
        background:
          radial-gradient(circle at 16% 0, rgba(240,197,106,.16), transparent 34%),
          linear-gradient(145deg, rgba(255,248,230,.075), rgba(83,107,55,.065)) !important;
        box-shadow: 0 24px 70px rgba(0,0,0,.22) !important;
      }

      #admin .metric-card::before {
        content: "";
        position: absolute;
        inset: 0;
        pointer-events: none;
        background: linear-gradient(135deg, rgba(255,248,230,.08), transparent 44%);
      }

      #admin .metric-card > * {
        position: relative;
        z-index: 1;
      }

      #admin .metric-card span {
        color: #d8cbb6;
        font-weight: 950;
        letter-spacing: .12em;
        text-transform: uppercase;
      }

      #admin .metric-card strong {
        color: #fff3c4;
        font-size: clamp(1.45rem, 3vw, 2.25rem);
        text-shadow: 0 0 22px rgba(240,197,106,.18);
      }

      .admin-premium-summary {
        position: relative;
        overflow: hidden;
        margin: 0 0 clamp(16px, 2vw, 24px);
        border: 1px solid rgba(184,201,119,.25);
        border-radius: 28px;
        padding: clamp(18px, 2.8vw, 26px);
        background:
          radial-gradient(circle at 10% 0, rgba(184,201,119,.14), transparent 32%),
          radial-gradient(circle at 90% 12%, rgba(240,197,106,.13), transparent 30%),
          rgba(3,3,5,.24);
        box-shadow: 0 24px 74px rgba(0,0,0,.22);
      }

      .admin-premium-summary::before {
        content: "";
        position: absolute;
        inset: 0;
        pointer-events: none;
        background: linear-gradient(120deg, rgba(255,248,230,.07), transparent 42%, rgba(184,201,119,.05));
      }

      .admin-premium-summary > * {
        position: relative;
        z-index: 1;
      }

      .admin-premium-summary h3 {
        margin: 4px 0 8px;
        color: #fff3d4;
        font-family: Cinzel, Georgia, serif;
        letter-spacing: .06em;
      }

      .admin-premium-summary p {
        margin: 0 0 14px;
        color: #e5d8bf;
        font-weight: 680;
        line-height: 1.5;
      }

      .admin-premium-summary-grid {
        display: grid;
        grid-template-columns: repeat(3, minmax(0, 1fr));
        gap: 10px;
      }

      .admin-premium-summary-chip {
        border: 1px solid rgba(240,197,106,.18);
        border-radius: 18px;
        padding: 12px;
        background: rgba(255,248,230,.045);
      }

      .admin-premium-summary-chip span {
        display: block;
        color: #cfc2ad;
        font-size: .78rem;
        font-weight: 900;
        letter-spacing: .08em;
        text-transform: uppercase;
      }

      .admin-premium-summary-chip strong {
        display: block;
        margin-top: 5px;
        color: #f0c56a;
        font-size: 1.12rem;
      }

      @media (max-width: 760px) {
        .admin-premium-summary-grid {
          grid-template-columns: 1fr;
        }
      }
    `;

    document.head.appendChild(style);
  }

  function text(id) {
    return document.getElementById(id)?.textContent?.trim() || "0";
  }

  function lowStockCount() {
    const root = document.getElementById("lowStockAlerts");
    if (!root) return "0";
    const items = root.querySelectorAll(".history-item, article, li");
    if (items.length) return String(items.length);
    const raw = root.textContent.trim();
    return raw ? "Verificar" : "0";
  }

  function mountSummary() {
    const admin = document.getElementById("adminContent");
    const dashboard = admin?.querySelector(".dashboard-grid");
    if (!admin || !dashboard) return;

    let summary = document.getElementById(summaryId);
    if (!summary) {
      summary = document.createElement("section");
      summary.id = summaryId;
      summary.className = "admin-premium-summary";
      dashboard.insertAdjacentElement("beforebegin", summary);
    }

    summary.innerHTML = `
      <p class="eyebrow">Resumo operacional</p>
      <h3>Visão rápida da loja</h3>
      <p>Acompanhe faturamento, vendas e alertas principais antes de conferir estoque, fornecedores e backup.</p>
      <div class="admin-premium-summary-grid">
        <div class="admin-premium-summary-chip"><span>Hoje</span><strong>${text("revenueToday")}</strong></div>
        <div class="admin-premium-summary-chip"><span>Vendas</span><strong>${text("salesCount")}</strong></div>
        <div class="admin-premium-summary-chip"><span>Estoque mínimo</span><strong>${lowStockCount()}</strong></div>
      </div>
    `;
  }

  function installObservers() {
    ["revenueToday", "salesCount", "lowStockAlerts"].forEach(id => {
      const el = document.getElementById(id);
      if (!el || el.dataset.adminDashboardPremiumObserver === "true") return;
      el.dataset.adminDashboardPremiumObserver = "true";
      new MutationObserver(() => requestAnimationFrame(mountSummary)).observe(el, {
        childList: true,
        subtree: true,
        characterData: true,
      });
    });
  }

  function apply() {
    installStyle();
    mountSummary();
    installObservers();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", apply, { once: true });
  } else {
    apply();
  }

  window.addEventListener("load", () => {
    apply();
    setTimeout(apply, 700);
    setTimeout(apply, 1800);
  });

  window.misticaAdminDashboardPremium = { apply: mountSummary };
})();
