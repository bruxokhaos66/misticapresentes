// Isis 2.0 — Safety Guardrails.
//
// A Isis é uma assistente de vitrine, não profissional de saúde. Este
// módulo classifica mensagens sensíveis (saúde mental, alegações
// médicas, risco imediato, substâncias como rapé/ayahuasca) para que o
// Conversation Manager responda com linguagem acolhedora, sem
// diagnosticar, sem prometer cura, sem incentivar interromper tratamento
// e sem instruir dose/preparo/combinação de substâncias. Roda antes de
// qualquer recomendação de produto.
(() => {
  window.Isis2 = window.Isis2 || {};
  if (window.Isis2.SafetyGuardrails) return;

  function normalize(value) {
    return window.Isis2.IntentEngine
      ? window.Isis2.IntentEngine.normalize(value)
      : String(value || "").normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase().trim();
  }

  // Risco imediato: nunca tenta vender nada, só acolhe e orienta ajuda.
  // Frases completas de propósito (não palavras soltas como "morrer"
  // sozinha) para não disparar o fluxo de emergência por engano num
  // contexto ambíguo/não relacionado.
  const CRISIS_PATTERNS = [
    /quero morrer/, /me matar/, /vou me matar/, /nao aguento mais viver/, /não aguento mais viver/,
    /suicid/, /acabar com (a minha vida|tudo|minha vida)/, /nao quero mais viver/, /não quero mais viver/,
    /me machucar/, /se machucar/, /me cortar/, /me ferir/, /automutila/,
  ];

  // Termos de saúde mental comuns: segue para a recomendação normal, mas
  // sempre com aviso de que não é diagnóstico nem tratamento.
  const MENTAL_HEALTH_PATTERNS = [
    /ansiedade/, /ansios/, /depress/, /insonia/, /insônia/, /panico/, /pânico/, /crise de choro/, /burnout/,
  ];

  // Pedido de cura/tratamento/substituição de terapia ou remédio: nunca
  // confirmar, sempre desviar para orientação profissional.
  const MEDICAL_CLAIM_PATTERNS = [
    /\bcura\b/, /\bcurar\b/, /cura (o )?cancer|cura (o )?câncer/, /trata(r)? (a |o )?(doenca|doença|cancer|câncer)/,
    /substitui (a |o )?(remedio|remédio|terapia|tratamento)/, /parar (o |meu |com o )?(remedio|remédio|tratamento)/,
    /posso parar (o |meu )?(remedio|remédio|tratamento)/,
  ];

  // Rapé, ayahuasca, medicinas da floresta: educativo por padrão; se
  // pedir dose/preparo/combinação ou envolver menor de idade, é ainda
  // mais restrito (substance_risk).
  const SUBSTANCE_PATTERNS = [/\brape\b/, /rapé/, /ayahuasca/, /daime/, /medicina(s)? da floresta/];
  const DOSAGE_PATTERNS = [/quanto (tomar|usar|cheirar)/, /qual (a |eh a |é a )?dose/, /como (preparar|combinar|misturar)/, /misturar com/, /overdose/, /combinar com (o |meu )?remedio|remédio/];
  const MINOR_PATTERNS = [/menor de idade/, /\bcrianca\b|\bcriança\b/, /adolescente/, /meu filho/, /minha filha/, /\b1[0-7] anos\b/];

  function classify(text) {
    const norm = normalize(text);
    if (CRISIS_PATTERNS.some(pattern => pattern.test(norm))) return "crisis";
    if (MEDICAL_CLAIM_PATTERNS.some(pattern => pattern.test(norm))) return "medical_claim";
    const mentionsSubstance = SUBSTANCE_PATTERNS.some(pattern => pattern.test(norm));
    if (mentionsSubstance && (DOSAGE_PATTERNS.some(pattern => pattern.test(norm)) || MINOR_PATTERNS.some(pattern => pattern.test(norm)))) {
      return "substance_risk";
    }
    if (mentionsSubstance) return "substance_education";
    if (MENTAL_HEALTH_PATTERNS.some(pattern => pattern.test(norm))) return "mental_health";
    return null;
  }

  window.Isis2.SafetyGuardrails = { classify };
})();
