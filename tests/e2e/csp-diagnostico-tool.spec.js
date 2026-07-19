const { test, expect } = require("@playwright/test");

/*
 * tests/manual/mp-csp-diagnostico.html é uma ferramenta de uso manual (não é
 * página pública) para homologar, num navegador real com acesso de rede ao
 * SDK do Mercado Pago, se o script inline bloqueado pela CSP é necessário
 * para o CardForm ficar interativo -- ver docs/admin/CSP.md.
 *
 * Este ambiente de CI/sandbox não tem acesso a sdk.mercadopago.com (mesma
 * limitação documentada em tests/e2e/csp-mercadopago-cardform.spec.js), então
 * não é possível montar o CardForm real aqui. Este teste valida só o
 * MECANISMO de captura da ferramenta (listener de securitypolicyviolation,
 * tabela na tela, nenhum dado sensível exposto) provocando uma violação de
 * CSP sintética (um <script> inline, bloqueado pela mesma script-src de
 * produção já embutida na página).
 */

test.describe("Ferramenta de diagnóstico CSP x CardForm (mecanismo de captura)", () => {
  test("captura uma violação de script-src e mostra effectiveDirective/sourceFile/lineNumber na tabela", async ({ page }) => {
    await page.goto("/tests/manual/mp-csp-diagnostico.html");

    await page.evaluate(() => {
      const script = document.createElement("script");
      script.textContent = "window.__naoDeveriaRodar = true;";
      document.body.appendChild(script);
    });

    await expect(page.locator("#violacoes tbody tr")).toHaveCount(1, { timeout: 5000 });
    const linha = page.locator("#violacoes tbody tr").first();
    await expect(linha.locator("td").nth(0)).toHaveText("script-src-elem");

    // Nunca executa o script bloqueado.
    const rodou = await page.evaluate(() => window.__naoDeveriaRodar);
    expect(rodou).toBeUndefined();
  });

  test("a tabela de violações nunca contém texto de cartão/CVV/token (a ferramenta não lê o DOM do CardForm)", async ({ page }) => {
    await page.goto("/tests/manual/mp-csp-diagnostico.html");
    await page.evaluate(() => {
      const script = document.createElement("script");
      script.textContent = "1+1;";
      document.body.appendChild(script);
    });
    await expect(page.locator("#violacoes tbody tr")).toHaveCount(1, { timeout: 5000 });

    const textoTabela = await page.locator("#violacoes").innerText();
    for (const termoProibido of ["cvv", "token", "cardNumber=", "cpf="]) {
      expect(textoTabela.toLowerCase()).not.toContain(termoProibido.toLowerCase());
    }
  });

  test("checklist manual e campo de hashes estão presentes para o uso real em sandbox", async ({ page }) => {
    await page.goto("/tests/manual/mp-csp-diagnostico.html");
    await expect(page.locator(".checklist input[type=checkbox]")).toHaveCount(8);
    await expect(page.locator("#hashesColados")).toBeVisible();
  });
});
