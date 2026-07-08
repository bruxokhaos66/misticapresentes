(() => {
  const styleId = "misticaAmbientPlayerUnifyStyle";
  const VOLUME_KEY = "misticaAmbientUnifiedVolume";
  const config = window.misticaSiteConfig || {};
  const API_BASE = String(config.apiBaseUrl || "https://api.misticaesotericos.com.br").replace(/\/$/, "");
  let sources = [];
  let audio = null;
  let index = 0;

  function savedVolume() {
    const value = Number(localStorage.getItem(VOLUME_KEY));
    return Number.isFinite(value) && value >= 0 && value <= 1 ? value : 0.35;
  }

  function setVolume(value) {
    const volume = Math.max(0, Math.min(1, Number(value) || 0));
    localStorage.setItem(VOLUME_KEY, String(volume));
    if (audio) audio.volume = volume;
  }

  function statusText(text) {
    const mainStatus = document.querySelector("[data-ambient-status]");
    if (mainStatus) mainStatus.textContent = text;
    const playerStatus = document.querySelector("[data-unified-status]");
    if (playerStatus) playerStatus.textContent = text;
  }

  function installStyle() {
    if (document.getElementById(styleId)) return;
    const style = document.createElement("style");
    style.id = styleId;
    style.textContent = `
      [data-ambient-player-inline],
      [data-ambient-player-fix],
      [data-ambient-playlist-public],
      [data-unified-player-panel],
      .ambient-unified-actions,
      .ambient-unified-audio,
      [data-unified-next],
      [data-unified-volume] {
        position: absolute !important;
        left: -9999px !important;
        width: 1px !important;
        height: 1px !important;
        opacity: 0 !important;
        pointer-events: none !important;
        overflow: hidden !important;
      }
    `;
    document.head.appendChild(style);
  }

  function apiUrl(path) { return path ? (String(path).startsWith("http") ? path : `${API_BASE}${path}`) : ""; }
  function addSource(next, url) { if (url && !next.includes(url)) next.push(url); }

  async function loadSources() {
    const next = [];
    try {
      const response = await fetch(`${API_BASE}/api/uploads/musicas`, { cache: "no-store" });
      if (response.ok) {
        const data = await response.json();
        (data.musicas || []).forEach((item) => addSource(next, apiUrl(item.url)));
      }
    } catch {}
    if (next.length) sources = next;
    return sources;
  }

  function card() { return document.querySelector("[data-ambient-card]"); }

  function ensurePanel() {
    const parent = card();
    if (!parent) return null;
    document.querySelectorAll("[data-ambient-player-inline], [data-ambient-player-fix]").forEach((item) => item.remove());
    let panel = parent.querySelector("[data-unified-player-panel]");
    if (!panel) {
      panel = document.createElement("div");
      panel.dataset.unifiedPlayerPanel = "true";
      panel.dataset.open = "false";
      panel.innerHTML = `<span class="ambient-unified-status" data-unified-status>Toque no painel para ouvir a trilha da loja</span>`;
      parent.appendChild(panel);
    }
    return panel;
  }

  function ensureAudio() {
    const panel = ensurePanel();
    if (!panel) return null;
    if (!audio) {
      audio = document.createElement("audio");
      audio.className = "ambient-unified-audio";
      audio.controls = false;
      audio.preload = "metadata";
      audio.loop = true;
      audio.volume = savedVolume();
      panel.appendChild(audio);
    }
    return audio;
  }

  function updateSource() {
    const player = ensureAudio();
    if (!player || !sources.length) return null;
    if (index >= sources.length) index = 0;
    const src = sources[index];
    if (player.src !== src) { player.src = src; player.load(); }
    setVolume(savedVolume());
    return player;
  }

  async function play() {
    await loadSources();
    const player = updateSource();
    if (!player) return statusText("Cadastre uma música no Admin para ativar a trilha.");
    try {
      player.volume = savedVolume();
      await player.play();
      statusText("Ambiente ativado no site");
    } catch {
      statusText("Toque novamente no painel para iniciar a música");
    }
  }

  function pause() {
    if (audio) audio.pause();
    statusText("Toque no painel para ouvir a trilha da loja");
  }

  async function nextTrack() {
    if (!sources.length) await loadSources();
    if (!sources.length) return statusText("Cadastre uma música no Admin para ativar a trilha.");
    index = (index + 1) % sources.length;
    updateSource();
    await play();
  }

  function hookMainButton() {
    const button = document.querySelector("[data-ambient-toggle]");
    if (!button || button.dataset.unifiedHook === "true") return;
    button.dataset.unifiedHook = "true";
    if (button.tagName === "BUTTON") {
      button.setAttribute("aria-pressed", "false");
      button.textContent = "Ativar ambiente xamânico";
    }
    localStorage.removeItem("misticaAmbientEnabled");
    button.addEventListener("click", () => {
      setTimeout(() => {
        const active = button.getAttribute("aria-pressed") === "true";
        if (active) play();
        else pause();
      }, 80);
    });
  }

  async function apply() {
    installStyle();
    ensurePanel();
    hookMainButton();
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", apply, { once: true });
  else apply();
  window.addEventListener("load", () => { apply(); setTimeout(apply, 700); setTimeout(apply, 1800); });
  window.misticaAmbientUnifiedPlayer = { play, pause, next: nextTrack, volume: setVolume, reload: loadSources };
  window.misticaAmbientPlayerFix = { play, pause, next: nextTrack, volume: setVolume, reload: loadSources };
})();