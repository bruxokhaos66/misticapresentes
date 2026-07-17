"use strict";
// Carrega os módulos da Isis 2.0 (scripts clássicos, não-módulo, iguais
// ao padrão do restante do site) num ambiente Node mínimo, simulando
// `window`, `sessionStorage`, `products`, `getStock` e `currency` como o
// navegador faria. Usado pelos testes unitários em tests/isis2/*.test.js.

function createMemoryStorage() {
  const store = new Map();
  return {
    getItem: key => (store.has(key) ? store.get(key) : null),
    setItem: (key, value) => store.set(key, String(value)),
    removeItem: key => store.delete(key),
    clear: () => store.clear(),
  };
}

function loadIsis2({ products = [], stock = null } = {}) {
  delete require.cache[require.resolve("../../../isis2/product-knowledge.js")];
  delete require.cache[require.resolve("../../../isis2/intent-engine.js")];
  delete require.cache[require.resolve("../../../isis2/recommendation-engine.js")];
  delete require.cache[require.resolve("../../../isis2/context-memory.js")];
  delete require.cache[require.resolve("../../../isis2/analytics.js")];
  delete require.cache[require.resolve("../../../isis2/cart-assistant.js")];
  delete require.cache[require.resolve("../../../isis2/ai-providers.js")];
  delete require.cache[require.resolve("../../../isis2/conversation-manager.js")];

  global.window = global;
  global.window.Isis2 = undefined;
  global.window.sessionStorage = createMemoryStorage();
  global.window.misticaTrack = undefined;
  global.window.misticaSiteConfig = {};
  global.products = products;
  global.getStock = stock || (id => {
    const product = products.find(item => item.id === id);
    return product ? Number(product.stock || 0) : 0;
  });
  global.currency = {
    format: value => `R$ ${Number(value || 0).toFixed(2).replace(".", ",")}`,
  };
  global.cart = [];
  global.window.cart = global.cart;
  global.window.addToCart = productId => {
    const product = products.find(item => item.id === productId);
    if (!product) return;
    const existing = global.cart.find(item => item.id === productId);
    if (existing) existing.qty += 1;
    else global.cart.push({ id: product.id, name: product.name, price: product.price, qty: 1 });
  };
  global.window.removeFromCart = productId => {
    global.cart = global.cart.filter(item => item.id !== productId);
    global.window.cart = global.cart;
  };
  global.window.products = products;

  require("../../../isis2/product-knowledge.js");
  require("../../../isis2/intent-engine.js");
  require("../../../isis2/recommendation-engine.js");
  require("../../../isis2/context-memory.js");
  require("../../../isis2/analytics.js");
  require("../../../isis2/cart-assistant.js");
  require("../../../isis2/ai-providers.js");
  require("../../../isis2/conversation-manager.js");

  return global.window.Isis2;
}

const SAMPLE_PRODUCTS = [
  { id: "incenso-natural", name: "Incensos Naturais", category: "Aromas e proteção", description: "Incensos para oração, limpeza do ambiente, acolhimento e boas energias.", price: 12.9, stock: 30, icon: "🌿" },
  { id: "vela-ritualistica", name: "Velas de Intenção", category: "Fé e luz", description: "Velas para momentos de fé, pedidos, gratidão, decoração e conexão espiritual.", price: 18.0, stock: 24, icon: "🕯️" },
  { id: "pedra-energetica", name: "Pedras e Cristais", category: "Proteção e equilíbrio", description: "Pedras selecionadas para proteção, equilíbrio, presente e cuidado energético.", price: 24.9, stock: 18, icon: "💎" },
  { id: "banho-ervas", name: "Banhos de Ervas", category: "Ervas e limpeza", description: "Preparos especiais para renovação, descarrego, harmonia e bem-estar espiritual.", price: 16.5, stock: 20, icon: "🍃" },
  { id: "aromatizador", name: "Aromatizadores Via Aroma", category: "Casa perfumada", description: "Essências e aromas para deixar o lar mais leve, acolhedor e agradável.", price: 29.9, stock: 16, icon: "✨" },
  { id: "incensario", name: "Incensários Decorativos", category: "Decoração mística", description: "Peças bonitas e funcionais para usar com incensos e compor ambientes especiais.", price: 35.0, stock: 12, icon: "🔮" },
  { id: "artigo-fe", name: "Artigos de Fé e Proteção", category: "Fé e bênçãos", description: "Itens para presentear, abençoar ambientes e fortalecer momentos de oração e esperança.", price: 32.9, stock: 14, icon: "🙏" },
  { id: "presente-mistico", name: "Kit Presente Especial", category: "Kits e presentes", description: "Combinação especial com aromas, velas, pedras e artigos escolhidos com carinho.", price: 59.9, stock: 8, icon: "🎁" },
];

module.exports = { loadIsis2, SAMPLE_PRODUCTS, createMemoryStorage };
