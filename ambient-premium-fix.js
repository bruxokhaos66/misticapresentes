(() => {
  const styleId = "misticaAmbientPremiumFixStyle";

  function installStyle() {
    if (document.getElementById(styleId)) return;

    const style = document.createElement("style");
    style.id = styleId;
    style.textContent = `
      .ambient-card {
        position: relative !important;
        overflow: hidden !important;
        display: grid !important;
        gap: 12px !important;
        border-radius: 30px !important;
        border-color: rgba(240,197,106,.34) !important;
        padding: clamp(18px, 2.6vw, 26px) !important;
        background:
          radial-gradient(circle at 12% 10%, rgba(240,197,106,.18), transparent 34%),
          radial-gradient(circle at 92% 12%, rgba(184,201,119,.14), transparent 30%),
          linear-gradient(145deg, rgba(8,7,13,.82), rgba(83,107,55,.18)) !important;
        box-shadow: 0 26px 78px rgba(0,0,0,.26), inset 0 1px 0 rgba(255,248,230,.08) !important;
      }

      .ambient-card::before {
        content: "";
        position: absolute;
        inset: 0;
        pointer-events: none;
        background: linear-gradient(120deg, rgba(255,248,230,.09), transparent 30%, transparent 70%, rgba(240,197,106,.06));
      }

      .ambient-card::after {
        content: "♪";
        position: absolute;
        right: 18px;
        top: 12px;
        color: rgba(240,197,106,.16);
        font-family: Cinzel, Georgia, serif;
        font-size: clamp(2.8rem, 5vw, 5rem);
        line-height: 1;
        pointer-events: none;
      }

      .ambient-card strong,
      .ambient-card p,
      .ambient-controls {
        position: relative;
        z-index: 1;
      }

      .ambient-card strong {
        display: flex !important;
        align-items: center;
        gap: 10px;
        color: #fff6dc !important;
        letter-spacing: .06em !important;
        text-transform: uppercase;
      }

      .ambient-card p {
        max-width: 720px;
        margin: 0 !important;
        color: #efe1c5 !important;
        font-weight: 650;
      }

      .ambient-controls {
        gap: 12px !important;
        margin-top: 2px;
      }

      .ambient-toggle {
        min-width: min(100%, 240px);
      }

      .ambient-toggle[aria-pressed="true"] {
        box-shadow: 0 18px 44px rgba(184,201,119,.20) !important;
      }

      .ambient-volume {
        height: 34px;
        padding: 0;
      }

      .ambient-status {
        border: 1px solid rgba(184,201,119,.20);
        border-radius: 999px;
        padding: 8px 11px;
        background: rgba(184,201,119,.07);
        color: #dfeab2 !important;
      }

      @media (max-width: 680px) {
        .ambient-card {
          border-radius: 26px !important;
        }

        .ambient-status {
          width: 100%;
          border-radius: 18px;
        }
      }
    `;

    document.head.appendChild(style);
  }

  function improveCopy() {
    const card = document.querySelector("[data-ambient-card]");
    if (!card || card.dataset.premiumAmbient === "true") return;

    card.dataset.premiumAmbient = "true";

    const title = card.querySelector("strong");
    const text = card.querySelector("p");

    if (title) title.textContent = "🌿 Ambiente xamânico suave";
    if (text) text.textContent = "Ative uma trilha discreta para navegar com clima místico. O som só começa com sua autorização e pode ser desligado a qualquer momento.";
  }

  function apply() {
    installStyle();
    improveCopy();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", apply, { once: true });
  } else {
    apply();
  }

  window.addEventListener("load", () => {
    apply();
    setTimeout(apply, 700);
    setTimeout(apply, 1800);
  });
})();
