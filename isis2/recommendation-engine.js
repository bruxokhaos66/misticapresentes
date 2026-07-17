// Isis 2.0 — Recommendation Engine.
//
// Combina a intenção detectada (Intent Engine) com o catálogo real
// (Product Knowledge) para ranquear produtos e sempre justificar a
// escolha. Nunca inventa produtos: só recomenda o que existe no catálogo
// vigente e em estoque, nunca ignora exclusões ("não quero X", "já tenho
// Y") e nunca extrapola o orçamento informado.
(() => {
  window.Isis2 = window.Isis2 || {};
  if (window.Isis2.RecommendationEngine) return;

  const PK = () => window.Isis2.ProductKnowledge;

  function matchesExcludedTerm(product, excludeTerms) {
    if (!excludeTerms || !excludeTerms.length) return false;
    const knowledge = PK();
    const haystack = knowledge.normalize(`${product.name} ${product.description} ${product.category} ${product.id}`);
    return excludeTerms.some(term => haystack.includes(term));
  }

  function applyExclusions(candidates, detection) {
    if (!detection.excludeTerms || !detection.excludeTerms.length) return candidates;
    return candidates.filter(product => !matchesExcludedTerm(product, detection.excludeTerms));
  }

  function reasonFor(product, detection) {
    const intent = detection.primaryIntent;
    if (detection.sortOrder === "asc") return "é uma das opções mais em conta do catálogo";
    if (detection.sortOrder === "desc") return "é uma das opções mais completas/valorizadas do catálogo";
    if (detection.budgetMin != null && detection.budget != null) {
      return `fica dentro da faixa que você pediu (${PK().formatPrice(detection.budgetMin)} a ${PK().formatPrice(detection.budget)})`;
    }
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
    if (detection.sortOrder === "asc") return candidates.slice().sort((a, b) => a.price - b.price);
    if (detection.sortOrder === "desc") return candidates.slice().sort((a, b) => b.price - a.price);
    const intent = detection.primaryIntent;
    return candidates
      .map((product, index) => {
        let score = candidates.length - index;
        if (intent && product.category === intent.priorityCategory) score += 2;
        if (detection.budget && product.price <= detection.budget) score += 1;
        if (detection.budgetMin != null && product.price >= detection.budgetMin) score += 1;
        return { product, score };
      })
      .sort((a, b) => b.score - a.score)
      .map(row => row.product);
  }

  function withinBudget(product, detection) {
    if (detection.budget != null && product.price > detection.budget) return false;
    if (detection.budgetMin != null && product.price < detection.budgetMin) return false;
    return true;
  }

  function recommend(detection, { limit = 3, excludeIds = [] } = {}) {
    const knowledge = PK();
    if (!knowledge || !knowledge.hasCatalog()) {
      return { products: [], complements: [], reasons: {}, note: "catalog_unavailable" };
    }

    // "mais barato"/"mais caro" pedem uma ordenação sobre o catálogo
    // inteiro, não uma busca textual — usar searchByTerms aqui arriscaria
    // pegar só os produtos cuja descrição contém palavras soltas da frase
    // (ex.: "mais" aparecendo em outra frase do catálogo) em vez de
    // realmente comparar todos os preços.
    let candidates = detection.sortOrder
      ? knowledge.listAll()
      : knowledge.searchByTerms(detection.searchTerms, { limit: limit + excludeIds.length + 5 });

    if (!candidates.length && (detection.budget != null || detection.budgetMin != null)) {
      candidates = knowledge.listAll();
    }
    if (!candidates.length && detection.primaryIntent) {
      candidates = knowledge.listAll().filter(product => product.category === detection.primaryIntent.priorityCategory);
    }

    // Se há orçamento, filtra por ele — mas se a busca textual/categoria
    // encontrou candidatos que a caíram todos fora do orçamento (ex.:
    // "presente até R$50" quando o único produto com "presente" no texto
    // custa R$250), amplia para o catálogo inteiro em vez de desistir:
    // pode haver opção mais barata que só não bateu a busca textual.
    if (detection.budget != null || detection.budgetMin != null) {
      let withinB = candidates.filter(product => withinBudget(product, detection));
      if (!withinB.length) withinB = knowledge.listAll().filter(product => withinBudget(product, detection));
      candidates = withinB;
    }

    candidates = applyExclusions(candidates, detection);
    candidates = candidates.filter(product => !excludeIds.includes(product.id));
    const ranked = rankProducts(candidates, detection).slice(0, limit);

    const reasons = {};
    ranked.forEach(product => {
      reasons[product.id] = reasonFor(product, detection);
    });

    const complements = ranked.length
      ? knowledge.getComplements(ranked[0].id).filter(row => !matchesExcludedTerm(row.product, detection.excludeTerms))
      : [];

    return { products: ranked, complements, reasons, note: ranked.length ? "ok" : "no_match" };
  }

  // "três produtos com total máximo de R$120": monta uma combinação real
  // do catálogo (nunca inventa itens) que respeita a contagem e o teto de
  // gasto, priorizando relevância (ordem do catálogo/estoque) e greedy
  // por menor preço quando a soma não cabe.
  function recommendCombo(detection) {
    const knowledge = PK();
    if (!knowledge || !knowledge.hasCatalog() || !detection.combo) {
      return { products: [], total: 0, note: "catalog_unavailable" };
    }
    const { count, budget } = detection.combo;
    let pool = applyExclusions(knowledge.listAll(), detection).slice().sort((a, b) => a.price - b.price);

    const combo = [];
    let total = 0;
    for (const product of pool) {
      if (combo.length >= count) break;
      if (total + product.price <= budget) {
        combo.push(product);
        total += product.price;
      }
    }
    return { products: combo, total, note: combo.length ? "ok" : "no_match", requested: { count, budget } };
  }

  window.Isis2.RecommendationEngine = { recommend, recommendCombo, rankProducts };
})();
