(() => {
  const cfg = window.misticaSiteConfig || {};
  const API_BASE = (cfg.apiBaseUrl || "https://api.misticaesotericos.com.br").replace(/\/$/, "");
  const SITE_API_KEY = String(cfg.siteApiKey || "").trim();

  function headers() {
    return {
      "Content-Type": "application/json",
      ...(SITE_API_KEY ? { "X-Mistica-Api-Key": SITE_API_KEY } : {}),
    };
  }

  async function api(path) {
    const response = await fetch(`${API_BASE}${path}`, { headers: headers() });
    if (!response.ok) throw new Error(`API ${response.status}`);
    return response.json();
  }

  function datePt(value) {
    try { return new Date(value).toLocaleString("pt-BR"); } catch { return String(value || ""); }
  }

  function itemAtividade(item) {
    const status = item.status || "Atualização";
    const cliente = item.cliente ? ` • ${item.cliente}` : "";
    const obs = item.observacao ? `<small>${item.observacao}</small>` : "";
    return `
      <article class="admin-activity-row">
        <div>
          <strong>${status}</strong>
          <span>Pedido ${item.venda_id || ""}${cliente}</span>
          ${obs}
        </div>
        <time>${datePt(item.data_hora)}</time>
      </article>
    `;
  }

  async function carregarAtividade() {
    const root = document.getElementById("adminActivityContent");
    if (!root) return;
    root.innerHTML = `<p class="privacy-note">Carregando atividade recente...</p>`;
    try {
      const lista = await api("/api/pedidos/status-log?limite=12");
      const rows = Array.isArray(lista) ? lista : [];
      root.innerHTML = rows.length
        ? rows.map(itemAtividade).join("")
        : `<p class="privacy-note">Nenhuma atividade recente encontrada.</p>`;
    } catch (error) {
      root.innerHTML = `<p class="privacy-note">Não foi possível carregar atividade: ${error.message}</p>`;
    }
  }

  function montarPainel() {
    const admin = document.getElementById("adminContent");
    if (!admin || document.getElementById("adminActivityPanel")) return;
    const panel = document.createElement("section");
    panel.id = "adminActivityPanel";
    panel.className = "form-panel admin-activity-panel";
    panel.innerHTML = `
      <p class="eyebrow">Atividade</p>
      <h2>Últimas ações do Admin</h2>
      <p class="privacy-note">Histórico recente de mudanças em pedidos, Pix, status e estoque.</p>
      <button class="btn btn-ghost" type="button" data-reload-admin-activity>Atualizar atividade</button>
      <div id="adminActivityContent" class="admin-activity-content"></div>
    `;
    const alerts = document.getElementById("adminAlertsPanel");
    const report = document.getElementById("adminReportPanel");
    admin.insertBefore(panel, alerts?.nextSibling || report || admin.firstChild);
    carregarAtividade();
  }

  document.addEventListener("click", event => {
    if (event.target?.dataset?.reloadAdminActivity !== undefined) carregarAtividade();
  });

  window.misticaAdminActivity = { reload: carregarAtividade };

  window.addEventListener("load", () => {
    montarPainel();
    setInterval(montarPainel, 1500);
    setInterval(carregarAtividade, 45000);
  });
})();
