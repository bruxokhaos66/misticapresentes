(() => {
  "use strict";

  const ASSETS = window.INCENSOS_ASSETS || {};
  const HERO_BY_LESSON = { 1: ASSETS.aula1, 2: ASSETS.aula2, 3: ASSETS.aula3 };
  const preloaded = new Set();

  function preloadHero(id) {
    const src = HERO_BY_LESSON[id];
    if (!src || preloaded.has(src)) return;
    preloaded.add(src);
    const img = new Image();
    img.src = src;
  }

  function preloadNextHeroWhenIdle(id) {
    const connection = navigator.connection;
    if (connection && (connection.saveData || /(^|-)2g$/.test(connection.effectiveType || ""))) return;
    const run = () => preloadHero(id);
    if ("requestIdleCallback" in window) requestIdleCallback(run, { timeout: 2000 });
    else setTimeout(run, 1200);
  }

  const STORAGE_KEY = "misticaIncensosModulo1";
  const lessons = [...document.querySelectorAll("[data-lesson]")];
  const articles = [...document.querySelectorAll("[data-article]")];
  const progressFill = document.querySelector("[data-progress-fill]");
  const progressLabel = document.querySelector("[data-progress-label]");
  const progressCount = document.querySelector("[data-progress-count]");
  const finish = document.querySelector("[data-finish]");

  function loadState() {
    try {
      const parsed = JSON.parse(sessionStorage.getItem(STORAGE_KEY) || "{}");
      return { current: Number(parsed.current) || 1, done: Array.isArray(parsed.done) ? parsed.done.map(Number) : [] };
    } catch (_) {
      return { current: 1, done: [] };
    }
  }

  let state = loadState();

  function saveState() {
    sessionStorage.setItem(STORAGE_KEY, JSON.stringify(state));
  }

  function updateProgress() {
    const count = new Set(state.done).size;
    const pct = Math.round((count / 3) * 100);
    if (progressFill) progressFill.style.width = `${pct}%`;
    if (progressLabel) progressLabel.textContent = `${pct}%`;
    if (progressCount) progressCount.textContent = `${count} de 3 aulas concluídas`;
    lessons.forEach(button => {
      const id = Number(button.dataset.lesson);
      const done = state.done.includes(id);
      button.classList.toggle("is-done", done);
      const badge = button.querySelector(":scope > span:first-child");
      if (badge) badge.textContent = done ? "✓" : String(id);
      const status = button.querySelector("small");
      if (status) {
        const minutes = id === 2 ? 15 : 12;
        status.textContent = `${minutes} min · ${done ? "Concluída nesta sessão" : id === state.current ? "Você está aqui" : "Disponível"}`;
      }
    });
    if (finish) finish.hidden = !(state.done.includes(1) && state.done.includes(2) && state.done.includes(3));
  }

  function showLesson(id, { focus = true } = {}) {
    const target = articles.find(article => Number(article.dataset.article) === Number(id));
    if (!target) return;
    state.current = Number(id);
    saveState();
    articles.forEach(article => {
      const active = article === target;
      article.hidden = !active;
      article.classList.toggle("is-active", active);
    });
    lessons.forEach(button => {
      const active = Number(button.dataset.lesson) === Number(id);
      button.classList.toggle("is-active", active);
      if (active) button.setAttribute("aria-current", "page");
      else button.removeAttribute("aria-current");
    });
    updateProgress();
    document.title = `${target.querySelector("h2")?.textContent || "Incensos"} | Mística Escola`;
    window.scrollTo({ top: 0, behavior: matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth" });
    if (Number(id) < 3) preloadNextHeroWhenIdle(Number(id) + 1);
    if (focus) {
      const title = target.querySelector("h2");
      if (title) {
        title.tabIndex = -1;
        setTimeout(() => title.focus({ preventScroll: true }), 250);
      }
    }
  }

  lessons.forEach(button => button.addEventListener("click", () => showLesson(Number(button.dataset.lesson))));
  document.addEventListener("click", event => {
    const go = event.target.closest("[data-go]");
    if (go) showLesson(Number(go.dataset.go));

    const complete = event.target.closest("[data-complete]");
    if (!complete) return;
    const id = Number(complete.dataset.complete);
    if (!state.done.includes(id)) state.done.push(id);
    saveState();
    updateProgress();
    if (id < 3) showLesson(id + 1);
    else finish?.scrollIntoView({ behavior: matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth", block: "center" });
  });

  showLesson(Math.min(3, Math.max(1, state.current)), { focus: false });
})();
