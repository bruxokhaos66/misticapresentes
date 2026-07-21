const { test, expect } = require("@playwright/test");

// Fase 3 — correção do bloqueante: a escolha de retirada/entrega continua
// sendo uma decisão explícita do cliente (nenhuma opção pré-selecionada),
// mas os botões de pagamento agora começam desabilitados e só liberam
// quando a modalidade (e o endereço, quando aplicável) estiverem prontos —
// nunca depois do clique, como acontecia antes desta correção.

const produtoApi = {
  id: 980,
  codigo_p: "TESTE-980",
  nome: "Amuleto de teste — Fase 3",
  categoria: "Cristais",
  descricao: "Produto controlado para teste de obrigatoriedade de modalidade.",
  preco: 59.9,
  quantidade: 10,
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

function respostaPedido(id = "PED-OBR-1") {
  return {
    id,
    pix_copia_cola: `00020101021226800014br.gov.bcb.pix-${id}`,
    pix_txid: `TX-${id}`,
    expira_em: new Date(Date.now() + 15 * 60_000).toISOString(),
    total_final: 59.9,
    desconto: 0,
  };
}

async function irParaCheckoutComCarrinho(page) {
  await prepararCatalogo(page);
  await page.goto("/index.html");
  await expect.poll(() => page.evaluate(() => window.misticaCatalogState)).toBe("ready");
  await page.locator("[data-product-grid] button", { hasText: "Adicionar" }).click();
  await expect(page.locator("#cartList")).toContainText("Amuleto de teste — Fase 3");
}

const enderecoValidoChapeco = {
  cep: "89801000",
  rua: "Rua Teste",
  numero: "100",
  bairro: "Centro",
  cidade: "Chapecó",
  uf: "SC",
};

async function preencherEndereco(page, dados) {
  if (dados.cep !== undefined) await page.locator("#enderecoCep").fill(dados.cep);
  if (dados.rua !== undefined) await page.locator("#enderecoRua").fill(dados.rua);
  if (dados.numero !== undefined) await page.locator("#enderecoNumero").fill(dados.numero);
  if (dados.bairro !== undefined) await page.locator("#enderecoBairro").fill(dados.bairro);
  if (dados.cidade !== undefined) await page.locator("#enderecoCidade").fill(dados.cidade);
  if (dados.uf !== undefined) await page.locator("#enderecoUf").fill(dados.uf);
}

test.describe("Fase 3 — obrigatoriedade de modalidade não bloqueia mais o checkout", () => {
  test("1) ao carregar o checkout, nenhuma modalidade está selecionada", async ({ page }) => {
    await irParaCheckoutComCarrinho(page);
    const marcados = await page.locator('[data-recebimento-radio]:checked').count();
    expect(marcados).toBe(0);
  });

  test("2) botão de Pix começa desabilitado", async ({ page }) => {
    await irParaCheckoutComCarrinho(page);
    await expect(page.locator("[data-generate-pix]")).toBeDisabled();
  });

  test("3) botão de cartão começa desabilitado", async ({ page }) => {
    await irParaCheckoutComCarrinho(page);
    await expect(page.locator("#mpCardSubmit")).toBeDisabled();
  });

  test("4) selecionar retirada habilita o pagamento", async ({ page }) => {
    await irParaCheckoutComCarrinho(page);
    await page.locator('[data-recebimento-radio][value="retirada"]').check();
    await expect(page.locator("[data-generate-pix]")).toBeEnabled();
  });

  test("5) selecionar entrega sem endereço mantém pagamento desabilitado", async ({ page }) => {
    await irParaCheckoutComCarrinho(page);
    await page.locator('[data-recebimento-radio][value="entrega"]').check();
    await expect(page.locator("[data-generate-pix]")).toBeDisabled();
  });

  test("6) preencher endereço válido habilita pagamento", async ({ page }) => {
    await irParaCheckoutComCarrinho(page);
    await page.locator('[data-recebimento-radio][value="entrega"]').check();
    await preencherEndereco(page, enderecoValidoChapeco);
    await expect(page.locator("[data-generate-pix]")).toBeEnabled();
  });

  test("7) apagar um campo obrigatório desabilita novamente", async ({ page }) => {
    await irParaCheckoutComCarrinho(page);
    await page.locator('[data-recebimento-radio][value="entrega"]').check();
    await preencherEndereco(page, enderecoValidoChapeco);
    await expect(page.locator("[data-generate-pix]")).toBeEnabled();

    await page.locator("#enderecoCidade").fill("");
    await expect(page.locator("[data-generate-pix]")).toBeDisabled();
  });

  test("8) clique alternativo sem modalidade não cria chamada de rede", async ({ page }) => {
    await irParaCheckoutComCarrinho(page);
    let chamadas = 0;
    await page.route("**/api/checkout/pedidos", async route => {
      chamadas += 1;
      await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(respostaPedido()) });
    });

    // Botão desabilitado bloqueia o clique real; simulamos um acionamento
    // alternativo (evento sintético) para provar que o guard defensivo em
    // JS também nunca chama a API sem modalidade válida.
    await page.locator("[data-generate-pix]").dispatchEvent("click");
    await page.waitForTimeout(300);
    expect(chamadas).toBe(0);
  });

  test("9) foco vai para a seção ao tentar avançar sem escolha", async ({ page }) => {
    await irParaCheckoutComCarrinho(page);
    await page.locator("[data-generate-pix]").dispatchEvent("click");
    await expect(page.locator('[data-recebimento-radio]').first()).toBeFocused();
  });

  test("10) mensagem é anunciada por aria-live", async ({ page }) => {
    await irParaCheckoutComCarrinho(page);
    const validacao = page.locator("#recebimentoValidacao");
    await expect(validacao).toBeVisible();
    await expect(validacao).toHaveAttribute("aria-live", "assertive");
    await expect(validacao).toContainText("Escolha retirada ou entrega para continuar");
  });

  test("11) duplo clique continua sem duplicar pedido", async ({ page }) => {
    await irParaCheckoutComCarrinho(page);
    let chamadas = 0;
    await page.route("**/api/checkout/pedidos", async route => {
      chamadas += 1;
      await new Promise(resolve => setTimeout(resolve, 150));
      await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(respostaPedido()) });
    });

    await page.locator('[data-recebimento-radio][value="retirada"]').check();
    const gerarPix = page.locator("[data-generate-pix]");
    await gerarPix.dispatchEvent("click");
    await gerarPix.dispatchEvent("click");

    await expect(page.locator("#pixStatus")).toContainText("aguardando pagamento", { ignoreCase: true });
    expect(chamadas).toBe(1);
  });

  test("12) troca de entrega para retirada remove a exigência de endereço", async ({ page }) => {
    await irParaCheckoutComCarrinho(page);
    await page.locator('[data-recebimento-radio][value="entrega"]').check();
    await expect(page.locator("[data-generate-pix]")).toBeDisabled();

    await page.locator('[data-recebimento-radio][value="retirada"]').check();
    await expect(page.locator("[data-generate-pix]")).toBeEnabled();
    await expect(page.locator("#enderecoEntregaForm")).toBeHidden();
  });

  test("13) troca de retirada para entrega volta a exigir endereço", async ({ page }) => {
    await irParaCheckoutComCarrinho(page);
    await page.locator('[data-recebimento-radio][value="retirada"]').check();
    await expect(page.locator("[data-generate-pix]")).toBeEnabled();

    await page.locator('[data-recebimento-radio][value="entrega"]').check();
    await expect(page.locator("[data-generate-pix]")).toBeDisabled();
    await expect(page.locator("#enderecoEntregaForm")).toBeVisible();
  });

  test("14) layout mobile não apresenta sobreposição na seção de recebimento", async ({ page }) => {
    await page.setViewportSize({ width: 360, height: 800 });
    await irParaCheckoutComCarrinho(page);
    await page.locator('[data-recebimento-radio][value="entrega"]').check();
    await preencherEndereco(page, enderecoValidoChapeco);
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
    expect(overflow).toBeLessThanOrEqual(1);
  });

  test("15) teclado permite escolher a modalidade e prosseguir", async ({ page }) => {
    await irParaCheckoutComCarrinho(page);
    await page.route("**/api/checkout/pedidos", route => route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(respostaPedido()),
    }));

    const primeiroRadio = page.locator('[data-recebimento-radio]').first();
    await primeiroRadio.focus();
    await page.keyboard.press("Space");
    await expect(page.locator('[data-recebimento-radio][value="retirada"]')).toBeChecked();
    await expect(page.locator("[data-generate-pix]")).toBeEnabled();

    await page.locator("[data-generate-pix]").focus();
    await page.keyboard.press("Enter");
    await expect(page.locator("#pixStatus")).toContainText("aguardando pagamento", { ignoreCase: true });
  });

  test("16) carrinho permanece intacto após tentativa inválida", async ({ page }) => {
    await irParaCheckoutComCarrinho(page);
    await page.locator("[data-generate-pix]").dispatchEvent("click");
    await expect(page.locator("#cartList")).toContainText("Amuleto de teste — Fase 3");
  });
});
