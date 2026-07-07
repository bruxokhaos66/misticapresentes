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
    return Number.isFinite(value) && value >= 0 && value <= 1 ? value : 0.30;
  }

  function setVolume(value) {
    const volume = Math.max(0, Math.min(1, Number(value) || 0));
    localStorage.setItem(VOLUME_KEY, String(volume));
    if (audio) audio.volume = volume;
    document.querySelectorAll("[data-unified-volume-label]").forEach((label) => {
      label.textContent = `Volume ${Math.round(volume * 100)}%`;
    });
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
      [data-ambient-player-fix] { display: none !important; }
      [data-ambient-playlist-public] { position: absolute !important; left: -9999px !important; width: 1px !important; height: 1px !important; opacity: 0 !important; pointer-events: none !important; overflow: hidden !important; }
      [data-unified-player-panel] { width: 100%; margin-top: 12px; display: none; border: 1px solid rgba(240,197,106,.22); border-radius: 20px; padding: 12px; background: rgba(0,0,0,.20); }
      [data-unified-player-panel][data-open="true"] { display: block; }
      .ambient-unified-actions { display: flex; flex-wrap: wrap; gap: 10px; align-items: center; margin-top: 10px; }
      .ambient-unified-volume { width: min(420px, 100%); accent-color: #f0c56a; }
      .ambient-unified-audio { width: 100%; margin-top: 10px; }
      .ambient-unified-status { color: #b8c977; font-weight: 800; font-size: .86rem; }
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
      panel.innerHTML = `
        <div class="ambient-unified-actions">
          <button class="btn btn-secondary" type="button" data-unified-next>Próxima música</button>
          <label style="display:flex;gap:8px;align-items:center;flex-wrap:wrap;color:#efe1c5;font-weight:800;">Volume
            <input class="ambient-unified-volume" type="range" min="0" max="1" step="0.01" value="${savedVolume()}" data-unified-volume>
            <span data-unified-volume-label>Volume ${Math.round(savedVolume() * 100)}%</span>
          </label>
          <span class="ambient-unified-status" data-unified-status>Aguardando ativação.</span>
        </div>
      `;
      const controls = parent.querySelector(".ambient-controls") || parent;
      controls.appendChild(panel);
      panel.querySelector("[data-unified-next]")?.addEventListener("click", nextTrack);
      panel.querySelector("[data-unified-volume]")?.addEventListener("input", (event) => setVolume(event.target.value));
    }
    return panel;
  }

  function openDrawer(open) { const panel = ensurePanel(); if (panel) panel.dataset.open = open ? "true" : "false"; }

  function ensureAudio() {
    const panel = ensurePanel();
    if (!panel) return null;
    if (!audio) {
      audio = document.createElement("audio");
      audio.className = "ambient-unified-audio";
      audio.controls = true;
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
    openDrawer(true);
    await loadSources();
    const player = updateSource();
    if (!player) return statusText("Nenhuma música cadastrada.");
    try { player.volume = savedVolume(); await player.play(); statusText("Música ativada."); }
    catch { statusText("Clique no player para iniciar."); }
  }

  async function nextTrack() {
    if (!sources.length) await loadSources();
    if (!sources.length) return statusText("Nenhuma música cadastrada.");
    index = (index + 1) % sources.length;
    updateSource();
    await play();
  }

  function hookMainButton() {
    const button = document.querySelector("[data-ambient-toggle]");
    if (!button || button.dataset.unifiedHook === "true") return;
    button.dataset.unifiedHook = "true";
    button.setAttribute("aria-pressed", "false");
    button.textContent = "Ativar ambiente xamânico";
    localStorage.removeItem("misticaAmbientEnabled");
    statusText("Aguardando ativação.");
    button.addEventListener("click", () => {
      setTimeout(() => {
        ensurePanel();
        const active = button.getAttribute("aria-pressed") === "true";
        if (active) play();
        else { if (audio) audio.pause(); openDrawer(false); statusText("Aguardando ativação."); }
      }, 80);
    });
  }

  async function apply() {
    installStyle();
    ensurePanel();
    openDrawer(false);
    hookMainButton();
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", apply, { once: true });
  else apply();
  window.addEventListener("load", () => { apply(); setTimeout(apply, 700); setTimeout(apply, 1800); });
  window.misticaAmbientUnifiedPlayer = { play, next: nextTrack, volume: setVolume, reload: loadSources };
  window.misticaAmbientPlayerFix = { play, next: nextTrack, volume: setVolume, reload: loadSources };
})();
