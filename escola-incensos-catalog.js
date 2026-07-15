(() => {
  "use strict";
  const grid = document.querySelector("[data-escola-grid]");
  if (!grid) return;

  function addCard() {
    if (grid.querySelector('[data-course="incensos-introducao"]')) return true;
    if (!grid.children.length) return false;
    const card = document.createElement("article");
    // Reaproveita a mesma classe/estrutura do card de Xamanismo (escola.js)
    // para que os dois cards "gratuitos" tenham exatamente o mesmo padrão
    // visual (largura, altura, imagem, selo, tags, preço e botão).
    card.className = "escola-card";
    card.dataset.course = "incensos-introducao";
    const capa = window.INCENSOS_ASSETS?.curso || "assets/escola/incensos/incensos-curso-capa.webp";
    card.innerHTML = `
      <img class="escola-card-cover" src="${capa}" alt="Capa do curso Incensos: História, Cultura e Tradições" width="1200" height="630" loading="lazy" onerror="this.remove()">
      <span class="escola-badge gratuito">Gratuito</span>
      <div class="escola-card-icon" aria-hidden="true">🔥</div>
      <div class="escola-card-tags"><span>Incensos</span><span>Iniciante</span></div>
      <h3>Incensos: História, Cultura e Tradições</h3>
      <p>Conheça a origem dos incensos, suas rotas históricas, usos culturais, presença em tradições espirituais e cuidados para uma queima consciente.</p>
      <div class="escola-card-price"><strong>Grátis</strong><small>acesso imediato</small></div>
      <div class="escola-card-actions">
        <a class="btn btn-full" href="escola-incensos.html">Começar gratuitamente</a>
      </div>
      <p class="escola-card-note" aria-hidden="true">&nbsp;</p>`;
    grid.insertBefore(card, grid.children[1] || null);
    return true;
  }

  if (addCard()) return;
  const observer = new MutationObserver(() => {
    if (addCard()) observer.disconnect();
  });
  observer.observe(grid, { childList: true });
})();
