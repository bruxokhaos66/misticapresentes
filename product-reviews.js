(() => {
  const API_BASE = ((window.misticaSiteConfig || {}).apiBaseUrl || "https://api.misticaesotericos.com.br").replace(/\/$/, "");
  const STARS = "★★★★★";

  function escapeHtml(value) {
    return String(value || "").replace(/[&<>"']/g, char => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[char]));
  }

  function starsHtml(nota) {
    const cheias = Math.round(Number(nota) || 0);
    return `<span class="review-stars" aria-hidden="true">${STARS.slice(0, cheias)}<span class="review-stars-empty">${STARS.slice(cheias)}</span></span>`;
  }

  function formatDate(iso) {
    try {
      return new Date(iso).toLocaleDateString("pt-BR");
    } catch {
      return "";
    }
  }

  function renderResumo(container, resumo) {
    const box = container.querySelector("[data-reviews-summary]");
    if (!resumo.total) {
      box.innerHTML = `<p class="reviews-empty">Ainda não há avaliações para este produto. Seja a primeira pessoa a avaliar!</p>`;
      return;
    }
    box.innerHTML = `
      ${starsHtml(resumo.media)}
      <strong>${resumo.media.toFixed(1).replace(".", ",")}</strong>
      <span class="reviews-count">${resumo.total} avaliaç${resumo.total === 1 ? "ão" : "ões"} de clientes</span>
    `;
  }

  function renderLista(container, avaliacoes) {
    const lista = container.querySelector("[data-reviews-list]");
    if (!avaliacoes.length) {
      lista.innerHTML = "";
      return;
    }
    lista.innerHTML = avaliacoes
      .map(item => `
        <li class="review-item">
          <div class="review-item-head">
            ${starsHtml(item.nota)}
            <strong>${escapeHtml(item.nome_cliente)}</strong>
            <time>${formatDate(item.data_hora)}</time>
          </div>
          ${item.comentario ? `<p>${escapeHtml(item.comentario)}</p>` : ""}
        </li>
      `)
      .join("");
  }

  async function carregarAvaliacoes(container, produtoId) {
    try {
      const response = await fetch(`${API_BASE}/api/produtos/${encodeURIComponent(produtoId)}/avaliacoes`);
      if (!response.ok) throw new Error("Falha ao carregar avaliações");
      const data = await response.json();
      renderResumo(container, data);
      renderLista(container, data.avaliacoes || []);
    } catch {
      container.querySelector("[data-reviews-summary]").innerHTML = `<p class="reviews-empty">Não foi possível carregar as avaliações agora.</p>`;
    }
  }

  function buildSection(product) {
    const section = document.createElement("section");
    section.className = "product-reviews";
    section.innerHTML = `
      <p class="eyebrow">Avaliações</p>
      <h2>O que dizem sobre ${escapeHtml(product.name)}</h2>
      <div class="reviews-summary" data-reviews-summary></div>
      <ul class="reviews-list" data-reviews-list></ul>
      <form class="reviews-form" data-reviews-form>
        <h3>Deixe sua avaliação</h3>
        <label>
          Seu nome
          <input type="text" name="nome_cliente" maxlength="60" required />
        </label>
        <label>
          Nota
          <select name="nota" required>
            <option value="5">★★★★★ Excelente</option>
            <option value="4">★★★★ Muito bom</option>
            <option value="3">★★★ Bom</option>
            <option value="2">★★ Regular</option>
            <option value="1">★ Ruim</option>
          </select>
        </label>
        <label>
          Comentário (opcional)
          <textarea name="comentario" maxlength="500" rows="3"></textarea>
        </label>
        <input type="text" name="empresa" class="reviews-honeypot" tabindex="-1" autocomplete="off" aria-hidden="true" />
        <button class="btn" type="submit">Enviar avaliação</button>
        <p class="reviews-form-status" data-reviews-form-status role="status"></p>
      </form>
    `;
    return section;
  }

  function installForm(section, product) {
    const form = section.querySelector("[data-reviews-form]");
    const status = section.querySelector("[data-reviews-form-status]");
    form.addEventListener("submit", async event => {
      event.preventDefault();
      if (form.empresa.value) return; // honeypot: bots preenchem campos ocultos
      const nome = form.nome_cliente.value.trim();
      const nota = Number(form.nota.value);
      const comentario = form.comentario.value.trim();
      if (nome.length < 2) {
        status.textContent = "Informe seu nome para enviar a avaliação.";
        return;
      }
      const button = form.querySelector("button[type=submit]");
      button.disabled = true;
      status.textContent = "Enviando...";
      try {
        const response = await fetch(`${API_BASE}/api/produtos/${encodeURIComponent(product.apiId)}/avaliacoes`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ nome_cliente: nome, nota, comentario }),
        });
        if (!response.ok) throw new Error("Falha ao enviar avaliação");
        status.textContent = "Obrigado! Sua avaliação foi publicada.";
        window.misticaTrack?.("submit_review", { item_id: product.apiId, item_name: product.name, rating: nota });
        form.reset();
        carregarAvaliacoes(section, product.apiId);
      } catch {
        status.textContent = "Não foi possível enviar agora. Tente novamente em instantes.";
      } finally {
        button.disabled = false;
      }
    });
  }

  function init(product) {
    if (!product || !product.apiId) return;
    const root = document.getElementById("produtoPageRoot");
    if (!root || root.querySelector(".product-reviews")) return;
    const section = buildSection(product);
    root.appendChild(section);
    installForm(section, product);
    carregarAvaliacoes(section, product.apiId);
  }

  window.addEventListener("mistica:product-rendered", event => init(event.detail?.product));
  if (window.misticaCurrentProduct) init(window.misticaCurrentProduct);
})();
