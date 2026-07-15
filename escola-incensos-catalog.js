(() => {
  "use strict";
  const grid = document.querySelector("[data-escola-grid]");
  if (!grid) return;

  function addCard() {
    if (grid.querySelector('[data-course="incensos-introducao"]')) return true;
    if (!grid.children.length) return false;
    const card = document.createElement("article");
    card.className = "course-card is-free";
    card.dataset.course = "incensos-introducao";
    const capa = window.INCENSOS_ASSETS?.curso || "assets/escola/incensos/incensos-curso-capa.webp";
    card.innerHTML = `
      <div class="course-card-cover" style="background-image:linear-gradient(180deg,transparent,rgba(0,0,0,.88)),url('${capa}')">
        <span class="course-card-badge">Gratuito</span>
        <span class="course-card-icon" aria-hidden="true">🔥</span>
      </div>
      <div class="course-card-body">
        <div class="course-card-tags"><span>Incensos</span><span>Iniciante</span></div>
        <h3>Incensos: História, Cultura e Tradições</h3>
        <p>Conheça a origem dos incensos, suas rotas históricas, usos culturais, presença em tradições espirituais e cuidados para uma queima consciente.</p>
        <a class="btn" href="escola-incensos.html">Começar gratuitamente</a>
      </div>`;
    grid.insertBefore(card, grid.children[1] || null);
    return true;
  }

  if (addCard()) return;
  const observer = new MutationObserver(() => {
    if (addCard()) observer.disconnect();
  });
  observer.observe(grid, { childList: true });
})();
