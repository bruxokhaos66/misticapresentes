(() => {
  if (window.__MISTICA_AMBIENT_EXPERIENCE_LOADED__) return;
  window.__MISTICA_AMBIENT_EXPERIENCE_LOADED__ = true;

  let isPlaying = false;

  function injectStyles() {
    if (document.getElementById("misticaAmbientStyles")) return;
    const style = document.createElement("style");
    style.id = "misticaAmbientStyles";
    style.textContent = `
      .ambient-card {
        position: relative;
        display: grid !important;
        grid-template-columns: minmax(0, 1fr) auto;
        gap: 18px;
        align-items: center;
        width: 100%;
        margin: 26px 0 18px;
        padding: 22px;
        overflow: hidden;
        cursor: pointer;
        border: 1px solid rgba(240, 197, 106, .30);
        border-radius: 28px;
        color: #fff4d5;
        background:
          radial-gradient(circle at 82% 18%, rgba(240,197,106,.28), transparent 25%),
          radial-gradient(circle at 12% 100%, rgba(184,201,119,.18), transparent 36%),
          linear-gradient(135deg, rgba(13,15,12,.98), rgba(26,22,13,.96) 58%, rgba(7,8,7,.98));
        box-shadow: 0 26px 70px rgba(0,0,0,.42), inset 0 1px 0 rgba(255,255,255,.06);
        isolation: isolate;
      }
      .ambient-card::before {
        content: "";
        position: absolute;
        inset: 1px;
        border-radius: 26px;
        pointer-events: none;
        background:
          linear-gradient(120deg, rgba(255,255,255,.08), transparent 32%, rgba(240,197,106,.10) 65%, transparent),
          repeating-linear-gradient(90deg, rgba(255,255,255,.026) 0 1px, transparent 1px 72px);
        opacity: .82;
        z-index: -1;
      }
      .ambient-card::after {
        content: "☾";
        position: absolute;
        right: 28px;
        top: 12px;
        font-family: Cinzel, serif;
        font-size: clamp(4rem, 10vw, 8rem);
        line-height: 1;
        color: rgba(240,197,106,.11);
        pointer-events: none;
      }
      .ambient-card:focus-visible {
        outline: 3px solid rgba(240,197,106,.70);
        outline-offset: 4px;
      }
      .ambient-content { position: relative; z-index: 1; }
      .ambient-kicker {
        display: inline-flex;
        align-items: center;
        gap: 8px;
        padding: 8px 13px;
        border: 1px solid rgba(184,201,119,.35);
        border-radius: 999px;
        color: #dce8a7;
        background: rgba(184,201,119,.09);
        font-size: .74rem;
        font-weight: 900;
        letter-spacing: .12em;
        text-transform: uppercase;
      }
      .ambient-card h3 {
        margin: 14px 0 9px;
        max-width: 720px;
        font-family: Cinzel, serif;
        font-size: clamp(1.75rem, 4.2vw, 3.25rem);
        line-height: .98;
        letter-spacing: -.035em;
        text-transform: uppercase;
        color: #fff4d5;
        text-shadow: 0 6px 28px rgba(0,0,0,.48);
      }
      .ambient-card p {
        margin: 0;
        max-width: 680px;
        color: rgba(255,244,213,.82);
        font-weight: 750;
        line-height: 1.55;
      }
      .ambient-promise {
        display: flex;
        flex-wrap: wrap;
        gap: 9px;
        margin-top: 16px;
      }
      .ambient-promise span {
        padding: 9px 12px;
        border: 1px solid rgba(240,197,106,.20);
        border-radius: 999px;
        color: #f3dfae;
        background: rgba(0,0,0,.20);
        font-size: .86rem;
        font-weight: 850;
      }
      .ambient-orb {
        position: relative;
        z-index: 1;
        width: clamp(92px, 18vw, 150px);
        aspect-ratio: 1;
        border: 1px solid rgba(240,197,106,.42);
        border-radius: 999px;
        background:
          radial-gradient(circle, rgba(255,232,148,.92) 0 12%, rgba(240,197,106,.28) 13% 36%, rgba(184,201,119,.10) 37% 54%, rgba(0,0,0,.12) 55%),
          radial-gradient(circle at 50% 50%, rgba(255,255,255,.12), transparent 60%);
        box-shadow: 0 0 0 12px rgba(240,197,106,.055), 0 0 58px rgba(240,197,106,.25), inset 0 0 28px rgba(0,0,0,.30);
      }
      .ambient-orb::after {
        content: "♪";
        position: absolute;
        inset: auto 0 -2px 0;
        text-align: center;
        color: rgba(255,244,213,.82);
        font-size: 1.3rem;
        font-weight: 900;
      }
      .ambient-status {
        display: inline-flex;
        align-items: center;
        gap: 8px;
        margin-top: 13px;
        color: #b8c977;
        font-size: .92rem;
        font-weight: 900;
      }
      .ambient-status::before {
        content: "";
        width: 9px;
        height: 9px;
        border-radius: 999px;
        background: currentColor;
        box-shadow: 0 0 18px currentColor;
      }
      .ambient-card[aria-pressed="true"] .ambient-status { color: #ffe28a; }
      .ambient-controls { display: none !important; }
      .ambient-toggle { display: none !important; }
      @media (max-width: 720px) {
        .ambient-card { grid-template-columns: 1fr; padding: 20px; }
        .ambient-orb { width: 94px; order: -1; }
      }
    `;
    document.head.appendChild(style);
  }

  function pauseAudio() {
    document.querySelectorAll("audio").forEach(audio => {
      try { audio.pause(); } catch {}
    });
  }

  function updateUi(card) {
    const status = card.querySelector("[data-ambient-status]");
    card.setAttribute("aria-pressed", isPlaying ? "true" : "false");
    card.setAttribute("aria-label", isPlaying ? "Pausar ambiente xamânico da loja" : "Ativar ambiente xamânico da loja");
    if (status) status.textContent = isPlaying ? "Ambiente ativado no site" : "Toque no painel para ouvir a trilha da loja";
  }

  function createAmbientCard() {
    let target = document.querySelector(".hero-copy");
    if (!target) target = document.querySelector("#inicio .container") || document.querySelector("main") || document.body;
    if (!target || document.querySelector("[data-ambient-card]")) return;

    const card = document.createElement("section");
    card.className = "ambient-card";
    card.dataset.ambientCard = "true";
    card.tabIndex = 0;
    card.setAttribute("role", "button");
    card.setAttribute("aria-pressed", "false");

    const content = document.createElement("div");
    content.className = "ambient-content";
    content.innerHTML = `
      <span class="ambient-kicker">Ambiente xamânico</span>
      <h3>Entre no clima da Mística</h3>
      <p>Uma trilha suave para deixar a visita mais envolvente, misteriosa e acolhedora enquanto o cliente conhece os produtos da loja.</p>
      <div class="ambient-promise" aria-hidden="true">
        <span>Tambores suaves</span>
        <span>Floresta mística</span>
        <span>Cristais e incensos</span>
      </div>
      <span class="ambient-status" data-ambient-status>Toque no painel para ouvir a trilha da loja</span>
    `;

    const orb = document.createElement("div");
    orb.className = "ambient-orb";
    orb.setAttribute("aria-hidden", "true");
    card.append(content, orb);

    const trustRow = target.querySelector(".trust-row");
    if (trustRow) target.insertBefore(card, trustRow);
    else target.appendChild(card);

    function toggle() {
      isPlaying = !isPlaying;
      if (!isPlaying) pauseAudio();
      updateUi(card);
      if (isPlaying && window.misticaAmbientPlayerFix?.play) window.misticaAmbientPlayerFix.play(true);
      if (!isPlaying && window.misticaAmbientPlayerFix?.pause) window.misticaAmbientPlayerFix.pause();
    }

    card.addEventListener("click", toggle);
    card.addEventListener("keydown", (event) => {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        toggle();
      }
    });
    updateUi(card);
  }

  function init() {
    isPlaying = false;
    try { localStorage.removeItem("misticaAmbientEnabled"); } catch {}
    injectStyles();
    pauseAudio();
    createAmbientCard();
    const card = document.querySelector("[data-ambient-card]");
    if (card) updateUi(card);
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init, { once: true });
  else init();

  window.addEventListener("load", () => {
    if (!document.querySelector("[data-ambient-card]")) createAmbientCard();
  }, { once: true });

  window.misticaAmbientExperience = { start: () => { isPlaying = true; }, stop: () => { isPlaying = false; pauseAudio(); }, isPlaying: () => isPlaying, setVolume: () => 0 };
})();