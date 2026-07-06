(() => {
  const config = window.misticaSiteConfig || {};
  const API_BASE = String(config.apiBaseUrl || "https://api.misticaesotericos.com.br").replace(/\/$/, "");
  const VOLUME_KEY = "misticaAmbientPlayerVolume";
  const AUDIO_RE = /\.(mp3|wav|ogg|webm|m4a)(\?|#|$)/i;

  let sources = [];
  let sourceIndex = 0;
  let audio = null;

  function apiUrl(path) {
    if (!path) return "";
    return String(path).startsWith("http") ? path : `${API_BASE}${path}`;
  }

  function savedVolume() {
    const value = Number(localStorage.getItem(VOLUME_KEY));
    return Number.isFinite(value) && value >= 0 && value <= 1 ? value : 0.24;
  }

  function setStatus(text) {
    const status = document.querySelector("[data-ambient-player-status]");
    if (status) status.textContent = text;
  }

  function setVolume(value) {
    const next = Math.max(0, Math.min(1, Number(value) || 0));
    localStorage.setItem(VOLUME_KEY, String(next));
    if (audio) audio.volume = next;
    const label = document.querySelector("[data-ambient-player-volume-label]");
    if (label) label.textContent = `Volume ${Math.round(next * 100)}%`;
  }

  function isAudioLink(value) {
    try {
      const url = new URL(String(value || ""));
      return ["http:", "https:"].includes(url.protocol) && AUDIO_RE.test(url.pathname + url.search + url.hash);
    } catch (error) {
      return false;
    }
  }

  async function loadSources() {
    const next = [];

    try {
      const response = await fetch(`${API_BASE}/api/uploads/musicas`, { cache: "no-store" });
      if (response.ok) {
        const data = await response.json();
        (data.musicas || []).forEach((item) => {
          const url = apiUrl(item.url);
          if (url && !next.includes(url)) next.push(url);
        });
      }
    } catch (error) {
      // Mantém apenas as fontes já conhecidas.
    }

    try {
      const response = await fetch(`${API_BASE}/api/uploads/musicas/links`, { cache: "no-store" });
      if (response.ok) {
        const data = await response.json();
        (data.links || []).forEach((url) => {
          if (isAudioLink(url) && !next.includes(url)) next.push(url);
        });
      }
    } catch (error) {
      // Mantém apenas as fontes já conhecidas.
    }

    if (next.length) sources = next;
    return sources;
  }

  function ensurePanel() {
    const card = document.querySelector("[data-ambient-card]");
    if (!card) return null;

    let panel = document.querySelector("[data-ambient-player-fix]");
    if (!panel) {
      panel = document.createElement("div");
      panel.className = "ambient-playlist-public";
      panel.dataset.ambientPlayerFix = "true";
      panel.innerHTML = `
        <strong>Música ambiente da loja</strong>
        <span>Player do site para músicas enviadas no ADM ou links diretos de áudio.</span>
        <div class="ambient-playlist-public-actions">
          <button class="btn btn-secondary" type="button" data-ambient-player-start>Tocar no site</button>
          <button class="btn btn-secondary" type="button" data-ambient-player-next>Próxima música</button>
          <span class="ambient-player-status" data-ambient-player-status>Carregando músicas...</span>
        </div>
        <div class="ambient-volume-row">
          <label>Volume <input class="ambient-volume-control" type="range" min="0" max="1" step="0.01" value="${savedVolume()}" data-ambient-player-volume></label>
          <span class="ambient-player-status" data-ambient-player-volume-label>Volume ${Math.round(savedVolume() * 100)}%</span>
        </div>
      `;
      card.appendChild(panel);
      panel.querySelector("[data-ambient-player-start]")?.addEventListener("click", playCurrent);
      panel.querySelector("[data-ambient-player-next]")?.addEventListener("click", playNext);
      panel.querySelector("[data-ambient-player-volume]")?.addEventListener("input", (event) => setVolume(event.target.value));
    }
    return panel;
  }

  function ensureAudio() {
    const panel = ensurePanel();
    if (!panel) return null;

    if (!audio) {
      audio = document.createElement("audio");
      audio.className = "ambient-audio-player";
      audio.controls = true;
      audio.loop = true;
      audio.preload = "auto";
      audio.addEventListener("error", () => {
        setStatus("Esta música falhou. Tentando a próxima...");
        playNext();
      });
      panel.appendChild(audio);
    }
    audio.volume = savedVolume();
    return audio;
  }

  function updateSource() {
    const player = ensureAudio();
    if (!player || !sources.length) return null;
    if (sourceIndex >= sources.length) sourceIndex = 0;
    const src = sources[sourceIndex];
    if (player.src !== src) {
      player.src = src;
      player.load();
    }
    setStatus(`Faixa ${sourceIndex + 1} de ${sources.length}.`);
    return player;
  }

  async function playCurrent() {
    if (!sources.length) await loadSources();
    const player = updateSource();
    if (!player) {
      setStatus("Nenhuma música de áudio direto encontrada.");
      return;
    }
    try {
      player.volume = savedVolume();
      await player.play();
      setStatus("Música tocando no player do site.");
    } catch (error) {
      setStatus("Clique no player ou no botão Tocar no site para iniciar.");
    }
  }

  async function playNext() {
    if (!sources.length) await loadSources();
    if (!sources.length) return;
    sourceIndex = (sourceIndex + 1) % sources.length;
    updateSource();
    await playCurrent();
  }

  function hookAmbientButton() {
    const button = document.querySelector("[data-ambient-toggle]");
    if (!button || button.dataset.playerFixHook === "true") return;
    button.dataset.playerFixHook = "true";

    button.addEventListener("pointerdown", () => {
      if (sources.length) playCurrent();
    });

    button.addEventListener("click", () => {
      setTimeout(async () => {
        await loadSources();
        ensurePanel();
        updateSource();
        if (button.getAttribute("aria-pressed") === "true") await playCurrent();
        else if (audio) {
          audio.pause();
          setStatus("Música pausada.");
        }
      }, 40);
    });
  }

  async function apply() {
    await loadSources();
    if (sources.length) {
      ensurePanel();
      updateSource();
    }
    hookAmbientButton();
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", apply, { once: true });
  else apply();

  window.addEventListener("load", () => {
    apply();
    setTimeout(apply, 700);
    setTimeout(apply, 1800);
  });

  window.misticaAmbientPlayerFix = {
    play: playCurrent,
    next: playNext,
    volume: setVolume,
    reload: loadSources,
  };
})();
