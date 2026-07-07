(() => {
  if (window.__MISTICA_AMBIENT_EXPERIENCE_LOADED__) return;
  window.__MISTICA_AMBIENT_EXPERIENCE_LOADED__ = true;

  let isPlaying = false;

  function injectStyles() {
    if (document.getElementById("misticaAmbientStyles")) return;
    const style = document.createElement("style");
    style.id = "misticaAmbientStyles";
    style.textContent = `
      .ambient-card { display:block !important; }
      .ambient-controls { display: flex; flex-wrap: wrap; align-items: center; gap: 12px; }
      .ambient-toggle[aria-pressed="true"] { border-color: rgba(184,201,119,.52); color: #10150e; background: linear-gradient(135deg, #dfeab2, #b8c977 62%, #fff6cc); }
    `;
    document.head.appendChild(style);
  }

  function pauseAudio() {
    document.querySelectorAll("audio").forEach(audio => {
      try { audio.pause(); } catch {}
    });
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
    let target = document.querySelector(".hero-copy");
    if (!target) target = document.querySelector("#inicio .container") || document.querySelector("main") || document.body;
    if (!target || document.querySelector("[data-ambient-card]")) return;

    const card = document.createElement("div");
    card.className = "ambient-card";
    card.dataset.ambientCard = "true";

    const title = document.createElement("strong");
    title.textContent = "🌿 Ambiente Xamânico da Mística";
    const description = document.createElement("p");
    description.textContent = "Ative uma trilha suave para navegar pela loja com mais imersão. A música só começa depois do seu clique.";
    const controls = document.createElement("div");
    controls.className = "ambient-controls";
    const button = document.createElement("button");
    button.className = "btn ambient-toggle";
    button.type = "button";
    button.dataset.ambientToggle = "true";
    button.setAttribute("aria-pressed", "false");
    button.textContent = "Ativar ambiente xamânico";
    const status = document.createElement("span");
    status.className = "ambient-status";
    status.dataset.ambientStatus = "true";
    status.textContent = "Aguardando ativação.";
    controls.append(button, status);
    card.append(title, description, controls);

    const trustRow = target.querySelector(".trust-row");
    if (trustRow) target.insertBefore(card, trustRow);
    else target.appendChild(card);

    button.addEventListener("click", () => {
      isPlaying = !isPlaying;
      if (!isPlaying) pauseAudio();
      updateUi(card);
      if (isPlaying && window.misticaAmbientPlayerFix?.play) window.misticaAmbientPlayerFix.play(true);
      if (!isPlaying) {
        document.querySelectorAll("[data-unified-player-panel]").forEach(panel => { panel.dataset.open = "false"; });
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
