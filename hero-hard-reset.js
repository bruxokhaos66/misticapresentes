(() => {
  if (window.__MISTICA_HERO_HARD_RESET__) return;
  window.__MISTICA_HERO_HARD_RESET__ = true;

  const ISIS_IMAGE = "assets/isis-hero.webp.png?v=20260707-isis-upload";

  function css() {
    if (document.getElementById("misticaHeroHardResetStyle")) return;
    const style = document.createElement("style");
    style.id = "misticaHeroHardResetStyle";
    style.textContent = `
      #inicio.hero-section {
        min-height: 520px !important;
        padding: 34px 0 54px !important;
      }
      #inicio .hero-grid {
        display: grid !important;
        grid-template-columns: minmax(0,.88fr) minmax(300px,.50fr) !important;
        gap: clamp(26px,3.8vw,50px) !important;
        align-items: center !important;
      }
      #inicio .hero-copy .eyebrow {
        max-width: 520px !important;
        padding: 8px 12px !important;
        font-size: .76rem !important;
        line-height: 1.35 !important;
      }
      #inicio .hero-copy h1 {
        max-width: 560px !important;
        margin-bottom: 16px !important;
        font-size: clamp(2rem,3.05vw,3.15rem) !important;
        line-height: 1.06 !important;
        letter-spacing: -.025em !important;
        text-transform: uppercase !important;
      }
      #inicio .hero-text {
        max-width: 530px !important;
        margin-bottom: 20px !important;
        font-size: .96rem !important;
        line-height: 1.5 !important;
      }
      #inicio .hero-actions {
        gap: 11px !important;
      }
      #inicio .hero-actions .btn {
        min-height: 42px !important;
        padding: 11px 18px !important;
        font-size: .86rem !important;
      }
      #inicio .trust-row {
        display: none !important;
      }
      #inicio .hero-visual {
        display: grid !important;
        place-items: center !important;
      }
      #inicio .hero-isis-final-card {
        position: relative !important;
        width: min(330px,100%) !important;
        min-height: 430px !important;
        display: grid !important;
        align-content: end !important;
        padding: 18px !important;
        border: 1px solid rgba(240,197,106,.34) !important;
        border-radius: 26px !important;
        overflow: hidden !important;
        background:
          linear-gradient(180deg, rgba(3,3,5,.02), rgba(3,3,5,.08) 45%, rgba(3,3,5,.84) 100%),
          url('${ISIS_IMAGE}') center top / cover no-repeat,
          radial-gradient(circle at 50% 22%, rgba(240,197,106,.18), transparent 30%),
          linear-gradient(145deg, rgba(8,7,13,.94), rgba(34,24,44,.54)) !important;
        box-shadow: 0 24px 76px rgba(0,0,0,.40), 0 0 48px rgba(240,197,106,.11) !important;
      }
      #inicio .hero-isis-final-card::before,
      #inicio .hero-isis-final-card::after {
        display: none !important;
      }
      #inicio .hero-isis-final-caption {
        position: relative !important;
        z-index: 3 !important;
        border: 1px solid rgba(240,197,106,.28) !important;
        border-radius: 16px !important;
        padding: 12px !important;
        background: rgba(3,3,5,.72) !important;
        backdrop-filter: blur(14px) !important;
      }
      #inicio .hero-isis-final-caption strong {
        display: block !important;
        margin-bottom: 6px !important;
        color: #f0c56a !important;
        font-family: Cinzel, Georgia, serif !important;
        font-size: .88rem !important;
      }
      #inicio .hero-isis-final-caption span {
        color: #efe1c5 !important;
        font-size: .78rem !important;
        font-weight: 750 !important;
        line-height: 1.42 !important;
      }
      @media (max-width: 980px) {
        #inicio.hero-section { padding-top: 32px !important; }
        #inicio .hero-grid { grid-template-columns: 1fr !important; }
        #inicio .hero-copy { text-align: center !important; }
        #inicio .hero-copy .eyebrow,
        #inicio .hero-copy h1,
        #inicio .hero-text { margin-left: auto !important; margin-right: auto !important; }
        #inicio .hero-copy h1 { font-size: clamp(1.95rem, 7vw, 2.85rem) !important; }
        #inicio .hero-isis-final-card { min-height: 430px !important; width: min(350px,100%) !important; }
      }
      @media (max-width: 560px) {
        #inicio .hero-copy h1 { font-size: clamp(1.8rem, 9vw, 2.45rem) !important; }
        #inicio .hero-actions .btn { width: 100% !important; }
        #inicio .hero-isis-final-card { min-height: 385px !important; border-radius: 24px !important; }
      }
    `;
    document.head.appendChild(style);
  }

  function apply() {
    document.body.classList.add("mistica-home-premium");
    const hero = document.querySelector("#inicio.hero-section");
    if (!hero) return;
    hero.classList.add("legacy-premium-hero");
    const eyebrow = hero.querySelector(".hero-copy .eyebrow");
    if (eyebrow) eyebrow.textContent = "Mística Presentes • atendimento espiritual e comercial em Pinhalzinho-SC";
    const title = hero.querySelector(".hero-copy h1");
    if (title) title.textContent = "Presentes místicos fáceis de escolher e comprar pelo WhatsApp";
    const text = hero.querySelector(".hero-text");
    if (text) text.textContent = "Cristais, incensos, velas, aromas, banhos e kits especiais para escolher com segurança e finalizar em poucos cliques.";
    const visual = hero.querySelector(".hero-visual");
    if (visual) {
      visual.innerHTML = "";
      const card = document.createElement("div");
      card.className = "hero-isis-final-card";
      const caption = document.createElement("div");
      caption.className = "hero-isis-final-caption";
      const strong = document.createElement("strong");
      strong.textContent = "Curadoria Mística";
      const span = document.createElement("span");
      span.textContent = "Produtos escolhidos para intenção, beleza e significado.";
      caption.append(strong, span);
      card.appendChild(caption);
      visual.appendChild(card);
    }
  }

  css();
  apply();
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", () => { css(); apply(); }, { once: true });
  window.addEventListener("load", () => { css(); apply(); setTimeout(apply, 600); }, { once: true });
})();