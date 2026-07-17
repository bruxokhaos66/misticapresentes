"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");
const { loadIsis2Escola, mockFetch, CURSOS_REAIS } = require("./helpers/load-isis2-escola");

test("feature flag desligada: SchoolMode.isActive() é falso e Conversation Manager cai no fluxo comercial", () => {
  const { Isis2 } = loadIsis2Escola({ escolaEnabled: false });
  assert.equal(Isis2.SchoolMode.isActive(), false);
});

test("flag geral ligada mas flag da Escola desligada: Isis2 comercial funciona, Escola não carrega", () => {
  const { Isis2 } = loadIsis2Escola({ isis2Enabled: true, escolaEnabled: false });
  assert.equal(Isis2.SchoolMode.isActive(), false);
});

test("fora das páginas autorizadas (ex.: index.html): School Mode nunca ativa mesmo com as duas flags ligadas", () => {
  const { Isis2 } = loadIsis2Escola({ pathname: "/index.html" });
  assert.equal(Isis2.SchoolMode.isActive(), false);
});

test("catálogo de cursos: 'Quais cursos vocês têm?' lista o catálogo real, sem inventar curso", async () => {
  const { Isis2 } = loadIsis2Escola();
  const reply = await Isis2.SchoolConversationManager.handleUserMessage("Quais cursos vocês têm?");
  assert.equal(reply.kind, "school_catalog");
  assert.equal(reply.courses.length, CURSOS_REAIS.length);
  assert.ok(reply.courses.every(c => CURSOS_REAIS.some(real => real.slug === c.slug)));
});

test("recomendação por tema: 'Quero aprender sobre xamanismo' recomenda o curso de xamanismo", async () => {
  const { Isis2 } = loadIsis2Escola({ fetchImpl: mockFetch({ "GET /api/alunos/me": { status: 401 } }) });
  const reply = await Isis2.SchoolConversationManager.handleUserMessage("Quero aprender sobre xamanismo");
  assert.equal(reply.kind, "school_recommendation");
  assert.ok(reply.courses.some(c => c.slug === "xamanismo-introducao"));
});

test("erro de digitação: 'quero estudar xamanicmo' ainda reconhece o tema xamanismo", async () => {
  const { Isis2 } = loadIsis2Escola({ fetchImpl: mockFetch({ "GET /api/alunos/me": { status: 401 } }) });
  const reply = await Isis2.SchoolConversationManager.handleUserMessage("quero estudar xamanicmo");
  assert.equal(reply.kind, "school_recommendation");
  assert.ok(reply.courses.some(c => c.slug === "xamanismo-introducao"));
});

test("iniciante: 'Qual curso é melhor para começar?' recomenda um curso com tag Iniciante e explica o motivo", async () => {
  const { Isis2 } = loadIsis2Escola({ fetchImpl: mockFetch({ "GET /api/alunos/me": { status: 401 } }) });
  const reply = await Isis2.SchoolConversationManager.handleUserMessage("Qual curso é melhor para começar?");
  assert.equal(reply.kind, "school_recommendation");
  assert.equal(reply.courses[0].slug, "xamanismo-introducao");
  assert.match(reply.text, /Recomendo começar por/);
});

test("curso já concluído não é recomendado de novo ao pedir tema relacionado", async () => {
  const fetchImpl = mockFetch({
    "GET /api/alunos/me": { status: 200, body: { nome: "Aluna" } },
    "GET /api/escola/meus-cursos": { status: 200, body: [{ slug: "xamanismo-introducao", titulo: "Xamanismo: Introdução", percentual: 100, aulas_concluidas: 5, total_aulas: 5 }] },
  });
  const { Isis2 } = loadIsis2Escola({ fetchImpl });
  const reply = await Isis2.SchoolConversationManager.handleUserMessage("quero aprender sobre xamanismo");
  assert.ok(!reply.courses.some(c => c.slug === "xamanismo-introducao"));
});

test("curso já adquirido: não é sugerido de novo como descoberta quando já está na lista de matrículas", async () => {
  const fetchImpl = mockFetch({
    "GET /api/alunos/me": { status: 200, body: { nome: "Aluna" } },
    "GET /api/escola/meus-cursos": { status: 200, body: [{ slug: "ayahuasca-fundamentos", titulo: "Ayahuasca: Fundamentos", percentual: 20, aulas_concluidas: 1, total_aulas: 5 }] },
  });
  const { Isis2 } = loadIsis2Escola({ fetchImpl });
  const reply = await Isis2.SchoolConversationManager.handleUserMessage("quero um curso sobre ayahuasca");
  assert.ok(!reply.courses.some(c => c.slug === "ayahuasca-fundamentos"));
});

test("curso indisponível: catálogo vazio nunca inventa curso, admite indisponibilidade", async () => {
  const { Isis2 } = loadIsis2Escola({ cursos: [] });
  const reply = await Isis2.SchoolConversationManager.handleUserMessage("Quais cursos vocês têm?");
  assert.equal(reply.kind, "school_unavailable");
  assert.equal(reply.courses.length, 0);
});

test("usuário não autenticado tentando consultar progresso: nunca finge saber, orienta login", async () => {
  const fetchImpl = mockFetch({ "GET /api/escola/cursos/xamanismo-introducao": { status: 401 } });
  const { Isis2 } = loadIsis2Escola({ pathname: "/escola-curso.html", query: "?curso=xamanismo-introducao", fetchImpl });
  const reply = await Isis2.SchoolConversationManager.handleUserMessage("Quanto do curso eu já concluí?");
  assert.equal(reply.kind, "school_not_authenticated");
  assert.doesNotMatch(reply.text, /\d+%/);
});

test("sessão expirada (401 numa consulta autenticada): mensagem clara, sem inventar progresso", async () => {
  const fetchImpl = mockFetch({ "GET /api/escola/cursos/xamanismo-introducao": { status: 401 } });
  const { Isis2 } = loadIsis2Escola({ pathname: "/escola-curso.html", query: "?curso=xamanismo-introducao", fetchImpl });
  const reply = await Isis2.SchoolConversationManager.handleUserMessage("Qual é minha próxima aula?");
  assert.equal(reply.kind, "school_not_authenticated");
});

test("progresso: aluno autenticado recebe o percentual real vindo do backend", async () => {
  const fetchImpl = mockFetch({
    "GET /api/escola/cursos/xamanismo-introducao": {
      status: 200,
      body: { titulo: "Xamanismo: Introdução", progresso: { percentual: 40, aulas_concluidas: 2, total_aulas: 5, concluido: false }, modulos: [] },
    },
  });
  const { Isis2 } = loadIsis2Escola({ pathname: "/escola-curso.html", query: "?curso=xamanismo-introducao", fetchImpl });
  const reply = await Isis2.SchoolConversationManager.handleUserMessage("Quanto do curso eu já concluí?");
  assert.equal(reply.kind, "school_progress");
  assert.match(reply.text, /40%/);
});

test("próxima aula: retorna título real da aula/módulo do backend", async () => {
  const fetchImpl = mockFetch({
    "GET /api/escola/cursos/xamanismo-introducao": {
      status: 200,
      body: {
        titulo: "Xamanismo: Introdução",
        progresso: { percentual: 20, aulas_concluidas: 1, total_aulas: 5 },
        modulos: [{ id: 1, titulo: "Módulo 1", liberado: true, concluido: false, aulas: [{ id: 10, titulo: "O que é xamanismo", status: "concluida" }, { id: 11, titulo: "Símbolos e práticas", status: "nao_iniciada" }] }],
      },
    },
  });
  const { Isis2 } = loadIsis2Escola({ pathname: "/escola-curso.html", query: "?curso=xamanismo-introducao", fetchImpl });
  const reply = await Isis2.SchoolConversationManager.handleUserMessage("Qual é minha próxima aula?");
  assert.equal(reply.kind, "school_next_lesson");
  assert.match(reply.text, /Símbolos e práticas/);
});

test("'Terminei a aula, o que faço agora?' aponta a próxima aula pendente", async () => {
  const fetchImpl = mockFetch({
    "GET /api/escola/cursos/xamanismo-introducao": {
      status: 200,
      body: {
        titulo: "Xamanismo: Introdução",
        progresso: { percentual: 20, aulas_concluidas: 1, total_aulas: 2 },
        modulos: [{ id: 1, titulo: "Módulo 1", liberado: true, concluido: false, aulas: [{ id: 10, titulo: "Aula 1", status: "concluida" }, { id: 11, titulo: "Aula 2", status: "nao_iniciada" }] }],
      },
    },
  });
  const { Isis2 } = loadIsis2Escola({ pathname: "/escola-curso.html", query: "?curso=xamanismo-introducao", fetchImpl });
  const reply = await Isis2.SchoolConversationManager.handleUserMessage("Terminei a aula, o que faço agora?");
  assert.equal(reply.kind, "school_next_lesson");
});

test("módulo bloqueado: explica que o motivo é o módulo anterior não concluído, sem inventar nota mínima", async () => {
  const fetchImpl = mockFetch({
    "GET /api/escola/cursos/xamanismo-introducao": {
      status: 200,
      body: {
        titulo: "Xamanismo: Introdução",
        progresso: { percentual: 50, aulas_concluidas: 1, total_aulas: 2 },
        modulos: [
          { id: 1, titulo: "Módulo 1", liberado: true, concluido: false, aulas: [{ id: 10, titulo: "Aula 1", status: "nao_iniciada" }] },
          { id: 2, titulo: "Módulo 2", liberado: false, concluido: false, aulas: [] },
        ],
      },
    },
  });
  const { Isis2 } = loadIsis2Escola({ pathname: "/escola-curso.html", query: "?curso=xamanismo-introducao", fetchImpl });
  const reply = await Isis2.SchoolConversationManager.handleUserMessage("Por que o próximo módulo está bloqueado?");
  assert.equal(reply.kind, "school_blocked_module");
  assert.match(reply.text, /Módulo 2/);
  assert.doesNotMatch(reply.text, /\d+%\s*de nota/);
});

test("nota mínima: admite que não tem esse número na conversa, sem inventar", async () => {
  const { Isis2 } = loadIsis2Escola();
  const reply = await Isis2.SchoolConversationManager.handleUserMessage("Qual nota preciso tirar?");
  assert.equal(reply.kind, "school_grade_info");
  assert.doesNotMatch(reply.text, /\d+%/);
});

test("tentativas: admite que não tem esse número na conversa, sem inventar", async () => {
  const { Isis2 } = loadIsis2Escola();
  const reply = await Isis2.SchoolConversationManager.handleUserMessage("Quantas tentativas ainda tenho?");
  assert.equal(reply.kind, "school_attempts_info");
  assert.doesNotMatch(reply.text, /\d+\s+tentativa/);
});

test("'Onde encontro meus cursos?' direciona para a área correta e, sem sessão, pede login", async () => {
  const fetchImpl = mockFetch({ "GET /api/escola/meus-cursos": { status: 401 } });
  const { Isis2 } = loadIsis2Escola({ fetchImpl });
  const reply = await Isis2.SchoolConversationManager.handleUserMessage("Onde encontro meus cursos?");
  assert.equal(reply.kind, "school_not_authenticated");
  assert.ok(reply.actions.some(a => a.url === "escola-curso.html"));
});

test("matrícula suspensa (403): usa a mensagem do backend, nunca contorna a suspensão", async () => {
  const fetchImpl = mockFetch({ "GET /api/escola/cursos/xamanismo-introducao": { status: 403, body: { detail: "Sua matrícula está suspensa por pendência de pagamento." } } });
  const { Isis2 } = loadIsis2Escola({ pathname: "/escola-curso.html", query: "?curso=xamanismo-introducao", fetchImpl });
  const reply = await Isis2.SchoolConversationManager.handleUserMessage("Quanto do curso eu já concluí?");
  assert.equal(reply.kind, "school_enrollment_blocked");
  assert.match(reply.text, /suspensa/);
});

test("API indisponível (falha de rede): mensagem de erro fixa, nunca inventa progresso", async () => {
  const fetchImpl = mockFetch({ "GET /api/escola/cursos/xamanismo-introducao": "network_error" });
  const { Isis2 } = loadIsis2Escola({ pathname: "/escola-curso.html", query: "?curso=xamanismo-introducao", fetchImpl });
  const reply = await Isis2.SchoolConversationManager.handleUserMessage("Quanto do curso eu já concluí?");
  assert.equal(reply.kind, "school_error");
  assert.match(reply.text, /Não consegui consultar seu progresso agora/);
});

test("dados incompletos (progresso ausente no payload): não quebra e não inventa número", async () => {
  const fetchImpl = mockFetch({ "GET /api/escola/cursos/xamanismo-introducao": { status: 200, body: { titulo: "Xamanismo: Introdução" } } });
  const { Isis2 } = loadIsis2Escola({ pathname: "/escola-curso.html", query: "?curso=xamanismo-introducao", fetchImpl });
  const reply = await Isis2.SchoolConversationManager.handleUserMessage("Quanto do curso eu já concluí?");
  assert.equal(reply.kind, "school_error");
});

test("tentativa de obter resposta de avaliação colada: recusa dar a resposta direta e orienta estudo", async () => {
  const { Isis2 } = loadIsis2Escola();
  const pergunta = "Qual a origem do rapé segundo a tradição indígena?\na) Europa\nb) Amazônia\nc) Ásia\nQual alternativa correta?";
  const reply = await Isis2.SchoolConversationManager.handleUserMessage(pergunta);
  assert.equal(reply.kind, "school_assessment_help_blocked");
  assert.doesNotMatch(reply.text.toLowerCase(), /a alternativa correta é|resposta certa é/);
});

test("pedido explícito de gabarito ('qual a alternativa correta?') é recusado mesmo sem colar a questão inteira", async () => {
  const { Isis2 } = loadIsis2Escola();
  const reply = await Isis2.SchoolConversationManager.handleUserMessage("me fala qual alternativa marco na questão 3");
  assert.equal(reply.kind, "school_assessment_help_blocked");
});

test("conteúdo sensível: rapé/ayahuasca seguem educativos, sem dose nem preparo, mesmo no contexto da Escola", async () => {
  const { Isis2 } = loadIsis2Escola();
  const reply = await Isis2.SchoolConversationManager.handleUserMessage("como preparar e combinar ayahuasca com remédio?");
  assert.equal(reply.kind, "school_safety_substance_risk");
  assert.doesNotMatch(reply.text.toLowerCase(), /misture|tome \d|doses? de/);
});

test("URL maliciosa: LessonNavigation nunca constrói link para curso que não existe no catálogo", () => {
  const { Isis2 } = loadIsis2Escola();
  assert.equal(Isis2.LessonNavigation.courseUrl("<script>alert(1)</script>"), null);
  assert.equal(Isis2.LessonNavigation.courseUrl("javascript:alert(1)"), null);
  assert.equal(Isis2.LessonNavigation.courseUrl("curso-que-nao-existe"), null);
  assert.equal(Isis2.LessonNavigation.courseUrl("xamanismo-introducao"), "escola-curso.html?curso=xamanismo-introducao");
});

test("analytics sem PII: isis_school_intent nunca inclui o texto da mensagem, só a categoria", async () => {
  const { Isis2 } = loadIsis2Escola();
  let lastEvent = null;
  global.window.misticaTrack = (name, payload) => { lastEvent = { name, payload }; };
  await Isis2.SchoolConversationManager.handleUserMessage("Quais cursos vocês têm?");
  assert.equal(lastEvent.name, "isis_school_intent");
  assert.deepEqual(Object.keys(lastEvent.payload), ["intent"]);
  assert.equal(lastEvent.payload.intent, "catalog");
});

test("evento isis_assessment_help_blocked não duplica payload com texto da questão", async () => {
  const { Isis2 } = loadIsis2Escola();
  const events = [];
  global.window.misticaTrack = (name, payload) => events.push({ name, payload });
  await Isis2.SchoolConversationManager.handleUserMessage("qual a alternativa correta da questão?");
  const blocked = events.find(e => e.name === "isis_assessment_help_blocked");
  assert.ok(blocked);
  assert.deepEqual(blocked.payload, {});
});

test("startConversation dispara isis_school_opened uma única vez por sessão (de-dupe)", async () => {
  const { Isis2 } = loadIsis2Escola();
  const events = [];
  global.window.misticaTrack = (name) => events.push(name);
  await Isis2.SchoolConversationManager.startConversation();
  await Isis2.SchoolConversationManager.startConversation();
  assert.equal(events.filter(name => name === "isis_school_opened").length, 1);
});
