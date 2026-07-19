const { test, expect } = require("@playwright/test");

function pedido(overrides = {}) {
  return {
    id: 901,
    cliente: "Maria da Silva",
    telefone: "49999998888",
    email: "maria@example.com",
    data_venda: "19/07/2026 10:00:00",
    data_iso: "2026-07-19T10:00:00",
    subtotal: 100,
    desconto: 5,
    frete: 10,
    total_final: 105,
    forma_pagamento: "Crédito · Visa, 3x",
    payment_type_id: "credit_card",
    payment_method_id: "visa",
    parcelas: 3,
    status: "Pagamento confirmado",
    status_pedido: "confirmado",
    forma_recebimento: "entrega",
    codigo_rastreio: null,
    data_aprovacao: "2026-07-19T10:01:00",
    visualizado_admin_em: null,
    itens: [{ id: 1, nome_p: "Incenso", quantidade: 2, valor_unitario: 50, valor_total: 100 }],
    historico_status: [],
    historico_pagamentos: [],
    tentativas_pagamento: [],
    ...overrides,
  };
}

async function preparar(page, lista = [pedido()]) {
  await page.route("**/api/auth/me", route => route.fulfill({
    status: 200,
    contentType: "application/json",
    body: JSON.stringify({ status: "ok", usuario: { nome: "Admin", perfil: "adm" } }),
  }));
  await page.route("**/api/pedidos?**", route => route.fulfill({
    status: 200,
    contentType: "application/json",
    body: JSON.stringify(lista),
  }));
  await page.route("**/api/pedidos/notificacoes/pendentes**", route => route.fulfill({
    status: 200,
    contentType: "application/json",
    body: JSON.stringify({ ok: true, total: lista.length, total_nao_visualizados: lista.filter(p => !p.visualizado_admin_em).length, pedidos: lista }),
  }));
  await page.route("**/api/pedidos/*/detalhes-admin", route => {
    const id = Number(route.request().url().match(/pedidos\/(\d+)/)?.[1]);
    route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(lista.find(p => p.id === id) || lista[0]) });
  });
  await page.route("**/api/pedidos/*/visualizar", route => route.fulfill({
    status: 200,
    contentType: "application/json",
    body: JSON.stringify({ ok: true }),
  }));
}

test.describe("Fase 2 - pedidos unificados", () => {
  test("lista Pix, crédito e débito juntos e exibe À vista", async ({ page }) => {
    const dados = [
      pedido({ id: 901 }),
      pedido({ id: 902, cliente: "João Pix", payment_type_id: "pix", payment_method_id: "pix", forma_pagamento: "Pix", parcelas: 1 }),
      pedido({ id: 903, cliente: "Ana Débito", payment_type_id: "debit_card", payment_method_id: "master", forma_pagamento: "Débito · Mastercard", parcelas: 1 }),
    ];
    await preparar(page, dados);
    await page.goto("/admin-pedidos.html");
    await expect(page.locator(".admin-pedido-card")).toHaveCount(3);
    await expect(page.locator(".admin-pedido-card").nth(1)).toContainText("Pix · À vista");
    await expect(page.locator(".admin-pedido-card").nth(2)).toContainText("Débito");
    await expect(page.locator(".admin-pedido-card").nth(2)).not.toContainText("Crédito");
  });

  test("busca e filtros reduzem a lista", async ({ page }) => {
    await preparar(page, [
      pedido({ id: 910, cliente: "Cliente Crédito" }),
      pedido({ id: 911, cliente: "Cliente Pix", payment_type_id: "pix", forma_pagamento: "Pix", parcelas: 1 }),
    ]);
    await page.goto("/admin-pedidos.html");
    await page.fill("#filtroBuscaPedidos", "911");
    await expect(page.locator(".admin-pedido-card")).toHaveCount(1);
    await expect(page.locator(".admin-pedido-card")).toContainText("Cliente Pix");
    await page.fill("#filtroBuscaPedidos", "");
    await page.selectOption("#filtroPagamentoPedidos", "credit_card");
    await expect(page.locator(".admin-pedido-card")).toHaveCount(1);
    await expect(page.locator(".admin-pedido-card")).toContainText("Cliente Crédito");
  });

  test("abre detalhes, marca visualizado e altera somente status comercial uma vez", async ({ page }) => {
    const dados = [pedido({ id: 920 })];
    let patches = 0;
    let vistos = 0;
    await preparar(page, dados);
    await page.route("**/api/pedidos/920/visualizar", route => {
      vistos += 1;
      route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ ok: true }) });
    });
    await page.route("**/api/pedidos/920/status-comercial", async route => {
      patches += 1;
      const body = route.request().postDataJSON();
      expect(body.status_pedido).toBe("em_preparacao");
      route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ ok: true, status_pedido: body.status_pedido }) });
    });
    await page.goto("/admin-pedidos.html");
    await page.click("[data-acao='detalhes']");
    await expect(page.locator("#detalhePedidoDialog")).toBeVisible();
    expect(vistos).toBe(1);
    await page.selectOption(".admin-status-select", "em_preparacao");
    await page.click(".admin-status-form button[type='submit']");
    await page.waitForTimeout(100);
    expect(patches).toBe(1);
  });

  test("dados maliciosos aparecem como texto e não executam HTML", async ({ page }) => {
    await page.addInitScript(() => { window.__fase2Xss = 0; });
    await preparar(page, [pedido({ cliente: '<img src=x onerror="window.__fase2Xss=1">Cliente' })]);
    await page.goto("/admin-pedidos.html");
    await expect(page.locator(".admin-pedido-card")).toContainText("Cliente");
    await page.waitForTimeout(100);
    expect(await page.evaluate(() => window.__fase2Xss)).toBe(0);
    expect(await page.locator(".admin-pedido-card img").count()).toBe(0);
  });

  test("falha temporária mostra mensagem amigável sem erro técnico", async ({ page }) => {
    await page.route("**/api/auth/me", route => route.fulfill({ status: 200, contentType: "application/json", body: "{}" }));
    await page.route("**/api/pedidos?**", route => route.fulfill({ status: 500, contentType: "application/json", body: JSON.stringify({ detail: "sqlite locked stack trace" }) }));
    await page.route("**/api/pedidos/notificacoes/pendentes**", route => route.fulfill({ status: 500, contentType: "application/json", body: "{}" }));
    await page.goto("/admin-pedidos.html");
    await expect(page.locator("#statusListaPedidos")).toContainText("Não foi possível atualizar");
    await expect(page.locator("body")).not.toContainText("sqlite locked");
  });

  test("layout móvel não cria rolagem horizontal excessiva", async ({ page }, testInfo) => {
    test.skip(!testInfo.project.name.toLowerCase().includes("mobile"), "cenário reservado ao projeto mobile");
    await preparar(page, [pedido()]);
    await page.goto("/admin-pedidos.html");
    await expect(page.locator(".admin-pedido-card")).toBeVisible();
    const medidas = await page.evaluate(() => ({ largura: document.documentElement.clientWidth, conteudo: document.documentElement.scrollWidth }));
    expect(medidas.conteudo).toBeLessThanOrEqual(medidas.largura + 4);
    await page.click("[data-acao='detalhes']");
    await expect(page.locator("#detalhePedidoDialog")).toBeVisible();
  });
});
