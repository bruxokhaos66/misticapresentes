// Isis 2.0 — Product Knowledge module.
//
// Única fonte de verdade sobre o catálogo: lê sempre o array global
// `products` (e `getStock`/`currency` quando existem) já usado pelo
// site (app.js/mobile-sync.js). Nunca duplica nem inventa dados —
// se uma informação não existe no catálogo, os métodos retornam
// null/undefined e quem consome decide como admitir a lacuna.
(() => {
  window.Isis2 = window.Isis2 || {};
  if (window.Isis2.ProductKnowledge) return;

  function normalize(value) {
    return String(value || "")
      .normalize("NFD")
      .replace(/[̀-ͯ]/g, "")
      .toLowerCase()
      .trim();
  }

  function catalog() {
    return typeof products !== "undefined" && Array.isArray(products) ? products : [];
  }

  function hasCatalog() {
    return catalog().length > 0;
  }

  function stockOf(product) {
    try {
      if (typeof getStock === "function") return Number(getStock(product.id));
    } catch {
      /* getStock indisponível nesta página */
    }
    return Number(product.stock || 0);
  }

  function formatPrice(value) {
    try {
      if (typeof currency !== "undefined" && currency && typeof currency.format === "function") {
        return currency.format(Number(value || 0));
      }
    } catch {
      /* currency indisponível nesta página */
    }
    return `R$ ${Number(value || 0).toFixed(2).replace(".", ",")}`;
  }

  function ratingOf(product) {
    const total = Number(product.avaliacoesTotal || product.avaliacoes_total || 0);
    const media = Number(product.avaliacoesMedia || product.avaliacoes_media || 0);
    if (!total) return null;
    return { total, media };
  }

  // Compara por String() de propósito: o catálogo sincronizado
  // (mobile-sync.js) sempre usa IDs string ("api-123"), mas essa
  // comparação tolera também um ID numérico eventual sem quebrar.
  function byId(id) {
    return catalog().find(product => String(product.id) === String(id)) || null;
  }

  // Deduplica por ID: se o catálogo de origem (API) trouxer o mesmo
  // produto duas vezes, a Isis nunca deve recomendar/exibir o mesmo item
  // repetido — mantém a primeira ocorrência.
  function dedupeById(list) {
    const seen = new Set();
    return list.filter(product => {
      const key = String(product.id);
      if (seen.has(key)) return false;
      seen.add(key);
      return true;
    });
  }

  function listAll({ onlyInStock = true } = {}) {
    const all = dedupeById(catalog());
    return onlyInStock ? all.filter(product => stockOf(product) > 0) : all;
  }

  function categories() {
    const set = new Set(catalog().map(product => product.category).filter(Boolean));
    return Array.from(set);
  }

  // Pontuação simples por frequência de termos no texto (nome + descrição +
  // categoria) do produto — camada de "busca semântica" leve da Fase 1.
  // Documentado no relatório: substituível por embeddings/RAG no futuro
  // sem mudar o contrato desta função.
  function searchByTerms(terms, { onlyInStock = true, limit = 3 } = {}) {
    const normTerms = (terms || []).map(normalize).filter(Boolean);
    if (!normTerms.length) return [];
    return listAll({ onlyInStock })
      .map(product => {
        const haystack = normalize(`${product.name} ${product.description} ${product.category}`);
        const score = normTerms.reduce((acc, term) => acc + (haystack.includes(term) ? 1 : 0), 0);
        return { product, score };
      })
      .filter(row => row.score > 0)
      .sort((a, b) => b.score - a.score)
      .slice(0, limit)
      .map(row => row.product);
  }

  function byBudget(maxPrice, { onlyInStock = true } = {}) {
    if (!Number.isFinite(maxPrice)) return [];
    return listAll({ onlyInStock })
      .filter(product => Number(product.price) <= maxPrice)
      .sort((a, b) => b.price - a.price);
  }

  // Mapa de complementos por categoria — reflete combinações reais do
  // catálogo (incenso+incensário, pedra+kit, essência+aromatizador...).
  // Fase 2 pode substituir por um motor de afinidade aprendido; a
  // interface (getComplements) permanece igual.
  const COMPLEMENT_RULES = [
    { from: "incenso-natural", to: "incensario", reason: "um incensário deixa o ritual com o incenso mais seguro e bonito" },
    { from: "pedra-energetica", to: "artigo-fe", reason: "combina bem com artigos de fé para reforçar a intenção" },
    { from: "aromatizador", to: "incensario", reason: "compõe o ambiente junto com o aroma, para um ritual completo" },
    { from: "vela-ritualistica", to: "artigo-fe", reason: "vela e artigos de fé costumam ser usados juntos em orações e pedidos" },
    { from: "banho-ervas", to: "vela-ritualistica", reason: "banho de ervas e vela de intenção se complementam em rituais de renovação" },
    { from: "artigo-fe", to: "vela-ritualistica", reason: "vela acompanha bem os momentos de oração e fé" },
    { from: "incensario", to: "incenso-natural", reason: "incensário funciona melhor com um bom incenso natural" },
  ];

  function getComplements(id, { limit = 2 } = {}) {
    return COMPLEMENT_RULES
      .filter(rule => rule.from === id)
      .map(rule => ({ product: byId(rule.to), reason: rule.reason }))
      .filter(row => row.product && stockOf(row.product) > 0)
      .slice(0, limit);
  }

  function explainDifference(idA, idB) {
    const a = byId(idA);
    const b = byId(idB);
    if (!a || !b) return null;
    return {
      a: { name: a.name, category: a.category, description: a.description, price: a.price },
      b: { name: b.name, category: b.category, description: b.description, price: b.price },
    };
  }

  window.Isis2.ProductKnowledge = {
    normalize,
    hasCatalog,
    byId,
    listAll,
    categories,
    searchByTerms,
    byBudget,
    getComplements,
    explainDifference,
    stockOf,
    ratingOf,
    formatPrice,
  };
})();
