// Isis 2.0 — Assessment Safety (Fase 2 — Especialista da Mística
// Escola, reforçado na Fase 2.1).
//
// Guardrail dedicado a proteção acadêmica: detecta quando o aluno colou
// (ou digitou) uma pergunta de avaliação pedindo a resposta direta — ou
// tenta contornar essa proteção de forma indireta (confirmar alternativa,
// eliminar opções, pedir tradução/codificação da resposta, pedir só a
// letra, fingir que não é avaliação, pedir porcentagem de chance, pedir
// para ordenar alternativas) — e garante que a Isis nunca entregue a
// resposta certa por nenhum desses caminhos. A Isis pode explicar a
// matéria e propor perguntas de estudo inéditas (não idênticas à
// avaliação) — a diferenciação de intenção acontece aqui. Fase 2.1 não
// afrouxa nenhuma regra da Fase 2: só adiciona detecção (classify()
// continua bloqueando tudo que já bloqueava) e reduz falso-positivo em
// estudo genuinamente legítimo via isLegitimateStudyRequest().
(() => {
  window.Isis2 = window.Isis2 || {};
  if (window.Isis2.AssessmentSafety) return;

  function normalize(value) {
    return window.Isis2.IntentEngine
      ? window.Isis2.IntentEngine.normalize(value)
      : String(value || "").normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase().trim();
  }

  // Pedido explícito de resposta/gabarito (Fase 2, preservado).
  const DIRECT_ANSWER_PATTERNS = [
    /qual\s+(e\s+|é\s+)?a\s+(resposta|alternativa)\s+(certa|correta)/,
    /qual\s+(e\s+|é\s+)?a\s+correta\b/,
    /me\s+d[eê]\s+a\s+resposta/,
    /resolve\s+(essa|esta|a)\s+questao/,
    /qual\s+alternativa\s+(marco|marcar|escolho)/,
    /gabarito/,
    /me\s+fala\s+a\s+correta/,
    /qual\s+(a\s+)?letra\s+certa/,
  ];

  // Fase 2.1 — tentativas indiretas de obter a resposta.
  const CONFIRM_PATTERNS = [
    /^\s*[eé]\s+a\s+alternativa\s+[a-e]\s*\??\s*$/,
    /\balternativa\s+[a-e]\s*\?/,
    /confirm[ae]\s+se\s+(eu\s+)?acertei/,
    /confirm[ae]\s+(a\s+)?(minha\s+)?resposta/,
    /acho\s+que\s+[eé]\s+a\s+(alternativa\s+)?[a-e]\b.*(certo|certa|correto|correta)?/,
    /pode\s+confirmar\s+(a\s+)?(letra|alternativa)/,
  ];
  const ELIMINATION_PATTERNS = [
    /qual\s+alternativa\s+(voce|você)\s+eliminaria/,
    /qual\s+(voce|você)\s+eliminaria/,
    /resposta\s+por\s+exclusao|resposta\s+por\s+exclusão/,
    /qual\s+(alternativa|opcao|opção)\s+(esta|está)\s+errada/,
    /elimina(r)?\s+as\s+alternativas/,
  ];
  const SECOND_BEST_PATTERNS = [/segunda\s+melhor\s+resposta/, /segunda\s+alternativa\s+mais\s+provavel|provável/];
  const ENCODE_TRANSLATE_PATTERNS = [
    /traduz(a|ir)\s+(a\s+)?resposta/,
    /codigo\s+morse|código\s+morse/,
    /decodifiqu?e\s+a\s+resposta/,
    /responda\s+em\s+(outro\s+)?(idioma|ingles|inglês|codigo|código)/,
  ];
  const LETTER_ONLY_PATTERNS = [
    /responda\s+(apenas\s+)?(so\s+|só\s+)?com\s+a\s+letra/,
    /so\s+a\s+letra|só\s+a\s+letra/,
    /so\s+quero\s+a\s+letra|só\s+quero\s+a\s+letra/,
  ];
  const PRETEND_NOT_EXAM_PATTERNS = [
    /finja\s+que\s+(nao|não)\s+[eé]\s+(uma\s+)?(avaliacao|avaliação|prova)/,
    /nao\s+[eé]\s+prova.*pode\s+responder|não\s+[eé]\s+prova.*pode\s+responder/,
    /perguntando\s+para\s+um\s+amigo/,
    /(e|é)\s+so\s+curiosidade|só\s+curiosidade/,
    /isso\s+nao\s+conta|isso\s+não\s+conta/,
  ];
  const ORDER_PATTERNS = [/ordene\s+as\s+alternativas/, /ordenar\s+as\s+alternativas/, /coloque\s+as\s+alternativas\s+em\s+ordem/];
  const PROBABILITY_PATTERNS = [
    /porcentagem\s+de\s+chance/, /qual\s+(opcao|opção)\s+tem\s+mais\s+chance/, /chance\s+de\s+acerto/,
    /probabilidade\s+de\s+(estar\s+)?(certo|certa|correta|correto)/,
  ];
  const HINT_REVEAL_PATTERNS = [/dica\s+que\s+(praticamente\s+)?entregue/, /uma\s+dica\s+bem\s+forte/, /da\s+uma\s+dica\s+grande|dá\s+uma\s+dica\s+grande/];

  const INDIRECT_BYPASS_PATTERNS = [
    ...CONFIRM_PATTERNS, ...ELIMINATION_PATTERNS, ...SECOND_BEST_PATTERNS, ...ENCODE_TRANSLATE_PATTERNS,
    ...LETTER_ONLY_PATTERNS, ...PRETEND_NOT_EXAM_PATTERNS, ...ORDER_PATTERNS, ...PROBABILITY_PATTERNS, ...HINT_REVEAL_PATTERNS,
  ];

  // Estrutura típica de uma questão de múltipla escolha colada
  // (enunciado + alternativas "a)"/"b)"/"c)" ou "a."/"b."), combinada com
  // sinal de que é avaliação (não uma dúvida de conteúdo comum).
  const OPTION_LINE_PATTERN = /(^|\n|\s)[a-e][\).]\s+\S/gi;
  const ASSESSMENT_CONTEXT_PATTERN = /avalia[cç][aã]o|quiz|prova|questao|questão|teste/;

  function looksLikePastedQuestion(norm, raw) {
    const optionMatches = raw.match(OPTION_LINE_PATTERN) || [];
    return optionMatches.length >= 2 && (ASSESSMENT_CONTEXT_PATTERN.test(norm) || raw.includes("?"));
  }

  // Fase 2.1 — estudo legítimo: pedidos explícitos de gerar conteúdo
  // INÉDITO (não resolver algo existente) — quiz inventado pela Isis,
  // pergunta de treino nova, revisão conceitual, comparação/explicação
  // aberta. Só passa a barreira quando a frase é claramente um pedido de
  // criação/explicação, nunca quando também contém um pedido de resposta
  // pronta (checado antes desta função, que só é uma segunda camada).
  const LEGITIMATE_STUDY_PATTERNS = [
    /crie\s+(uma\s+)?pergunta\s+(de\s+)?(multipla|múltipla)\s+escolha/,
    /crie\s+um\s+quiz/,
    /fa[cç]a\s+um\s+quiz\s+inventado/,
    /me\s+d[eê]\s+uma\s+pergunta\s+(de\s+)?treino/,
    /explique\s+(a[s]?\s+)?diferen[cç]a/,
    /explique\s+por\s+que\s+.*estaria\s+errad[ao]/,
    /quero\s+revisar\s+o\s+conceito/,
    /revise?\s+(o\s+)?conteudo|conteúdo/,
    /pode\s+explicar/,
  ];

  function isLegitimateStudyRequest(text) {
    const norm = normalize(text);
    return LEGITIMATE_STUDY_PATTERNS.some(pattern => pattern.test(norm));
  }

  // Retorna "direct_answer_request" quando a mensagem pede (direta ou
  // indiretamente) a resposta pronta de uma avaliação, ou colou o
  // enunciado com alternativas. Retorna null quando é só uma dúvida de
  // conteúdo comum (ex.: "pode explicar o que é rapé?") ou um pedido
  // explícito de conteúdo de estudo inédito, que a Isis pode responder
  // normalmente. Em caso de ambiguidade real (não capturada por nenhum
  // padrão de estudo legítimo), o padrão de bloqueio prevalece — erra
  // para o lado seguro.
  function classify(text) {
    const raw = String(text || "");
    const norm = normalize(text);

    if (DIRECT_ANSWER_PATTERNS.some(pattern => pattern.test(norm))) return "direct_answer_request";
    if (INDIRECT_BYPASS_PATTERNS.some(pattern => pattern.test(norm))) return "direct_answer_request";
    if (looksLikePastedQuestion(norm, raw)) return "direct_answer_request";

    return null;
  }

  window.Isis2.AssessmentSafety = { classify, isLegitimateStudyRequest };
})();
