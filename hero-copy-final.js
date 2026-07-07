(() => {
  if (window.__MISTICA_HERO_COPY_FINAL__) return;
  window.__MISTICA_HERO_COPY_FINAL__ = true;

  function installStyle() {
    if (document.getElementById("misticaHeroCopyFinalStyle")) return;
    const style = document.createElement("style");
    style.id = "misticaHeroCopyFinalStyle";
    style.textContent = `
      body.mistica-home-premium .hero-section.legacy-premium-hero,
      .hero-section { min-height: 540px !important; padding: 34px 0 50px !important; }
      body.mistica-home-premium .legacy-premium-hero .hero-grid,
      .hero-grid { grid-template-columns: minmax(0,.86fr) minmax(280px,.52fr) !important; gap: clamp(22px,4vw,48px) !important; align-items:center !important; }
      body.mistica-home-premium .legacy-premium-hero .hero-copy h1,
      .hero-copy h1 { max-width: 520px !important; font-size: clamp(1.9rem,2.75vw,2.95rem) !important; line-height: 1.1 !important; letter-spacing: -.02em !important; }
      body.mistica-home-premium .legacy-premium-hero .hero-text,
      .hero-text { max-width: 500px !important; font-size: .98rem !important; line-height: 1.52 !important; }
      .legacy-isis-card { width: min(330px,100%) !important; min-height: 395px !important; border-radius: 24px !important; }
      .legacy-isis-symbol { width: 112px !important; height: 112px !important; font-size: 3rem !important; margin: 72px auto 54px !important; }
      .legacy-isis-orb { width: 180px !important; height: 180px !important; top: 102px !important; }
      .legacy-isis-caption { padding: 12px !important; border-radius: 15px !important; }
      .legacy-isis-caption strong { font-size: .84rem !important; }
      .legacy-isis-caption span { font-size: .8rem !important; }
      @media (max-width: 980px) { .hero-grid { grid-template-columns: 1fr !important; } .hero-copy { text-align:center !important; } .hero-copy h1, .hero-text { margin-left:auto !important; margin-right:auto !important; } }
    `;
    document.head.appendChild(style);
  }

  function apply() {
    installStyle();
    const title = document.querySelector("#inicio .hero-copy h1");
    if (title) title.textContent = "Mística Presentes: energia, proteção e beleza";
    const text = document.querySelector("#inicio .hero-text");
    if (text) text.textContent = "Cristais, incensos, velas, aromas e presentes com significado para transformar sua casa e seus momentos.";
    const caption = document.querySelector("#inicio .legacy-isis-caption span");
    if (caption) caption.textContent = "Produtos escolhidos para proteção, energia e presentes com significado.";
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", apply, { once: true });
  else apply();
  window.addEventListener("load", apply, { once: true });
})();
