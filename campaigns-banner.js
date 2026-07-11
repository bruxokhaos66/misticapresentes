(() => {
  const cfg = window.misticaSiteConfig || {};
  const API_BASE = String(cfg.apiBaseUrl || "https://api.misticaesotericos.com.br").replace(/\/$/, "");

  function montarBanner(campanha) {
    const banner = document.createElement("div");
    banner.className = "campaign-banner";
    banner.setAttribute("role", "note");
    const cupom = campanha.codigo_cupom ? ` Use o cupom <strong>${campanha.codigo_cupom}</strong>.` : "";
    const conteudo = `<strong>${campanha.titulo}</strong>${campanha.descricao ? ` — ${campanha.descricao}` : ""}${cupom}`;
    if (campanha.link) {
      const link = document.createElement("a");
      link.href = campanha.link;
      link.innerHTML = conteudo;
      banner.appendChild(link);
    } else {
      banner.innerHTML = conteudo;
    }
    return banner;
  }

  async function carregarCampanhas() {
    try {
      const resposta = await fetch(`${API_BASE}/api/campanhas/ativas`, { cache: "no-store" });
      if (!resposta.ok) return;
      const campanhas = await resposta.json();
      if (!Array.isArray(campanhas) || !campanhas.length) return;
      const container = document.createElement("div");
      container.id = "campaignBannerContainer";
      campanhas.slice(0, 3).forEach((campanha) => container.appendChild(montarBanner(campanha)));
      const ribbon = document.querySelector(".top-ribbon");
      if (ribbon) ribbon.insertAdjacentElement("afterend", container);
      else document.body.insertBefore(container, document.body.firstChild);
    } catch {
      // Falha ao buscar campanhas não deve impedir o carregamento do site.
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", carregarCampanhas);
  } else {
    carregarCampanhas();
  }
})();
