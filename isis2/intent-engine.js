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
      keywords: ["relax", "relaxar", "ansiedade", "ansios", "calma", "acalmar", "dormir", "sono", "estresse", "stress", "nervos", "tensao"],
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
      keywords: ["presente", "presentear", "aniversario", "aniversário", "surpresa", "de presente"],
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

  function detectGreeting(norm) {
    return GREETINGS.some(word => norm === word || norm.startsWith(`${word} `));
  }

  function detectThanks(norm) {
    return THANKS.some(word => norm.includes(word));
  }

  // Extrai orçamento de frases como "até R$100", "ate 100 reais", "no
  // máximo 80".
  function detectBudget(norm) {
    const match = norm.match(/(?:ate|até|no maximo|no máximo|maximo de|máximo de)\s*r?\$?\s*(\d+(?:[.,]\d+)?)/)
      || norm.match(/r\$\s*(\d+(?:[.,]\d+)?)/);
    if (!match) return null;
    const value = Number(match[1].replace(",", "."));
    return Number.isFinite(value) ? value : null;
  }

  function detectIntents(text) {
    const norm = normalize(text);
    const scored = INTENTS.map(intent => {
      const score = intent.keywords.reduce((acc, keyword) => acc + (norm.includes(normalize(keyword)) ? 1 : 0), 0);
      return { intent, score };
    }).filter(row => row.score > 0).sort((a, b) => b.score - a.score);
    return scored.map(row => row.intent);
  }

  function mentionedProducts(norm) {
    const knowledge = PK();
    if (!knowledge) return [];
    return knowledge.listAll({ onlyInStock: false }).filter(product => norm.includes(normalize(product.name)));
  }

  function fallbackTerms(norm) {
    return norm.split(/\s+/).filter(word => word.length > 2 && !GREETINGS.includes(word));
  }

  function detect(text) {
    const norm = normalize(text);
    const intents = detectIntents(text);
    const budget = detectBudget(norm);
    const isGreeting = detectGreeting(norm);
    const isThanks = detectThanks(norm);
    const products = mentionedProducts(norm);
    const terms = intents.length ? intents[0].terms : fallbackTerms(norm);
    return {
      raw: text,
      normalized: norm,
      intents,
      primaryIntent: intents[0] || null,
      budget,
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
