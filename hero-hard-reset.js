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
        min-height: 610px !important;
        padding: clamp(38px, 5vw, 62px) 0 clamp(54px, 6vw, 74px) !important;
      }
      #inicio .hero-grid {
        display: grid !important;
        grid-template-columns: minmax(0,.9fr) minmax(320px,.58fr) !important;
        gap: clamp(30px,4.6vw,64px) !important;
        align-items: center !important;
      }
      #inicio .hero-copy .eyebrow {
        max-width: 620px !important;
      }
      #inicio .hero-copy h1 {
        max-width: 660px !important;
        margin-bottom: 20px !important;
        font-size: clamp(2.35rem,4.05vw,4.15rem) !important;
        line-height: 1.02 !important;
        letter-spacing: -.035em !important;
        text-transform: uppercase !important;
      }
      #inicio .hero-text {
        max-width: 610px !important;
        margin-bottom: 24px !important;
        font-size: clamp(.98rem,1.08vw,1.08rem) !important;
        line-height: 1.58 !important;
      }
      #inicio .hero-actions {
        gap: 12px !important;
      }
      #inicio .hero-actions .btn {
        min-height: 48px !important;
        padding-inline: 24px !important;
      }
      #inicio .trust-row {
        margin-top: 20px !important;
      }
      #inicio .hero-visual {
        display: grid !important;
        place-items: center !important;
      }
      #inicio .hero-isis-final-card {
        position: relative !important;
        width: min(390px,100%) !important;
        min-height: 520px !important;
        display: grid !important;
        align-content: end !important;
        padding: 22px !important;
        border: 1px solid rgba(240,197,106,.34) !important;
        border-radius: 30px !important;
        overflow: hidden !important;
        background:
          linear-gradient(180deg, rgba(3,3,5,.02), rgba(3,3,5,.08) 45%, rgba(3,3,5,.84) 100%),
          url('${ISIS_IMAGE}') center top / cover no-repeat,
          radial-gradient(circle at 50% 22%, rgba(240,197,106,.20), transparent 30%),
          linear-gradient(145deg, rgba(8,7,13,.94), rgba(34,24,44,.54)) !important;
        box-shadow: 0 28px 90px rgba(0,0,0,.42), 0 0 58px rgba(240,197,106,.12) !important;
      }
      #inicio .hero-isis-final-card::before,
      #inicio .hero-isis-final-card::after {
        display: none !important;
      }
      #inicio .hero-isis-final-caption {
        position: relative !important;
        z-index: 3 !important;
        border: 1px solid rgba(240,197,106,.28) !important;
        border-radius: 20px !important;
        padding: 16px !important;
        background: rgba(3,3,5,.72) !important;
        backdrop-filter: blur(14px) !important;
      }
      #inicio .hero-isis-final-caption strong {
        display: block !important;
        margin-bottom: 7px !important;
        color: #f0c56a !important;
        font-family: Cinzel, Georgia, serif !important;
        font-size: 1.02rem !important;
      }
      #inicio .hero-isis-final-caption span {
        color: #efe1c5 !important;
        font-size: .94rem !important;
        font-weight: 750 !important;
        line-height: 1.45 !important;
      }
      @media (max-width: 980px) {
        #inicio.hero-section { padding-top: 36px !important; }
        #inicio .hero-grid { grid-template-columns: 1fr !important; }
        #inicio .hero-copy { text-align: center !important; }
        #inicio .hero-copy .eyebrow,
        #inicio .hero-copy h1,
        #inicio .hero-text { margin-left: auto !important; margin-right: auto !important; }
        #inicio .hero-copy h1 { font-size: clamp(2.05rem, 8vw, 3.25rem) !important; }
        #inicio .hero-isis-final-card { min-height: 500px !important; }
      }
      @media (max-width: 560px) {
        #inicio .hero-copy h1 { font-size: clamp(1.95rem, 10vw, 2.8rem) !important; }
        #inicio .hero-actions .btn { width: 100% !important; }
        #inicio .hero-isis-final-card { min-height: 430px !important; border-radius: 26px !important; }
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
    if (title) title.textContent = "Presentes místicos fáceis de escolher, comprar e enviar pelo WhatsApp";
    const text = hero.querySelector(".hero-text");
    if (text) text.textContent = "Cristais, incensos, velas, aromas, banhos e kits especiais para escolher com segurança e finalizar o pedido em poucos cliques.";
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