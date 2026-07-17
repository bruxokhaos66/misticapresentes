(() => {
  "use strict";
  const grid = document.querySelector("[data-escola-grid]");
  if (!grid) return;

  function addCard() {
    if (grid.querySelector('[data-course="medicinas-floresta-introducao"]')) return true;
    if (!grid.children.length) return false;
    const card = document.createElement("article");
    // Reaproveita a mesma classe/estrutura do card de Xamanismo (escola.js)
    // para que os cards "gratuitos" tenham exatamente o mesmo padrão
    // visual (largura, altura, imagem, selo, tags, preço e botão).
    card.className = "escola-card";
    card.dataset.course = "medicinas-floresta-introducao";
    const capa = window.MEDICINAS_FLORESTA_ASSETS?.curso || "";
    const cover = capa
      ? `<img class="escola-card-cover" src="${capa}" alt="Capa do curso Medicinas da Floresta: primeiros caminhos" width="1200" height="630" loading="lazy" onerror="this.remove()">`
      : "";
    card.innerHTML = `
      ${cover}
      <span class="escola-badge gratuito">Gratuito</span>
      <div class="escola-card-icon" aria-hidden="true">🌿</div>
      <div class="escola-card-tags"><span>Rapé</span><span>Ayahuasca</span><span>Iniciante</span></div>
      <h3>Medicinas da Floresta: primeiros caminhos</h3>
      <p>Uma introdução responsável sobre rapé, ayahuasca, consagração, contexto cultural, segurança e os caminhos para aprofundar os estudos.</p>
      <div class="escola-card-price"><strong>Grátis</strong><small>acesso imediato</small></div>
      <div class="escola-card-actions">
        <a class="btn btn-full" href="escola-medicinas-floresta.html">Assistir à aula gratuita</a>
      </div>
      <p class="escola-card-note" aria-hidden="true">&nbsp;</p>`;
    grid.insertBefore(card, grid.children[2] || null);
    return true;
  }

  if (addCard()) return;
  const observer = new MutationObserver(() => {
    if (addCard()) observer.disconnect();
  });
  observer.observe(grid, { childList: true });
})();
