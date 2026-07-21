const { test, expect } = require("@playwright/test");

const produtoApi = {
  id: 902,
  codigo_p: "TESTE-902",
  nome: "Cristal de teste",
  categoria: "Cristais",
  descricao: "Produto controlado para teste de idempotência.",
  preco: 29.9,
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
// para manter o foco no comportamento original de idempotência.
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

function respostaPedido(id, txid) {
  return {
    id,
    pix_copia_cola: `00020101021226800014br.gov.bcb.pix-${id}`,
    pix_txid: txid,
    expira_em: new Date(Date.now() + 15 * 60_000).toISOString(),
    total_final: 29.9,
    desconto: 0,
  };
}

test.describe("checkout público: Idempotency-Key e acompanhamento por txid", () => {
  test("envia Idempotency-Key, reaproveita a chave num retry e mantém a mesma chave para o carrinho inalterado após o sucesso", async ({ page }) => {
    await prepararCatalogo(page);
    const chavesRecebidas = [];
    let contador = 0;

    await page.route("**/api/checkout/pedidos", async route => {
      contador += 1;
      chavesRecebidas.push(route.request().headers()["idempotency-key"] || null);
      if (contador === 1) {
        // Primeira tentativa falha (ex.: timeout/erro de rede simulado).
        await route.fulfill({ status: 500, contentType: "application/json", body: JSON.stringify({ detail: "Erro simulado" }) });
        return;
      }
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(respostaPedido(`PED-${contador}`, `TX-${contador}`)),
      });
    });

    await page.goto("/index.html");
    await expect.poll(() => page.evaluate(() => window.misticaCatalogState)).toBe("ready");
    await page.locator("[data-product-grid] button", { hasText: "Adicionar" }).click();
    await selecionarRetirada(page);

    const gerarPix = page.locator("[data-generate-pix]");

    // Tentativa 1: falha.
    await gerarPix.click();
    await expect.poll(() => chavesRecebidas.length).toBe(1);
    expect(chavesRecebidas[0]).toBeTruthy();

    // Retry da MESMA tentativa (carrinho não mudou): deve reaproveitar a chave.
    await gerarPix.click();
    await expect.poll(() => chavesRecebidas.length).toBe(2);
    expect(chavesRecebidas[1]).toBe(chavesRecebidas[0]);
    await expect(page.locator("#pixStatus")).toContainText("aguardando pagamento", { ignoreCase: true });

    // Depois do sucesso, "Gerar Pix" trava (melhoria de UX: nunca recriar o
    // mesmo pedido por engano) — um novo clique no mesmo carrinho não gera
    // uma terceira requisição.
    await expect(gerarPix).toBeDisabled();
    await gerarPix.click({ force: true });
    await page.waitForTimeout(300);
    expect(chavesRecebidas.length).toBe(2);

    // Gerar o Pix de novo para o MESMO carrinho via reload (ex.: cliente deu
    // F5) ainda deve reaproveitar a mesma chave — nunca criar um segundo
    // pedido/reserva de estoque para o mesmo conteúdo (ver Fase B: achado de
    // duplicidade em refresh/múltiplas abas, coberto em
    // checkout-duplicidade-multitab.spec.js).
    await page.reload();
    await expect.poll(() => page.evaluate(() => window.misticaCatalogState)).toBe("ready");
    // Fase 3: a modalidade de recebimento não é persistida (é sempre uma
    // escolha explícita, nunca lida de localStorage) — o reload volta a
    // exigi-la antes de permitir gerar o Pix de novo.
    await selecionarRetirada(page);
    await page.locator("[data-generate-pix]").click();
    await expect.poll(() => chavesRecebidas.length).toBe(3);
    expect(chavesRecebidas[2]).toBe(chavesRecebidas[1]);
  });

  test("mudar o carrinho entre duas tentativas usa uma Idempotency-Key diferente", async ({ page }) => {
    await prepararCatalogo(page);
    const chavesRecebidas = [];

    await page.route("**/api/checkout/pedidos", async route => {
      chavesRecebidas.push(route.request().headers()["idempotency-key"] || null);
      await route.fulfill({ status: 500, contentType: "application/json", body: JSON.stringify({ detail: "Erro simulado" }) });
    });

    await page.goto("/index.html");
    await expect.poll(() => page.evaluate(() => window.misticaCatalogState)).toBe("ready");

    const adicionar = page.locator("[data-product-grid] button", { hasText: "Adicionar" });
    await adicionar.click();
    await selecionarRetirada(page);

    const gerarPix = page.locator("[data-generate-pix]");
    await gerarPix.click();
    await expect.poll(() => chavesRecebidas.length).toBe(1);

    // Muda o carrinho (nova unidade do mesmo produto) antes de tentar de novo.
    await adicionar.click();
    await gerarPix.click();
    await expect.poll(() => chavesRecebidas.length).toBe(2);

    expect(chavesRecebidas[1]).toBeTruthy();
    expect(chavesRecebidas[1]).not.toBe(chavesRecebidas[0]);
  });

  test("acompanhamento do pedido consulta status enviando id e pix_txid", async ({ page }) => {
    await prepararCatalogo(page);
    await page.route("**/api/checkout/pedidos", route => route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(respostaPedido("PED-STATUS-1", "TX-STATUS-1")),
    }));

    let statusUrl = null;
    await page.route("**/api/pedidos/PED-STATUS-1/status**", route => {
      statusUrl = route.request().url();
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ ok: true, venda_id: "PED-STATUS-1", status_atual: "Aguardando pagamento", estoque_baixado: false, historico: [] }),
      });
    });

    await page.goto("/index.html");
    await expect.poll(() => page.evaluate(() => window.misticaCatalogState)).toBe("ready");
    await page.locator("[data-product-grid] button", { hasText: "Adicionar" }).click();
    await selecionarRetirada(page);
    await page.locator("[data-generate-pix]").click();
    await expect(page.locator("#pixStatus")).toContainText("aguardando pagamento", { ignoreCase: true });

    const resultado = await page.evaluate(() => window.misticaConsultarStatusPedido("PED-STATUS-1", "TX-STATUS-1"));
    expect(resultado.status).toBe("Aguardando pagamento");
    expect(statusUrl).toContain("/api/pedidos/PED-STATUS-1/status");
    expect(statusUrl).toContain("txid=TX-STATUS-1");
  });

  test("nenhum txid ou dado pessoal fica salvo permanentemente no localStorage após o checkout", async ({ page }) => {
    await prepararCatalogo(page);
    await page.route("**/api/checkout/pedidos", route => route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(respostaPedido("PED-PRIVACIDADE-1", "TX-PRIVACIDADE-SEGREDO")),
    }));

    await page.goto("/index.html");
    await expect.poll(() => page.evaluate(() => window.misticaCatalogState)).toBe("ready");
    await page.locator("[data-product-grid] button", { hasText: "Adicionar" }).click();
    await selecionarRetirada(page);
    await page.locator("[data-generate-pix]").click();
    await expect(page.locator("#pixStatus")).toContainText("aguardando pagamento", { ignoreCase: true });

    const conteudoLocalStorage = await page.evaluate(() => {
      const dump = {};
      for (let i = 0; i < localStorage.length; i++) {
        const key = localStorage.key(i);
        dump[key] = localStorage.getItem(key);
      }
      return dump;
    });

    const bruto = JSON.stringify(conteudoLocalStorage);
    expect(bruto).not.toContain("TX-PRIVACIDADE-SEGREDO");
    expect(conteudoLocalStorage.misticaSales || null).toBeFalsy();
  });
});
