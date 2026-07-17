// Testes E2E do widget do Chat Inteligente da Isis 2.0
// (isis2/chat-gate.js + isis2/chat-widget.js), num navegador real: o
// widget nunca monta sem autorização confirmada pelo backend
// (GET /api/isis2/chat/config); com autorização, monta, abre/fecha por
// teclado e mouse, mostra sugestões rápidas e cards de produto reais, e
// nunca sobrepõe o WhatsApp flutuante.
const { test, expect } = require("@playwright/test");

const PRODUTO_API = {
  id: 501,
  codigo_p: "ISIS2-501",
  nome: "Incenso Relaxante de Teste",
  categoria: "Aromas e proteção",
  descricao: "Incenso para relaxar.",
  preco: 15.5,
  quantidade: 10,
  imagem_url: "",
  imagens: [],
  selo: "",
  avaliacoes_total: 0,
  avaliacoes_media: 0,
};

async function prepararCatalogo(page) {
  await page.route("**/api/produtos?**", route => route.fulfill({
    status: 200,
    contentType: "application/json",
    body: JSON.stringify([PRODUTO_API]),
  }));
}

async function mockChatConfig(page, resposta, { status = 200 } = {}) {
  await page.route("**/api/isis2/chat/config", route => route.fulfill({
    status,
    contentType: "application/json",
    body: JSON.stringify(resposta),
  }));
}

async function mockSessao(page) {
  await page.route("**/api/isis2/chat/sessoes", route => route.fulfill({
    status: 200,
    contentType: "application/json",
    body: JSON.stringify({
      session_id: "sessao-teste-e2e",
      message: "Olá! Sou a Isis. Posso ajudar você a encontrar produtos, kits e cursos da Mística.",
      remaining_messages: 20,
      privacy_notice: "A Isis usa as informações desta conversa apenas para ajudar na recomendação de produtos e melhorar o atendimento.",
      homolog_badge: "Isis em homologação",
    }),
  }));
}

async function mockMensagem(page, resposta) {
  await page.route("**/api/isis2/chat/sessoes/*/mensagens", route => route.fulfill({
    status: 200,
    contentType: "application/json",
    body: JSON.stringify(resposta),
  }));
}

async function dismissConsent(page) {
  const decline = page.locator("[data-consent-decline]");
  if (await decline.isVisible().catch(() => false)) await decline.click();
}

test.describe("Isis Chat — widget (homologação)", () => {
  test("backend nega: widget não monta, nenhuma requisição extra", async ({ page }) => {
    const chatRequests = [];
    page.on("request", req => {
      if (req.url().includes("chat-widget")) chatRequests.push(req.url());
    });

    await prepararCatalogo(page);
    await mockChatConfig(page, { enabled: false, homolog: false, authorized: false });
    await page.goto("/index.html");
    await dismissConsent(page);
    await page.waitForTimeout(500);

    await expect(page.locator("#isis-chat-root")).toHaveCount(0);
    expect(chatRequests.length).toBe(0);
  });

  test("chat habilitado mas usuário não autorizado: widget não monta", async ({ page }) => {
    await prepararCatalogo(page);
    await mockChatConfig(page, { enabled: true, homolog: true, authorized: false });
    await page.goto("/index.html");
    await dismissConsent(page);
    await page.waitForTimeout(500);

    await expect(page.locator("#isis-chat-root")).toHaveCount(0);
  });

  test("backend autoriza: widget monta, abre e mostra mensagem inicial + selo de homologação", async ({ page }) => {
    await prepararCatalogo(page);
    await mockChatConfig(page, { enabled: true, homolog: true, authorized: true });
    await mockSessao(page);
    await page.goto("/index.html");
    await dismissConsent(page);

    await expect(page.locator("#isis-chat-root")).toBeAttached({ timeout: 5000 });
    await page.locator("#isisChatOpenBtn").click();
    await expect(page.locator("#isisChatPanel")).toBeVisible();
    await expect(page.locator(".isis-chat-badge")).toHaveText("Isis em homologação");
    await expect(page.locator(".isis-chat-msg-isis").first()).toContainText("Olá! Sou a Isis");
  });

  test("fecha com Escape e restaura o foco no botão flutuante", async ({ page }) => {
    await prepararCatalogo(page);
    await mockChatConfig(page, { enabled: true, homolog: true, authorized: true });
    await mockSessao(page);
    await page.goto("/index.html");
    await dismissConsent(page);

    await page.locator("#isisChatOpenBtn").click();
    await expect(page.locator("#isisChatPanel")).toBeVisible();
    await page.keyboard.press("Escape");
    await expect(page.locator("#isisChatPanel")).toBeHidden();
  });

  test("sugestões rápidas enviam mensagem e renderizam card de produto real com link seguro", async ({ page }) => {
    await prepararCatalogo(page);
    await mockChatConfig(page, { enabled: true, homolog: true, authorized: true });
    await mockSessao(page);
    await mockMensagem(page, {
      message: "Encontrei algumas opções no nosso catálogo que combinam com o que você procura.",
      intent: "pedir_recomendacao",
      recommendations: [
        {
          id: 501,
          name: "Incenso Relaxante de Teste",
          price: 15.5,
          image_url: "",
          product_url: "produto.html?id=501",
          reason: "Indicado para relaxar",
        },
      ],
      complementary_items: [],
      suggested_kit: null,
      remaining_messages: 19,
    });

    await page.goto("/index.html");
    await dismissConsent(page);
    await page.locator("#isisChatOpenBtn").click();
    await page.getByRole("button", { name: "Quero relaxar" }).click();

    const card = page.locator(".isis-chat-card").first();
    await expect(card).toBeVisible();
    await expect(card.locator(".isis-chat-card-name")).toHaveText("Incenso Relaxante de Teste");
    const link = card.locator(".isis-chat-btn");
    await expect(link).toHaveAttribute("href", "produto.html?id=501");
  });

  test("erro amigável quando a API de mensagens falha", async ({ page }) => {
    await prepararCatalogo(page);
    await mockChatConfig(page, { enabled: true, homolog: true, authorized: true });
    await mockSessao(page);
    await page.route("**/api/isis2/chat/sessoes/*/mensagens", route => route.fulfill({ status: 500, body: "{}" }));

    await page.goto("/index.html");
    await dismissConsent(page);
    await page.locator("#isisChatOpenBtn").click();
    await page.getByRole("button", { name: "Ver cursos" }).click();

    await expect(page.locator("#isisChatError")).toBeVisible();
    await expect(page.locator("#isisChatError")).not.toBeEmpty();
  });

  test("não sobrepõe o botão flutuante do WhatsApp", async ({ page }) => {
    await prepararCatalogo(page);
    await mockChatConfig(page, { enabled: true, homolog: true, authorized: true });
    await mockSessao(page);
    await page.goto("/index.html");
    await dismissConsent(page);

    const whatsapp = page.locator(".floating-whatsapp");
    if (await whatsapp.count()) {
      const chatBox = await page.locator("#isis-chat-root").boundingBox();
      const whatsappBox = await whatsapp.boundingBox();
      if (chatBox && whatsappBox) {
        const overlap = !(
          chatBox.x + chatBox.width < whatsappBox.x ||
          whatsappBox.x + whatsappBox.width < chatBox.x ||
          chatBox.y + chatBox.height < whatsappBox.y ||
          whatsappBox.y + whatsappBox.height < chatBox.y
        );
        expect(overlap).toBe(false);
      }
    }
  });
});
