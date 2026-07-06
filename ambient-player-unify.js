(() => {
  const styleId = "misticaAmbientPlayerUnifyStyle";
  const VOLUME_KEY = "misticaAmbientUnifiedVolume";

  function savedVolume() {
    const value = Number(localStorage.getItem(VOLUME_KEY));
    return Number.isFinite(value) && value >= 0 && value <= 1 ? value : 0.22;
  }

  function setVolume(value) {
    const volume = Math.max(0, Math.min(1, Number(value) || 0));
    localStorage.setItem(VOLUME_KEY, String(volume));
    document.querySelectorAll(".ambient-playlist-public audio, .ambient-audio-player").forEach((audio) => {
      audio.volume = volume;
    });
    document.querySelectorAll("[data-unified-volume-label]").forEach((label) => {
      label.textContent = `Volume ${Math.round(volume * 100)}%`;
    });
  }

  function installStyle() {
    if (document.getElementById(styleId)) return;
    const style = document.createElement("style");
    style.id = styleId;
    style.textContent = `
      [data-ambient-player-inline],
      [data-ambient-player-fix] {
        display: none !important;
      }

      .ambient-playlist-public {
        width: 100% !important;
        margin-top: 8px !important;
        border: 0 !important;
        border-radius: 0 !important;
        padding: 0 !important;
        background: transparent !important;
        box-shadow: none !important;
      }

      .ambient-playlist-public strong,
      .ambient-playlist-public > span,
      .ambient-playlist-public [data-ambient-player-play],
      .ambient-playlist-public [data-ambient-playlist-open] {
        display: none !important;
      }

      .ambient-playlist-public-actions {
        display: flex !important;
        flex-wrap: wrap !important;
        gap: 10px !important;
        align-items: center !important;
        margin-top: 0 !important;
      }

      .ambient-playlist-public audio {
        width: 100% !important;
        margin-top: 10px !important;
      }

      .ambient-unified-volume {
        width: min(420px, 100%);
        accent-color: #f0c56a;
      }
    `;
    document.head.appendChild(style);
  }

  function lowerPanel() {
    return document.querySelector("[data-ambient-playlist-public]");
  }

  function lowerAudio() {
    return lowerPanel()?.querySelector("audio") || document.querySelector(".ambient-playlist-public audio");
  }

  function statusText(text) {
    const mainStatus = document.querySelector("[data-ambient-status]");
    if (mainStatus) mainStatus.textContent = text;
    const playerStatus = lowerPanel()?.querySelector("[data-ambient-player-status]");
    if (playerStatus) playerStatus.textContent = text;
  }

  function addControls() {
    const panel = lowerPanel();
    if (!panel || panel.dataset.unifiedPlayer === "true") return;
    panel.dataset.unifiedPlayer = "true";

    const actions = panel.querySelector(".ambient-playlist-public-actions") || panel;

    const next = document.createElement("button");
    next.className = "btn btn-secondary";
    next.type = "button";
    next.textContent = "Próxima música";
    next.dataset.unifiedNext = "true";
    next.addEventListener("click", () => {
      const audio = lowerAudio();
      if (!audio) return;
      audio.currentTime = 0;
      audio.play().then(() => statusText("Música ativada.")).catch(() => statusText("Clique no player para iniciar."));
    });

    const label = document.createElement("label");
    label.style.display = "flex";
    label.style.gap = "8px";
    label.style.alignItems = "center";
    label.style.flexWrap = "wrap";
    label.style.color = "#efe1c5";
    label.style.fontWeight = "800";
    label.innerHTML = `Volume <input class="ambient-unified-volume" type="range" min="0" max="1" step="0.01" value="${savedVolume()}" data-unified-volume> <span data-unified-volume-label>Volume ${Math.round(savedVolume() * 100)}%</span>`;

    actions.prepend(label);
    actions.prepend(next);

    label.querySelector("[data-unified-volume]")?.addEventListener("input", (event) => setVolume(event.target.value));
    setVolume(savedVolume());
  }

  async function playLower() {
    const audio = lowerAudio();
    if (!audio) {
      statusText("Carregando músicas...");
      return;
    }
    try {
      audio.volume = savedVolume();
      await audio.play();
      statusText("Música ativada.");
    } catch (error) {
      statusText("Clique no player para iniciar.");
    }
  }

  function hookMainButton() {
    const button = document.querySelector("[data-ambient-toggle]");
    if (!button || button.dataset.unifiedHook === "true") return;
    button.dataset.unifiedHook = "true";
    button.addEventListener("click", () => {
      setTimeout(() => {
        addControls();
        if (button.getAttribute("aria-pressed") === "true") playLower();
        else {
          const audio = lowerAudio();
          if (audio) audio.pause();
          statusText("Aguardando ativação.");
        }
      }, 260);
    });
  }

  function updateCountFromWorkingPanel() {
    const panel = lowerPanel();
    if (!panel) return;
    const audio = lowerAudio();
    const existing = document.querySelector("[data-ambient-player-diagnostics]");
    if (existing && audio?.src) existing.textContent = "Música carregada pelo player funcional.";
  }

  function apply() {
    installStyle();
    document.querySelectorAll("[data-ambient-player-inline], [data-ambient-player-fix]").forEach((item) => item.remove());
    addControls();
    hookMainButton();
    updateCountFromWorkingPanel();
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", apply, { once: true });
  else apply();

  window.addEventListener("load", () => {
    apply();
    setTimeout(apply, 600);
    setTimeout(apply, 1500);
  });
})();
