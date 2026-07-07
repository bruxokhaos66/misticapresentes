(() => {
  if (window.__MISTICA_HERO_HARD_RESET__) return;
  window.__MISTICA_HERO_HARD_RESET__ = true;

  function css() {
    if (document.getElementById("misticaHeroHardResetStyle")) return;
    const style = document.createElement("style");
    style.id = "misticaHeroHardResetStyle";
    style.textContent = `
      #inicio.hero-section {
        min-height: 680px !important;
        padding: 56px 0 80px !important;
      }
      #inicio .hero-grid {
        display: grid !important;
        grid-template-columns: minmax(0,.94fr) minmax(340px,.66fr) !important;
        gap: clamp(36px,5vw,76px) !important;
        align-items: center !important;
      }
      #inicio .hero-copy h1 {
        max-width: 780px !important;
        font-size: clamp(2.7rem,4.8vw,5rem) !important;
        line-height: .97 !important;
        letter-spacing: -.04em !important;
        text-transform: uppercase !important;
      }
      #inicio .hero-text {
        max-width: 660px !important;
        font-size: clamp(1rem,1.2vw,1.12rem) !important;
        line-height: 1.6 !important;
      }
      #inicio .hero-visual {
        display: grid !important;
        place-items: center !important;
      }
      #inicio .hero-isis-final-card {
        width: min(440px,100%) !important;
        min-height: 620px !important;
        display: grid !important;
        align-content: end !important;
        padding: 26px !important;
        border: 1px solid rgba(240,197,106,.34) !important;
        border-radius: 34px !important;
        overflow: hidden !important;
        background: linear-gradient(180deg, rgba(3,3,5,.04), rgba(3,3,5,.12) 44%, rgba(3,3,5,.83)), var(--isisHeroImage), radial-gradient(circle at 50% 20%, rgba(240,197,106,.18), transparent 30%), linear-gradient(145deg, rgba(8,7,13,.94), rgba(34,24,44,.54)) !important;
        background-size: cover, cover, auto, auto !important;
        background-position: center top, center top, center, center !important;
        box-shadow: 0 34px 110px rgba(0,0,0,.44), 0 0 70px rgba(240,197,106,.13) !important;
      }
      #inicio .hero-isis-final-caption {
        border: 1px solid rgba(240,197,106,.28) !important;
        border-radius: 22px !important;
        padding: 18px !important;
        background: rgba(3,3,5,.74) !important;
        backdrop-filter: blur(14px) !important;
      }
      #inicio .hero-isis-final-caption strong {
        display: block !important;
        margin-bottom: 7px !important;
        color: #f0c56a !important;
        font-family: Cinzel, Georgia, serif !important;
        font-size: 1.12rem !important;
      }
      #inicio .hero-isis-final-caption span {
        color: #efe1c5 !important;
        font-size: 1rem !important;
        font-weight: 750 !important;
        line-height: 1.48 !important;
      }
      @media (max-width: 980px) {
        #inicio .hero-grid { grid-template-columns: 1fr !important; }
        #inicio .hero-copy { text-align: center !important; }
        #inicio .hero-copy h1, #inicio .hero-text { margin-left: auto !important; margin-right: auto !important; }
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
    if (text) text.textContent = "Cristais, incensos, velas, aromas, banhos e kits especiais organizados para o cliente entender rápido, escolher com segurança e finalizar o pedido em poucos cliques.";
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
