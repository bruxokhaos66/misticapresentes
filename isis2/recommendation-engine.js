// Isis 2.0 — Recommendation Engine.
//
// Combina a intenção detectada (Intent Engine) com o catálogo real
// (Product Knowledge) para ranquear produtos e sempre justificar a
// escolha. Nunca inventa produtos: só recomenda o que existe no catálogo
// vigente e em estoque.
(() => {
  window.Isis2 = window.Isis2 || {};
  if (window.Isis2.RecommendationEngine) return;

  const PK = () => window.Isis2.ProductKnowledge;

  function reasonFor(product, detection) {
    const intent = detection.primaryIntent;
    if (detection.budget) {
      return `fica dentro do valor que você pediu (até ${PK().formatPrice(detection.budget)}) e combina com ${intent ? intent.label.toLowerCase() : "o que você procura"}`;
    }
    if (intent) {
      return `é uma das opções mais indicadas para ${intent.label.toLowerCase()}`;
    }
    return "combina com os termos que você mencionou";
  }

  // Fase 1: ranking = pontuação textual (Product Knowledge) + bônus por
  // categoria prioritária da intenção + penalidade leve fora do orçamento.
  // A interface (recommend) é estável mesmo se o cálculo interno evoluir
  // para embeddings/RAG numa fase futura.
  function rankProducts(candidates, detection) {
    const intent = detection.primaryIntent;
    return candidates
      .map((product, index) => {
        let score = candidates.length - index;
        if (intent && product.category === intent.priorityCategory) score += 2;
        if (detection.budget && product.price <= detection.budget) score += 1;
        return { product, score };
      })
      .sort((a, b) => b.score - a.score)
      .map(row => row.product);
  }

  function recommend(detection, { limit = 3, excludeIds = [] } = {}) {
    const knowledge = PK();
    if (!knowledge || !knowledge.hasCatalog()) {
      return { products: [], complements: [], reasons: {}, note: "catalog_unavailable" };
    }

    let candidates = knowledge.searchByTerms(detection.searchTerms, { limit: limit + excludeIds.length + 2 });

    if (!candidates.length && detection.budget) {
      candidates = knowledge.byBudget(detection.budget);
    }
    if (!candidates.length && detection.primaryIntent) {
      candidates = knowledge.listAll().filter(product => product.category === detection.primaryIntent.priorityCategory);
    }
    if (detection.budget) {
      const withinBudget = candidates.filter(product => product.price <= detection.budget);
      if (withinBudget.length) candidates = withinBudget;
    }

    candidates = candidates.filter(product => !excludeIds.includes(product.id));
    const ranked = rankProducts(candidates, detection).slice(0, limit);

    const reasons = {};
    ranked.forEach(product => {
      reasons[product.id] = reasonFor(product, detection);
    });

    const complements = ranked.length ? knowledge.getComplements(ranked[0].id) : [];

    return { products: ranked, complements, reasons, note: ranked.length ? "ok" : "no_match" };
  }

  window.Isis2.RecommendationEngine = { recommend, rankProducts };
})();
