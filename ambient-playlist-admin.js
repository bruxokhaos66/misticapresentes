(() => {
  const STORAGE_KEY = "misticaAmbientPlaylistLinks";
  const styleId = "misticaAmbientPlaylistStyle";
  const config = window.misticaSiteConfig || {};
  const API_BASE = String(config.apiBaseUrl || "https://api.misticaesotericos.com.br").replace(/\/$/, "");

  let remoteLinks = null;
  let remoteLoaded = false;
  let remoteTracks = [];
  let tracksLoaded = false;
  let currentAudio = null;

  function isAdminView() {
    return window.location.search.includes("admin=mistica") || window.location.hash.includes("admin-mistica") || document.body?.classList.contains("admin-mode");
  }

  function apiHeaders(json = true) {
    const headers = {};
    if (json) headers["Content-Type"] = "application/json";
    if (config.siteApiKey) headers["X-Mistica-Api-Key"] = config.siteApiKey;
    return headers;
  }

  function absoluteApiUrl(path) {
    if (!path) return "";
    if (String(path).startsWith("http")) return path;
    return `${API_BASE}${path}`;
  }

  function normalizeUrl(value) {
    const text = String(value || "").trim();
    if (!text) return "";
    try {
      const url = new URL(text);
      const host = url.hostname.replace(/^www\./, "");
      if (!["youtube.com", "youtu.be", "music.youtube.com"].includes(host)) return "";
      return url.toString();
    } catch (error) {
      return "";
    }
  }

  function cleanLinks(links) {
    return [...new Set((links || []).map(normalizeUrl).filter(Boolean))].slice(0, 12);
  }

  function readLocalLinks() {
    try {
      const parsed = JSON.parse(localStorage.getItem(STORAGE_KEY) || "[]");
      if (!Array.isArray(parsed)) return [];
      return cleanLinks(parsed);
    } catch (error) {
      return [];
    }
  }

  function writeLocalLinks(links) {
    const clean = cleanLinks(links);
    localStorage.setItem(STORAGE_KEY, JSON.stringify(clean));
    return clean;
  }

  function readLinks() {
    return remoteLinks || readLocalLinks();
  }

  async function fetchRemoteLinks() {
    try {
      const response = await fetch(`${API_BASE}/api/site/playlist-ambiente`, { cache: "no-store" });
      if (!response.ok) throw new Error("Playlist remota indisponível.");
      const data = await response.json();
      remoteLinks = cleanLinks(data.links || []);
      remoteLoaded = true;
      if (remoteLinks.length) writeLocalLinks(remoteLinks);
      return remoteLinks;
    } catch (error) {
      remoteLoaded = true;
      remoteLinks = null;
      return readLocalLinks();
    }
  }

  async function fetchTracks() {
    try {
      const response = await fetch(`${API_BASE}/api/uploads/musicas`, { cache: "no-store" });
      if (!response.ok) throw new Error("Músicas indisponíveis.");
      const data = await response.json();
      remoteTracks = Array.isArray(data.musicas) ? data.musicas : [];
      tracksLoaded = true;
      return remoteTracks;
    } catch (error) {
      remoteTracks = [];
      tracksLoaded = true;
      return [];
    }
  }

  async function uploadTrack(file, status) {
    if (!file) return null;
    const form = new FormData();
    form.append("arquivo", file);
    form.append("nome_base", file.name.replace(/\.[^.]+$/, "") || "ambiente-xamanico");
    try {
      const response = await fetch(`${API_BASE}/api/uploads/musicas`, {
        method: "POST",
        headers: apiHeaders(false),
        body: form,
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(data.detail || "Não foi possível enviar a música.");
      if (status) status.textContent = "Música enviada para a API.";
      await fetchTracks();
      renderPublicPlaylist(true);
      return data;
    } catch (error) {
      if (status) status.textContent = error.message || "Falha ao enviar música.";
      return null;
    }
  }

  async function saveLinks(links) {
    const clean = writeLocalLinks(links);
    remoteLinks = clean;
    try {
      const response = await fetch(`${API_BASE}/api/site/playlist-ambiente`, {
        method: "POST",
        headers: apiHeaders(),
        body: JSON.stringify({ links: clean }),
      });
      if (!response.ok) throw new Error("Não foi possível salvar na API.");
      const data = await response.json();
      remoteLinks = cleanLinks(data.links || clean);
      writeLocalLinks(remoteLinks);
      return { links: remoteLinks, mode: "api" };
    } catch (error) {
      return { links: clean, mode: "local" };
    }
  }

  function installStyles() {
    if (document.getElementById(styleId)) return;
    const style = document.createElement("style");
    style.id = styleId;
    style.textContent = `
      .ambient-playlist-admin,
      .ambient-playlist-public {
        margin-top: 14px;
        border: 1px solid rgba(240,197,106,.22);
        border-radius: 22px;
        padding: 14px;
        background: rgba(255,248,230,.055);
      }

      .ambient-playlist-admin h3,
      .ambient-playlist-public strong {
        margin: 0 0 8px;
        color: #fff6dc;
        font-family: Cinzel, Georgia, serif;
        letter-spacing: .04em;
      }

      .ambient-playlist-admin p,
      .ambient-playlist-public span {
        display: block;
        margin: 0 0 10px;
        color: #e7dac1;
        font-size: .92rem;
        line-height: 1.45;
      }

      .ambient-playlist-admin textarea,
      .ambient-playlist-admin input[type="file"] {
        width: 100%;
        border: 1px solid rgba(240,197,106,.28);
        border-radius: 16px;
        padding: 12px;
        color: #fff6dc;
        background: rgba(0,0,0,.24);
      }

      .ambient-playlist-admin textarea {
        min-height: 120px;
        resize: vertical;
      }

      .ambient-playlist-admin-actions,
      .ambient-playlist-public-actions {
        display: flex;
        flex-wrap: wrap;
        gap: 10px;
        align-items: center;
        margin-top: 10px;
      }

      .ambient-playlist-admin-status {
        color: #b8c977;
        font-weight: 800;
        font-size: .86rem;
      }

      .ambient-track-list {
        display: grid;
        gap: 8px;
        margin-top: 10px;
        color: #d9ccb5;
        font-size: .88rem;
      }

      .ambient-playlist-public a {
        text-decoration: none;
      }

      .ambient-audio-player {
        width: 100%;
        margin-top: 10px;
      }
    `;
    document.head.appendChild(style);
  }

  async function renderAdminPanel() {
    if (!isAdminView() || document.querySelector("[data-ambient-playlist-admin]")) return;
    const target = document.querySelector("#adminPanel") || document.querySelector(".admin-panel") || document.querySelector("main") || document.body;
    if (!target) return;

    const links = remoteLoaded ? readLinks() : await fetchRemoteLinks();
    const tracks = tracksLoaded ? remoteTracks : await fetchTracks();
    const panel = document.createElement("section");
    panel.className = "ambient-playlist-admin";
    panel.dataset.ambientPlaylistAdmin = "true";
    panel.innerHTML = `
      <h3>Playlist do ambiente xamânico</h3>
      <p>Cadastre links do YouTube ou envie músicas próprias/licenciadas. Quando a API estiver ativa, isso passa a valer para todos os clientes.</p>
      <textarea data-ambient-playlist-input placeholder="https://www.youtube.com/watch?v=...">${links.join("\n")}</textarea>
      <div class="ambient-playlist-admin-actions">
        <button class="btn" type="button" data-ambient-playlist-save>Salvar links</button>
        <button class="btn btn-secondary" type="button" data-ambient-playlist-clear>Limpar links</button>
        <span class="ambient-playlist-admin-status" data-ambient-playlist-status>${links.length} link(s) carregado(s).</span>
      </div>
      <hr>
      <p>Upload de música ambiente: use apenas arquivos próprios, autorizados ou livres para uso comercial.</p>
      <input type="file" accept="audio/mpeg,audio/mp3,audio/wav,audio/ogg,audio/webm" data-ambient-audio-file>
      <div class="ambient-playlist-admin-actions">
        <button class="btn" type="button" data-ambient-audio-upload>Enviar música</button>
        <span class="ambient-playlist-admin-status" data-ambient-audio-status>${tracks.length} música(s) na API.</span>
      </div>
      <div class="ambient-track-list" data-ambient-track-list>
        ${tracks.slice(0, 8).map((track) => `<span>🎵 ${track.filename}</span>`).join("") || "<span>Nenhuma música enviada ainda.</span>"}
      </div>
    `;

    target.appendChild(panel);

    const input = panel.querySelector("[data-ambient-playlist-input]");
    const status = panel.querySelector("[data-ambient-playlist-status]");
    panel.querySelector("[data-ambient-playlist-save]")?.addEventListener("click", async () => {
      status.textContent = "Salvando links...";
      const result = await saveLinks(String(input.value || "").split(/\n+/));
      input.value = result.links.join("\n");
      status.textContent = result.mode === "api" ? `${result.links.length} link(s) salvo(s) na API.` : `${result.links.length} link(s) salvo(s) neste navegador. API indisponível.`;
      renderPublicPlaylist(true);
    });
    panel.querySelector("[data-ambient-playlist-clear]")?.addEventListener("click", async () => {
      status.textContent = "Limpando links...";
      const result = await saveLinks([]);
      input.value = "";
      status.textContent = result.mode === "api" ? "Links limpos na API." : "Links limpos neste navegador. API indisponível.";
      renderPublicPlaylist(true);
    });

    const fileInput = panel.querySelector("[data-ambient-audio-file]");
    const audioStatus = panel.querySelector("[data-ambient-audio-status]");
    const trackList = panel.querySelector("[data-ambient-track-list]");
    panel.querySelector("[data-ambient-audio-upload]")?.addEventListener("click", async () => {
      audioStatus.textContent = "Enviando música...";
      const uploaded = await uploadTrack(fileInput.files?.[0], audioStatus);
      if (uploaded) {
        fileInput.value = "";
        const tracksNow = await fetchTracks();
        audioStatus.textContent = `${tracksNow.length} música(s) na API.`;
        trackList.innerHTML = tracksNow.slice(0, 8).map((track) => `<span>🎵 ${track.filename}</span>`).join("") || "<span>Nenhuma música enviada ainda.</span>";
      }
    });
  }

  function firstPlaylistUrl() {
    return readLinks()[0] || "";
  }

  async function ensureAudioPlayer(panel) {
    if (panel.querySelector("[data-ambient-audio-player]")) return;
    if (!tracksLoaded) await fetchTracks();
    const track = remoteTracks[0];
    if (!track?.url) return;

    const audio = document.createElement("audio");
    audio.className = "ambient-audio-player";
    audio.controls = true;
    audio.loop = true;
    audio.preload = "none";
    audio.dataset.ambientAudioPlayer = "true";
    audio.src = absoluteApiUrl(track.url);
    panel.appendChild(audio);
    currentAudio = audio;
  }

  async function playUploadedTrack() {
    const panel = document.querySelector("[data-ambient-playlist-public]");
    if (!panel) return;
    await ensureAudioPlayer(panel);
    if (currentAudio) {
      try {
        currentAudio.volume = 0.22;
        await currentAudio.play();
      } catch (error) {
        // O navegador pode exigir novo clique; o player fica disponível manualmente.
      }
    }
  }

  async function renderPublicPlaylist(force = false) {
    if (force) document.querySelectorAll("[data-ambient-playlist-public]").forEach((item) => item.remove());
    if (document.querySelector("[data-ambient-playlist-public]")) return;

    if (!remoteLoaded) await fetchRemoteLinks();
    if (!tracksLoaded) await fetchTracks();
    const url = firstPlaylistUrl();
    const hasTrack = remoteTracks.length > 0;
    if (!url && !hasTrack) return;

    const card = document.querySelector("[data-ambient-card]");
    if (!card) return;

    const panel = document.createElement("div");
    panel.className = "ambient-playlist-public";
    panel.dataset.ambientPlaylistPublic = "true";
    panel.innerHTML = `
      <strong>Playlist especial da loja</strong>
      <span>Ao ativar o ambiente, o cliente pode ouvir uma música suave da Mística Presentes ou abrir a playlist escolhida no YouTube.</span>
      <div class="ambient-playlist-public-actions">
        ${url ? `<a class="btn btn-secondary" href="${url}" target="_blank" rel="noopener" data-ambient-playlist-open>Abrir playlist no YouTube</a>` : ""}
      </div>
    `;
    card.appendChild(panel);
    await ensureAudioPlayer(panel);
  }

  function hookAmbientButton() {
    const button = document.querySelector("[data-ambient-toggle]");
    if (!button || button.dataset.playlistHook === "true") return;
    button.dataset.playlistHook = "true";
    button.addEventListener("click", () => {
      setTimeout(async () => {
        await renderPublicPlaylist();
        const isOn = button.getAttribute("aria-pressed") === "true";
        if (isOn) playUploadedTrack();
        else if (currentAudio) currentAudio.pause();
      }, 180);
    });
  }

  function apply() {
    installStyles();
    renderAdminPanel();
    renderPublicPlaylist();
    hookAmbientButton();
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

  window.misticaAmbientPlaylist = {
    read: readLinks,
    save: saveLinks,
    load: fetchRemoteLinks,
    tracks: fetchTracks,
    upload: uploadTrack,
    apply,
  };
})();
