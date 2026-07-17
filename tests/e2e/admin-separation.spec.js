const { test, expect } = require("@playwright/test");

// Todas as páginas destes testes carregam uma folha de estilo bloqueante do
// Google Fonts (<link rel="stylesheet" href="https://fonts.googleapis.com/...">)
// -- o evento "load" só dispara depois que o navegador resolve (sucesso ou
// falha) esse recurso externo, e sob a rede deste ambiente de teste o tempo
// até essa falha é inconsistente, o que deixava esperas por "load" (mesmo
// implícitas, como o `waitForURL` padrão) intermitentemente lentas.
// Interceptar e responder esse recurso na hora remove essa variável de
// tempo externa, sem alterar nada do site em produção.
test.beforeEach(async ({ page }) => {
  await page.route("**/fonts.googleapis.com/**", route => route.fulfill({ status: 200, contentType: "text/css", body: "" }));
});

// index.html carrega o player ambiente (v2-shamanic-player.js), que mantém
// uma conexão de rede aberta para o áudio de fundo (preload="metadata") --
// sob o servidor estático de teste (python -m http.server, sem suporte a
// Range/206), essa conexão nunca fica ociosa, então `waitUntil: "networkidle"`
// (ou `waitForLoadState("networkidle")`) nunca resolve e o teste estoura o
// timeout de forma intermitente. Nenhuma das duas asserções abaixo depende
// de rede ociosa -- a marcação do admin (ou sua ausência) e o redirecionamento
// já existem no HTML/script síncrono processado no evento "load", então
// esperar só até "load" é suficiente e determinístico. O mesmo se aplica a
// admin.html: os scripts/estilos "sob demanda" do painel são injetados de
// forma síncrona por site-config.js (script defer, roda antes de "load"),
// então o evento "load" já aguarda esses recursos carregarem.
test("public index.html never ships the admin markup/scripts", async ({ page }) => {
  const requests = [];
  page.on("request", (r) => requests.push(r.url()));
  await page.goto("/index.html", { waitUntil: "load" });
  await expect(page.locator("#admin")).toHaveCount(0);
  expect(requests.some((u) => u.includes("v2-admin-products"))).toBe(false);
  expect(requests.some((u) => u.includes("v2-courses"))).toBe(false);
});

// Este teste navega para uma URL que se redireciona por JavaScript
// (site-config.js chama window.location.replace("admin.html") de forma
// síncrona, antes do evento "load" de index.html disparar). Esperar
// `waitUntil: "load"`/"networkidle" na PRÓPRIA navegação inicial é uma
// corrida conhecida do Playwright: o documento de origem é abandonado no
// meio do carregamento, então o evento que o goto() aguarda pode nunca
// disparar para aquele documento -- ocasionalmente (raro, mas observado em
// repeat-each=10) o goto() só resolve depois do timeout de 30s. Esperar só
// o "commit" da navegação inicial (cabeçalhos recebidos, sem aguardar
// carregar recursos) e observar o destino real do redirecionamento via
// `waitForURL` testa o comportamento que interessa sem essa corrida.
test("old #admin hash on index.html redirects to admin.html", async ({ page }) => {
  await page.goto("/index.html#admin", { waitUntil: "commit" });
  await page.waitForURL(/admin\.html$/, { waitUntil: "commit" });
  await expect(page).toHaveURL(/admin\.html$/);
});

test("admin.html loads the login panel and the on-demand admin assets", async ({ page }) => {
  const requests = [];
  page.on("request", (r) => requests.push(r.url()));
  await page.goto("/admin.html", { waitUntil: "load" });
  await expect(page.locator("#adminLoginForm")).toHaveCount(1);
  await expect(page.locator("#adminContent")).toBeHidden();
  await expect(page.locator("#adminUserLogin")).toHaveCount(1);
  expect(requests.some((u) => u.includes("v2-admin-products.css"))).toBe(true);
  expect(requests.some((u) => u.includes("v2-admin-products.js"))).toBe(true);
  expect(requests.some((u) => u.includes("v2-courses.css"))).toBe(true);
  expect(requests.some((u) => u.includes("v2-courses.js"))).toBe(true);
});
