/*
 * Renderiza dinamicamente os produtos da categoria "Achados Místicos" (sob
 * encomenda) na página /achados-misticos/. Reaproveita a mesma API pública do
 * catálogo (GET /api/produtos) e a regra central de mistica-encomenda.js.
 *
 * Estados tratados: carregando, vazio e erro (com botão de tentar de novo).
 * Cada card leva à página de detalhes já existente (produto.html), onde o
 * fluxo de carrinho/checkout funciona normalmente.
 */
(() => {
  "use strict";

  const cfg = window.misticaSiteConfig || {};
  const API_BASE = String(cfg.apiBaseUrl || "https://api.misticaesotericos.com.br").replace(/\/$/, "");
  const money = new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" });
  const enc = window.misticaEncomenda || null;

  const grid = document.querySelector("[data-achados-grid]");
  const stateEl = document.querySelector("[data-achados-state]");
  if (!grid || !stateEl) return;

  const esc = (value) => String(value == null ? "" : value).replace(/[&<>"']/g, (ch) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[ch]));

  function fullUrl(path) {
    const value = String(path || "").trim();
    if (!value) return "";
    if (value.startsWith("http://") || value.startsWith("https://")) return value;
    return `${API_BASE}${value.startsWith("/") ? "" : "/"}${value}`;
  }

  function isSob(item) {
    if (enc) return enc.isSobEncomenda(item);
    const cat = String(item.categoria || "").normalize("NFD").replace(/[̀-ͯ]/g, "").trim().toLowerCase();
    const selo = String(item.selo || "").normalize("NFD").replace(/[̀-ͯ]/g, "").trim().toLowerCase();
    return cat === "achados misticos" || selo === "sob encomenda";
  }

  function setState(html) {
    stateEl.innerHTML = html || "";
    stateEl.hidden = !html;
  }

  function cardHtml(item) {
    const id = `api-${item.id}`;
    const href = `/produto.html?id=${encodeURIComponent(id)}`;
    const nome = esc(item.nome || "Produto");
    const imagem = fullUrl(item.imagem_url || (Array.isArray(item.imagens) ? item.imagens[0] : "") || "");
    const preco = money.format(Number(item.preco || 0));
    const badge = enc ? esc(enc.BADGE) : "Sob encomenda";
    const nota = enc ? esc(enc.CARD_NOTE) : "Envio após confirmação de disponibilidade";
    // Imagem com fallback visual: se a URL externa falhar, escondemos o <img> e
    // revelamos o ícone padrão da marca (sem depender de hosts de terceiros).
    const media = imagem
      ? `<div class="achados-card-media"><img src="${esc(imagem)}" alt="${nome}" loading="lazy" onerror="this.style.display='none';this.nextElementSibling.style.display='grid';"><span class="achados-card-fallback" style="display:none" aria-hidden="true">✦</span></div>`
      : `<div class="achados-card-media"><span class="achados-card-fallback" aria-hidden="true">✦</span></div>`;
    return `
      <a class="achados-card" href="${href}">
        <span class="product-badge-encomenda">${badge}</span>
        ${media}
        <div class="achados-card-body">
          <p class="eyebrow">${esc(item.categoria || "Achados Místicos")}</p>
          <h3>${nome}</h3>
          <p class="product-encomenda-note">${nota}</p>
        </div>
        <strong class="product-price">${preco}</strong>
        <span class="btn btn-full achados-card-cta">Ver produto</span>
      </a>`;
  }

  function render(items) {
    if (!items.length) {
      grid.innerHTML = "";
      setState(`
        <div class="achados-empty">
          <p class="eyebrow">Em curadoria</p>
          <h2>Novos achados chegando</h2>
          <p>Ainda não há produtos sob encomenda publicados. Fale com a Mística pelo WhatsApp para pedidos especiais ou volte em breve.</p>
          <a class="btn" href="/index.html#produtos">Ver o catálogo completo</a>
        </div>`);
      return;
    }
    setState("");
    grid.innerHTML = items.map(cardHtml).join("");
  }

  async function load() {
    setState(`<div class="achados-loading"><span class="achados-spinner" aria-hidden="true"></span><p>Carregando os Achados Místicos...</p></div>`);
    grid.innerHTML = "";
    try {
      const response = await fetch(`${API_BASE}/api/produtos?limite=500`, { cache: "no-store" });
      if (!response.ok) throw new Error(`API ${response.status}`);
      const data = await response.json();
      const items = (Array.isArray(data) ? data : []).filter(isSob);
      render(items);
    } catch (error) {
      grid.innerHTML = "";
      setState(`
        <div class="achados-error">
          <p class="eyebrow">Não foi possível carregar agora</p>
          <h2>Tente novamente em instantes</h2>
          <p>Houve uma falha ao buscar os produtos sob encomenda. Verifique sua conexão e tente de novo.</p>
          <button class="btn" type="button" data-achados-retry>Tentar novamente</button>
          <a class="btn btn-ghost" href="/index.html#produtos">Voltar ao catálogo</a>
        </div>`);
    }
  }

  stateEl.addEventListener("click", (event) => {
    if (event.target.closest("[data-achados-retry]")) load();
  });

  load();
})();
