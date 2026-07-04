(() => {
  const cfg = window.misticaSiteConfig || {};
  const API_BASE = (cfg.apiBaseUrl || "https://api.misticaesotericos.com.br").replace(/\/$/, "");
  const SITE_API_KEY = String(cfg.siteApiKey || "").trim();
  let ultimoRelatorio = { pedidos: [], estoqueBaixo: [], maisVendidos: [] };

  function money(value) {
    try { return currency.format(Number(value || 0)); } catch { return `R$ ${Number(value || 0).toFixed(2)}`; }
  }

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

  function origemDoPedido(pedido) {
    const origem = String(pedido.origem || pedido.origem_sync || "api").toLowerCase();
    const vendedor = String(pedido.vendedor || "").toLowerCase();
    const cliente = String(pedido.cliente || "").toLowerCase();
    if (origem.includes("isis") || vendedor.includes("isis") || cliente.includes("isis")) return "Isis";
    if (origem.includes("site") || origem.includes("api") || vendedor.includes("site")) return "Site/API";
    return "Manual";
  }

  function calcularMaisVendidos(pedidos) {
    const mapa = new Map();
    pedidos.forEach(pedido => {
      if (String(pedido.status || "").toLowerCase().includes("cancel")) return;
      (pedido.itens || []).forEach(item => {
        const nome = item.nome_p || item.nome || "Item";
        const atual = mapa.get(nome) || { nome, quantidade: 0, total: 0 };
        atual.quantidade += Number(item.quantidade || 1);
        atual.total += Number(item.valor_total || item.valor_unitario || 0) * Number(item.quantidade || 1);
        mapa.set(nome, atual);
      });
    });
    return [...mapa.values()].sort((a, b) => b.quantidade - a.quantidade).slice(0, 20);
  }

  function resumoPedidos(pedidos) {
    return {
      total: pedidos.length,
      pendentes: pedidos.filter(p => p.status === "Aguardando pagamento").length,
      pagos: pedidos.filter(p => p.status === "Pagamento confirmado").length,
      separados: pedidos.filter(p => p.status === "Separando pedido" || p.status === "Pronto para retirada").length,
      estoqueBaixado: pedidos.filter(p => Number(p.estoque_baixado || 0) === 1).length,
      isis: pedidos.filter(p => origemDoPedido(p) === "Isis").length,
      faturamento: pedidos
        .filter(p => !String(p.status || "").toLowerCase().includes("cancel"))
        .reduce((sum, p) => sum + Number(p.total_final || 0), 0),
    };
  }

  function csvEscape(value) {
    const text = String(value ?? "").replace(/"/g, '""');
    return `"${text}"`;
  }

  function baixarCsv(nome, linhas) {
    const csv = linhas.map(row => row.map(csvEscape).join(";")).join("\n");
    const blob = new Blob(["\ufeff" + csv], { type: "text/csv;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = nome;
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
  }

  function exportarPedidos() {
    const linhas = [["id", "data", "cliente", "origem", "status", "total", "forma_pagamento", "estoque_baixado"]];
    ultimoRelatorio.pedidos.forEach(p => {
      linhas.push([p.id, p.data_venda || p.data_iso || "", p.cliente || "", origemDoPedido(p), p.status || "", Number(p.total_final || 0), p.forma_pagamento || "", Number(p.estoque_baixado || 0) === 1 ? "sim" : "nao"]);
    });
    baixarCsv("mistica-pedidos.csv", linhas);
  }

  function exportarEstoqueBaixo() {
    const linhas = [["id", "codigo", "nome", "categoria", "quantidade", "estoque_minimo"]];
    ultimoRelatorio.estoqueBaixo.forEach(p => {
      linhas.push([p.id, p.codigo_p || "", p.nome || "", p.categoria || "", Number(p.quantidade || 0), Number(p.estoque_minimo || 0)]);
    });
    baixarCsv("mistica-estoque-baixo.csv", linhas);
  }

  function exportarMaisVendidos() {
    const linhas = [["produto", "quantidade", "total"]];
    ultimoRelatorio.maisVendidos.forEach(p => {
      linhas.push([p.nome, p.quantidade, Number(p.total || 0)]);
    });
    baixarCsv("mistica-mais-vendidos.csv", linhas);
  }

  function card(label, value, hint = "") {
    return `<article class="report-card"><span>${label}</span><strong>${value}</strong>${hint ? `<small>${hint}</small>` : ""}</article>`;
  }

  function tabelaEstoqueBaixo(lista) {
    if (!lista.length) return `<p class="privacy-note">Nenhum item crítico de estoque baixo encontrado.</p>`;
    return `
      <div class="report-list">
        ${lista.slice(0, 8).map(item => `
          <div class="report-row">
            <strong>${item.nome}</strong>
            <span>Qtd: ${Number(item.quantidade || 0)} • mínimo: ${Number(item.estoque_minimo || 0)}</span>
          </div>
        `).join("")}
      </div>
    `;
  }

  function tabelaMaisVendidos(lista) {
    if (!lista.length) return `<p class="privacy-note">Ainda não há itens vendidos suficientes para ranking.</p>`;
    return `
      <div class="report-list">
        ${lista.slice(0, 8).map(item => `
          <div class="report-row">
            <strong>${item.nome}</strong>
            <span>${item.quantidade} un. • ${money(item.total)}</span>
          </div>
        `).join("")}
      </div>
    `;
  }

  async function carregarRelatorio() {
    const root = document.getElementById("adminReportContent");
    if (!root) return;
    root.innerHTML = `<p class="privacy-note">Carregando relatório...</p>`;
    try {
      const [pedidos, estoqueBaixo] = await Promise.all([
        api("/api/pedidos?limite=300"),
        api("/api/estoque/baixo?limite=50"),
      ]);
      const pedidosList = Array.isArray(pedidos) ? pedidos : [];
      const estoqueList = Array.isArray(estoqueBaixo) ? estoqueBaixo : [];
      const resumo = resumoPedidos(pedidosList);
      const maisVendidos = calcularMaisVendidos(pedidosList);
      ultimoRelatorio = { pedidos: pedidosList, estoqueBaixo: estoqueList, maisVendidos };
      root.innerHTML = `
        <div class="report-export-actions">
          <button class="btn btn-ghost" type="button" data-export-report="pedidos">Exportar pedidos CSV</button>
          <button class="btn btn-ghost" type="button" data-export-report="estoque">Exportar estoque baixo CSV</button>
          <button class="btn btn-ghost" type="button" data-export-report="vendidos">Exportar mais vendidos CSV</button>
        </div>
        <div class="report-grid">
          ${card("Pedidos", resumo.total)}
          ${card("Pendentes", resumo.pendentes, "Aguardando pagamento")}
          ${card("Pagos", resumo.pagos, "Pagamento confirmado")}
          ${card("Separação", resumo.separados, "Separando/pronto")}
          ${card("Estoque baixado", resumo.estoqueBaixado)}
          ${card("Pedidos Isis", resumo.isis)}
          ${card("Faturamento", money(resumo.faturamento), "sem cancelados")}
          ${card("Estoque baixo", estoqueList.length)}
        </div>
        <div class="report-columns">
          <section>
            <h3>Produtos mais vendidos</h3>
            ${tabelaMaisVendidos(maisVendidos)}
          </section>
          <section>
            <h3>Estoque baixo</h3>
            ${tabelaEstoqueBaixo(estoqueList)}
          </section>
        </div>
      `;
    } catch (error) {
      root.innerHTML = `<p class="privacy-note">Não foi possível carregar o relatório agora: ${error.message}</p>`;
    }
  }

  function montarPainel() {
    const admin = document.getElementById("adminContent");
    if (!admin || document.getElementById("adminReportPanel")) return;
    const panel = document.createElement("section");
    panel.id = "adminReportPanel";
    panel.className = "form-panel admin-report-panel";
    panel.innerHTML = `
      <p class="eyebrow">Relatórios</p>
      <h2>Resumo de pedidos e estoque</h2>
      <p class="privacy-note">Acompanhe pedidos, origem Isis, estoque baixado, faturamento e itens com estoque baixo.</p>
      <button class="btn btn-ghost" type="button" data-reload-admin-report>Atualizar relatório</button>
      <div id="adminReportContent" class="admin-report-content"></div>
    `;
    const pedidos = document.getElementById("pedidosAdminPanel");
    admin.insertBefore(panel, pedidos?.nextSibling || admin.firstChild);
    carregarRelatorio();
  }

  document.addEventListener("click", event => {
    if (event.target?.dataset?.reloadAdminReport !== undefined) carregarRelatorio();
    const tipo = event.target?.dataset?.exportReport;
    if (tipo === "pedidos") exportarPedidos();
    if (tipo === "estoque") exportarEstoqueBaixo();
    if (tipo === "vendidos") exportarMaisVendidos();
  });

  window.misticaAdminReport = { reload: carregarRelatorio, exportarPedidos, exportarEstoqueBaixo, exportarMaisVendidos };

  window.addEventListener("load", () => {
    montarPainel();
    setInterval(montarPainel, 1500);
  });
})();
