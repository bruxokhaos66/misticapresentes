// Isis 2.0 — Conversation Manager.
//
// Orquestra Intent Engine + Product Knowledge + Recommendation Engine +
// Context Memory + Analytics para transformar uma mensagem do cliente
// numa resposta estruturada. Não gera HTML (isso é responsabilidade da
// camada de UI); devolve dados para o widget renderizar.
(() => {
  window.Isis2 = window.Isis2 || {};
  if (window.Isis2.ConversationManager) return;

  const DIFF_PAIRS = {
    // pares comuns de "qual a diferença entre X e Y" no domínio da loja.
    "pedra-energetica|artigo-fe": true,
    "incenso-natural|aromatizador": true,
  };

  function explainDifferenceIfAsked(detection) {
    const knowledge = window.Isis2.ProductKnowledge;
    if (!knowledge || detection.mentionedProductIds.length < 2) return null;
    const [a, b] = detection.mentionedProductIds;
    return knowledge.explainDifference(a, b);
  }

  function greetingReply() {
    return {
      kind: "greeting",
      text: "Olá! Eu sou a Isis, consultora da Mística Presentes. Me conte o que você procura — por exemplo \"quero um incenso para relaxar\" ou \"presente até R$100\" — que eu te ajudo a encontrar.",
      products: [],
      complements: [],
      quickReplies: window.Isis2.IntentEngine.INTENTS.slice(0, 4).map(intent => ({ id: intent.id, label: intent.label })),
    };
  }

  function thanksReply() {
    return {
      kind: "thanks",
      text: "Por nada! Se quiser mais alguma sugestão, é só me chamar. 🔮",
      products: [],
      complements: [],
      quickReplies: [],
    };
  }

  function catalogUnavailableReply() {
    return {
      kind: "unavailable",
      text: "No momento não consigo consultar o catálogo completo desta página. Você pode ver todos os produtos na seção de produtos, ou tentar novamente em instantes.",
      products: [],
      complements: [],
      quickReplies: [],
    };
  }

  function differenceReply(diff, detection) {
    return {
      kind: "difference",
      text: `A diferença: "${diff.a.name}" é da categoria ${diff.a.category} (${diff.a.description}), já "${diff.b.name}" é da categoria ${diff.b.category} (${diff.b.description}). Os dois custam ${window.Isis2.ProductKnowledge.formatPrice(diff.a.price)} e ${window.Isis2.ProductKnowledge.formatPrice(diff.b.price)} respectivamente.`,
      products: [],
      complements: [],
      quickReplies: [],
      detection,
    };
  }

  function recommendationReply(detection) {
    const memory = window.Isis2.ContextMemory.get();
    const { products, complements, reasons, note } = window.Isis2.RecommendationEngine.recommend(detection, {
      excludeIds: [],
    });

    if (note === "catalog_unavailable") return catalogUnavailableReply();

    if (!products.length) {
      return {
        kind: "no_match",
        text: "Ainda não encontrei um produto certeiro para isso. Pode me contar um pouco mais (por exemplo, a intenção ou um orçamento aproximado)? Também posso te mostrar nossas categorias.",
        products: [],
        complements: [],
        quickReplies: window.Isis2.IntentEngine.INTENTS.slice(0, 4).map(intent => ({ id: intent.id, label: intent.label })),
        detection,
      };
    }

    window.Isis2.Analytics.track("product_recommended", { count: products.length, intent: detection.primaryIntent?.id || null });
    products.forEach(product => window.Isis2.ContextMemory.addViewedProduct(product.id));

    const intro = detection.primaryIntent
      ? `Para ${detection.primaryIntent.label.toLowerCase()}, escolhi estas opções:`
      : "Encontrei estas opções para você:";

    return {
      kind: "recommendation",
      text: intro,
      products,
      reasons,
      complements,
      quickReplies: window.Isis2.IntentEngine.INTENTS
        .filter(intent => intent.id !== detection.primaryIntent?.id)
        .slice(0, 3)
        .map(intent => ({ id: intent.id, label: intent.label })),
      detection,
      memory,
    };
  }

  function handleUserMessage(text) {
    const knowledge = window.Isis2.ProductKnowledge;
    const detection = window.Isis2.IntentEngine.detect(text);
    window.Isis2.ContextMemory.registerMessage(detection);
    window.Isis2.Analytics.track("message_sent", { intent: detection.primaryIntent?.id || null });

    if (!knowledge.hasCatalog()) return catalogUnavailableReply();
    if (detection.isGreeting) return greetingReply();
    if (detection.isThanks) return thanksReply();

    const diff = explainDifferenceIfAsked(detection);
    if (diff) return differenceReply(diff, detection);

    return recommendationReply(detection);
  }

  function handleIntentShortcut(intentId) {
    const intent = window.Isis2.IntentEngine.INTENTS.find(item => item.id === intentId);
    if (!intent) return null;
    return handleUserMessage(intent.label);
  }

  function startConversation() {
    window.Isis2.Analytics.track("conversation_started", {});
    return greetingReply();
  }

  window.Isis2.ConversationManager = {
    handleUserMessage,
    handleIntentShortcut,
    startConversation,
  };
})();
