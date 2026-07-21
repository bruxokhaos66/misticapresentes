const { test, expect } = require("@playwright/test");

// Fase B — Auditoria do fluxo comercial: reload/segunda aba com o mesmo
// carrinho não pode gerar um segundo pedido/reserva de estoque no servidor.
// A defesa é a Idempotency-Key persistida via window.misticaSecureStorage
// (site-config.js), compartilhada entre abas/reloads da mesma origem
// enquanto o carrinho não mudar (ver mobile-sync.js).

const produtoApi = {
  id: 950,
  codigo_p: "TESTE-950",
  nome: "Amuleto de teste",
  categoria: "Cristais",
  descricao: "Produto controlado para teste de duplicidade de pedido.",
  preco: 39.9,
  quantidade: 5,
  imagem_url: "",
  imagens: [],
  selo: "",
};

async function prepararCatalogo(page) {
  await page.route("**/api/produtos?**", route => route.fulfill({
    status: 200,
    contentType: "application/json",
    body: JSON.stringify([produtoApi]),
  }));
}

// Fase 3: a escolha de modalidade é obrigatória e o botão "Gerar Pix" começa
// desabilitado até uma opção ser marcada. Estes testes não avaliam frete ou
// endereço, então usamos "Retirar na loja" (frete zero, sem campos extras)
// para manter o foco no comportamento original de idempotência/duplicidade.
async function selecionarRetirada(page) {
  // .evaluate() em vez de .check(): pode haver reflow logo após um
  // reload (banners/imagens assentando), e .check() falha por
  // "element is not stable" nesse instante — marcar o radio e
  // disparar "change" direto no DOM é equivalente e não depende de
  // estabilidade visual.
  await page.locator('[data-recebimento-radio][value="retirada"]').evaluate((el) => {
  el.checked = true;
  el.dispatchEvent(new Event("change", { bubbles: true }));
  });
  await expect(page.locator("[data-generate-pix]")).toBeEnabled();
}

function respostaPedido(id) {
  return {
    id,
    pix_copia_cola: `00020101021226800014br.gov.bcb.pix-${id}`,
    pix_txid: `TX-${id}`,
    expira_em: new Date(Date.now() + 15 * 60_000).toISOString(),
    total_final: 39.9,
    desconto: 0,
  };
}

test.describe("checkout: duplicidade de pedido em refresh e múltiplas abas", () => {
  test("gerar o Pix de novo após um F5 com o mesmo carrinho reaproveita a Idempotency-Key", async ({ page }) => {
    await prepararCatalogo(page);
    const chavesRecebidas = [];
    let contador = 0;

    await page.route("**/api/checkout/pedidos", async route => {
      contador += 1;
      chavesRecebidas.push(route.request().headers()["idempotency-key"] || null);
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(respostaPedido(`PED-REFRESH-${contador}`)),
      });
    });

    await page.goto("/index.html");
    await expect.poll(() => page.evaluate(() => window.misticaCatalogState)).toBe("ready");
    await page.locator("[data-product-grid] button", { hasText: "Adicionar" }).click();
    await selecionarRetirada(page);

    const gerarPix = page.locator("[data-generate-pix]");
    await gerarPix.dispatchEvent("click");
    await expect.poll(() => chavesRecebidas.length).toBe(1);
    await expect(page.locator("#pixStatus")).toContainText("aguardando pagamento", { ignoreCase: true });

    // Cliente dá F5 (ex.: achou que travou) com o mesmo carrinho ainda salvo.
    await page.reload();
    await expect.poll(() => page.evaluate(() => window.misticaCatalogState)).toBe("ready");
    await expect(page.locator("#cartList")).toContainText("Amuleto de teste");
    // Fase 3: a modalidade não é persistida — o reload volta a exigi-la.
    await selecionarRetirada(page);

    await page.locator("[data-generate-pix]").dispatchEvent("click");
    await expect.poll(() => chavesRecebidas.length).toBe(2);

    // Mesma chave reaproveitada: o backend (idempotency.py) devolve o MESMO
    // pedido em vez de criar um segundo e reservar estoque em dobro.
    expect(chavesRecebidas[1]).toBe(chavesRecebidas[0]);
  });

  test("duas abas com o mesmo carrinho reaproveitam a Idempotency-Key ao gerar o Pix em cada uma", async ({ context }) => {
    const pageA = await context.newPage();
    const pageB = await context.newPage();
    await prepararCatalogo(pageA);
    await prepararCatalogo(pageB);

    const chavesRecebidas = [];
    let contador = 0;
    const registrarRota = async page => page.route("**/api/checkout/pedidos", async route => {
      contador += 1;
      chavesRecebidas.push(route.request().headers()["idempotency-key"] || null);
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(respostaPedido(`PED-TAB-${contador}`)),
      });
    });
    await registrarRota(pageA);
    await registrarRota(pageB);

    await pageA.goto("/index.html");
    await expect.poll(() => pageA.evaluate(() => window.misticaCatalogState)).toBe("ready");
    await pageA.locator("[data-product-grid] button", { hasText: "Adicionar" }).click();
    await expect(pageA.locator("#cartList")).toContainText("Amuleto de teste");
    await selecionarRetirada(pageA);

    // Aba B abre depois, já enxergando o mesmo carrinho persistido.
    await pageB.goto("/index.html");
    await expect.poll(() => pageB.evaluate(() => window.misticaCatalogState)).toBe("ready");
    await expect(pageB.locator("#cartList")).toContainText("Amuleto de teste");
    await selecionarRetirada(pageB);

    await pageA.locator("[data-generate-pix]").dispatchEvent("click");
    await expect.poll(() => chavesRecebidas.length).toBe(1);
    await expect(pageA.locator("#pixStatus")).toContainText("aguardando pagamento", { ignoreCase: true });

    // Cliente indeciso clica em "Gerar Pix" também na aba B, para o mesmo carrinho.
    await pageB.locator("[data-generate-pix]").dispatchEvent("click");
    await expect.poll(() => chavesRecebidas.length).toBe(2);

    expect(chavesRecebidas[1]).toBe(chavesRecebidas[0]);

    await pageA.close();
    await pageB.close();
  });

  test("mudar o carrinho depois de gerar o Pix usa uma Idempotency-Key nova", async ({ page }) => {
    await prepararCatalogo(page);
    const chavesRecebidas = [];
    let contador = 0;

    await page.route("**/api/checkout/pedidos", async route => {
      contador += 1;
      chavesRecebidas.push(route.request().headers()["idempotency-key"] || null);
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(respostaPedido(`PED-MUDA-${contador}`)),
      });
    });

    await page.goto("/index.html");
    await expect.poll(() => page.evaluate(() => window.misticaCatalogState)).toBe("ready");
    const adicionar = page.locator("[data-product-grid] button", { hasText: "Adicionar" });
    await adicionar.click();
    await selecionarRetirada(page);

    const gerarPix = page.locator("[data-generate-pix]");
    await gerarPix.dispatchEvent("click");
    await expect.poll(() => chavesRecebidas.length).toBe(1);

    // Carrinho muda de fato (nova unidade) depois do Pix gerado: a
    // Idempotency-Key antiga não pode ser reaproveitada para um conteúdo
    // diferente do pedido já criado.
    await adicionar.click();
    await gerarPix.dispatchEvent("click");
    await expect.poll(() => chavesRecebidas.length).toBe(2);

    expect(chavesRecebidas[1]).not.toBe(chavesRecebidas[0]);
  });
});
