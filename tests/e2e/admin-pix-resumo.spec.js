const { test, expect } = require("@playwright/test");

const lt = "<";
const gt = ">";

function pedidoBase(overrides = {}) {
  return {
    id: 701,
    cliente: "Cliente normal",
    telefone: "49999998888",
    data_venda: "01/01/2026 10:00:00",
    data_iso: "2026-01-01T10:00:00",
    total_final: 59.9,
    forma_pagamento: "Pix site/celular",
    status: "Aguardando pagamento",
    visualizado_admin_em: null,
    visualizado_admin_por: null,
    comprovante_enviado_em: null,
    itens: [{ quantidade: 1, nome_p: "Produto normal" }],
    ...overrides,
  };
}

async function mockPendentes(page, respostaFn) {
  await page.route("**/api/pedidos/pix/pendentes**", (route) => {
    const resposta = typeof respostaFn === "function" ? respostaFn() : respostaFn;
    route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(resposta) });
  });
}

// Abre admin.html já com a seção "Pedidos Pix" presente no DOM e simula a
// liberação da sessão administrativa (o mesmo estado que qualquer um dos
// fluxos de login existentes produz: #adminContent visível), sem depender
// da UI de login legada, que já é coberta por outros testes.
async function abrirComoAdminLogado(page) {
  await page.route("**/fonts.googleapis.com/**", (route) => route.fulfill({ status: 200, contentType: "text/css", body: "" }));
  await page.goto("/admin.html", { waitUntil: "load" });
  await expect(page.locator("#pedidosPixResumo")).toHaveCount(1);
  await page.evaluate(() => {
    document.getElementById("adminLoginPanel").hidden = true;
    document.getElementById("adminContent").hidden = false;
  });
}

test.describe("admin.html: resumo de Pedidos Pix", () => {
  test("nome, telefone e itens maliciosos são exibidos como texto, nunca executados", async ({ page }) => {
    await page.addInitScript(() => { window.__adminPixResumoInjectionExecuted = 0; });

    const imgPayload = `${lt}img src=x onerror="window.__adminPixResumoInjectionExecuted=1"${gt}`;
    const svgPayload = `${lt}svg onload="window.__adminPixResumoInjectionExecuted=2"${gt}`;
    const scriptPayload = `${lt}script${gt}window.__adminPixResumoInjectionExecuted=3${lt}/script${gt}`;

    const pedidoMalicioso = pedidoBase({
      cliente: `${imgPayload}Cliente malicioso`,
      telefone: `${svgPayload}49900000000`,
      itens: [{ quantidade: 1, nome_p: `${scriptPayload}Item malicioso` }],
    });

    await mockPendentes(page, { ok: true, total: 1, total_nao_visualizados: 1, pedidos: [pedidoMalicioso] });
    await abrirComoAdminLogado(page);

    await expect(page.locator(".pedido-pix-resumo-card")).toContainText("Cliente malicioso");
    await page.waitForTimeout(200);
    expect(await page.evaluate(() => window.__adminPixResumoInjectionExecuted)).toBe(0);
    expect(await page.locator(".pedido-pix-resumo-card script").count()).toBe(0);
    expect(await page.locator(".pedido-pix-resumo-card svg").count()).toBe(0);
    expect(await page.locator(".pedido-pix-resumo-card img").count()).toBe(0);
  });

  test("estado vazio mostra a mensagem exigida", async ({ page }) => {
    await mockPendentes(page, { ok: true, total: 0, total_nao_visualizados: 0, pedidos: [] });
    await abrirComoAdminLogado(page);
    await expect(page.locator("#pixResumoLista")).toContainText("Não há pedidos Pix aguardando atendimento.");
  });

  test("falha de rede mostra aviso de nova tentativa e não trava a página", async ({ page }) => {
    let chamadas = 0;
    await page.route("**/api/pedidos/pix/pendentes**", (route) => {
      chamadas += 1;
      route.fulfill({ status: 500, contentType: "application/json", body: JSON.stringify({ detail: "erro simulado" }) });
    });
    await abrirComoAdminLogado(page);
    await expect(page.locator("#pixResumoLista")).toContainText("Não foi possível atualizar os pedidos. Tentaremos novamente.");
    await page.waitForTimeout(300);
    expect(chamadas).toBeGreaterThanOrEqual(1);
    expect(chamadas).toBeLessThan(6);
  });

  test("pedido novo aparece automaticamente, gera aviso uma única vez, e o contador do cabeçalho reflete os não visualizados", async ({ page }) => {
    let versao = 0;
    await page.route("**/api/pedidos/pix/pendentes**", (route) => {
      const pedidos = versao === 0 ? [] : [pedidoBase({ id: 900 + versao })];
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ ok: true, total: pedidos.length, total_nao_visualizados: pedidos.length, pedidos }),
      });
    });
    await abrirComoAdminLogado(page);
    await expect(page.locator("#pixResumoLista")).toContainText("Não há pedidos Pix aguardando atendimento.");
    await expect(page.locator("#badgeHeaderPixPedidos")).toBeHidden();

    versao = 1;
    await page.click("#pixResumoAtualizar");
    await expect(page.locator(".pedido-pix-resumo-card")).toBeVisible();
    await expect(page.locator("#pixResumoAvisoNovo")).toBeVisible();
    await expect(page.locator("#pixResumoAvisoNovo")).toContainText("Novo pedido recebido");
    await expect(page.locator("#badgeHeaderPixPedidos")).toBeVisible();
    await expect(page.locator("#badgeHeaderPixPedidos")).toHaveText("1");
  });

  test("não é possível confirmar pagamento pelo resumo do painel principal", async ({ page }) => {
    await mockPendentes(page, { ok: true, total: 1, total_nao_visualizados: 1, pedidos: [pedidoBase()] });
    await abrirComoAdminLogado(page);
    await expect(page.locator(".pedido-pix-resumo-card")).toBeVisible();
    expect(await page.locator('[data-acao="confirmar-pagamento"]').count()).toBe(0);
    expect(await page.locator('[data-acao="comprovante-recebido"]').count()).toBe(0);
    await expect(page.locator(".pedido-pix-resumo-card")).toContainText("Abrir painel completo");
  });

  test("apenas um timer de polling fica ativo e ocultar/mostrar a aba não acumula chamadas", async ({ page }) => {
    let chamadas = 0;
    await page.route("**/api/pedidos/pix/pendentes**", (route) => {
      chamadas += 1;
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ ok: true, total: 1, total_nao_visualizados: 0, pedidos: [pedidoBase()] }),
      });
    });
    await abrirComoAdminLogado(page);
    await expect(page.locator(".pedido-pix-resumo-card")).toBeVisible();

    await page.evaluate(() => document.dispatchEvent(new Event("visibilitychange")));
    await page.evaluate(() => document.dispatchEvent(new Event("visibilitychange")));
    await page.waitForTimeout(300);
    expect(chamadas).toBeLessThan(6);
  });

  test("ocultar #adminContent (logout) interrompe o polling", async ({ page }) => {
    let chamadas = 0;
    await page.route("**/api/pedidos/pix/pendentes**", (route) => {
      chamadas += 1;
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ ok: true, total: 1, total_nao_visualizados: 0, pedidos: [pedidoBase()] }),
      });
    });
    await abrirComoAdminLogado(page);
    await expect(page.locator(".pedido-pix-resumo-card")).toBeVisible();

    await page.evaluate(() => { document.getElementById("adminContent").hidden = true; });
    const chamadasNoLogout = chamadas;
    await page.waitForTimeout(1000);
    expect(chamadas).toBe(chamadasNoLogout);
    await expect(page.locator("#badgeHeaderPixPedidos")).toBeHidden();
  });
});
