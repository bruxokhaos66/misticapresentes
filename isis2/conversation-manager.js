// Isis 2.0 — Conversation Manager.
//
// Orquestra Safety Guardrails + Intent Engine + Product Knowledge +
// Recommendation Engine + Context Memory + Analytics para transformar
// uma mensagem do cliente numa resposta estruturada. Não gera HTML (isso
// é responsabilidade da camada de UI); devolve dados para o widget
// renderizar. Honestidade: a Isis 2.0 nunca finge ser humana, nunca
// finge ter IA generativa conectada nem memória permanente — é uma
// assistente baseada em regras e no catálogo real desta fase.
(() => {
  window.Isis2 = window.Isis2 || {};
  if (window.Isis2.ConversationManager) return;

  function knowledge() {
    return window.Isis2.ProductKnowledge;
  }

  function explainDifferenceIfAsked(detection) {
    if (!knowledge() || detection.mentionedProductIds.length < 2) return null;
    const [a, b] = detection.mentionedProductIds;
    return knowledge().explainDifference(a, b);
  }

  function greetingReply() {
    return {
      kind: "greeting",
      text: "Olá! Eu sou a Isis, uma assistente virtual baseada no catálogo e em regras da Mística Presentes (ainda não sou uma pessoa nem uma IA generativa nesta fase). Me conte o que você procura — por exemplo \"quero um incenso para relaxar\" ou \"presente até R$100\" — que eu te ajudo a encontrar.",
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

  function differenceReply(diff) {
    return {
      kind: "difference",
      text: `A diferença: "${diff.a.name}" é da categoria ${diff.a.category} (${diff.a.description}), já "${diff.b.name}" é da categoria ${diff.b.category} (${diff.b.description}). Os dois custam ${knowledge().formatPrice(diff.a.price)} e ${knowledge().formatPrice(diff.b.price)} respectivamente.`,
      products: [],
      complements: [],
      quickReplies: [],
    };
  }

  // Respostas para mensagens sensíveis (ver safety-guardrails.js). Nunca
  // diagnostica, nunca promete cura, nunca sugere interromper tratamento;
  // em risco imediato, não tenta vender nada.
  function safetyReply(classification) {
    const genericQuickReplies = window.Isis2.IntentEngine.INTENTS.slice(0, 3).map(intent => ({ id: intent.id, label: intent.label }));

    if (classification === "crisis") {
      window.Isis2.Analytics.track("safety_crisis_detected", {});
      return {
        kind: "safety_crisis",
        text: "Sinto muito que você esteja passando por isso. Eu sou uma assistente de loja e não tenho como ajudar numa emergência — por favor, fale agora com alguém de confiança ou busque ajuda profissional. No Brasil, o CVV (Centro de Valorização da Vida) atende de graça pelo telefone 188, 24h por dia, todos os dias. Em emergência imediata, ligue 192 (SAMU) ou vá ao pronto-socorro mais próximo.",
        products: [],
        complements: [],
        quickReplies: [],
      };
    }

    if (classification === "medical_claim") {
      window.Isis2.Analytics.track("safety_medical_claim_detected", {});
      return {
        kind: "safety_medical_claim",
        text: "Não posso diagnosticar, prometer cura, nem indicar que algum produto substitui tratamento médico — isso é sempre trabalho de um profissional de saúde, e eu nunca recomendo interromper um tratamento em curso. Nossos produtos (pedras, incensos, velas, banhos de ervas...) são para experiência aromática, decorativa, cultural ou de bem-estar não médico. Se quiser, posso sugerir algo nesse sentido.",
        products: [],
        complements: [],
        quickReplies: genericQuickReplies,
      };
    }

    if (classification === "substance_risk") {
      window.Isis2.Analytics.track("safety_substance_risk_detected", {});
      return {
        kind: "safety_substance_risk",
        text: "Sobre rapé, ayahuasca e medicinas da floresta eu só trago informação educativa geral — não indico dose, preparo, combinação com remédios ou outras substâncias, e não são para menores de idade nem apresentados como tratamento. Para aprender com responsabilidade, veja o conteúdo da Escola Mística; decisões de uso pessoal devem ter orientação de um facilitador ou profissional qualificado, respeitando a legislação local.",
        products: [],
        complements: [],
        quickReplies: [],
      };
    }

    if (classification === "substance_education") {
      window.Isis2.Analytics.track("safety_substance_education_shown", {});
      return {
        kind: "safety_substance_education",
        text: "Posso ajudar com produtos relacionados de forma cultural e decorativa. Para contexto, tradição e uso responsável de rapé, ayahuasca e medicinas da floresta, a Escola Mística tem conteúdo educativo dedicado — por aqui eu não indico dose, preparo nem uso medicinal.",
        products: [],
        complements: [],
        quickReplies: [],
      };
    }

    return null;
  }

  function comboReply(detection) {
    const pk = knowledge();
    const { products, total, note, requested } = window.Isis2.RecommendationEngine.recommendCombo(detection);

    if (note === "catalog_unavailable") return catalogUnavailableReply();

    if (!products.length) {
      return {
        kind: "combo_no_match",
        text: `Não consegui montar ${detection.combo.count} produto(s) dentro de ${pk.formatPrice(detection.combo.budget)} com o catálogo atual. Quer tentar com um orçamento maior ou menos itens?`,
        products: [],
        complements: [],
        quickReplies: [],
        detection,
      };
    }

    products.forEach(product => window.Isis2.ContextMemory.addViewedProduct(product.id));
    window.Isis2.Analytics.track("product_recommended", { count: products.length, combo: true });

    const reasons = {};
    products.forEach(product => {
      reasons[product.id] = `faz parte da combinação de ${products.length} produto(s) que somam ${pk.formatPrice(total)}, dentro do orçamento de ${pk.formatPrice(requested.budget)}`;
    });

    return {
      kind: "combo",
      text: `Montei ${products.length} produto(s) que somam ${pk.formatPrice(total)} (seu orçamento era até ${pk.formatPrice(requested.budget)}):`,
      products,
      reasons,
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

    let intro;
    if (detection.sortOrder === "asc") intro = "A opção mais em conta que encontrei foi:";
    else if (detection.sortOrder === "desc") intro = "A opção mais completa que encontrei foi:";
    else if (detection.primaryIntent) intro = `Para ${detection.primaryIntent.label.toLowerCase()}, escolhi estas opções:`;
    else intro = "Encontrei estas opções para você:";

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
    const detection = window.Isis2.IntentEngine.detect(text);
    window.Isis2.ContextMemory.registerMessage(detection);
    window.Isis2.Analytics.track("message_sent", { intent: detection.primaryIntent?.id || null });

    if (!knowledge().hasCatalog()) return catalogUnavailableReply();
    if (detection.isGreeting) return greetingReply();
    if (detection.isThanks) return thanksReply();

    const classification = window.Isis2.SafetyGuardrails ? window.Isis2.SafetyGuardrails.classify(text) : null;
    if (classification === "crisis" || classification === "medical_claim" || classification === "substance_risk" || classification === "substance_education") {
      const safety = safetyReply(classification);
      if (safety) return safety;
    }

    const diff = explainDifferenceIfAsked(detection);
    if (diff) return differenceReply(diff);

    if (detection.combo) return comboReply(detection);

    const reply = recommendationReply(detection);
    if (classification === "mental_health") {
      reply.kind = `${reply.kind}_with_health_disclaimer`;
      reply.text = `Não sou profissional de saúde e não posso diagnosticar ou tratar isso — se estiver muito difícil, vale conversar com alguém especializado. Dito isso: ${reply.text.charAt(0).toLowerCase()}${reply.text.slice(1)}`;
    }
    return reply;
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
