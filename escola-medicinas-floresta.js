(() => {
  "use strict";

  const STORAGE_KEY = "misticaMedicinasFlorestaAula1";
  const progressFill = document.querySelector("[data-progress-fill]");
  const progressLabel = document.querySelector("[data-progress-label]");
  const progressCount = document.querySelector("[data-progress-count]");
  const lessonBadge = document.querySelector("[data-lesson-badge]");
  const lessonStatus = document.querySelector("[data-lesson-status]");
  const lessonButton = document.querySelector(".medicinas-lesson");
  const completeButton = document.querySelector("[data-complete]");
  const finish = document.querySelector("[data-finish]");
  const courseCover = document.querySelector("[data-course-cover]");
  const lessonCover = document.querySelector("[data-lesson-cover]");

  function isDone() {
    return sessionStorage.getItem(STORAGE_KEY) === "done";
  }

  function applyAssets() {
    const assets = window.MEDICINAS_FLORESTA_ASSETS || {};
    if (courseCover && assets.curso) courseCover.style.setProperty("--course-cover", `url('${assets.curso}')`);
    if (lessonCover && assets.aula) lessonCover.style.setProperty("--lesson-cover", `url('${assets.aula}')`);
  }

  function render() {
    const done = isDone();
    if (progressFill) progressFill.style.width = done ? "100%" : "0%";
    if (progressLabel) progressLabel.textContent = done ? "100%" : "0%";
    if (progressCount) progressCount.textContent = done ? "1 de 1 aula concluída" : "0 de 1 aula concluída";
    if (lessonBadge) lessonBadge.textContent = done ? "✓" : "1";
    if (lessonStatus) lessonStatus.textContent = done ? "18 min · Concluída nesta sessão" : "18 min · Você está aqui";
    lessonButton?.classList.toggle("is-done", done);
    if (finish) finish.hidden = !done;
    if (completeButton) {
      completeButton.disabled = done;
      completeButton.textContent = done ? "Aula concluída ✓" : "Concluir a aula ✓";
    }
  }

  completeButton?.addEventListener("click", () => {
    sessionStorage.setItem(STORAGE_KEY, "done");
    render();
    finish?.scrollIntoView({
      behavior: matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth",
      block: "center",
    });
  });

  applyAssets();
  render();
})();
