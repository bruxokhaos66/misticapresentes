(() => {
  const cfg = window.misticaSiteConfig || {};
  const API_BASE = String(cfg.apiBaseUrl || "https://api.misticaesotericos.com.br").replace(/\/$/, "");

  function montarConteudo(campanha) {
    const frag = document.createDocumentFragment();
    const titulo = document.createElement("strong");
    titulo.textContent = campanha.titulo;
    frag.appendChild(titulo);
    if (campanha.descricao) {
      frag.appendChild(document.createTextNode(` — ${campanha.descricao}`));
    }
    if (campanha.codigo_cupom) {
      frag.appendChild(document.createTextNode(" Use o cupom "));
      const cupom = document.createElement("strong");
      cupom.textContent = campanha.codigo_cupom;
      frag.appendChild(cupom);
      frag.appendChild(document.createTextNode("."));
    }
    return frag;
  }

  function linkSeguro(link) {
    if (!link) return null;
    try {
      const url = new URL(link, window.location.href);
      return url.protocol === "http:" || url.protocol === "https:" ? url.href : null;
    } catch {
      return null;
    }
  }

  function montarBanner(campanha) {
    const banner = document.createElement("div");
    banner.className = "campaign-banner";
    banner.setAttribute("role", "note");
    const href = linkSeguro(campanha.link);
    if (href) {
      const link = document.createElement("a");
      link.href = href;
      link.appendChild(montarConteudo(campanha));
      banner.appendChild(link);
    } else {
      banner.appendChild(montarConteudo(campanha));
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
