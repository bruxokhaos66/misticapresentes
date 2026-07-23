const { test, expect } = require("@playwright/test");
const fs = require("fs");
const path = require("path");

const REPO_ROOT = path.resolve(__dirname, "..", "..");
const CONSUMER_SCRIPTS = /(^|\/)(app|mobile-sync|product-admin|v2-admin-products)\.js(\?|$)/;

// Descobre TODAS as páginas HTML do repositório (exceto node_modules) que
// carregam algum consumidor de window.misticaSecureStorage, sem depender de
// uma lista fixa — uma página nova adicionada no futuro que carregue esses
// scripts é verificada automaticamente por este teste.
function findHtmlPagesLoadingConsumers() {
  const resultados = [];
  const pilha = [REPO_ROOT];
  while (pilha.length) {
    const dir = pilha.pop();
    for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
      if (entry.name === "node_modules" || entry.name.startsWith(".git")) continue;
      const full = path.join(dir, entry.name);
      if (entry.isDirectory()) { pilha.push(full); continue; }
      if (!entry.name.endsWith(".html")) continue;
      const html = fs.readFileSync(full, "utf8");
      const scripts = [...html.matchAll(/<script[^>]*\bsrc=["']([^"']+)["']/g)].map(m => m[1]);
      if (scripts.some(src => CONSUMER_SCRIPTS.test(src))) {
        resultados.push({ file: full, urlPath: "/" + path.relative(REPO_ROOT, full) });
      }
    }
  }
  return resultados;
}

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

// Fase 3: a escolha de modalidade é obrigatória e o botão "Gerar Pix" começa
// desabilitado até uma opção ser marcada. Este teste não avalia frete ou
// endereço, então usamos "Retirar na loja" (frete zero, sem campos extras).
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
    await expect(page.locator("#cartList")).toContainText("Seu carrinho está vazio");
  });

  test("Pix, txid, acompanhamento e resposta do pedido nunca são persistidos (localStorage, sessionStorage, cookies, IndexedDB)", async ({ page }) => {
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
    await page.route("**/api/pedidos/PED-STORAGE-1/status**", route => route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ ok: true, venda_id: "PED-STORAGE-1", status_atual: "Aguardando pagamento", estoque_baixado: false, historico: [] }),
    }));

    await page.goto("/index.html");
    await expect.poll(() => page.evaluate(() => window.misticaCatalogState)).toBe("ready");
    await page.locator("[data-product-grid] button", { hasText: "Adicionar" }).click();
    await selecionarRetirada(page);
    await page.locator("[data-generate-pix]").dispatchEvent("click");
    await expect(page.locator("#pixStatus")).toContainText("aguardando pagamento", { ignoreCase: true });

    // Acompanhamento do pedido (polling de status por id + pix_txid), como
    // acontece de verdade após gerar o Pix.
    const acompanhamento = await page.evaluate(() => window.misticaConsultarStatusPedido("PED-STORAGE-1", "TXID-SIGILOSO"));
    expect(acompanhamento.status).toBe("Aguardando pagamento");

    const storage = await dumpLocalStorage(page);
    const session = await page.evaluate(() => {
      const out = {};
      for (let i = 0; i < sessionStorage.length; i++) {
        const key = sessionStorage.key(i);
        out[key] = sessionStorage.getItem(key);
      }
      return out;
    });
    const cookies = await page.context().cookies();
    const indexedDbNames = await page.evaluate(async () => {
      if (!window.indexedDB?.databases) return [];
      try { return (await window.indexedDB.databases()).map(db => db.name); } catch { return []; }
    });

    const serialized = JSON.stringify({ storage, session, cookies }).toLowerCase();
    for (const term of FORBIDDEN_VALUE_TERMS) {
      expect(serialized.includes(term), `armazenamento não deveria conter "${term}"`).toBe(false);
    }
    expect(serialized.includes("txid-sigiloso")).toBe(false);
    expect(serialized.includes("00020101021226800014")).toBe(false);
    expect(serialized.includes("ped-storage-1")).toBe(false);
    // O site não usa cookies próprios não essenciais (a sessão administrativa
    // é HttpOnly, invisível a document.cookie/Playwright cookies() lê todos,
    // mas não deve haver cookie legível por JS com dado de pedido/cliente).
    for (const cookie of cookies) {
      expect(cookie.value.toLowerCase().includes("txid-sigiloso")).toBe(false);
    }
    // Nenhum banco IndexedDB relacionado a Pix/pedido/cliente é criado por
    // este fluxo. "misticaAudioStore" é o cache de áudio offline do player
    // xamânico (v2-shamanic-player.js), sem relação com dados comerciais —
    // é o único banco esperado nesta página.
    const bancosInesperados = indexedDbNames.filter(name => name !== "misticaAudioStore");
    expect(bancosInesperados).toEqual([]);
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

  test("formato do carrinho inspecionado em todo o ciclo de vida", async ({ context }, testInfo) => {
    testInfo.setTimeout(60000);
    const page = await context.newPage();
    await prepararCatalogo(page);
    await page.goto("/index.html");
    await expect.poll(() => page.evaluate(() => window.misticaCatalogState)).toBe("ready");
    await dismissConsent(page);

    // 1) adicionar produto
    await page.locator("[data-product-grid] button", { hasText: "Adicionar" }).click();
    let raw = await page.evaluate(() => localStorage.getItem("misticaCart"));
    expect(JSON.parse(raw)).toEqual([{ id: "api-701", qty: 1 }]);

    // 2) alterar quantidade pelo stepper do carrinho (a vitrine não tem mais
    // campo de quantidade -- ajuste passa a acontecer só no carrinho).
    await page.locator("#cartList [data-cart-qty-increase]").click();
    await page.locator("#cartList [data-cart-qty-increase]").click();
    raw = await page.evaluate(() => localStorage.getItem("misticaCart"));
    expect(JSON.parse(raw)).toEqual([{ id: "api-701", qty: 3 }]);

    // 3) remover produto
    await page.locator("#cartList .cart-remove").click();
    raw = await page.evaluate(() => localStorage.getItem("misticaCart"));
    expect(JSON.parse(raw)).toEqual([]);

    // adiciona de novo para testar reload/segunda aba/atualização de catálogo
    // (a vitrine sempre adiciona 1 unidade; ajuste de quantidade é só no carrinho)
    await page.locator("[data-product-grid] button", { hasText: "Adicionar" }).click();

    // 4) recarregar a página
    await page.reload();
    await expect.poll(() => page.evaluate(() => window.misticaCatalogState)).toBe("ready");
    raw = await page.evaluate(() => localStorage.getItem("misticaCart"));
    expect(JSON.parse(raw)).toEqual([{ id: "api-701", qty: 1 }]);

    // 5) abrir segunda aba: mesmo formato mínimo é visível
    const page2 = await context.newPage();
    await prepararCatalogo(page2);
    await page2.goto("/index.html");
    await expect.poll(() => page2.evaluate(() => window.misticaCatalogState)).toBe("ready");
    raw = await page2.evaluate(() => localStorage.getItem("misticaCart"));
    expect(JSON.parse(raw)).toEqual([{ id: "api-701", qty: 1 }]);

    // 6) atualizar o catálogo (preço muda): carrinho permanece só id+qty
    await prepararCatalogo(page, { ...produtoApi, preco: 99 });
    await page.evaluate(() => window.misticaMobileSync.syncNow());
    await expect(page.locator("#cartTotal")).toContainText("99,00");
    raw = await page.evaluate(() => localStorage.getItem("misticaCart"));
    expect(JSON.parse(raw)).toEqual([{ id: "api-701", qty: 1 }]);

    const serialized = raw.toLowerCase();
    for (const proibido of ["name", "nome", "price", "preco", "descri", "categ", "image", "estoque", "stock", "custo", "margem", "fornecedor", "sob_encomenda", "sob", "cliente", "pix", "pedido", "total", "subtotal"]) {
      expect(serialized.includes(proibido), `carrinho não deveria conter "${proibido}"`).toBe(false);
    }

    await page.close();
    await page2.close();
  });

  test("evento storage malicioso com preço/estoque/cliente falsos é sanitizado para id+qty", async ({ page }) => {
    await prepararCatalogo(page);
    await page.goto("/index.html");
    await expect.poll(() => page.evaluate(() => window.misticaCatalogState)).toBe("ready");

    const payloadMalicioso = JSON.stringify([{
      id: "api-701",
      qty: 2,
      price: 0.01,
      stock: 999999,
      customer: { name: "dados pessoais" },
    }]);
    await page.evaluate((payload) => {
      window.dispatchEvent(new StorageEvent("storage", { key: "misticaCart", newValue: payload }));
    }, payloadMalicioso);

    await expect.poll(() => page.evaluate(() => localStorage.getItem("misticaCart"))).not.toBeNull();
    const raw = await page.evaluate(() => localStorage.getItem("misticaCart"));
    expect(JSON.parse(raw)).toEqual([{ id: "api-701", qty: 2 }]);
    expect(raw.toLowerCase().includes("price")).toBe(false);
    expect(raw.toLowerCase().includes("customer")).toBe(false);
    expect(raw.toLowerCase().includes("stock")).toBe(false);
  });

  test("quantidade negativa, decimal, string ou excessiva no legado é descartada/limitada", async ({ page }) => {
    await page.addInitScript(() => {
      localStorage.setItem("misticaCart", JSON.stringify([
        { id: "api-701", qty: -5 },
        { id: "api-702", qty: 1.5 },
        { id: "api-703", qty: "abc" },
        { id: "api-704", qty: 5000 },
      ]));
    });
    await prepararCatalogo(page, { ...produtoApi, id: 704, codigo_p: "STORAGE-704" });
    await page.goto("/index.html");
    await expect.poll(() => page.evaluate(() => window.misticaCatalogState)).toBe("ready");

    // Só o item com quantidade inteira válida (704) sobrevive à sanitização
    // do módulo seguro; os demais (negativo/decimal/string) já são
    // descartados antes mesmo de chegar ao app.js. A quantidade de 5000 é
    // limitada pelo teto do módulo seguro e depois recortada pelo estoque
    // real do catálogo ao reconciliar.
    const raw = await page.evaluate(() => localStorage.getItem("misticaCart"));
    const cart = JSON.parse(raw);
    expect(cart.every(item => Number.isInteger(item.qty) && item.qty >= 1 && item.qty <= 999)).toBe(true);
    expect(cart.find(item => item.id === "api-701")).toBeUndefined();
    expect(cart.find(item => item.id === "api-702")).toBeUndefined();
    expect(cart.find(item => item.id === "api-703")).toBeUndefined();
  });

  test("chave proibida criada depois da inicialização é removida na próxima carga", async ({ page }) => {
    await prepararCatalogo(page);
    await page.goto("/index.html");
    await expect.poll(() => page.evaluate(() => window.misticaCatalogState)).toBe("ready");

    // Simula um script comprometido/futuro gravando uma chave proibida
    // depois que a página já carregou.
    await page.evaluate(() => { localStorage.setItem("misticaSales", JSON.stringify([{ total: 1 }])); });
    expect(await page.evaluate(() => localStorage.getItem("misticaSales"))).not.toBeNull();

    await page.reload();
    await expect.poll(() => page.evaluate(() => window.misticaCatalogState)).toBe("ready");
    expect(await page.evaluate(() => localStorage.getItem("misticaSales"))).toBeNull();
  });

  test("catálogo indisponível durante reload não trata cache local como autoritativo", async ({ page }) => {
    await prepararCatalogo(page);
    await page.goto("/index.html");
    await expect.poll(() => page.evaluate(() => window.misticaCatalogState)).toBe("ready");
    await page.locator("[data-product-grid] button", { hasText: "Adicionar" }).click();
    await expect(page.locator("#cartList")).toContainText("Vela de teste");

    await page.route("**/api/produtos?**", route => route.fulfill({
      status: 503,
      contentType: "application/json",
      body: JSON.stringify({ detail: "indisponível" }),
    }));
    await page.reload();
    await expect.poll(() => page.evaluate(() => window.misticaCatalogState)).toBe("error");

    // Carrinho não é exibido como confiável (catálogo indisponível bloqueia
    // compra); o valor mínimo salvo continua intacto para quando a API
    // voltar, mas não é tratado como fonte de verdade de preço/estoque.
    await expect(page.locator("[data-generate-pix]")).toBeDisabled();
    const raw = await page.evaluate(() => localStorage.getItem("misticaCart"));
    expect(JSON.parse(raw)).toEqual([{ id: "api-701", qty: 1 }]);
  });

  test("logout/limpeza remove o carrinho persistido", async ({ page }) => {
    await prepararCatalogo(page);
    await page.goto("/index.html");
    await expect.poll(() => page.evaluate(() => window.misticaCatalogState)).toBe("ready");
    await page.locator("[data-product-grid] button", { hasText: "Adicionar" }).click();
    expect(await page.evaluate(() => localStorage.getItem("misticaCart"))).not.toBeNull();

    await page.locator("[data-clear-cart]").click();
    const raw = await page.evaluate(() => localStorage.getItem("misticaCart"));
    expect(JSON.parse(raw)).toEqual([]);
  });

  test("localStorage indisponível (modo privado) não quebra a página nem usa fallback proibido", async ({ page }) => {
    const erros = [];
    page.on("pageerror", error => erros.push(String(error)));
    await page.addInitScript(() => {
      const throwStorage = {
        getItem() { throw new DOMException("SecurityError", "SecurityError"); },
        setItem() { throw new DOMException("SecurityError", "SecurityError"); },
        removeItem() { throw new DOMException("SecurityError", "SecurityError"); },
        get length() { return 0; },
        key() { return null; },
      };
      Object.defineProperty(window, "localStorage", { get: () => throwStorage, configurable: true });
    });
    await prepararCatalogo(page);
    await page.goto("/index.html");
    await expect.poll(() => page.evaluate(() => window.misticaCatalogState)).toBe("ready");
    await dismissConsent(page);

    // O carrinho continua funcionando em memória mesmo sem persistência.
    await page.locator("[data-product-grid] button", { hasText: "Adicionar" }).click();
    await expect(page.locator("#cartList")).toContainText("Vela de teste");
    expect(erros, `nenhum erro JS fatal deveria ocorrer: ${erros.join(" | ")}`).toEqual([]);

    // Nenhum fallback alternativo (cookie, variável global exposta, etc.)
    // recebeu os dados proibidos que iriam para localStorage.
    const cookies = await page.context().cookies();
    expect(cookies.some(c => /mistica(sales|stock|suppliers|cart)/i.test(c.name))).toBe(false);
  });

  test("quota de armazenamento excedida ao salvar o carrinho não lança erro fatal", async ({ page }) => {
    const erros = [];
    page.on("pageerror", error => erros.push(String(error)));
    await page.addInitScript(() => {
      const originalSetItem = Storage.prototype.setItem;
      Storage.prototype.setItem = function quotaExceeded(key, value) {
        if (this === window.localStorage && key === "misticaCart") {
          throw new DOMException("QuotaExceededError", "QuotaExceededError");
        }
        return originalSetItem.call(this, key, value);
      };
    });
    await prepararCatalogo(page);
    await page.goto("/index.html");
    await expect.poll(() => page.evaluate(() => window.misticaCatalogState)).toBe("ready");
    await dismissConsent(page);

    await page.locator("[data-product-grid] button", { hasText: "Adicionar" }).click();
    await expect(page.locator("#cartList")).toContainText("Vela de teste");
    expect(erros, `nenhum erro JS fatal deveria ocorrer: ${erros.join(" | ")}`).toEqual([]);
  });

  test("nenhum script grava em localStorage fora de window.misticaSecureStorage", async ({ request }) => {
    const arquivos = ["app.js", "mobile-sync.js", "site-production-guard.js", "product-admin.js", "v2-admin-products.js"];
    for (const arquivo of arquivos) {
      const response = await request.get(`/${arquivo}`);
      expect(response.ok()).toBe(true);
      const source = await response.text();
      expect(source.includes("localStorage.setItem"), `${arquivo} não deveria chamar localStorage.setItem diretamente`).toBe(false);
      expect(/localStorage\[/.test(source), `${arquivo} não deveria indexar localStorage[...] diretamente`).toBe(false);
    }
  });

  test("nenhuma página do repositório carrega consumidores antes de site-config.js", async () => {
    const paginas = findHtmlPagesLoadingConsumers();
    // Falha alto (em vez de passar silenciosamente) se a varredura não
    // encontrar nenhuma página: garante que o teste continua fiscalizando
    // páginas novas e não fica "verde por acidente" após uma refatoração.
    expect(paginas.length).toBeGreaterThan(0);
    for (const pagina of paginas) {
      const html = fs.readFileSync(pagina.file, "utf8");
      const scripts = [...html.matchAll(/<script[^>]*\bsrc=["']([^"']+)["']/g)].map(m => m[1]);
      const configIndex = scripts.findIndex(src => /site-config\.js/.test(src));
      const primeiroConsumidorIndex = scripts.findIndex(src => CONSUMER_SCRIPTS.test(src));
      expect(configIndex, `${pagina.urlPath}: site-config.js deve existir`).toBeGreaterThan(-1);
      expect(configIndex, `${pagina.urlPath}: site-config.js deve vir antes de ${scripts[primeiroConsumidorIndex]}`).toBeLessThan(primeiroConsumidorIndex);
    }
  });
});
