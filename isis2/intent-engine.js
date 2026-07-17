// Isis 2.0 — Intent Engine.
//
// Camada de regras + heurísticas leves para entender linguagem informal
// em português. Não depende de rede nem de modelos externos: é a base
// "sempre disponível" sobre a qual um provedor de IA (ver ai-providers.js)
// pode futuramente se apoiar via RAG.
(() => {
  window.Isis2 = window.Isis2 || {};
  if (window.Isis2.IntentEngine) return;

  const PK = () => window.Isis2.ProductKnowledge;

  function normalize(value) {
    return String(value || "")
      .normalize("NFD")
      .replace(/[̀-ͯ]/g, "")
      .toLowerCase()
      .trim();
  }

  // Cada intenção liga palavras/sinônimos informais a termos de busca no
  // catálogo e a uma categoria "prioritária" para desempate no ranking.
  const INTENTS = [
    {
      id: "calma",
      label: "Calma, ansiedade e sono",
      keywords: ["relax", "relaxar", "ansiedade", "ansios", "calma", "acalmar", "dormir", "sono", "insonia", "insônia", "estresse", "stress", "nervos", "tensao"],
      terms: ["calma", "relax", "erva", "banho", "lavanda", "aromatizador"],
      priorityCategory: "Ervas e limpeza",
    },
    {
      id: "protecao",
      label: "Proteção",
      keywords: ["protec", "proteg", "energia ruim", "mau olhado", "mau-olhado", "olho gordo", "descarrego", "blindagem"],
      terms: ["protec", "proteg", "limpeza", "descarrego", "pedra"],
      priorityCategory: "Proteção e equilíbrio",
    },
    {
      id: "amor",
      label: "Amor e relacionamento",
      keywords: ["amor", "paix", "relacionamento", "atrair amor", "casal"],
      terms: ["amor", "paix"],
      priorityCategory: "Fé e bênçãos",
    },
    {
      id: "prosperidade",
      label: "Prosperidade e trabalho",
      keywords: ["prosperidade", "dinheiro", "abund", "trabalho", "sorte", "riqueza", "emprego"],
      terms: ["prosperidade", "abund", "sorte", "fe"],
      priorityCategory: "Fé e bênçãos",
    },
    {
      id: "fe",
      label: "Fé e oração",
      keywords: ["fe ", "fé", "oracao", "oração", "benc", "espiritual", "reza"],
      terms: ["fe", "benc", "oracao", "vela"],
      priorityCategory: "Fé e luz",
    },
    {
      id: "xamanismo",
      label: "Xamanismo e tradições",
      keywords: ["xaman", "iniciante", "comecando", "começando", "tradicao", "tradição", "rape", "rapé", "ritual"],
      terms: ["incenso", "erva", "ritual"],
      priorityCategory: "Aromas e proteção",
    },
    {
      id: "altar",
      label: "Montar altar",
      keywords: ["altar", "montar altar", "espaco sagrado", "espaço sagrado"],
      terms: ["vela", "incensario", "pedra", "artigo"],
      priorityCategory: "Decoração mística",
    },
    {
      id: "presente",
      label: "Presente",
      keywords: ["presente", "presentear", "aniversario", "aniversário", "surpresa", "de presente", "outra pessoa", "para alguem", "para alguém", "presentear alguem", "presentear alguém"],
      terms: ["presente", "kit"],
      priorityCategory: "Kits e presentes",
    },
    {
      id: "aromas",
      label: "Aromas e essências",
      keywords: ["aroma", "perfume", "incenso", "cheiro", "essencia", "essência", "combina com"],
      terms: ["aroma", "incenso", "perfume", "essencia"],
      priorityCategory: "Casa perfumada",
    },
  ];

  const GREETINGS = ["ola", "oi", "bom dia", "boa tarde", "boa noite", "oii", "opa"];
  const THANKS = ["obrigad", "valeu", "gratidao", "gratidão"];
  const STOPWORDS = ["um", "uma", "uns", "umas", "de", "da", "do", "para", "pra", "com", "o", "a", "os", "as", "e", "mais", "muito", "produto", "produtos"];
  const NUMBER_WORDS = { um: 1, uma: 1, dois: 2, duas: 2, tres: 3, três: 3, quatro: 4, cinco: 5 };

  function detectGreeting(norm) {
    return GREETINGS.some(word => norm === word || norm.startsWith(`${word} `));
  }

  function detectThanks(norm) {
    return THANKS.some(word => norm.includes(word));
  }

  // Faixa de preço: "entre R$50 e R$100" → { min: 50, max: 100 }.
  function detectBudgetRange(norm) {
    const match = norm.match(/entre\s*r?\$?\s*(\d+(?:[.,]\d+)?)\s*(?:e|a)\s*r?\$?\s*(\d+(?:[.,]\d+)?)/);
    if (!match) return null;
    const min = Number(match[1].replace(",", "."));
    const max = Number(match[2].replace(",", "."));
    if (!Number.isFinite(min) || !Number.isFinite(max)) return null;
    return { min: Math.min(min, max), max: Math.max(min, max) };
  }

  // Extrai orçamento de frases como "até R$100", "ate 100 reais", "no
  // máximo 80". Não confundir com uma faixa ("entre X e Y"), verificada
  // antes por detectBudgetRange.
  function detectBudget(norm) {
    const match = norm.match(/(?:ate|até|no maximo|no máximo|maximo de|máximo de)\s*r?\$?\s*(\d+(?:[.,]\d+)?)/)
      || norm.match(/r\$\s*(\d+(?:[.,]\d+)?)/);
    if (!match) return null;
    const value = Number(match[1].replace(",", "."));
    return Number.isFinite(value) ? value : null;
  }

  // "mais barato"/"produto barato"/"em conta" → asc;
  // "mais caro"/"produto caro"/"premium" → desc.
  function detectSortOrder(norm) {
    if (/\bbarato\b|mais em conta|mais economic|mais econôm|mais acessivel|mais acessível|\beconomico\b|\beconômico\b/.test(norm)) return "asc";
    if (/\bcaro\b|mais premium|mais luxuos|\bpremium\b/.test(norm)) return "desc";
    return null;
  }

  // Negação/exclusão: "não quero X", "sem X", "já tenho X" → termos que a
  // recomendação deve evitar. Sem isso, um pedido como "já tenho
  // aromatizador, não quero outro" reconheceria só as palavras positivas
  // e erraria a recomendação.
  //
  // Importante: "não tenho X" (ex.: "quero um incenso, mas não tenho
  // incensário") é DE PROPÓSITO tratado como sinal positivo, não como
  // exclusão — a falta de um complemento é uma oportunidade de sugeri-lo
  // junto, não um motivo para escondê-lo. Não adicionar "não tenho" a
  // este padrão sem discutir a mudança de comportamento.
  function detectExclusions(norm) {
    const excluded = new Set();
    const patterns = [
      /(?:nao quero|não quero|nao gosto de|não gosto de|evite|evitar)\s+([a-z0-9çãáéíóúâêôõü ]{2,40})/g,
      /\bsem\s+([a-z0-9çãáéíóúâêôõü ]{2,40})/g,
      /\bja tenho\s+([a-z0-9çãáéíóúâêôõü ]{2,40})/g,
      /\bjá tenho\s+([a-z0-9çãáéíóúâêôõü ]{2,40})/g,
    ];
    patterns.forEach(pattern => {
      let match;
      // eslint-disable-next-line no-cond-assign
      while ((match = pattern.exec(norm))) {
        const clause = match[1].split(/[.,;!?]/)[0];
        clause.split(/\s+/).forEach(word => {
          const clean = normalize(word);
          if (clean.length > 2 && !STOPWORDS.includes(clean)) excluded.add(clean);
        });
      }
    });
    return Array.from(excluded);
  }

  // "três produtos com total máximo de R$120" → { count: 3, budget: 120 }.
  function detectCombo(norm) {
    const numberPattern = "(\\d+|" + Object.keys(NUMBER_WORDS).join("|") + ")";
    const match = norm.match(new RegExp(`${numberPattern}\\s+produtos?.{0,40}?(?:total|totalizando).{0,20}?r?\\$?\\s*(\\d+(?:[.,]\\d+)?)`));
    if (!match) return null;
    const rawCount = match[1];
    const count = NUMBER_WORDS[rawCount] || Number(rawCount);
    const budget = Number(match[2].replace(",", "."));
    if (!Number.isFinite(count) || !Number.isFinite(budget) || count < 1) return null;
    return { count, budget };
  }

  // excludeTerms vem de detectExclusions(): uma palavra-chave só conta
  // para uma intenção se ela não estiver dentro de uma cláusula de
  // negação ("não quero incenso" não deve acionar a intenção "aromas"
  // pela palavra "incenso").
  function detectIntents(text, excludeTerms = []) {
    const norm = normalize(text);
    const scored = INTENTS.map(intent => {
      const score = intent.keywords.reduce((acc, keyword) => {
        const normKeyword = normalize(keyword);
        if (excludeTerms.includes(normKeyword)) return acc;
        return acc + (norm.includes(normKeyword) ? 1 : 0);
      }, 0);
      return { intent, score };
    }).filter(row => row.score > 0).sort((a, b) => b.score - a.score);
    return scored.map(row => row.intent);
  }

  function mentionedProducts(norm) {
    const knowledge = PK();
    if (!knowledge) return [];
    return knowledge.listAll({ onlyInStock: false }).filter(product => norm.includes(normalize(product.name)));
  }

  function fallbackTerms(norm, excludeTerms = []) {
    return norm.split(/\s+/).filter(word => word.length > 2 && !GREETINGS.includes(word) && !excludeTerms.includes(word));
  }

  function detect(text) {
    const norm = normalize(text);
    const excludeTerms = detectExclusions(norm);
    const intents = detectIntents(text, excludeTerms);
    const budgetRange = detectBudgetRange(norm);
    const budget = budgetRange ? budgetRange.max : detectBudget(norm);
    const budgetMin = budgetRange ? budgetRange.min : null;
    const isGreeting = detectGreeting(norm);
    const isThanks = detectThanks(norm);
    const products = mentionedProducts(norm);
    const terms = intents.length ? intents[0].terms : fallbackTerms(norm, excludeTerms);
    return {
      raw: text,
      normalized: norm,
      intents,
      primaryIntent: intents[0] || null,
      budget,
      budgetMin,
      sortOrder: detectSortOrder(norm),
      excludeTerms,
      combo: detectCombo(norm),
      isGreeting,
      isThanks,
      mentionedProductIds: products.map(product => product.id),
      searchTerms: terms,
    };
  }

  window.Isis2.IntentEngine = {
    INTENTS,
    normalize,
    detect,
  };
})();
