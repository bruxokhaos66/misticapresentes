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
