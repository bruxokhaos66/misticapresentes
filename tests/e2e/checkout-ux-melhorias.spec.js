const { test, expect } = require("@playwright/test");

// Cobre as melhorias de UX do checkout/Pix (estado do botão "Gerar Pix",
// botão "Já realizei o pagamento", feedback de cópia, contador de reserva,
// chave Pix mascarada) sem tocar em regra de negócio: todas as respostas de
// pedido/valor continuam vindo mockadas do "backend" (page.route), só a
// camada visual é exercitada aqui.

const produtoApi = {
  id: 970,
  codigo_p: "TESTE-970",
  nome: "Cristal de teste",
  categoria: "Cristais",
  descricao: "Produto controlado para teste de UX do checkout.",
  preco: 45.5,
  quantidade: 9,
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

function respostaPedido({ id = "PED-UX-1", expiraEmMs = 15 * 60_000 } = {}) {
  return {
    id,
    pix_copia_cola: `00020101021226800014br.gov.bcb.pix-${id}`,
    pix_txid: `TX-${id}`,
    expira_em: new Date(Date.now() + expiraEmMs).toISOString(),
    total_final: 45.5,
    desconto: 0,
    pix: {
      chave_mascarada: "ab***@mistica.com.br",
      recebedor: "Mistica Presentes LTDA",
      nome_loja: "Mistica Presentes",
      cidade: "PORTO ALEGRE",
    },
  };
}

async function gerarPixComSucesso(page, opts) {
  await page.route("**/api/checkout/pedidos", async route => {
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(respostaPedido(opts)) });
  });
  await page.goto("/index.html");
  await expect.poll(() => page.evaluate(() => window.misticaCatalogState)).toBe("ready");
  await page.locator("[data-product-grid] button", { hasText: "Adicionar" }).click();
  await page.locator("[data-generate-pix]").dispatchEvent("click");
  await expect(page.locator("#pixStatus")).toContainText("aguardando pagamento", { ignoreCase: true });
}

test.describe("checkout: melhorias de UX do Pix", () => {
  test("botão Gerar Pix fica travado como 'Pix gerado' após sucesso", async ({ page }) => {
    await prepararCatalogo(page);
    await gerarPixComSucesso(page);

    const gerarPix = page.locator("[data-generate-pix]");
    await expect(gerarPix).toBeDisabled();
    await expect(gerarPix).toHaveText("Pix gerado");
  });

  test("botão Já realizei o pagamento aparece, registra uma vez e trava contra clique duplo", async ({ page }) => {
    await prepararCatalogo(page);
    await gerarPixComSucesso(page);

    let chamadas = 0;
    await page.route("**/api/pedidos/*/comprovante", async route => {
      chamadas += 1;
      await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify({ status: "Comprovante enviado", ja_registrado: chamadas > 1 }) });
    });

    const botaoComprovante = page.locator("[data-send-pix-comprovante]");
    await expect(botaoComprovante).toBeVisible();
    await expect(botaoComprovante).toHaveText("Já realizei o pagamento");

    // Dois cliques rápidos: só uma chamada ao backend deve ocorrer, e o
    // pagamento nunca é marcado como confirmado pelo clique do cliente.
    await botaoComprovante.dispatchEvent("click");
    await botaoComprovante.dispatchEvent("click");

    await expect(page.locator("#pixComprovanteFeedback")).toContainText("Pagamento informado. Seu pedido será conferido pela loja.");
    await expect.poll(() => chamadas).toBe(1);

    const statusLabel = await page.locator("#pixPedidoStatus").textContent();
    expect(statusLabel).not.toMatch(/confirmado/i);
    expect(statusLabel).toMatch(/aguardando conferência da loja/i);
  });

  test("feedback de cópia do Pix usa a mensagem completa e aria-live", async ({ page, context }) => {
    await prepararCatalogo(page);
    await context.grantPermissions(["clipboard-read", "clipboard-write"]);
    await gerarPixComSucesso(page);

    const feedback = page.locator("#pixCopyFeedback");
    await expect(feedback).toHaveAttribute("aria-live", "polite");
    await page.locator("[data-copy-pix]").click();
    await expect(feedback).toContainText("Código Pix copiado com sucesso! Cole no aplicativo do seu banco para concluir o pagamento.");
  });

  test("contador de reserva mostra 'Reserva expira em MM:SS' e fica urgente perto do fim", async ({ page }) => {
    await prepararCatalogo(page);
    await gerarPixComSucesso(page, { expiraEmMs: 4 * 60_000 + 30_000 });

    const reserva = page.locator("#pixReservaStatus");
    await expect(reserva).toContainText(/Atenção: reserva expira em 0?4:/);
    await expect(reserva).toHaveAttribute("data-urgent", "true");
  });

  test("reserva expirada desabilita copiar e Já realizei o pagamento, e destrava Gerar Pix", async ({ page }) => {
    await prepararCatalogo(page);
    await gerarPixComSucesso(page, { expiraEmMs: -1000 });

    const reserva = page.locator("#pixReservaStatus");
    await expect(reserva).toContainText(/Reserva expirada/i);
    await expect(reserva).toHaveAttribute("data-expired", "true");
    await expect(page.locator("[data-copy-pix]")).toBeDisabled();
    await expect(page.locator("[data-send-pix-comprovante]")).toBeDisabled();
    await expect(page.locator("[data-generate-pix]")).toBeEnabled();
  });

  test("chave Pix aparece mascarada por padrão e alterna com o botão Mostrar/Ocultar", async ({ page }) => {
    await prepararCatalogo(page);
    await gerarPixComSucesso(page);

    const pixKey = page.locator("#pixKey");
    const toggle = page.locator("[data-toggle-pix-key]");
    await expect(pixKey).toHaveValue(/oculta/i);
    await expect(toggle).toHaveText("Mostrar chave");

    await toggle.click();
    await expect(pixKey).toHaveValue("ab***@mistica.com.br");
    await expect(toggle).toHaveText("Ocultar chave");

    await toggle.click();
    await expect(pixKey).toHaveValue(/oculta/i);
  });

  test("itens do carrinho mostram nome, quantidade, preço unitário e subtotal separados", async ({ page }) => {
    await prepararCatalogo(page);
    await page.goto("/index.html");
    await expect.poll(() => page.evaluate(() => window.misticaCatalogState)).toBe("ready");
    await page.locator("[data-product-grid] button", { hasText: "Adicionar" }).click();

    const item = page.locator("#cartList .cart-item").first();
    await expect(item.locator(".cart-item-name")).toHaveText("Cristal de teste");
    await expect(item).toContainText("1 × R$ 45,50");
    await expect(item).toContainText("Subtotal: R$ 45,50");
    // Nunca texto colado tipo "Cristal de teste1x".
    await expect(item.locator(".cart-item-name")).not.toHaveText(/\d/);
  });

  test("total do pedido preserva o valor exibido e ganha rótulo/hierarquia", async ({ page }) => {
    await prepararCatalogo(page);
    await page.goto("/index.html");
    await expect.poll(() => page.evaluate(() => window.misticaCatalogState)).toBe("ready");
    await page.locator("[data-product-grid] button", { hasText: "Adicionar" }).click();

    await expect(page.locator(".total-box-label")).toHaveText("Total do pedido");
    await expect(page.locator("#cartTotal")).toHaveText("R$ 45,50");
  });

  test("indicador de etapas destaca a etapa atual sem alterar navegação", async ({ page }) => {
    await prepararCatalogo(page);
    await page.goto("/index.html");
    await expect.poll(() => page.evaluate(() => window.misticaCatalogState)).toBe("ready");

    const steps = page.locator("#checkoutSteps .checkout-step");
    await expect(steps.first()).toHaveAttribute("aria-current", "step");

    await page.locator("[data-product-grid] button", { hasText: "Adicionar" }).click();
    await page.locator("[data-generate-pix]").dispatchEvent("click");
    await page.route("**/api/checkout/pedidos", async route => {
      await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(respostaPedido()) });
    });
  });

  test("aviso de segurança aparece abaixo do QR Code", async ({ page }) => {
    await prepararCatalogo(page);
    await page.goto("/index.html");
    await expect.poll(() => page.evaluate(() => window.misticaCatalogState)).toBe("ready");
    await expect(page.locator(".pix-security-note")).toContainText("Pagamento seguro via Pix. Nunca solicitamos senha, código do banco ou token de autenticação.");
  });

  test("layout responsivo: sem overflow horizontal em mobile 360px e 390px", async ({ page }) => {
    await prepararCatalogo(page);
    for (const width of [360, 390]) {
      await page.setViewportSize({ width, height: 800 });
      await page.goto("/index.html");
      await expect.poll(() => page.evaluate(() => window.misticaCatalogState)).toBe("ready");
      const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
      expect(overflow).toBeLessThanOrEqual(1);
    }
  });
});
