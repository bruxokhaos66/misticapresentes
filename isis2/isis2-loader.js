// Isis 2.0 — loader.
//
// Único script sempre baixado nas páginas públicas (poucas centenas de
// bytes). Lê a feature flag síncrona de site-config.js e só injeta o
// resto da Isis 2.0 (CSS + 10 módulos + widget + bootstrap, ~60KB de JS)
// quando window.misticaSiteConfig.isis2.enabled === true. Com a flag
// desligada (default), nenhum outro arquivo da Isis 2.0 é requisitado —
// zero custo de rede/parse além deste loader.
(() => {
  if (window.__MISTICA_ISIS2_LOADER__) return;
  window.__MISTICA_ISIS2_LOADER__ = true;

  if (window.misticaSiteConfig?.isis2?.enabled !== true) return;

  const VERSION = "20260717-isis2-fase1";
  const BASE = "isis2/";
  const MODULES = [
    "product-knowledge.js",
    "intent-engine.js",
    "safety-guardrails.js",
    "recommendation-engine.js",
    "context-memory.js",
    "analytics.js",
    "cart-assistant.js",
    "ai-providers.js",
    "conversation-manager.js",
    "widget.js",
    "isis2-bootstrap.js",
  ];

  const link = document.createElement("link");
  link.rel = "stylesheet";
  link.href = `${BASE}widget.css?v=${VERSION}`;
  document.head.appendChild(link);

  // async=false preserva a ordem de execução entre scripts inseridos
  // dinamicamente (por padrão eles rodam async e fora de ordem) — sem
  // isso, conversation-manager.js poderia rodar antes de
  // product-knowledge.js estar registrado em window.Isis2.
  MODULES.forEach(name => {
    const script = document.createElement("script");
    script.src = `${BASE}${name}?v=${VERSION}`;
    script.async = false;
    document.head.appendChild(script);
  });
})();
