(() => {
  const config = window.misticaSiteConfig || {};
  const API_BASE = (config.apiBaseUrl || "https://api.misticaesotericos.com.br").replace(/\/$/, "");
  const ACCESS_KEY = "misticaAccessStats";
  const VISITOR_KEY = "misticaVisitorId";
  const SESSION_KEY = "misticaAccessSessionCounted";
  const MAX_RECENT = 30;

  function todayKey(date = new Date()) {
    return date.toISOString().slice(0, 10);
  }

  function loadStats() {
    try {
      const parsed = JSON.parse(localStorage.getItem(ACCESS_KEY) || "null");
      if (parsed && typeof parsed === "object") return parsed;
    } catch {}
    return { total: 0, today: {}, recent: [], uniqueVisitors: {} };
  }

  function saveStats(stats) {
    localStorage.setItem(ACCESS_KEY, JSON.stringify(stats));
  }

  function getVisitorId() {
    let visitorId = localStorage.getItem(VISITOR_KEY);
    if (!visitorId) {
      visitorId = `VIS-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 9)}`;
      localStorage.setItem(VISITOR_KEY, visitorId);
    }
    return visitorId;
  }

  function getDeviceType() {
    if (/Mobi|Android|iPhone|iPad|iPod/i.test(navigator.userAgent)) return "Celular";
    return "Desktop";
  }

  function getPageName() {
    const path = window.location.pathname || "/";
    if (path === "/" || path.endsWith("index.html")) return "Página inicial";
    return path.replace(/^\//, "") || "Página inicial";
  }

  function buildAccessEvent() {
    return {
      visitorId: getVisitorId(),
      page: getPageName(),
      url: window.location.href,
      referrer: document.referrer || "Direto",
      device: getDeviceType(),
      userAgent: navigator.userAgent,
      date: new Date().toISOString(),
      day: todayKey()
    };
  }

  function registerLocalAccess(event) {
    if (sessionStorage.getItem(SESSION_KEY) === "true") return loadStats();

    const stats = loadStats();
    stats.total = Number(stats.total || 0) + 1;
    stats.today[event.day] = Number(stats.today?.[event.day] || 0) + 1;
    stats.uniqueVisitors[event.visitorId] = stats.uniqueVisitors[event.visitorId] || event.date;
    stats.recent = [event].concat(Array.isArray(stats.recent) ? stats.recent : []).slice(0, MAX_RECENT);
    stats.lastAccessAt = event.date;

    saveStats(stats);
    sessionStorage.setItem(SESSION_KEY, "true");
    return stats;
  }

  async function sendAccessToApi(event) {
    try {
      const response = await fetch(`${API_BASE}/api/site/acessos`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(event),
        keepalive: true
      });
      return response.ok;
    } catch {
      return false;
    }
  }

  async function fetchApiStats() {
    try {
      const sessao = JSON.parse(sessionStorage.getItem("misticaPainelSessao") || "null");
      const token = sessao?.token || sessao?.accessToken || sessao?.jwt || "";
      const response = await fetch(`${API_BASE}/api/site/acessos/resumo`, {
        headers: token ? { Authorization: `Bearer ${token}` } : {}
      });
      if (!response.ok) throw new Error("Resumo não disponível.");
      return await response.json();
    } catch {
      return null;
    }
  }

  function countUniqueToday(stats) {
    const day = todayKey();
    const recent = Array.isArray(stats.recent) ? stats.recent : [];
    return new Set(recent.filter(item => item.day === day).map(item => item.visitorId)).size;
  }

  function normalizeSummary(apiSummary, localStats) {
    if (apiSummary) {
      return {
        source: "api",
        total: Number(apiSummary.total || apiSummary.totalAcessos || 0),
        today: Number(apiSummary.today || apiSummary.hoje || apiSummary.acessosHoje || 0),
        unique: Number(apiSummary.unique || apiSummary.visitantesUnicos || apiSummary.unicos || 0),
        lastAccessAt: apiSummary.lastAccessAt || apiSummary.ultimoAcesso || null,
        recent: apiSummary.recent || apiSummary.recentes || []
      };
    }

    return {
      source: "local",
      total: Number(localStats.total || 0),
      today: Number(localStats.today?.[todayKey()] || 0),
      unique: Object.keys(localStats.uniqueVisitors || {}).length,
      uniqueToday: countUniqueToday(localStats),
      lastAccessAt: localStats.lastAccessAt || null,
      recent: Array.isArray(localStats.recent) ? localStats.recent : []
    };
  }

  function formatDate(value) {
    if (!value) return "Sem registro";
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return "Sem registro";
    return date.toLocaleString("pt-BR");
  }

  function ensureDashboardCards() {
    const grid = document.querySelector("#adminContent .dashboard-grid");
    if (!grid || document.getElementById("siteAccessTotal")) return;

    const totalCard = document.createElement("article");
    totalCard.className = "metric-card access-metric-card";
    totalCard.innerHTML = `<span>Acessos site</span><strong id="siteAccessTotal">0</strong>`;

    const todayCard = document.createElement("article");
    todayCard.className = "metric-card access-metric-card";
    todayCard.innerHTML = `<span>Acessos hoje</span><strong id="siteAccessToday">0</strong>`;

    grid.append(totalCard, todayCard);
  }

  function ensureAccessPanel() {
    const adminContent = document.getElementById("adminContent");
    if (!adminContent || document.getElementById("siteAccessPanel")) return;

    const panel = document.createElement("div");
    panel.className = "form-panel access-panel";
    panel.id = "siteAccessPanel";
    panel.innerHTML = `
      <p class="eyebrow">Acessos</p>
      <h2>Contador de visitas do site</h2>
      <div class="access-summary-grid">
        <div><span>Total</span><strong id="siteAccessPanelTotal">0</strong></div>
        <div><span>Hoje</span><strong id="siteAccessPanelToday">0</strong></div>
        <div><span>Visitantes</span><strong id="siteAccessUnique">0</strong></div>
        <div><span>Último acesso</span><strong id="siteAccessLast">Sem registro</strong></div>
      </div>
      <div id="siteAccessNotice" class="warning-box"></div>
      <div id="siteAccessRecent" class="history-list"></div>
      <div class="stack-actions">
        <button class="btn btn-ghost btn-full" type="button" data-refresh-access>Atualizar acessos</button>
        <button class="btn btn-ghost btn-full" type="button" data-export-access>Exportar acessos CSV</button>
      </div>
    `;

    const firstGrid = adminContent.querySelector(".checkout-grid.admin-grid");
    if (firstGrid) {
      adminContent.insertBefore(panel, firstGrid);
    } else {
      adminContent.appendChild(panel);
    }

    panel.querySelector("[data-refresh-access]")?.addEventListener("click", renderAccessDashboard);
    panel.querySelector("[data-export-access]")?.addEventListener("click", exportAccessCsv);
  }

  function injectStyles() {
    if (document.getElementById("siteAccessStyles")) return;
    const style = document.createElement("style");
    style.id = "siteAccessStyles";
    style.textContent = `
      .access-summary-grid {
        display: grid;
        grid-template-columns: repeat(4, minmax(0, 1fr));
        gap: 12px;
        margin-bottom: 16px;
      }

      .access-summary-grid div {
        border: 1px solid rgba(240,197,106,.20);
        border-radius: 20px;
        padding: 16px;
        background: rgba(255,248,230,.055);
      }

      .access-summary-grid span,
      .access-metric-card span {
        display: block;
        color: #b8c977;
        font-size: .76rem;
        font-weight: 900;
        letter-spacing: .12em;
        text-transform: uppercase;
      }

      .access-summary-grid strong {
        display: block;
        margin-top: 6px;
        color: #fff6dc;
        font-size: clamp(1.15rem, 2vw, 1.7rem);
      }

      .access-panel .warning-box {
        margin-bottom: 16px;
      }

      @media (max-width: 980px) {
        .access-summary-grid {
          grid-template-columns: repeat(2, minmax(0, 1fr));
        }
      }

      @media (max-width: 620px) {
        .access-summary-grid {
          grid-template-columns: 1fr;
        }
      }
    `;
    document.head.appendChild(style);
  }

  function setText(id, value) {
    const element = document.getElementById(id);
    if (element) element.textContent = value;
  }

  async function renderAccessDashboard() {
    injectStyles();
    ensureDashboardCards();
    ensureAccessPanel();

    const localStats = loadStats();
    const summary = normalizeSummary(await fetchApiStats(), localStats);

    setText("siteAccessTotal", String(summary.total));
    setText("siteAccessToday", String(summary.today));
    setText("siteAccessPanelTotal", String(summary.total));
    setText("siteAccessPanelToday", String(summary.today));
    setText("siteAccessUnique", String(summary.source === "local" ? `${summary.unique} total / ${summary.uniqueToday || 0} hoje` : summary.unique));
    setText("siteAccessLast", formatDate(summary.lastAccessAt));

    const notice = document.getElementById("siteAccessNotice");
    if (notice) {
      notice.innerHTML = summary.source === "api"
        ? "<strong>Dados reais do servidor:</strong> contador carregado pela API do Mística Painel."
        : "<strong>Modo local:</strong> este contador registra acessos salvos neste navegador. Para contar todos os clientes reais, o servidor precisa aceitar os endpoints /api/site/acessos e /api/site/acessos/resumo.";
    }

    const recent = document.getElementById("siteAccessRecent");
    const recentItems = Array.isArray(summary.recent) ? summary.recent.slice(0, 10) : [];
    if (recent) {
      recent.innerHTML = recentItems.length
        ? recentItems.map(item => `<div class="history-item"><strong>${formatDate(item.date || item.createdAt || item.data)}</strong><span>${item.page || "Página"} • ${item.device || "Dispositivo"}</span><span>Origem: ${item.referrer || item.origem || "Direto"}</span></div>`).join("")
        : `<div class="history-item"><span>Nenhum acesso recente registrado ainda.</span></div>`;
    }
  }

  function exportAccessCsv() {
    const stats = loadStats();
    const recent = Array.isArray(stats.recent) ? stats.recent : [];
    if (!recent.length) return alert("Nenhum acesso local para exportar ainda.");
    const rows = [["Data", "Pagina", "Dispositivo", "Origem", "Visitante"]].concat(
      recent.map(item => [item.date, item.page, item.device, item.referrer, item.visitorId])
    );
    const csv = rows.map(row => row.map(value => `"${String(value ?? "").replace(/"/g, '""')}"`).join(";")).join("\n");
    const blob = new Blob(["\ufeff" + csv], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `mistica-acessos-${todayKey()}.csv`;
    link.click();
    URL.revokeObjectURL(url);
  }

  function init() {
    const accessEvent = buildAccessEvent();
    registerLocalAccess(accessEvent);
    sendAccessToApi(accessEvent);
    injectStyles();

    window.addEventListener("load", () => {
      renderAccessDashboard();
      setTimeout(renderAccessDashboard, 700);
      setTimeout(renderAccessDashboard, 1800);
    });
  }

  window.misticaAccessCounter = {
    render: renderAccessDashboard,
    stats: loadStats,
    exportCsv: exportAccessCsv
  };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
