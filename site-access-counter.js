(() => {
  const cfg = window.misticaSiteConfig || {};
  const API_BASE = (cfg.apiBaseUrl || "https://api.misticaesotericos.com.br").replace(/\/$/, "");
  const SITE_API_KEY = String(cfg.siteApiKey || "").trim();
  const STORAGE_KEY = "misticaSiteAccessStats";
  const SESSION_KEY = "misticaSiteAccessRegistered";
  const params = new URLSearchParams(window.location.search);
  const adminAccess = params.get("admin") === "mistica" || window.location.hash === "#admin-mistica";

  function headers() {
    return {
      "Content-Type": "application/json",
      ...(SITE_API_KEY ? { "X-Mistica-Api-Key": SITE_API_KEY } : {}),
    };
  }

  function todayKey() {
    return new Date().toISOString().slice(0, 10);
  }

  function loadLocal() {
    try {
      return JSON.parse(localStorage.getItem(STORAGE_KEY)) || { total: 0, days: {}, visits: [] };
    } catch {
      return { total: 0, days: {}, visits: [] };
    }
  }

  function saveLocal(data) {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(data));
  }

  function registerLocalVisit() {
    if (sessionStorage.getItem(SESSION_KEY) === "true") return loadLocal();

    const data = loadLocal();
    const day = todayKey();
    const visit = {
      at: new Date().toISOString(),
      path: window.location.pathname + window.location.hash,
      referrer: document.referrer || "direto",
      userAgent: navigator.userAgent,
    };

    data.total = Number(data.total || 0) + 1;
    data.days = data.days || {};
    data.days[day] = Number(data.days[day] || 0) + 1;
    data.visits = [visit, ...(data.visits || [])].slice(0, 80);

    saveLocal(data);
    sessionStorage.setItem(SESSION_KEY, "true");
    return data;
  }

  async function registerRemoteVisit() {
    try {
      await fetch(`${API_BASE}/api/site/acessos`, {
        method: "POST",
        headers: headers(),
        cache: "no-store",
        body: JSON.stringify({
          path: window.location.pathname + window.location.hash,
          referrer: document.referrer || "direto",
          userAgent: navigator.userAgent,
          origem: "site",
        }),
      });
    } catch {
      // Fallback local já mantém contagem mínima enquanto o backend real não existe.
    }
  }

  async function fetchRemoteSummary() {
    const response = await fetch(`${API_BASE}/api/site/acessos/resumo`, { headers: headers(), cache: "no-store" });
    if (!response.ok) throw new Error(`API ${response.status}`);
    return response.json();
  }

  function toSummary(localData) {
    const day = todayKey();
    const visits = Array.isArray(localData.visits) ? localData.visits : [];
    const uniqueVisitors = new Set(visits.map(item => item.userAgent || "visitante")).size;
    return {
      mode: "local",
      total: Number(localData.total || 0),
      today: Number(localData.days?.[day] || 0),
      uniqueVisitors,
      lastAccess: visits[0]?.at || null,
      visits,
    };
  }

  function datePt(value) {
    if (!value) return "-";
    const data = new Date(value);
    return Number.isNaN(data.getTime()) ? String(value) : data.toLocaleString("pt-BR");
  }

  function escapeHtml(value) {
    return String(value ?? "").replace(/[&<>'"]/g, char => ({
      "&": "&amp;",
      "<": "&lt;",
      ">": "&gt;",
      "'": "&#39;",
      '"': "&quot;",
    }[char]));
  }

  function ensureDashboardCards(summary) {
    const dashboard = document.querySelector("#adminContent .dashboard-grid");
    if (!dashboard) return;

    if (!document.getElementById("siteAccessTotal")) {
      const total = document.createElement("article");
      total.className = "metric-card";
      total.innerHTML = `<span>Acessos site</span><strong id="siteAccessTotal">0</strong>`;
      dashboard.appendChild(total);
    }

    if (!document.getElementById("siteAccessToday")) {
      const today = document.createElement("article");
      today.className = "metric-card";
      today.innerHTML = `<span>Acessos hoje</span><strong id="siteAccessToday">0</strong>`;
      dashboard.appendChild(today);
    }

    document.getElementById("siteAccessTotal").textContent = String(summary.total || 0);
    document.getElementById("siteAccessToday").textContent = String(summary.today || 0);
  }

  function renderPanel(summary) {
    let panel = document.getElementById("siteAccessPanel");
    const admin = document.getElementById("adminContent");
    if (!admin) return;

    if (!panel) {
      panel = document.createElement("section");
      panel.id = "siteAccessPanel";
      panel.className = "form-panel site-access-panel";
      admin.appendChild(panel);
    }

    const visits = Array.isArray(summary.visits) ? summary.visits.slice(0, 12) : [];
    const modeText = summary.mode === "remote" ? "dados da API" : "modo local neste navegador";

    panel.innerHTML = `
      <p class="eyebrow">Acessos</p>
      <h2>Contador de acessos do site</h2>
      <p class="privacy-note">Resumo em ${escapeHtml(modeText)}. Para contagem real de todos os clientes, use os endpoints do backend salvos na auditoria.</p>
      <div class="dashboard-grid compact-dashboard">
        <article class="metric-card"><span>Total</span><strong>${escapeHtml(summary.total || 0)}</strong></article>
        <article class="metric-card"><span>Hoje</span><strong>${escapeHtml(summary.today || 0)}</strong></article>
        <article class="metric-card"><span>Únicos</span><strong>${escapeHtml(summary.uniqueVisitors || 0)}</strong></article>
        <article class="metric-card"><span>Último</span><strong>${escapeHtml(datePt(summary.lastAccess))}</strong></article>
      </div>
      <div class="stack-actions">
        <button class="btn btn-ghost" type="button" data-refresh-site-access>Atualizar acessos</button>
        <button class="btn btn-ghost" type="button" data-export-site-access>Exportar CSV local</button>
      </div>
      <div class="history-list">
        ${visits.length ? visits.map(visit => `
          <div class="history-item">
            <strong>${escapeHtml(datePt(visit.at))}</strong>
            <span>${escapeHtml(visit.path || "/")}</span>
            <small>${escapeHtml(visit.referrer || "direto")}</small>
          </div>
        `).join("") : `<div class="history-item">Nenhum acesso local registrado ainda.</div>`}
      </div>
    `;
  }

  async function loadSummary() {
    const local = loadLocal();
    let summary = toSummary(local);

    try {
      const remote = await fetchRemoteSummary();
      summary = {
        mode: "remote",
        total: remote.total ?? remote.acessos_total ?? summary.total,
        today: remote.today ?? remote.acessos_hoje ?? summary.today,
        uniqueVisitors: remote.uniqueVisitors ?? remote.visitantes_unicos ?? summary.uniqueVisitors,
        lastAccess: remote.lastAccess ?? remote.ultimo_acesso ?? summary.lastAccess,
        visits: remote.visits ?? remote.acessos_recentes ?? summary.visits,
      };
    } catch {
      summary = toSummary(loadLocal());
    }

    ensureDashboardCards(summary);
    renderPanel(summary);
    return summary;
  }

  function exportCsv() {
    const data = loadLocal();
    const visits = Array.isArray(data.visits) ? data.visits : [];
    const rows = [["data", "pagina", "origem", "navegador"], ...visits.map(item => [item.at, item.path, item.referrer, item.userAgent])];
    const csv = rows.map(row => row.map(cell => `"${String(cell || "").replace(/"/g, '""')}"`).join(",")).join("\n");
    const blob = new Blob([csv], { type: "text/csv;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `mistica-acessos-${todayKey()}.csv`;
    link.click();
    URL.revokeObjectURL(url);
  }

  document.addEventListener("click", event => {
    if (event.target?.dataset?.refreshSiteAccess !== undefined) loadSummary();
    if (event.target?.dataset?.exportSiteAccess !== undefined) exportCsv();
  });

  window.misticaSiteAccessCounter = { loadSummary, exportCsv, local: loadLocal };

  registerLocalVisit();
  registerRemoteVisit();

  window.addEventListener("load", () => {
    if (!adminAccess) return;
    setTimeout(loadSummary, 1200);
    setTimeout(loadSummary, 3200);
  });
})();
