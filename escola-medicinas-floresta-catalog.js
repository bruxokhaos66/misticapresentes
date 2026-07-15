(() => {
  "use strict";
  const grid = document.querySelector("[data-escola-grid]");
  if (!grid) return;

  function addCard() {
    if (grid.querySelector('[data-course="medicinas-floresta-introducao"]')) return true;
    if (!grid.children.length) return false;
    const card = document.createElement("article");
    card.className = "course-card is-free";
    card.dataset.course = "medicinas-floresta-introducao";
    const capa = window.MEDICINAS_FLORESTA_ASSETS?.curso || "";
    const cover = capa
      ? `linear-gradient(180deg,rgba(9,12,8,.12),rgba(0,0,0,.82)),url('${capa}')`
      : `radial-gradient(circle at 72% 28%,rgba(211,165,79,.25),transparent 12rem),linear-gradient(135deg,#101b12,#382018)`;
    card.innerHTML = `
      <div class="course-card-cover" style="background-image:${cover}">
        <span class="course-card-badge">Aula gratuita</span>
        <span class="course-card-icon" aria-hidden="true">🌿</span>
      </div>
      <div class="course-card-body">
        <div class="course-card-tags"><span>Rapé</span><span>Ayahuasca</span><span>Iniciante</span></div>
        <h3>Medicinas da Floresta: primeiros caminhos</h3>
        <p>Uma introdução responsável sobre rapé, ayahuasca, consagração, contexto cultural, segurança e os caminhos para aprofundar os estudos.</p>
        <a class="btn" href="escola-medicinas-floresta.html">Assistir à aula gratuita</a>
      </div>`;
    grid.insertBefore(card, grid.children[2] || null);
    return true;
  }

  if (addCard()) return;
  const observer = new MutationObserver(() => {
    if (addCard()) observer.disconnect();
  });
  observer.observe(grid, { childList: true });
})();
