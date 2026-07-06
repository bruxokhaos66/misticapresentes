(() => {
  const styleId = "misticaSingleAmbientPlayerStyle";

  function installStyle() {
    if (document.getElementById(styleId)) return;
    const style = document.createElement("style");
    style.id = styleId;
    style.textContent = `
      [data-ambient-playlist-public],
      .ambient-playlist-public {
        display: none !important;
      }
    `;
    document.head.appendChild(style);
  }

  function pauseOldPlayers() {
    document.querySelectorAll("[data-ambient-playlist-public] audio, .ambient-playlist-public audio").forEach((audio) => {
      try {
        audio.pause();
        audio.removeAttribute("src");
        audio.load();
      } catch (error) {
        // Silencioso: apenas impede áudio duplicado.
      }
    });
  }

  function removeOldPanels() {
    document.querySelectorAll("[data-ambient-playlist-public], .ambient-playlist-public").forEach((panel) => {
      panel.querySelectorAll("audio").forEach((audio) => {
        try {
          audio.pause();
          audio.removeAttribute("src");
          audio.load();
        } catch (error) {
          // Silencioso.
        }
      });
      panel.remove();
    });
  }

  function keepOnlyUnifiedPlayer() {
    const unified = document.querySelector(".ambient-unified-audio");
    document.querySelectorAll("audio").forEach((audio) => {
      if (unified && audio !== unified && audio.closest("[data-ambient-card]")) {
        try {
          audio.pause();
          audio.removeAttribute("src");
          audio.load();
        } catch (error) {
          // Silencioso.
        }
      }
    });
  }

  function patchOldPlaylistApi() {
    if (!window.misticaAmbientPlaylist || window.misticaAmbientPlaylist.__singleGuardPatched) return;
    const original = window.misticaAmbientPlaylist;
    original.__singleGuardPatched = true;
    original.play = async () => {
      pauseOldPlayers();
      if (window.misticaAmbientUnifiedPlayer?.play) return window.misticaAmbientUnifiedPlayer.play();
      return undefined;
    };
    original.apply = () => {
      pauseOldPlayers();
      removeOldPanels();
    };
  }

  function hookButtons() {
    const button = document.querySelector("[data-ambient-toggle]");
    if (button && button.dataset.singlePlayerGuard !== "true") {
      button.dataset.singlePlayerGuard = "true";
      button.addEventListener("click", () => {
        setTimeout(() => {
          pauseOldPlayers();
          removeOldPanels();
          keepOnlyUnifiedPlayer();
        }, 120);
      });
    }
  }

  function apply() {
    installStyle();
    patchOldPlaylistApi();
    pauseOldPlayers();
    removeOldPanels();
    keepOnlyUnifiedPlayer();
    hookButtons();
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", apply, { once: true });
  else apply();

  window.addEventListener("load", () => {
    apply();
    setTimeout(apply, 500);
    setTimeout(apply, 1200);
    setTimeout(apply, 2500);
  });

  document.addEventListener("play", (event) => {
    const audio = event.target;
    if (!(audio instanceof HTMLAudioElement)) return;
    if (audio.classList.contains("ambient-unified-audio")) {
      pauseOldPlayers();
      keepOnlyUnifiedPlayer();
      return;
    }
    if (audio.closest("[data-ambient-playlist-public], .ambient-playlist-public")) {
      audio.pause();
      if (window.misticaAmbientUnifiedPlayer?.play) window.misticaAmbientUnifiedPlayer.play();
    }
  }, true);

  window.misticaSingleAmbientPlayerGuard = { apply };
})();
