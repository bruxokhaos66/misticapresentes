"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");

delete require.cache[require.resolve("../../isis-conteudo-admin.js")];
const IsisConteudoAdmin = require("../../isis-conteudo-admin.js");

test("escapeHtml neutraliza marcação e atributos perigosos", () => {
  const entrada = `<img src=x onerror="alert(1)"> & "aspas" 'simples'`;
  const saida = IsisConteudoAdmin.escapeHtml(entrada);
  assert.equal(saida.includes("<img"), false);
  assert.equal(saida.includes('"'), false);
  assert.ok(saida.includes("&lt;img"));
  assert.ok(saida.includes("&amp;"));
});

test("escapeHtml trata valores nulos/indefinidos sem lançar erro", () => {
  assert.equal(IsisConteudoAdmin.escapeHtml(null), "");
  assert.equal(IsisConteudoAdmin.escapeHtml(undefined), "");
});

test("sanitizeHashtagsInput remove marcação HTML digitada e colapsa espaços", () => {
  const entrada = "  #ritual   <script>alert(1)</script>#luz  ";
  assert.equal(IsisConteudoAdmin.sanitizeHashtagsInput(entrada), "#ritual alert(1)#luz");
});

test("formatDataReferencia converte AAAA-MM-DD para DD/MM/AAAA", () => {
  assert.equal(IsisConteudoAdmin.formatDataReferencia("2026-07-17"), "17/07/2026");
});

test("formatDataReferencia escapa entrada que não bate o formato esperado", () => {
  assert.equal(IsisConteudoAdmin.formatDataReferencia("<script>"), "&lt;script&gt;");
});

test("statusLabel e tipoLabel traduzem os valores conhecidos", () => {
  assert.equal(IsisConteudoAdmin.statusLabel("rascunho"), "Rascunho");
  assert.equal(IsisConteudoAdmin.statusLabel("publicado"), "Publicado");
  assert.equal(IsisConteudoAdmin.tipoLabel("bom_dia"), "Bom dia");
  assert.equal(IsisConteudoAdmin.tipoLabel("produto_do_dia"), "Produto do dia");
});

test("transições de status controlam quais ações ficam disponíveis", () => {
  const rascunho = { status: "rascunho" };
  const aprovado = { status: "aprovado" };
  const rejeitado = { status: "rejeitado" };
  const publicado = { status: "publicado" };

  assert.equal(IsisConteudoAdmin.podeEditar(rascunho), true);
  assert.equal(IsisConteudoAdmin.podeEditar(aprovado), false);

  assert.equal(IsisConteudoAdmin.podeAprovar(rascunho), true);
  assert.equal(IsisConteudoAdmin.podeAprovar(aprovado), false);

  assert.equal(IsisConteudoAdmin.podeRejeitar(rascunho), true);
  assert.equal(IsisConteudoAdmin.podeRejeitar(aprovado), true);
  assert.equal(IsisConteudoAdmin.podeRejeitar(publicado), false);

  assert.equal(IsisConteudoAdmin.podePublicarManual(aprovado), true);
  assert.equal(IsisConteudoAdmin.podePublicarManual(rascunho), false);
  assert.equal(IsisConteudoAdmin.podePublicarManual(rejeitado), false);
});
