// Regression notes for the public site production guard.
// These tests are intentionally dependency-free so they can be ported to Playwright/Jest later.
// Run in a browser-like test harness by loading app.js, mobile-sync.js and site-production-guard.js.

const siteProductionGuardScenarios = [
  {
    name: "sale waits for API before clearing cart or changing stock",
    steps: [
      "Seed cart with one API-synchronized product.",
      "Mock POST /api/vendas with 200 and a venda_id.",
      "Click [data-generate-pix].",
      "Expect cart to clear only after POST succeeds.",
      "Expect stock not to be reduced locally before syncNow refreshes from API.",
    ],
  },
  {
    name: "sale API failure preserves cart and does not lower stock",
    steps: [
      "Seed cart with one API-synchronized product.",
      "Mock POST /api/vendas with 500 or network error.",
      "Click [data-generate-pix].",
      "Expect cart to remain available for retry.",
      "Expect local stock to remain unchanged.",
      "Expect a misticaPendingOrders record for operator review.",
    ],
  },
  {
    name: "client data is not persisted locally in production",
    steps: [
      "Submit #clientForm with CPF, address and WhatsApp.",
      "Mock POST /api/clientes success.",
      "Expect localStorage.misticaClients to be absent.",
      "Expect backup payload clients array to be empty.",
    ],
  },
  {
    name: "cancel and status updates require API confirmation",
    steps: [
      "Render history action buttons from mobile-sync.js.",
      "Mock cancel/status endpoints as failed.",
      "Click cancel/status.",
      "Expect sale.status and stock to remain unchanged locally.",
      "Mock endpoint success and retry.",
      "Expect syncNow to be requested after confirmation.",
    ],
  },
  {
    name: "admin local writes are blocked on the public site",
    steps: [
      "Submit admin/product/supplier forms or export/backup buttons.",
      "Expect the guard to stop propagation before legacy handlers run.",
      "Expect message instructing use of authenticated Mística Painel/API.",
    ],
  },
];

if (typeof module !== "undefined") {
  module.exports = { siteProductionGuardScenarios };
}
