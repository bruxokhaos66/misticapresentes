(() => {
  const cfg = window.misticaSiteConfig || {};
  const API_BASE = (cfg.apiBaseUrl || "https://api.misticaesotericos.com.br").replace(/\/$/, "");
  const SITE_API_KEY = String(cfg.siteApiKey || "").trim();
  let atividadeRows = [];
  let termoBusca = "";
  let painelMontado = false;

  function headers() {
    return {
      "Content-Type": "application/json",
      ...(SITE_API_KEY ? { "X-Mistica-Api-Key": SITE_API_KEY } : {}),
    };
  }

  async function api(path) {
    const response = await fetch(`${API_BASE}${path}`, { headers: headers(), cache: "no-store" });
    if (!response.ok) throw new Error(`API ${response.status}`);
    return response.json();
  }

  function limpar(value) {
    return String(value || "").normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase();
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

  function normalizarTelefone(value) {
    const numero = String(value || "554999172137").replace(/\D/g, "");
    return numero || "554999172137";
  }

  function datePt(value) {
    if (!value) return "-";
    const data = new Date(value);
    return Number.isNaN(data.getTime()) ? String(value) : data.toLocaleString("pt-BR");
  }

  function mensagemPedido(item) {
    const pedido = item?.venda_id ? `pedido ${item.venda_id}` : "pedido";
    const status = item?.status || "Atualização";
    return `Olá! Aqui é da Mística Presentes. Estamos entrando em contato sobre o ${pedido}. Status atual: ${status}.`;
  }

  function textoBusca(item) {
    return limpar(`${item.venda_id || ""} ${item.status || ""} ${item.cliente || ""} ${item.observacao || ""} ${item.usuario || ""}`);
  }

  function filtrarRows() {
    const termo = limpar(termoBusca);
    if (!termo) return atividadeRows;
    return atividadeRows.filter(item => textoBusca(item).includes(termo));
  }

  function itemAtividade(item) {
    const status = escapeHtml(item.status || "Atualização");
    const pedido = escapeHtml(item.venda_id || "-");
    const cliente = item.cliente ? ` • ${escapeHtml(item.cliente)}` : "";
    const obs = item.observacao ? `<small>${escapeHtml(item.observacao)}</small>` : "";
    const numero = normalizarTelefone(window.misticaSiteConfig?.whatsappNumber);
    const link = `https://wa.me/${numero}?text=${encodeURIComponent(mensagemPedido(item))}`;
    return `
      <article class="admin-activity-row">
        <div>
          <strong>${status}</strong>
          <span>Pedido ${pedido}${cliente}</span>
          ${obs}
        </div>
        <div class="admin-activity-actions">
          <time>${escapeHtml(datePt(item.data_hora))}</time>
          <a class="btn btn-ghost" href="${link}" target="_blank" rel="noopener noreferrer">WhatsApp</a>
        </div>
      </article>
    `;
  }

  function renderizarAtividade() {
    const root = document.getElementById("adminActivityContent");
    if (!root) return;
    const rows = filtrarRows();
    root.innerHTML = rows.length
      ? rows.map(itemAtividade).join("")
      : `<p class="privacy-note">Nenhuma atividade encontrada para este filtro.</p>`;
  }

  async function carregarAtividade() {
    const root = document.getElementById("adminActivityContent");
    if (!root) return;
    root.innerHTML = `<p class="privacy-note">Carregando atividade recente...</p>`;
    try {
      const lista = await api("/api/pedidos/status-log?limite=30");
      atividadeRows = Array.isArray(lista) ? lista : [];
      renderizarAtividade();
    } catch (error) {
      root.innerHTML = `<p class="privacy-note">Não foi possível carregar atividade: ${escapeHtml(error.message || "erro desconhecido")}</p>`;
    }
  }

  function montarPainel() {
    const admin = document.getElementById("adminContent");
    if (!admin || document.getElementById("adminActivityPanel")) return false;
    const panel = document.createElement("section");
    panel.id = "adminActivityPanel";
    panel.className = "form-panel admin-activity-panel";
    panel.innerHTML = `
      <p class="eyebrow">Atividade</p>
      <h2>Últimas ações do Admin</h2>
      <p class="privacy-note">Histórico recente de mudanças em pedidos, Pix, status e estoque.</p>
      <div class="admin-activity-tools">
        <input type="search" placeholder="Buscar por pedido, cliente, status ou observação" data-admin-activity-search>
        <button class="btn btn-ghost" type="button" data-reload-admin-activity>Atualizar atividade</button>
      </div>
      <div id="adminActivityContent" class="admin-activity-content"></div>
    `;
    const alerts = document.getElementById("adminAlertsPanel");
    const report = document.getElementById("adminReportPanel");
    admin.insertBefore(panel, alerts?.nextSibling || report || admin.firstChild);
    carregarAtividade();
    painelMontado = true;
    return true;
  }

  document.addEventListener("input", event => {
    if (event.target?.dataset?.adminActivitySearch === undefined) return;
    termoBusca = event.target.value;
    renderizarAtividade();
  });

  document.addEventListener("click", event => {
    if (event.target?.dataset?.reloadAdminActivity !== undefined) carregarAtividade();
  });

  window.misticaAdminActivity = { reload: carregarAtividade, search: value => { termoBusca = value || ""; renderizarAtividade(); } };

  window.addEventListener("load", () => {
    if (!montarPainel()) {
      const montagem = setInterval(() => {
        if (painelMontado || montarPainel()) clearInterval(montagem);
      }, 1500);
    }
    setInterval(carregarAtividade, 45000);
  });
})();
