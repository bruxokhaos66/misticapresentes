const { test, expect } = require("@playwright/test");
const fs = require("node:fs");
const path = require("node:path");

const COMPONENT = ".escola-baloon";
const STORAGE_KEY = "misticaEscolaBaloonFechadoEm";
test.setTimeout(60_000);
const LAYERS = [
  ".escola-fx-halo-red",
  ".escola-fx-halo-orange",
  ".escola-fx-smoke",
  ".escola-fx-glow-outer",
  ".escola-fx-glow-inner",
  ".escola-fx-glass",
  ".escola-fx-rim",
  ".escola-baloon-particles",
];

async function openImmediately(page) {
  await page.addInitScript((key) => localStorage.removeItem(key), STORAGE_KEY);
  await page.goto("/index.html", { waitUntil: "domcontentloaded" });
  await page.locator(COMPONENT).waitFor({ state: "attached" });
  await page.locator(COMPONENT).evaluate((element) => element.classList.add("is-visible"));
  await expect(page.locator(COMPONENT)).toBeVisible();
}

test.beforeEach(async ({ page }) => {
  await page.route(/misticaesotericos\.com\.br/, (route) => route.abort());
});

test("CSS fica isolado e anima somente opacity/transform", async () => {
  const css = fs.readFileSync(path.join(__dirname, "..", "..", "escola-baloon.css"), "utf8");
  expect(css).not.toMatch(/(^|\n)\s*(?:body|html|main|section|\.card|\.glass|\.glow|\.overlay|\.content)\b[^{}]*\{/m);

  const forbiddenAnimatedProperties = /(?:background(?:-image)?|backdrop-filter|filter|box-shadow|mask|clip-path|width|height|top|right|bottom|left|margin|padding)\s*:/;
  let insideKeyframes = false;
  let keyframeDepth = 0;
  for (const line of css.split(/\r?\n/)) {
    if (line.includes("@keyframes")) insideKeyframes = true;
    if (insideKeyframes) {
      keyframeDepth += (line.match(/\{/g) || []).length - (line.match(/\}/g) || []).length;
      expect(line).not.toMatch(forbiddenAnimatedProperties);
      if (keyframeDepth === 0) insideKeyframes = false;
    }
  }
});

test("camadas permanecem filhas do card e limitadas ao halo", async ({ page }) => {
  await openImmediately(page);
  const audit = await page.evaluate(({ component, layers }) => {
    const root = document.querySelector(component);
    const rootRect = root.getBoundingClientRect();
    return {
      root: {
        position: getComputedStyle(root).position,
        isolation: getComputedStyle(root).isolation,
        width: rootRect.width,
        height: rootRect.height,
      },
      viewport: { width: innerWidth, scrollWidth: document.documentElement.scrollWidth },
      layers: layers.map((selector) => {
        const element = document.querySelector(selector);
        const rect = element.getBoundingClientRect();
        const style = getComputedStyle(element);
        return {
          selector,
          directChild: element.parentElement === root,
          display: style.display,
          pointerEvents: style.pointerEvents,
          x: rect.x,
          y: rect.y,
          right: rect.right,
          bottom: rect.bottom,
          filter: style.filter,
          backdropFilter: style.backdropFilter || style.webkitBackdropFilter,
          rootLeft: rootRect.left,
          rootTop: rootRect.top,
          rootRight: rootRect.right,
          rootBottom: rootRect.bottom,
        };
      }),
    };
  }, { component: COMPONENT, layers: LAYERS });

  expect(audit.root.position).toBe("fixed");
  expect(audit.root.isolation).toBe("isolate");
  expect(audit.viewport.scrollWidth).toBe(audit.viewport.width);
  for (const layer of audit.layers) {
    expect(layer.directChild).toBe(true);
    expect(layer.pointerEvents).toBe("none");

    if (layer.display === "none") {
      expect(audit.viewport.width).toBeLessThanOrEqual(560);
      expect(layer.selector).toBe(".escola-fx-smoke");
      continue;
    }

    expect(layer.x).toBeGreaterThanOrEqual(layer.rootLeft - 50);
    expect(layer.y).toBeGreaterThanOrEqual(layer.rootTop - 70);
    expect(layer.right).toBeLessThanOrEqual(layer.rootRight + 50);
    expect(layer.bottom).toBeLessThanOrEqual(layer.rootBottom + 50);
  }
});

test("abrir o card não altera pixels fora da margem de 50px", async ({ page }) => {
  await page.setViewportSize({ width: 1366, height: 768 });
  await page.goto("/index.html", { waitUntil: "domcontentloaded" });
  const card = page.locator(COMPONENT);
  await card.waitFor({ state: "attached" });
  const box = await card.boundingBox();

  await page.addStyleTag({ content: "* { animation-play-state: paused !important; transition: none !important; caret-color: transparent !important; }" });
  await page.waitForTimeout(1_000);

  const clips = [
    { x: Math.min(1365, box.x + box.width + 50), y: 0, width: Math.max(1, 1366 - box.x - box.width - 50), height: 768 },
    { x: 0, y: 0, width: 1366, height: Math.max(1, box.y - 50) },
  ];
  const before = [];
  for (const clip of clips) before.push(await page.screenshot({ clip }));

  await card.evaluate((element) => element.classList.add("is-visible"));
  await expect(card).toBeVisible();
  await page.waitForTimeout(500);
  for (let index = 0; index < clips.length; index += 1) {
    expect((await page.screenshot({ clip: clips[index] })).equals(before[index])).toBe(true);
  }
});

test("entrada, scroll, resize e fechamento não piscam nem alteram geometria", async ({ page }, testInfo) => {
  await page.setViewportSize({ width: 1366, height: 768 });
  await page.goto("/index.html", { waitUntil: "domcontentloaded" });
  const card = page.locator(COMPONENT);
  await card.waitFor({ state: "attached" });
  const initial = await card.evaluate((element) => ({ width: element.offsetWidth, height: element.offsetHeight }));
  const times = [0, 100, 250, 500, 900, 1500, 3000, 6000];
  await card.evaluate((element) => element.classList.add("is-visible"));
  let previous = 0;
  for (const time of times) {
    await page.waitForTimeout(time - previous);
    await page.screenshot({ path: testInfo.outputPath(`frame-${time}ms.png`) });
    previous = time;
  }
  const stable = await card.evaluate((element) => ({ width: element.offsetWidth, height: element.offsetHeight }));
  expect(Math.abs(stable.width - initial.width)).toBeLessThan(1);
  expect(Math.abs(stable.height - initial.height)).toBeLessThan(1);

  await page.evaluate(() => scrollTo(0, document.body.scrollHeight));
  await page.setViewportSize({ width: 1200, height: 700 });
  await expect(card).toBeVisible();
  await card.getByRole("button", { name: "Fechar aviso da Escola Mística" }).click();
  await expect(card).toBeHidden();
  await expect(card).toHaveCount(0, { timeout: 1_000 });
});

test("20 ciclos não deixam observers, listeners ou camadas órfãs", async ({ page }) => {
  test.setTimeout(120_000);
  await page.setViewportSize({ width: 390, height: 844 });
  await page.addInitScript(() => {
    window.__escolaAudit = { observers: 0, resizeListeners: 0 };
    const NativeObserver = window.MutationObserver;
    window.MutationObserver = class extends NativeObserver {
      constructor(callback) {
        super(callback);
        this.__active = false;
      }
      observe(...args) {
        if (!this.__active) window.__escolaAudit.observers += 1;
        this.__active = true;
        return super.observe(...args);
      }
      disconnect() {
        if (this.__active) window.__escolaAudit.observers -= 1;
        this.__active = false;
        return super.disconnect();
      }
    };
    const add = window.addEventListener.bind(window);
    const remove = window.removeEventListener.bind(window);
    window.addEventListener = (type, listener, options) => {
      if (type === "resize") window.__escolaAudit.resizeListeners += 1;
      return add(type, listener, options);
    };
    window.removeEventListener = (type, listener, options) => {
      if (type === "resize") window.__escolaAudit.resizeListeners -= 1;
      return remove(type, listener, options);
    };
  });
  await page.goto("/index.html", { waitUntil: "domcontentloaded" });
  const initialCard = page.locator(COMPONENT);
  await initialCard.waitFor({ state: "attached" });
  await initialCard.evaluate((element) => element.classList.add("is-visible"));

  const cta = initialCard.getByRole("link", { name: "Ver cursos" });
  await cta.evaluate((element) => {
    window.__escolaCtaClicked = false;
    element.addEventListener("click", (event) => {
      event.preventDefault();
      window.__escolaCtaClicked = true;
    }, { once: true });
  });
  await cta.click();
  expect(await page.evaluate(() => window.__escolaCtaClicked)).toBe(true);

  const initialClose = initialCard.getByRole("button", { name: "Fechar aviso da Escola Mística" });
  const closeSize = await initialClose.evaluate((element) => {
    const rect = element.getBoundingClientRect();
    return { width: rect.width, height: rect.height, zIndex: Number(getComputedStyle(element).zIndex) };
  });
  expect(closeSize.width).toBeGreaterThanOrEqual(36);
  expect(closeSize.height).toBeGreaterThanOrEqual(36);
  expect(closeSize.zIndex).toBeGreaterThanOrEqual(10);
  await initialClose.click();
  await expect(initialCard).toHaveCount(0, { timeout: 1_000 });
  const baseline = await page.evaluate(() => ({ ...window.__escolaAudit }));

  for (let cycle = 0; cycle < 20; cycle += 1) {
    await page.evaluate((key) => localStorage.removeItem(key), STORAGE_KEY);
    // url (não path): path injeta o conteúdo como <script> inline, bloqueado
    // pela CSP estrita (script-src sem 'unsafe-inline'); url injeta
    // <script src="/escola-baloon.js">, igual ao carregamento real em produção.
    await page.addScriptTag({ url: "/escola-baloon.js" });
    const card = page.locator(COMPONENT);
    await card.waitFor({ state: "attached" });
    await card.evaluate((element) => element.classList.add("is-visible"));
    await card.getByRole("button", { name: "Fechar aviso da Escola Mística" }).click();
    await expect(card).toHaveCount(0, { timeout: 1_000 });
  }

  const finalState = await page.evaluate(() => ({
    audit: { ...window.__escolaAudit },
    cards: document.querySelectorAll(".escola-baloon").length,
    layers: document.querySelectorAll('[class^="escola-fx-"]').length,
  }));
  expect(finalState.audit).toEqual(baseline);
  expect(finalState.cards).toBe(0);
  expect(finalState.layers).toBe(0);
});

test("prefers-reduced-motion mantém o card funcional e estático", async ({ page }) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  await openImmediately(page);
  await page.waitForTimeout(300);
  const animations = await page.locator(`${COMPONENT}, ${COMPONENT} *`).evaluateAll((elements) =>
    elements.flatMap((element) => element.getAnimations()).filter((animation) => animation.playState === "running").length
  );
  expect(animations).toBe(0);
  await expect(page.getByRole("link", { name: "Ver cursos" })).toHaveAttribute("href", "/escola.html");
});
