const { test, expect } = require("@playwright/test");

const lt = "<";
const gt = ">";

function pedidoBase(overrides = {}) {
  return {
    id: 501,
    cliente: "Cliente normal",
    telefone: "49999998888",
    data_venda: "01/01/2026 10:00:00",
    data_iso: "2026-01-01T10:00:00",
    total_final: 39.9,
    forma_pagamento: "Pix site/celular",
    status: "Aguardando pagamento",
    expira_em: null,
    pix_txid: "TXID-TESTE-501",
    visualizado_admin_em: null,
    visualizado_admin_por: null,
    comprovante_enviado_em: null,
    itens: [{ quantidade: 1, nome_p: "Produto normal" }],
    ...overrides,
  };
}

async function mockSessaoAdmin(page) {
  await page.route("**/api/auth/me", route => route.fulfill({
    status: 200,
    contentType: "application/json",
    body: JSON.stringify({ status: "ok", usuario: { nome: "Admin Teste", login: "admin-teste", perfil: "adm" }, permissoes: {} }),
  }));
}

test.describe("painel admin-pedidos-pix: segurança e polling", () => {
  test("dados do pedido (nome, telefone, itens) são exibidos como texto e não executam HTML", async ({ page }) => {
    await page.addInitScript(() => { window.__adminPixInjectionExecuted = 0; });
    await mockSessaoAdmin(page);

    const imgPayload = `${lt}img src=x onerror="window.__adminPixInjectionExecuted=1"${gt}`;
    const svgPayload = `${lt}svg onload="window.__adminPixInjectionExecuted=2"${gt}`;
    const scriptPayload = `${lt}script${gt}window.__adminPixInjectionExecuted=3${lt}/script${gt}`;

    const pedidoMalicioso = pedidoBase({
      cliente: `${imgPayload}Cliente malicioso`,
      telefone: `${svgPayload}(49) 90000-0000`,
      itens: [{ quantidade: 1, nome_p: `${scriptPayload}Item malicioso` }],
    });

    await page.route("**/api/pedidos/pix/pendentes**", route => route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ ok: true, total: 1, total_nao_visualizados: 1, pedidos: [pedidoMalicioso] }),
    }));

    await page.goto("/admin-pedidos-pix.html");
    await expect(page.locator("#painelPix")).toBeVisible();
    await expect(page.locator(".pedido-pix-card")).toContainText("Cliente malicioso");

    await page.waitForTimeout(200);
    expect(await page.evaluate(() => window.__adminPixInjectionExecuted)).toBe(0);
    expect(await page.locator(".pedido-pix-card script").count()).toBe(0);
    expect(await page.locator(".pedido-pix-card svg").count()).toBe(0);
    expect(await page.locator(".pedido-pix-card img").count()).toBe(0);
  });

  test("apenas um timer de polling fica ativo e logout encerra o polling", async ({ page }) => {
    await mockSessaoAdmin(page);

    let chamadas = 0;
    await page.route("**/api/pedidos/pix/pendentes**", route => {
      chamadas += 1;
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ ok: true, total: 1, total_nao_visualizados: 0, pedidos: [pedidoBase()] }),
      });
    });
    await page.route("**/api/auth/logout", route => route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ status: "ok" }) }));

    await page.goto("/admin-pedidos-pix.html");
    await expect(page.locator(".pedido-pix-card")).toBeVisible();

    // Carga inicial já disparou 1 chamada. Troca de aba/visibilidade duas
    // vezes não deve criar timers adicionais (nunca mais de uma chamada por
    // "voltar à aba", nunca crescimento composto).
    await page.evaluate(() => document.dispatchEvent(new Event("visibilitychange")));
    await page.evaluate(() => document.dispatchEvent(new Event("visibilitychange")));
    await page.waitForTimeout(300);
    const chamadasAntesDoLogout = chamadas;
    expect(chamadasAntesDoLogout).toBeLessThan(6);

    await page.click("#btnSairPix");
    await expect(page.locator("#loginPanelPix")).toBeVisible();

    const chamadasNoLogout = chamadas;
    // Sem sleeps longos: aguarda só o suficiente para um possível timer
    // fantasma disparar (bem menor que POLL_INTERVAL_MS=15000) e confirma
    // que nenhuma chamada nova chega depois do logout.
    await page.waitForTimeout(1000);
    expect(chamadas).toBe(chamadasNoLogout);
  });

  test("erro de rede no polling não trava a página nem duplica timers", async ({ page }) => {
    await mockSessaoAdmin(page);

    let chamadas = 0;
    await page.route("**/api/pedidos/pix/pendentes**", route => {
      chamadas += 1;
      route.fulfill({ status: 500, contentType: "application/json", body: JSON.stringify({ detail: "erro simulado" }) });
    });

    await page.goto("/admin-pedidos-pix.html");
    await expect(page.locator(".admin-pix-vazio")).toContainText("Não foi possível carregar");
    await page.waitForTimeout(300);
    expect(chamadas).toBeGreaterThanOrEqual(1);
    expect(chamadas).toBeLessThan(6);
  });
});
