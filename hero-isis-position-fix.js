(() => {
  function injectHeroIsisPositionFix() {
    const old = document.getElementById("heroIsisPositionFix");
    if (old) old.remove();

    const style = document.createElement("style");
    style.id = "heroIsisPositionFix";
    style.textContent = `
      /* Correção estável do hero/topo: sem pulo visual após carregamento */
      .hero-section {
        padding-top: clamp(28px, 3.2vw, 52px) !important;
        padding-bottom: clamp(28px, 3.6vw, 58px) !important;
        overflow: hidden !important;
      }

      .hero-grid {
        align-items: start !important;
      }

      .hero-copy {
        position: relative !important;
        z-index: 2 !important;
      }

      .hero-visual {
        position: relative !important;
        z-index: 1 !important;
        align-self: start !important;
        justify-self: center !important;
        display: flex !important;
        align-items: flex-start !important;
        justify-content: center !important;
        width: min(100%, 430px) !important;
        min-height: 0 !important;
        height: auto !important;
        padding: 10px !important;
        margin-top: clamp(8px, 1.4vw, 24px) !important;
        margin-bottom: 0 !important;
        overflow: hidden !important;
        border-radius: 30px !important;
      }

      .hero-visual::before {
        top: 2% !important;
        width: 72% !important;
        opacity: .45 !important;
      }

      .visual-orbit.one,
      .visual-orbit.two {
        opacity: .48 !important;
      }

      .mystic-logo-card.hero-card-isis,
      .mystic-logo-card.hero-card-isis-publicitaria {
        display: flex !important;
        flex-direction: column !important;
        align-items: center !important;
        justify-content: flex-start !important;
        width: 100% !important;
        max-width: 386px !important;
        min-height: 0 !important;
        height: auto !important;
        padding: 10px 10px 14px !important;
        margin: 0 auto !important;
        transform: none !important;
        border-radius: 28px !important;
      }

      .hero-isis-publicitaria {
        display: block !important;
        width: min(100%, 372px) !important;
        max-height: clamp(390px, 31vw, 500px) !important;
        object-fit: contain !important;
        object-position: center top !important;
        margin: 0 auto !important;
        transform: none !important;
      }

      .mystic-logo-card.hero-card-isis strong,
      .mystic-logo-card.hero-card-isis-publicitaria strong {
        margin-top: -10px !important;
        line-height: 1.1 !important;
      }

      .mystic-logo-card.hero-card-isis small,
      .mystic-logo-card.hero-card-isis-publicitaria small {
        margin-top: 0 !important;
        max-width: 300px !important;
        line-height: 1.3 !important;
      }

      @media (min-width: 1400px) {
        .hero-visual {
          margin-top: 18px !important;
        }
      }

      @media (max-width: 1280px) and (min-width: 981px) {
        .hero-visual {
          width: min(100%, 410px) !important;
          margin-top: 14px !important;
        }

        .hero-isis-publicitaria {
          max-height: 430px !important;
        }
      }

      @media (max-width: 980px) {
        .hero-section {
          overflow: hidden !important;
        }

        .hero-visual {
          width: min(100%, 460px) !important;
          margin: 0 auto !important;
          padding: 12px !important;
          overflow: hidden !important;
        }

        .mystic-logo-card.hero-card-isis,
        .mystic-logo-card.hero-card-isis-publicitaria {
          max-width: 100% !important;
          transform: none !important;
        }

        .hero-isis-publicitaria {
          max-height: 390px !important;
          margin-top: 0 !important;
          transform: none !important;
        }
      }

      @media (max-width: 680px) {
        .hero-visual {
          width: 100% !important;
          padding: 12px !important;
        }

        .hero-isis-publicitaria {
          max-height: 330px !important;
        }
      }
    `;

    document.head.appendChild(style);
  }

  function applyHeroClass() {
    const heroVisual = document.querySelector(".hero-visual");
    const heroCard = document.querySelector(".mystic-logo-card.hero-card-isis, .mystic-logo-card.hero-card-isis-publicitaria");
    if (heroVisual) heroVisual.dataset.heroIsisFixed = "true";
    if (heroCard) heroCard.dataset.heroIsisFixed = "true";
  }

  function apply() {
    injectHeroIsisPositionFix();
    applyHeroClass();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", apply, { once: true });
  } else {
    apply();
  }
})();
