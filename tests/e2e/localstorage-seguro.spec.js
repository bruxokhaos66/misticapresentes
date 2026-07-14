const { test, expect } = require("@playwright/test");

const produtoApi = {
  id: 701,
  codigo_p: "STORAGE-701",
  nome: "Vela de teste",
  categoria: "Velas",
  descricao: "Produto controlado para teste de armazenamento.",
  preco: 25,
  quantidade: 4,
  imagem_url: "",
  imagens: [],
  selo: "",
};

const FORBIDDEN_KEYS = [
  "misticaClients",
  "misticaSales",
  "misticaStock",
  "misticaSuppliers",
  "misticaAutoBackup",
  "misticaLastBackupAt",
  "misticaPendingOrderId",
  "misticaCustomProducts",
  "misticaApiProductsCache",
  "misticaApiProductsCacheAt",
];

const FORBIDDEN_VALUE_TERMS = [
  "telefone",
  "endereco",
  "cpf",
  "pix",
  "txid",
  "fornecedor",
  "custo",
  "margem",
  "lucro",
  "sales",
  "stock",
  "suppliers",
];

async function prepararCatalogo(page, produto = produtoApi) {
  await page.route("**/api/produtos?**", route => route.fulfill({
    status: 200,
    contentType: "application/json",
    body: JSON.stringify([produto]),
  }));
}

async function dismissConsent(page) {
  const decline = page.locator("[data-consent-decline]");
  if (await decline.isVisible().catch(() => false)) await decline.click();
}

async function dumpLocalStorage(page) {
  return page.evaluate(() => {
    const out = {};
    for (let i = 0; i < localStorage.length; i++) {
      const key = localStorage.key(i);
      out[key] = localStorage.getItem(key);
    }
    return out;
  });
}

test.describe("persistência segura do navegador", () => {
  test("chaves proibidas legadas são removidas antes de app.js consumi-las", async ({ page }) => {
    await page.addInitScript(() => {
      localStorage.setItem("misticaSales", JSON.stringify([{ total: 999, cliente: "Fulano" }]));
      localStorage.setItem("misticaStock", JSON.stringify({ demo: 99 }));
      localStorage.setItem("misticaSuppliers", JSON.stringify([{ name: "Fornecedor X", whatsapp: "5599999999" }]));
      localStorage.setItem("misticaClients", JSON.stringify([{ cpf: "11111111111" }]));
      localStorage.setItem("misticaAutoBackup", JSON.stringify({ sales: [], suppliers: [] }));
      localStorage.setItem("misticaLastBackupAt", new Date().toISOString());
      localStorage.setItem("misticaPendingOrderId", "PED-LEGADO");
      localStorage.setItem("misticaCustomProducts", JSON.stringify([{ price: 10, cost: 3 }]));
      localStorage.setItem("misticaApiProductsCache", JSON.stringify([{ preco: 10, custo: 3 }]));
      localStorage.setItem("misticaApiProductsCacheAt", String(Date.now()));
    });
    await prepararCatalogo(page);

    await page.goto("/index.html");
    await expect.poll(() => page.evaluate(() => window.misticaCatalogState)).toBe("ready");

    const storage = await dumpLocalStorage(page);
    for (const key of FORBIDDEN_KEYS) {
      expect(storage[key], `chave proibida ${key} não deveria existir`).toBeUndefined();
    }

    // sales/stock/suppliers/clients em memória nunca foram alimentados pelo legado.
    const memoria = await page.evaluate(() => ({
      sales: typeof sales !== "undefined" ? sales : null,
      suppliers: typeof suppliers !== "undefined" ? suppliers : null,
      clients: typeof clients !== "undefined" ? clients : null,
    }));
    expect(memoria.sales).toEqual([]);
    expect(memoria.suppliers).toEqual([]);
    expect(memoria.clients).toEqual([]);
  });

  test("carrinho persistido contém apenas id e quantidade, sem preço/nome/total", async ({ page }) => {
    await prepararCatalogo(page);
    await page.goto("/index.html");
    await expect.poll(() => page.evaluate(() => window.misticaCatalogState)).toBe("ready");

    await page.locator("[data-product-grid] button", { hasText: "Adicionar" }).click();
    await expect(page.locator("#cartList")).toContainText("Vela de teste");

    const cartRaw = await page.evaluate(() => localStorage.getItem("misticaCart"));
    const cart = JSON.parse(cartRaw);
    expect(cart).toEqual([{ id: "api-701", qty: 1 }]);

    const serialized = cartRaw.toLowerCase();
    for (const term of ["price", "preco", "name", "nome", "total", "desconto", "sob"]) {
      expect(serialized.includes(term), `carrinho não deveria conter "${term}"`).toBe(false);
    }
  });

  test("reload restaura carrinho usando preço atual do catálogo, não valor salvo", async ({ page }) => {
    await prepararCatalogo(page);
    await page.goto("/index.html");
    await expect.poll(() => page.evaluate(() => window.misticaCatalogState)).toBe("ready");
    await page.locator("[data-product-grid] button", { hasText: "Adicionar" }).click();
    await expect(page.locator("#cartTotal")).toContainText("25,00");

    // Produto muda de preço no catálogo oficial antes do reload.
    await prepararCatalogo(page, { ...produtoApi, preco: 40 });
    await page.reload();
    await expect.poll(() => page.evaluate(() => window.misticaCatalogState)).toBe("ready");

    await expect(page.locator("#cartList")).toContainText("Vela de teste");
    await expect(page.locator("#cartTotal")).toContainText("40,00");
  });

  test("produto removido do catálogo é descartado do carrinho ao reconciliar", async ({ page }) => {
    await prepararCatalogo(page);
    await page.goto("/index.html");
    await expect.poll(() => page.evaluate(() => window.misticaCatalogState)).toBe("ready");
    await page.locator("[data-product-grid] button", { hasText: "Adicionar" }).click();
    await expect(page.locator("#cartList")).toContainText("Vela de teste");

    await page.route("**/api/produtos?**", route => route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify([]),
    }));
    await page.evaluate(() => window.misticaMobileSync.syncNow());
    await expect(page.locator("#cartList")).not.toContainText("Vela de teste");
    const cartRaw = await page.evaluate(() => localStorage.getItem("misticaCart"));
    expect(JSON.parse(cartRaw)).toEqual([]);
  });

  test("quantidade acima do estoque é corrigida ao reconciliar com o catálogo", async ({ page }) => {
    await prepararCatalogo(page);
    await page.goto("/index.html");
    await expect.poll(() => page.evaluate(() => window.misticaCatalogState)).toBe("ready");
    await page.locator("[data-product-grid] button", { hasText: "Adicionar" }).click();

    await page.evaluate(() => {
      localStorage.setItem("misticaCart", JSON.stringify([{ id: "api-701", qty: 999 }]));
    });
    await page.reload();
    await expect.poll(() => page.evaluate(() => window.misticaCatalogState)).toBe("ready");

    const cartRaw = await page.evaluate(() => localStorage.getItem("misticaCart"));
    expect(JSON.parse(cartRaw)).toEqual([{ id: "api-701", qty: 4 }]);
  });

  test("payload malicioso com preço falso no carrinho é ignorado ao restaurar", async ({ page }) => {
    await page.addInitScript(() => {
      localStorage.setItem("misticaCart", JSON.stringify([
        { produto_id: "api-701", quantidade: 2, price: 0.01, name: "Item falsificado", total: 0.02 },
      ]));
    });
    await prepararCatalogo(page);
    await page.goto("/index.html");
    await expect.poll(() => page.evaluate(() => window.misticaCatalogState)).toBe("ready");

    await expect(page.locator("#cartList")).toContainText("Vela de teste");
    await expect(page.locator("#cartTotal")).toContainText("50,00");
    await expect(page.locator("#cartList")).not.toContainText("Item falsificado");
  });

  test("carrinho legado inválido é descartado sem quebrar a página", async ({ page }) => {
    await page.addInitScript(() => {
      localStorage.setItem("misticaCart", "{ isto nao e json valido");
    });
    await prepararCatalogo(page);
    await page.goto("/index.html");
    await expect.poll(() => page.evaluate(() => window.misticaCatalogState)).toBe("ready");
    await expect(page.locator("#cartList")).toContainText("Nenhum produto adicionado");
  });

  test("Pix, txid e resposta do pedido nunca são persistidos", async ({ page }) => {
    await prepararCatalogo(page);
    await page.route("**/api/checkout/pedidos", route => route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        id: "PED-STORAGE-1",
        pix_copia_cola: "00020101021226800014br.gov.bcb.pix",
        pix_txid: "TXID-SIGILOSO",
        expira_em: new Date(Date.now() + 15 * 60_000).toISOString(),
        total_final: 25,
        desconto: 0,
      }),
    }));

    await page.goto("/index.html");
    await expect.poll(() => page.evaluate(() => window.misticaCatalogState)).toBe("ready");
    await page.locator("[data-product-grid] button", { hasText: "Adicionar" }).click();
    await page.locator("[data-generate-pix]").dispatchEvent("click");
    await expect(page.locator("#pixStatus")).toContainText("aguardando pagamento", { ignoreCase: true });

    const storage = await dumpLocalStorage(page);
    const serialized = JSON.stringify(storage).toLowerCase();
    for (const term of FORBIDDEN_VALUE_TERMS) {
      expect(serialized.includes(term), `armazenamento não deveria conter "${term}"`).toBe(false);
    }
    expect(serialized.includes("txid-sigiloso")).toBe(false);
    expect(serialized.includes("00020101021226800014")).toBe(false);
  });

  test("duas abas sincronizam somente id e quantidade do carrinho", async ({ context }) => {
    const pageA = await context.newPage();
    const pageB = await context.newPage();
    await prepararCatalogo(pageA);
    await prepararCatalogo(pageB);

    await pageA.goto("/index.html");
    await expect.poll(() => pageA.evaluate(() => window.misticaCatalogState)).toBe("ready");
    await pageB.goto("/index.html");
    await expect.poll(() => pageB.evaluate(() => window.misticaCatalogState)).toBe("ready");
    await dismissConsent(pageA);
    await dismissConsent(pageB);

    await pageA.locator("[data-product-grid] button", { hasText: "Adicionar" }).click();
    await expect(pageA.locator("#cartList")).toContainText("Vela de teste");

    await expect.poll(() => pageB.evaluate(() => localStorage.getItem("misticaCart"))).toContain("api-701");
    await pageB.evaluate(() => window.dispatchEvent(new StorageEvent("storage", {
      key: "misticaCart",
      newValue: localStorage.getItem("misticaCart"),
    })));
    await expect(pageB.locator("#cartList")).toContainText("Vela de teste");

    await pageA.close();
    await pageB.close();
  });

  test("aba antiga não reintroduz chaves proibidas via evento storage", async ({ page }) => {
    await prepararCatalogo(page);
    await page.goto("/index.html");
    await expect.poll(() => page.evaluate(() => window.misticaCatalogState)).toBe("ready");

    await page.evaluate(() => {
      window.dispatchEvent(new StorageEvent("storage", {
        key: "misticaSales",
        newValue: JSON.stringify([{ total: 500 }]),
      }));
    });

    const salesValue = await page.evaluate(() => localStorage.getItem("misticaSales"));
    expect(salesValue).toBeNull();
  });

  test("todas as páginas comerciais carregam site-config.js antes de app.js", async ({ request }) => {
    for (const url of ["/index.html", "/produto.html", "/kit.html", "/achados-misticos/index.html", "/teste-commerce.html", "/admin.html"]) {
      const response = await request.get(url);
      expect(response.ok()).toBe(true);
      const html = await response.text();
      const scripts = [...html.matchAll(/<script[^>]*\bsrc=["']([^"']+)["']/g)].map(match => match[1]);
      const configIndex = scripts.findIndex(src => /site-config\.js/.test(src));
      const appIndex = scripts.findIndex(src => /(^|\/)app\.js/.test(src));
      if (appIndex === -1) continue;
      expect(configIndex, `${url}: site-config.js deve existir`).toBeGreaterThan(-1);
      expect(configIndex, `${url}: site-config.js deve vir antes de app.js`).toBeLessThan(appIndex);
    }
  });
});
