// Isis 2.0 — Assessment Safety (Fase 2 — Especialista da Mística
// Escola).
//
// Guardrail dedicado a proteção acadêmica: detecta quando o aluno colou
// (ou digitou) uma pergunta de avaliação pedindo a resposta direta, e
// garante que a Isis nunca entregue a alternativa correta, resolva a
// pergunta por ele ou ajude a burlar tentativas/nota. A Isis pode
// explicar a matéria e propor perguntas de estudo (não idênticas à
// avaliação) — a diferenciação de intenção acontece aqui.
(() => {
  window.Isis2 = window.Isis2 || {};
  if (window.Isis2.AssessmentSafety) return;

  function normalize(value) {
    return window.Isis2.IntentEngine
      ? window.Isis2.IntentEngine.normalize(value)
      : String(value || "").normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase().trim();
  }

  // Pedido explícito de resposta/gabarito.
  const DIRECT_ANSWER_PATTERNS = [
    /qual\s+(e\s+|é\s+)?a\s+(resposta|alternativa)\s+(certa|correta)/,
    /me\s+d[eê]\s+a\s+resposta/,
    /resolve\s+(essa|esta|a)\s+questao/,
    /qual\s+alternativa\s+(marco|marcar|escolho)/,
    /gabarito/,
    /me\s+fala\s+a\s+correta/,
    /qual\s+(a\s+)?letra\s+certa/,
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

  // Retorna "direct_answer_request" quando a mensagem pede a resposta
  // pronta de uma avaliação (explicitamente, ou por ter colado o
  // enunciado com alternativas). Retorna null quando é só uma dúvida de
  // conteúdo comum (ex.: "pode explicar o que é rapé?"), que a Isis pode
  // responder normalmente.
  function classify(text) {
    const norm = normalize(text);
    if (DIRECT_ANSWER_PATTERNS.some(pattern => pattern.test(norm))) return "direct_answer_request";
    if (looksLikePastedQuestion(norm, String(text || ""))) return "direct_answer_request";
    return null;
  }

  window.Isis2.AssessmentSafety = { classify };
})();
