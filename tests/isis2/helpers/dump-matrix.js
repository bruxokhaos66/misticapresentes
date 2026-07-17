"use strict";
// Script utilitário (não é teste automatizado) para capturar a saída
// REAL do Conversation Manager para a matriz de mensagens pedida na
// auditoria da Isis 2.0, e usar isso no relatório em vez de descrever de
// memória. Rodar com: node tests/isis2/helpers/dump-matrix.js
const { loadIsis2, SAMPLE_PRODUCTS } = require("./load-isis2");

const MESSAGES = [
  "Quero um presente até R$ 50.",
  "Quero um presente entre R$ 50 e R$ 100.",
  "Quero algo para relaxar.",
  "Quero montar um altar.",
  "Quero uma essência floral.",
  "Quero um incenso, mas não tenho incensário.",
  "Quero proteção.",
  "Quero um produto barato.",
  "Quero o produto mais caro.",
  "Não quero lavanda.",
  "Não quero incenso.",
  "Já tenho aromatizador.",
  "Quero comprar para outra pessoa.",
  "Quero três produtos com total máximo de R$ 120.",
];

const Isis2 = loadIsis2({ products: SAMPLE_PRODUCTS });

for (const message of MESSAGES) {
  const detection = Isis2.IntentEngine.detect(message);
  const reply = Isis2.ConversationManager.handleUserMessage(message);
  console.log("====================================");
  console.log(`Mensagem: ${message}`);
  console.log(`Intenção: ${detection.primaryIntent ? detection.primaryIntent.id : "(nenhuma)"}`);
  console.log(`Orçamento: min=${detection.budgetMin} max=${detection.budget}`);
  console.log(`Ordenação: ${detection.sortOrder || "(nenhuma)"}`);
  console.log(`Exclusões: ${JSON.stringify(detection.excludeTerms)}`);
  console.log(`Combo: ${JSON.stringify(detection.combo)}`);
  console.log(`Resposta (kind): ${reply.kind}`);
  console.log(`Texto: ${reply.text}`);
  console.log(`Produtos recomendados: ${reply.products.map(p => `${p.id} (R$${p.price})`).join(", ") || "(nenhum)"}`);
  if (reply.reasons) {
    reply.products.forEach(p => console.log(`  Justificativa ${p.id}: ${reply.reasons[p.id]}`));
  }
  if (reply.complements && reply.complements.length) {
    console.log(`Complementos: ${reply.complements.map(c => `${c.product.id} (${c.reason})`).join(", ")}`);
  }
}
