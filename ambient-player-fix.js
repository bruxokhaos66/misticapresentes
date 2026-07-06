(() => {
  const config = window.misticaSiteConfig || {};
  const API_BASE = String(config.apiBaseUrl || "https://api.misticaesotericos.com.br").replace(/\/$/, "");
  const VOLUME_KEY = "misticaAmbientPlayerVolume";
  const AUDIO_RE = /\.(mp3|wav|ogg|webm|m4a)(\?|#|$)/i;

  let sources = [];
  let sourceIndex = 0;
  let audio = null;
  let lastDiagnostics = { uploads: 0, links: 0, errors: [] };
  let warmedUp = false;

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
    lastDiagnostics = { uploads: 0, links: 0, errors: [] };

    try {
      const response = await fetch(`${API_BASE}/api/uploads/musicas`, { cache: "no-store" });
      if (!response.ok) throw new Error(`uploads ${response.status}`);
      const data = await response.json();
      const list = Array.isArray(data.musicas) ? data.musicas : [];
      lastDiagnostics.uploads = list.length;
      list.forEach((item) => {
        const url = apiUrl(item.url);
        if (url && !next.includes(url)) next.push(url);
      });
    } catch (error) {
      lastDiagnostics.errors.push("falha ao ler músicas enviadas");
    }

    try {
      const response = await fetch(`${API_BASE}/api/uploads/musicas/links`, { cache: "no-store" });
      if (!response.ok) throw new Error(`links ${response.status}`);
      const data = await response.json();
      const list = Array.isArray(data.links) ? data.links : [];
      lastDiagnostics.links = list.length;
      list.forEach((url) => {
        if (isAudioLink(url) && !next.includes(url)) next.push(url);
      });
    } catch (error) {
      lastDiagnostics.errors.push("falha ao ler links diretos");
    }

    sources = next;
    updateDiagnostics();
    return sources;
  }

  function updateDiagnostics() {
    const box = document.querySelector("[data-ambient-player-diagnostics]");
    if (!box) return;
    const total = sources.length;
    const erros = lastDiagnostics.errors.length ? ` • ${lastDiagnostics.errors.join(" • ")}` : "";
    box.textContent = `Encontradas: ${lastDiagnostics.uploads} música(s), ${lastDiagnostics.links} link(s), ${total} fonte(s).${erros}`;
  }

  function removeLowerPlaylistBlocks() {
    document.querySelectorAll("[data-ambient-playlist-public], [data-ambient-player-fix]").forEach((item) => item.remove());
  }

  function ensurePanel() {
    const card = document.querySelector("[data-ambient-card]");
    if (!card) return null;

    removeLowerPlaylistBlocks();

    let target = card.querySelector(".ambient-controls");
    if (!target) {
      target = document.createElement("div");
      target.className = "ambient-controls";
      card.appendChild(target);
    }

    let panel = card.querySelector("[data-ambient-player-inline]");
    if (!panel) {
      panel = document.createElement("div");
      panel.dataset.ambientPlayerInline = "true";
      panel.style.width = "100%";
      panel.innerHTML = `
        <button class="btn btn-secondary" type="button" data-ambient-player-next>Próxima música</button>
        <label style="display:flex;gap:8px;align-items:center;flex-wrap:wrap;color:#efe1c5;font-weight:800;">Volume
          <input class="ambient-volume" type="range" min="0" max="1" step="0.01" value="${savedVolume()}" data-ambient-player-volume>
          <span data-ambient-player-volume-label>Volume ${Math.round(savedVolume() * 100)}%</span>
        </label>
        <span class="ambient-status" data-ambient-player-status>Toque somente após ativar o ambiente.</span>
        <small class="privacy-note" style="display:block;margin-top:8px;" data-ambient-player-diagnostics>Verificando músicas...</small>
      `;
      target.appendChild(panel);
      panel.querySelector("[data-ambient-player-next]")?.addEventListener("click", playNext);
      panel.querySelector("[data-ambient-player-volume]")?.addEventListener("input", (event) => setVolume(event.target.value));
    }
    updateDiagnostics();
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
      audio.style.width = "100%";
      audio.style.marginTop = "10px";
      audio.addEventListener("error", () => {
        setStatus("Esta faixa falhou. Tentando a próxima...");
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

  function warmUpPlayer() {
    if (warmedUp || !sources.length) return;
    const player = updateSource();
    if (!player) return;
    warmedUp = true;
    player.volume = 0;
    player.play().then(() => {
      player.pause();
      player.currentTime = 0;
      player.volume = savedVolume();
      setStatus("Pronto para iniciar ao ativar.");
    }).catch(() => {
      player.volume = savedVolume();
    });
  }

  async function playCurrent(skipReload = false) {
    if (!skipReload) await loadSources();
    const player = updateSource();
    if (!player) {
      setStatus("Nenhuma música tocável encontrada.");
      return;
    }
    try {
      player.volume = savedVolume();
      await player.play();
      setStatus("Música ambiente tocando.");
    } catch (error) {
      setStatus("Clique no player para iniciar neste navegador.");
    }
  }

  async function playNext() {
    if (!sources.length) await loadSources();
    if (!sources.length) {
      setStatus("Nenhuma música tocável encontrada.");
      return;
    }
    sourceIndex = (sourceIndex + 1) % sources.length;
    updateSource();
    await playCurrent(true);
  }

  function hookAmbientButton() {
    const button = document.querySelector("[data-ambient-toggle]");
    if (!button || button.dataset.playerFixHook === "true") return;
    button.dataset.playerFixHook = "true";

    button.addEventListener("pointerdown", () => {
      ensurePanel();
      if (sources.length) {
        updateSource();
        playCurrent(true);
      }
    });

    button.addEventListener("click", () => {
      setTimeout(async () => {
        ensurePanel();
        await loadSources();
        updateSource();
        const isOn = button.getAttribute("aria-pressed") === "true";
        if (isOn) await playCurrent(true);
        else if (audio) {
          audio.pause();
          setStatus("Música pausada.");
        }
        removeLowerPlaylistBlocks();
      }, 20);
    });
  }

  async function apply() {
    removeLowerPlaylistBlocks();
    ensurePanel();
    await loadSources();
    updateSource();
    warmUpPlayer();
    hookAmbientButton();
    removeLowerPlaylistBlocks();
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
