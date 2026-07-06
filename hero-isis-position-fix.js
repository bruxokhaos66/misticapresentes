(() => {
  function injectHeroIsisPositionFix() {
    if (document.getElementById("heroIsisPositionFix")) return;

    const style = document.createElement("style");
    style.id = "heroIsisPositionFix";
    style.textContent = `
      .hero-section {
        padding-top: clamp(30px, 3.6vw, 54px) !important;
      }

      .hero-grid {
        align-items: start !important;
      }

      .hero-visual {
        align-self: start !important;
        display: flex !important;
        align-items: flex-start !important;
        justify-content: center !important;
        width: min(100%, 430px) !important;
        margin-top: 0 !important;
        padding: 12px !important;
        min-height: 0 !important;
        height: auto !important;
        overflow: visible !important;
        border-radius: 30px !important;
      }

      .hero-visual::before,
      .visual-orbit {
        transform: translateY(-16px) !important;
      }

      .mystic-logo-card.hero-card-isis,
      .mystic-logo-card.hero-card-isis-publicitaria {
        display: flex !important;
        flex-direction: column !important;
        align-items: center !important;
        justify-content: flex-start !important;
        max-width: 386px !important;
        width: 100% !important;
        min-height: 0 !important;
        height: auto !important;
        padding: 10px 10px 14px !important;
        margin: 0 auto !important;
        transform: translateY(-34px) !important;
        border-radius: 28px !important;
      }

      .hero-isis-publicitaria {
        display: block !important;
        width: min(100%, 370px) !important;
        max-height: clamp(360px, 30vw, 470px) !important;
        object-fit: contain !important;
        object-position: center top !important;
        margin: -18px auto 0 !important;
        transform: translateY(-18px) !important;
      }

      .mystic-logo-card.hero-card-isis strong,
      .mystic-logo-card.hero-card-isis-publicitaria strong {
        margin-top: -14px !important;
      }

      .mystic-logo-card.hero-card-isis small,
      .mystic-logo-card.hero-card-isis-publicitaria small {
        margin-top: 0 !important;
      }

      @media (max-width: 1280px) {
        .hero-visual {
          width: min(100%, 410px) !important;
        }

        .mystic-logo-card.hero-card-isis,
        .mystic-logo-card.hero-card-isis-publicitaria {
          transform: translateY(-26px) !important;
        }

        .hero-isis-publicitaria {
          max-height: 420px !important;
          transform: translateY(-14px) !important;
        }
      }

      @media (max-width: 980px) {
        .hero-visual {
          width: min(100%, 460px) !important;
          overflow: hidden !important;
        }

        .mystic-logo-card.hero-card-isis,
        .mystic-logo-card.hero-card-isis-publicitaria {
          transform: none !important;
        }

        .hero-isis-publicitaria {
          margin-top: 0 !important;
          transform: none !important;
          max-height: 390px !important;
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

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", injectHeroIsisPositionFix);
  } else {
    injectHeroIsisPositionFix();
  }
})();
