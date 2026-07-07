(() => {
  if (window.__MISTICA_AMBIENT_EXPERIENCE_LOADED__) return;
  window.__MISTICA_AMBIENT_EXPERIENCE_LOADED__ = true;

  const STORAGE_KEY = "misticaAmbientEnabled";
  let isPlaying = false;

  function injectStyles() {
    if (document.getElementById("misticaAmbientStyles")) return;
    const style = document.createElement("style");
    style.id = "misticaAmbientStyles";
    style.textContent = `
      .ambient-card { position: relative; z-index: 4; margin-top: 18px; border: 1px solid rgba(240,197,106,.28); border-radius: 26px; padding: clamp(16px, 2.4vw, 22px); background: radial-gradient(circle at 12% 10%, rgba(240,197,106,.16), transparent 34%), linear-gradient(145deg, rgba(255,248,230,.075), rgba(83,107,55,.11)); box-shadow: 0 22px 68px rgba(0,0,0,.24); }
      .ambient-card strong { display: block; color: #fff6dc; font-family: Cinzel, Georgia, serif; font-size: clamp(1.05rem, 1.8vw, 1.35rem); letter-spacing: .03em; }
      .ambient-card p { margin: 8px 0 14px; color: #efe1c5; font-size: clamp(.98rem, 1.15vw, 1.08rem); line-height: 1.55; }
      .ambient-controls { display: flex; flex-wrap: wrap; align-items: center; gap: 12px; }
      .ambient-toggle[aria-pressed="true"] { border-color: rgba(184,201,119,.52); color: #10150e; background: linear-gradient(135deg, #dfeab2, #b8c977 62%, #fff6cc); }
      .ambient-status { color: #b8c977; font-size: .86rem; font-weight: 800; }
      @media (max-width: 680px) { .ambient-card { text-align: left; } .ambient-controls .btn { width: 100%; } }
    `;
    document.head.appendChild(style);
  }

  function pauseAudio() {
    document.querySelectorAll("audio").forEach(audio => {
      try { audio.pause(); } catch {}
    });
  }

  function startAmbient() {
    isPlaying = true;
    localStorage.setItem(STORAGE_KEY, "true");
  }

  function stopAmbient() {
    isPlaying = false;
    localStorage.removeItem(STORAGE_KEY);
    pauseAudio();
  }

  function updateUi(card) {
    const button = card.querySelector("[data-ambient-toggle]");
    const status = card.querySelector("[data-ambient-status]");
    if (button) {
      button.setAttribute("aria-pressed", isPlaying ? "true" : "false");
      button.textContent = isPlaying ? "Desligar ambiente xamânico" : "Ativar ambiente xamânico";
    }
    if (status) status.textContent = isPlaying ? "Música ativada." : "Aguardando ativação.";
  }

  function createAmbientCard() {
    const heroCopy = document.querySelector(".hero-copy");
    if (!heroCopy || document.querySelector("[data-ambient-card]")) return;
    const card = document.createElement("div");
    card.className = "ambient-card";
    card.dataset.ambientCard = "true";
    card.innerHTML = `
      <strong>🌿 Experiência sonora xamânica</strong>
      <p>Para uma navegação mais imersiva, o cliente pode ativar uma trilha ambiente suave. Ela só começa com a escolha do visitante e pode ser desligada a qualquer momento.</p>
      <div class="ambient-controls">
        <button class="btn ambient-toggle" type="button" data-ambient-toggle aria-pressed="false">Ativar ambiente xamânico</button>
        <span class="ambient-status" data-ambient-status>Aguardando ativação.</span>
      </div>
    `;
    const trustRow = heroCopy.querySelector(".trust-row");
    if (trustRow) heroCopy.insertBefore(card, trustRow);
    else heroCopy.appendChild(card);
    const button = card.querySelector("[data-ambient-toggle]");
    button.addEventListener("click", () => {
      if (isPlaying) stopAmbient();
      else startAmbient();
      updateUi(card);
      if (isPlaying && window.misticaAmbientPlayerFix?.play) window.misticaAmbientPlayerFix.play(true);
      if (!isPlaying) {
        try { document.querySelector("[data-unified-player-panel]").dataset.open = "false"; } catch {}
      }
    });
    updateUi(card);
  }

  function forceInitialOff() {
    isPlaying = false;
    localStorage.removeItem(STORAGE_KEY);
    pauseAudio();
    document.querySelectorAll("[data-ambient-toggle]").forEach(button => {
      button.setAttribute("aria-pressed", "false");
      button.textContent = "Ativar ambiente xamânico";
    });
    document.querySelectorAll("[data-ambient-status]").forEach(status => { status.textContent = "Aguardando ativação."; });
    document.querySelectorAll("[data-unified-player-panel]").forEach(panel => { panel.dataset.open = "false"; });
  }

  function init() {
    injectStyles();
    forceInitialOff();
    createAmbientCard();
    const card = document.querySelector("[data-ambient-card]");
    if (card) updateUi(card);
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init, { once: true });
  else init();

  window.misticaAmbientExperience = { start: startAmbient, stop: stopAmbient, isPlaying: () => isPlaying, setVolume: () => 0 };
})();
