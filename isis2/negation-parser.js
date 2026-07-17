// Isis 2.0 — Negation Parser (Fase 2.1 — Refinamento da Especialista da
// Mística Escola).
//
// Interpreta negações, exclusões e preferências em pedidos educacionais,
// sem depender apenas da palavra "não". Devolve uma estrutura fechada,
// limitada e validada — nunca o texto integral da conversa. É consumido
// pelo School Intent Engine e pelo Course Recommendation Engine só quando
// window.Isis2.SchoolMode.isRefinementActive() é verdadeiro; com a flag
// desligada, este módulo nem é carregado (ver isis2-loader.js).
(() => {
  window.Isis2 = window.Isis2 || {};
  if (window.Isis2.NegationParser) return;

  function normalize(value) {
    return String(value || "")
      .normalize("NFD")
      .replace(/[̀-ͯ]/g, "")
      .toLowerCase()
      .trim();
  }

  const MAX_LIST = 10;

  // Temas reconhecidos e suas variações — mesmo vocabulário do School
  // Intent Engine (mantido aqui separado para não criar dependência
  // circular entre os dois módulos; ambos são "irmãos" do domínio Escola).
  const THEMES = [
    { term: "xamanismo", keywords: ["xamanismo", "xamanica", "xamânica", "xamanismos", "xamanizmo", "xamanisco", "xaman"] },
    { term: "cristais", keywords: ["cristais", "cristal", "cristalzinho", "pedras", "kristais", "cristias", "crista"] },
    { term: "aromaterapia", keywords: ["aromaterapia", "aromaterapa", "aromoterapia", "aromoterapa", "óleos essenciais", "oleos essenciais", "aromater"] },
    { term: "rape", keywords: ["rape", "rapé", "rapes"] },
    { term: "ayahuasca", keywords: ["ayahuasca", "aiuasca", "daime"] },
    { term: "cosmologia", keywords: ["universo", "cosmologia", "origem do universo", "big bang"] },
    { term: "medicinas-da-floresta", keywords: ["medicina da floresta", "medicinas da floresta", "medicina floresta"] },
  ];

  const LEVELS = [
    { term: "iniciante", keywords: ["iniciante", "basico", "básico", "introdutorio", "introdutório", "do zero", "comecando", "começando"] },
    { term: "avancado", keywords: ["avancado", "avançado", "avancada", "avançada"] },
  ];

  // Marcadores de negação/exclusão — muito mais amplos do que só "não".
  // Cada marcador delimita uma "zona negada": os temas/níveis encontrados
  // depois dele (até o próximo marcador de negação, conjunção "mas"/"só
  // que", ou fim da frase) entram em excludeTopics/excludeLevels.
  const NEGATION_MARKERS = [
    "nao quero", "não quero", "nao gosto", "não gosto", "nao tenho interesse", "não tenho interesse",
    "nao preciso", "não preciso", "nao me recomende", "não me recomende", "nao me indique", "não me indique",
    "sem ", "evite", "evita", "menos ", "exceto", "tirando", "fora ", "nao ", "não ",
  ];

  // "já fiz" / "já concluí" / "já tenho" / "não preciso repetir": sinaliza
  // curso concluído/adquirido, não necessariamente um tema recusado — vira
  // completedCourseIds (por termo de tema, resolvido pelo chamador contra
  // o catálogo real) em vez de excludeTopics.
  const COMPLETED_MARKERS = [
    "ja fiz", "já fiz", "ja conclui", "já concluí", "ja terminei", "já terminei",
    "nao preciso repetir", "não preciso repetir", "ja tenho", "já tenho",
  ];

  // "quero continuar de onde parei" vs. "quero começar do zero".
  const RESUME_PATTERNS = [/continuar de onde parei/, /retomar de onde parei/, /continuar meus estudos/, /de onde eu parei/];
  const RESTART_PATTERNS = [/comecar do zero/, /começar do zero/, /do zero/, /nunca estudei/];

  // "qualquer um, exceto X" / "qualquer curso, tirando X".
  const EXCEPT_PATTERNS = [/qualquer\s+(um|curso)[^.!?]*(exceto|tirando|fora)\s+([a-zà-ÿ\s]+)/i];

  function splitClauses(norm) {
    // Conjunções que costumam separar uma preferência positiva de uma
    // negativa dentro da mesma frase ("quero X, mas não quero Y").
    return norm.split(/,|\bmas\b|\bporem\b|\bporém\b|\bso que\b|\bsó que\b|\be\b(?=\s*(?:nao|não|sem|evite|evita|menos|exceto|tirando|fora))/);
  }

  function findMarkerIndex(clause) {
    for (const marker of NEGATION_MARKERS) {
      const idx = clause.indexOf(marker);
      if (idx !== -1) return { idx, marker };
    }
    return null;
  }

  function matchThemesIn(text, list) {
    return list.filter(entry => entry.keywords.some(keyword => text.includes(normalize(keyword)))).map(entry => entry.term);
  }

  function dedupe(list) {
    return Array.from(new Set(list)).slice(0, MAX_LIST);
  }

  // Estrutura de saída, sempre com todos os campos presentes (arrays
  // limitados a MAX_LIST itens), nunca com texto integral da conversa —
  // só termos normalizados de um vocabulário fechado (THEMES/LEVELS) ou
  // slugs de curso já validados pelo chamador.
  function emptyResult() {
    return {
      includeTopics: [],
      excludeTopics: [],
      includeLevels: [],
      excludeLevels: [],
      excludeCourseIds: [],
      completedCourseIds: [],
      wantsRestart: false,
      wantsResume: false,
    };
  }

  function parse(text) {
    const norm = normalize(text);
    const result = emptyResult();
    if (!norm) return result;

    result.wantsResume = RESUME_PATTERNS.some(p => p.test(norm));
    result.wantsRestart = RESTART_PATTERNS.some(p => p.test(norm));

    // "já fiz o curso básico" etc.: marca o(s) tema(s)/nível(is) mencionados
    // no trecho como "já cursados" — o chamador decide se isso vira
    // completedCourseIds (resolvendo contra o catálogo) ou excludeLevels
    // (ex.: "já fiz o básico, não quero repetir" -> nível excluído).
    const hasCompletedMarker = COMPLETED_MARKERS.some(marker => norm.includes(marker));

    const clauses = splitClauses(norm).map(c => c.trim()).filter(Boolean);
    const positiveTopics = [];
    const negatedTopics = [];
    const positiveLevels = [];
    const negatedLevels = [];

    clauses.forEach(clause => {
      const marker = findMarkerIndex(clause);
      if (marker) {
        const negatedPart = clause.slice(marker.idx + marker.marker.length);
        const positivePart = clause.slice(0, marker.idx);
        negatedTopics.push(...matchThemesIn(negatedPart, THEMES));
        negatedLevels.push(...matchThemesIn(negatedPart, LEVELS));
        positiveTopics.push(...matchThemesIn(positivePart, THEMES));
        positiveLevels.push(...matchThemesIn(positivePart, LEVELS));
      } else if (hasCompletedMarker && COMPLETED_MARKERS.some(m => clause.includes(m))) {
        // Trecho de "já fiz X": tema/nível mencionado é "concluído", não
        // necessariamente recusado — tratado à parte abaixo.
      } else {
        positiveTopics.push(...matchThemesIn(clause, THEMES));
        positiveLevels.push(...matchThemesIn(clause, LEVELS));
      }
    });

    // "qualquer um, exceto cristais": captura o termo pós "exceto/tirando/fora"
    // mesmo sem marcador de negação clássico antes dele.
    EXCEPT_PATTERNS.forEach(pattern => {
      const match = norm.match(pattern);
      if (match && match[3]) negatedTopics.push(...matchThemesIn(match[3], THEMES));
    });

    // "já fiz o básico, não quero repetir": trecho com marcador de
    // conclusão vira excludeLevels/excludeTopics também (não repetir =
    // excluir da próxima recomendação), além de completedCourseIds ficar a
    // cargo do chamador (que resolve contra o catálogo real).
    if (hasCompletedMarker) {
      clauses.forEach(clause => {
        if (COMPLETED_MARKERS.some(m => clause.includes(m))) {
          negatedTopics.push(...matchThemesIn(clause, THEMES));
          negatedLevels.push(...matchThemesIn(clause, LEVELS));
        }
      });
    }

    // Um termo nunca fica em include e exclude ao mesmo tempo — a
    // exclusão (mais restritiva, e a que carrega risco de recomendação
    // indevida se ignorada) sempre vence o conflito.
    result.excludeTopics = dedupe(negatedTopics);
    result.excludeLevels = dedupe(negatedLevels);
    result.includeTopics = dedupe(positiveTopics.filter(t => !result.excludeTopics.includes(t)));
    result.includeLevels = dedupe(positiveLevels.filter(l => !result.excludeLevels.includes(l)));

    return result;
  }

  // Resolve termos de tema/nível "concluídos" (marcados por COMPLETED_MARKERS)
  // contra o catálogo real para produzir completedCourseIds — nunca
  // inventa um ID de curso que não exista no catálogo.
  function resolveCompletedCourseIds(text, catalog) {
    const norm = normalize(text);
    const hasCompletedMarker = COMPLETED_MARKERS.some(marker => norm.includes(marker));
    if (!hasCompletedMarker || !Array.isArray(catalog)) return [];
    const themeTerms = matchThemesIn(norm, THEMES);
    const levelTerms = matchThemesIn(norm, LEVELS);
    if (!themeTerms.length && !levelTerms.length) return [];
    const matches = catalog.filter(curso => {
      const haystack = normalize(`${curso.titulo} ${(curso.tags || []).join(" ")} ${curso.resumo || ""}`);
      const themeHit = themeTerms.some(term => THEMES.find(t => t.term === term)?.keywords.some(k => haystack.includes(normalize(k))));
      const levelHit = levelTerms.some(term => LEVELS.find(l => l.term === term)?.keywords.some(k => haystack.includes(normalize(k))));
      return themeHit || levelHit;
    });
    return dedupe(matches.map(c => c.slug));
  }

  window.Isis2.NegationParser = { parse, resolveCompletedCourseIds, THEMES, LEVELS };
})();
