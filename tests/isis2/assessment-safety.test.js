"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");
const { loadIsis2Escola } = require("./helpers/load-isis2-escola");

test("AssessmentSafety: dúvida comum de conteúdo não é bloqueada", () => {
  const { Isis2 } = loadIsis2Escola();
  assert.equal(Isis2.AssessmentSafety.classify("Pode explicar de novo o que é rapé?"), null);
  assert.equal(Isis2.AssessmentSafety.classify("Não entendi o módulo 2, pode revisar comigo?"), null);
});

test("AssessmentSafety: pergunta de múltipla escolha colada com alternativas é bloqueada", () => {
  const { Isis2 } = loadIsis2Escola();
  const colada = "Qual a origem do rapé?\na) Europa\nb) Amazônia\nc) Ásia";
  assert.equal(Isis2.AssessmentSafety.classify(colada), "direct_answer_request");
});

test("AssessmentSafety: pedido de gabarito é bloqueado mesmo sem colar a questão", () => {
  const { Isis2 } = loadIsis2Escola();
  assert.equal(Isis2.AssessmentSafety.classify("me passa o gabarito da avaliação"), "direct_answer_request");
  assert.equal(Isis2.AssessmentSafety.classify("qual a resposta certa dessa questão"), "direct_answer_request");
});

test("LessonNavigation: só constrói URL para curso válido, nunca aceita entrada arbitrária", () => {
  const { Isis2 } = loadIsis2Escola();
  assert.equal(Isis2.LessonNavigation.isKnownCourse("xamanismo-introducao"), true);
  assert.equal(Isis2.LessonNavigation.isKnownCourse("../../etc/passwd"), false);
  assert.equal(Isis2.LessonNavigation.isKnownCourse("https://evil.example.com"), false);
  assert.equal(Isis2.LessonNavigation.courseUrl("javascript:alert(1)"), null);
  assert.equal(Isis2.LessonNavigation.myCoursesUrl(), "escola-curso.html");
  assert.equal(Isis2.LessonNavigation.catalogUrl(), "escola.html");
});

test("SchoolKnowledge: nunca inventa curso fora do catálogo real exposto por escola.js", () => {
  const { Isis2 } = loadIsis2Escola({ cursos: [{ slug: "curso-teste", titulo: "Curso Teste", tipo: "gratuito", preco: 0, tags: [], resumo: "" }] });
  assert.equal(Isis2.SchoolKnowledge.bySlug("curso-teste").titulo, "Curso Teste");
  assert.equal(Isis2.SchoolKnowledge.bySlug("curso-inexistente"), null);
  assert.equal(Isis2.SchoolKnowledge.listCourses().length, 1);
});

test("SchoolKnowledge: catálogo é congelado em profundidade (array, curso e campos aninhados como tags)", () => {
  const { Isis2 } = loadIsis2Escola({ cursos: [{ slug: "curso-teste", titulo: "Curso Teste", tipo: "gratuito", preco: 0, tags: ["A"], resumo: "" }] });
  // listCourses() devolve uma cópia rasa do array (para o chamador poder
  // filtrar/ordenar livremente sem afetar o catálogo interno), mas cada
  // curso dentro dela é o mesmo objeto congelado internamente.
  const catalogo = Isis2.SchoolKnowledge.listCourses();
  assert.throws(() => { catalogo[0].titulo = "Alterado"; });
  assert.throws(() => { catalogo[0].tags.push("B"); });
  assert.equal(catalogo[0].tags.length, 1);
});

test("SchoolKnowledge: sem window.MISTICA_ESCOLA_CURSOS, admite indisponibilidade em vez de inventar", () => {
  const { Isis2 } = loadIsis2Escola({ cursos: [] });
  delete global.window.MISTICA_ESCOLA_CURSOS;
  assert.equal(Isis2.SchoolKnowledge.hasCatalog(), false);
  assert.deepEqual(Isis2.SchoolKnowledge.listCourses(), []);
});

test("ContextMemory da Escola expira depois do TTL (mesmo sem fechar a aba)", () => {
  const { Isis2 } = loadIsis2Escola();
  Isis2.ContextMemory.updateSchool({ courseOfInterest: "xamanismo-introducao" });
  const fresh = Isis2.ContextMemory.getSchool();
  assert.equal(fresh.courseOfInterest, "xamanismo-introducao");

  // Simula o relógio avançando além do TTL (45min) sem depender de cache
  // interno de módulo.
  const realNow = Date.now;
  Date.now = () => realNow() + 60 * 60 * 1000;
  try {
    const expired = Isis2.ContextMemory.getSchool();
    assert.equal(expired.courseOfInterest, null);
  } finally {
    Date.now = realNow;
  }
});

test("ContextMemory da Escola limita presentedCourseIds a 10 entradas", () => {
  const { Isis2 } = loadIsis2Escola();
  for (let i = 0; i < 15; i += 1) Isis2.ContextMemory.addPresentedCourse(`curso-${i}`);
  assert.equal(Isis2.ContextMemory.getSchool().presentedCourseIds.length, 10);
});

// Login/logout na mesma aba (sem recarregar a página) troca a sessão do
// navegador, mas StudentContext.me() cacheia o resultado em memória —
// escola.js/escola-curso.js chamam estas duas funções em login/logout
// para nunca misturar contexto de conversa/identidade entre contas
// diferentes na mesma aba (ver escola.js#resetIsis2SchoolIdentity).
test("StudentContext.resetCache() força uma nova consulta a /api/alunos/me (não fica preso ao aluno anterior)", async () => {
  let chamadas = 0;
  const fetchImpl = async () => {
    chamadas += 1;
    return { ok: true, status: 200, json: async () => ({ nome: `Aluno ${chamadas}` }) };
  };
  const { Isis2 } = loadIsis2Escola({ fetchImpl });
  const primeiro = await Isis2.StudentContext.me();
  const segundoSemReset = await Isis2.StudentContext.me();
  assert.equal(chamadas, 1, "segunda chamada deveria usar o cache");
  assert.deepEqual(segundoSemReset, primeiro);

  Isis2.StudentContext.resetCache();
  const terceiro = await Isis2.StudentContext.me();
  assert.equal(chamadas, 2, "depois de resetCache(), deve consultar a API de novo");
  assert.equal(terceiro.nome, "Aluno 2");
});

test("ContextMemory.resetSchool() limpa a memória da Escola sem depender do TTL", () => {
  const { Isis2 } = loadIsis2Escola();
  Isis2.ContextMemory.updateSchool({ courseOfInterest: "xamanismo-introducao", studentLevel: "iniciante" });
  Isis2.ContextMemory.addPresentedCourse("xamanismo-introducao");
  assert.equal(Isis2.ContextMemory.getSchool().courseOfInterest, "xamanismo-introducao");

  Isis2.ContextMemory.resetSchool();
  const limpo = Isis2.ContextMemory.getSchool();
  assert.equal(limpo.courseOfInterest, null);
  assert.equal(limpo.studentLevel, null);
  assert.deepEqual(limpo.presentedCourseIds, []);
});
