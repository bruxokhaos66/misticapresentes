const { test, expect } = require("@playwright/test");

const produtoApi = {
  id: 901,
  codigo_p: "TESTE-901",
  nome: "Incenso de teste",
  categoria: "Incensos",
  descricao: "Produto controlado para teste do checkout.",
  preco: 19.9,
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

test.describe("checkout de produção estável", () => {
  test("remove dados sensíveis e não mostra produtos demonstrativos", async ({ page }) => {
    await page.addInitScript(() => {
      localStorage.setItem("misticaSales", "[{}]");
      localStorage.setItem("misticaStock", "{\"demo\":99}");
      localStorage.setItem("misticaSuppliers", "[{}]");
      localStorage.setItem("misticaAutoBackup", "{\"clientes\":[]}");
      localStorage.setItem("misticaLastBackupAt", new Date().toISOString());
    });
    await prepararCatalogo(page);

    await page.goto("/index.html");
    await expect.poll(() => page.evaluate(() => window.misticaCatalogState)).toBe("ready");
    await expect(page.locator("[data-product-grid]")).toContainText("Incenso de teste");
    await expect(page.locator("[data-product-grid]")).not.toContainText("Velas de Intenção");

    const storage = await page.evaluate(() => ({
      sales: localStorage.getItem("misticaSales"),
      stock: localStorage.getItem("misticaStock"),
      suppliers: localStorage.getItem("misticaSuppliers"),
      backup: localStorage.getItem("misticaAutoBackup"),
      backupAt: localStorage.getItem("misticaLastBackupAt"),
    }));
    expect(storage).toEqual({ sales: null, stock: null, suppliers: null, backup: null, backupAt: null });
  });

  test("falha da API bloqueia catálogo, carrinho e Pix", async ({ page }) => {
    await page.route("**/api/produtos?**", route => route.fulfill({
      status: 503,
      contentType: "application/json",
      body: JSON.stringify({ detail: "indisponível" }),
    }));

    await page.goto("/index.html");
    await expect.poll(() => page.evaluate(() => window.misticaCatalogState)).toBe("error");
    await expect(page.locator("[data-product-grid]")).toContainText("Catálogo indisponível");
    await expect(page.locator("[data-generate-pix]")).toBeDisabled();
    await expect(page.locator("[data-product-grid] article")).toHaveCount(0);
  });

  test("cliques rápidos criam um único pedido com payload mínimo e preservam carrinho", async ({ page }) => {
    await prepararCatalogo(page);
    let requisicoes = 0;
    let payloadRecebido = null;

    await page.route("**/api/checkout/pedidos", async route => {
      requisicoes += 1;
      payloadRecebido = route.request().postDataJSON();
      await new Promise(resolve => setTimeout(resolve, 150));
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          id: "PED-TESTE-1",
          pix_copia_cola: "00020101021226800014br.gov.bcb.pix",
          pix_txid: "TX-TESTE-1",
          expira_em: new Date(Date.now() + 15 * 60_000).toISOString(),
          total_final: 19.9,
          desconto: 0,
        }),
      });
    });

    await page.goto("/index.html");
    await expect.poll(() => page.evaluate(() => window.misticaCatalogState)).toBe("ready");
    await page.locator("[data-product-grid] button", { hasText: "Adicionar" }).click();
    await expect(page.locator("#cartList")).toContainText("Incenso de teste");

    const gerarPix = page.locator("[data-generate-pix]");
    await gerarPix.dispatchEvent("click");
    await gerarPix.dispatchEvent("click");

    await expect(page.locator("#pixStatus")).toContainText("aguardando pagamento", { ignoreCase: true });
    expect(requisicoes).toBe(1);
    expect(payloadRecebido.itens).toEqual([{ produto_id: 901, codigo_p: "TESTE-901", quantidade: 1 }]);
    expect(payloadRecebido).not.toHaveProperty("subtotal");
    expect(payloadRecebido).not.toHaveProperty("desconto");
    expect(payloadRecebido).not.toHaveProperty("total_final");
    await expect(page.locator("#cartList")).toContainText("Incenso de teste");

    const pendingId = await page.evaluate(() => localStorage.getItem("misticaPendingOrderId"));
    expect(pendingId).toBe("PED-TESTE-1");
  });
});
