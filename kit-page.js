(() => {
  function normalize(value) {
    return String(value || "").normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase();
  }

  function availableQty(product) {
    try { return typeof getStock === "function" ? getStock(product.id) : Number(product.stock || 0); } catch { return Number(product.stock || 0); }
  }

  function intentFromQuery() {
    const id = new URLSearchParams(window.location.search).get("intencao") || "";
    return (window.misticaIntents || []).find(intent => intent.id === id) || null;
  }

  function matchingProducts(intent) {
    if (typeof products === "undefined" || !Array.isArray(products)) return [];
    const terms = intent.terms.map(normalize);
    return products
      .filter(product => availableQty(product) > 0)
      .map(product => {
        const text = normalize(`${product.name} ${product.description} ${product.category}`);
        const score = terms.filter(term => text.includes(term)).length;
        return { product, score };
      })
      .filter(row => row.score > 0)
      .sort((a, b) => b.score - a.score)
      .map(row => row.product);
  }

  function chipsHtml(currentId) {
    return (window.misticaIntents || [])
      .map(intent => `<a class="v2-chip${intent.id === currentId ? " active" : ""}" href="kit.html?intencao=${encodeURIComponent(intent.id)}">${intent.label}</a>`)
      .join("");
  }

  function renderNotFound() {
    const root = document.getElementById("kitRoot");
    if (!root) return;
    root.innerHTML = `
      <div class="container section-title centered">
        <p class="eyebrow">Kits por intenção</p>
        <h2>Escolha uma intenção para ver a vitrine</h2>
        <p>Selecione uma opção abaixo para ver os produtos selecionados para esse momento.</p>
      </div>
      <div class="container isis-followup-chips">${chipsHtml("")}</div>
    `;
  }

  function render() {
    const root = document.getElementById("kitRoot");
    if (!root) return;
    const intent = intentFromQuery();
    if (!intent) return renderNotFound();

    document.title = `Kit para ${intent.label} | Mística Presentes`;
    const found = matchingProducts(intent);
    const grid = found.length
      ? `<div class="container product-grid">${found.map(productCardHtml).join("")}</div>`
      : `<div class="container"><p class="privacy-note">Ainda não há produtos disponíveis para esta intenção agora. Fale pelo WhatsApp que a gente ajuda a encontrar a opção certa.</p></div>`;

    root.innerHTML = `
      <div class="container section-title centered">
        <p class="eyebrow">Kits por intenção</p>
        <h2>Kit para ${intent.label}</h2>
        <p>Produtos selecionados especialmente para ${intent.label.toLowerCase()}. Adicione ao carrinho e finalize pelo WhatsApp ou Pix.</p>
      </div>
      <div class="container isis-followup-chips">${chipsHtml(intent.id)}</div>
      ${grid}
    `;
  }

  // O 1º render() já usa o catálogo estático de fallback (app.js), então a
  // vitrine por intenção nunca fica em branco na primeira pintura. Reagir a
  // "mistica:catalog-state" (disparado por mobile-sync.js) em vez de
  // re-renderizar em atrasos fixos evita repetir aqui o mesmo bug já
  // corrigido na vitrine principal: um re-render em horário fixo podia cair
  // bem no meio de uma falha transitória de sincronização — quando o
  // catálogo real ainda não foi confirmado e products[] está temporariamente
  // vazio — travando a página nessa foto vazia mesmo depois do catálogo
  // real chegar. Só re-renderiza quando o catálogo oficial é de fato
  // confirmado ("ready").
  function schedule() {
    render();
    window.addEventListener("mistica:catalog-state", event => {
      if (event.detail?.state === "ready") render();
    });
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", schedule, { once: true });
  else schedule();
})();
