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

  function origemIsis(pedido) {
    const origem = String(pedido.origem || pedido.origem_sync || "").toLowerCase();
    const vendedor = String(pedido.vendedor || "").toLowerCase();
    const cliente = String(pedido.cliente || "").toLowerCase();
    return origem.includes("isis") || vendedor.includes("isis") || cliente.includes("isis");
  }

  function alerta(tipo, titulo, texto) {
    return `<article class="admin-alert-card admin-alert-${tipo}"><strong>${titulo}</strong><span>${texto}</span></article>`;
  }

  async function carregarAlertas() {
    const root = document.getElementById("adminAlertsContent");
    if (!root) return;
    try {
      const [pedidos, estoqueBaixo] = await Promise.all([
        api("/api/pedidos?limite=200"),
        api("/api/estoque/baixo?limite=50"),
      ]);
      const listaPedidos = Array.isArray(pedidos) ? pedidos : [];
      const listaEstoque = Array.isArray(estoqueBaixo) ? estoqueBaixo : [];
      const pendentes = listaPedidos.filter(p => p.status === "Aguardando pagamento");
      const isisPendentes = pendentes.filter(origemIsis);
      const semBaixa = listaPedidos.filter(p => ["Pagamento confirmado", "Separando pedido"].includes(p.status) && Number(p.estoque_baixado || 0) !== 1);

      const cards = [];
      if (pendentes.length) cards.push(alerta("warn", "Pedidos pendentes", `${pendentes.length} pedido(s) aguardando pagamento.`));
      if (isisPendentes.length) cards.push(alerta("isis", "Isis aguardando", `${isisPendentes.length} pedido(s) da Isis precisam de confirmação.`));
      if (semBaixa.length) cards.push(alerta("danger", "Estoque pendente", `${semBaixa.length} pedido(s) pagos/separados ainda sem baixa de estoque.`));
      if (listaEstoque.length) cards.push(alerta("stock", "Estoque baixo", `${listaEstoque.length} item(ns) abaixo ou no mínimo definido.`));
      if (!cards.length) cards.push(alerta("ok", "Tudo em ordem", "Nenhum alerta importante no momento."));

      root.innerHTML = cards.join("");
    } catch (error) {
      root.innerHTML = alerta("danger", "Falha nos alertas", `Não foi possível carregar: ${error.message}`);
    }
  }

  function montarPainel() {
    const admin = document.getElementById("adminContent");
    if (!admin || document.getElementById("adminAlertsPanel")) return;
    const panel = document.createElement("section");
    panel.id = "adminAlertsPanel";
    panel.className = "form-panel admin-alerts-panel";
    panel.innerHTML = `
      <p class="eyebrow">Alertas</p>
      <h2>Atenção rápida da loja</h2>
      <p class="privacy-note">Avisos automáticos sobre pedidos, Isis e estoque.</p>
      <div id="adminAlertsContent" class="admin-alerts-content"></div>
    `;
    const report = document.getElementById("adminReportPanel");
    const pedidos = document.getElementById("pedidosAdminPanel");
    admin.insertBefore(panel, report || pedidos || admin.firstChild);
    carregarAlertas();
  }

  window.misticaAdminAlerts = { reload: carregarAlertas };

  window.addEventListener("load", () => {
    montarPainel();
    setInterval(montarPainel, 1500);
    setInterval(carregarAlertas, 30000);
  });
})();
