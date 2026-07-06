(() => {
  const STORAGE_KEY = "misticaAmbientPlaylistLinks";
  const styleId = "misticaAmbientPlaylistStyle";
  const config = window.misticaSiteConfig || {};
  const API_BASE = String(config.apiBaseUrl || "https://api.misticaesotericos.com.br").replace(/\/$/, "");
  const AUDIO_EXT_RE = /\.(mp3|wav|ogg|webm|m4a)(\?|#|$)/i;

  let remoteYoutubeLinks = null;
  let remoteAudioLinks = null;
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

  function normalizeYoutubeUrl(value) {
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

  function normalizeAudioUrl(value) {
    const text = String(value || "").trim();
    if (!text) return "";
    try {
      const url = new URL(text);
      if (!["http:", "https:"].includes(url.protocol)) return "";
      if (!AUDIO_EXT_RE.test(url.pathname + url.search + url.hash)) return "";
      return url.toString();
    } catch (error) {
      return "";
    }
  }

  function cleanYoutubeLinks(links) {
    return [...new Set((links || []).map(normalizeYoutubeUrl).filter(Boolean))].slice(0, 12);
  }

  function cleanAudioLinks(links) {
    return [...new Set((links || []).map(normalizeAudioUrl).filter(Boolean))].slice(0, 20);
  }

  function splitLinks(links) {
    const youtube = [];
    const audio = [];
    (links || []).forEach((item) => {
      const yt = normalizeYoutubeUrl(item);
      const aud = normalizeAudioUrl(item);
      if (yt && !youtube.includes(yt)) youtube.push(yt);
      else if (aud && !audio.includes(aud)) audio.push(aud);
    });
    return { youtube: youtube.slice(0, 12), audio: audio.slice(0, 20) };
  }

  function readLocalLinks() {
    try {
      const parsed = JSON.parse(localStorage.getItem(STORAGE_KEY) || "[]");
      if (!Array.isArray(parsed)) return [];
      const split = splitLinks(parsed);
      return [...split.youtube, ...split.audio];
    } catch (error) {
      return [];
    }
  }

  function writeLocalLinks(links) {
    const split = splitLinks(links);
    const clean = [...split.youtube, ...split.audio];
    localStorage.setItem(STORAGE_KEY, JSON.stringify(clean));
    return clean;
  }

  function readLinks() {
    if (remoteYoutubeLinks || remoteAudioLinks) return [...(remoteYoutubeLinks || []), ...(remoteAudioLinks || [])];
    return readLocalLinks();
  }

  async function fetchRemoteLinks() {
    const local = readLocalLinks();
    try {
      const response = await fetch(`${API_BASE}/api/site/playlist-ambiente`, { cache: "no-store" });
      if (!response.ok) throw new Error("Playlist remota indisponível.");
      const data = await response.json();
      remoteYoutubeLinks = cleanYoutubeLinks(data.links || []);
    } catch (error) {
      remoteYoutubeLinks = null;
    }

    try {
      const response = await fetch(`${API_BASE}/api/uploads/musicas/links`, { cache: "no-store" });
      if (!response.ok) throw new Error("Links de áudio indisponíveis.");
      const data = await response.json();
      remoteAudioLinks = cleanAudioLinks(data.links || []);
    } catch (error) {
      remoteAudioLinks = null;
    }

    remoteLoaded = true;
    const merged = readLinks();
    if (merged.length) writeLocalLinks(merged);
    return merged.length ? merged : local;
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
    if (!file) {
      if (status) status.textContent = "Selecione uma música antes de enviar.";
      return null;
    }
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
      tracksLoaded = false;
      await fetchTracks();
      await renderPublicPlaylist(true);
      updateAudioSource(true);
      return data;
    } catch (error) {
      if (status) status.textContent = error.message || "Falha ao enviar música.";
      return null;
    }
  }

  async function saveLinks(links) {
    const split = splitLinks(links);
    const clean = writeLocalLinks([...split.youtube, ...split.audio]);
    remoteYoutubeLinks = split.youtube;
    remoteAudioLinks = split.audio;
    let savedYoutube = false;
    let savedAudio = false;

    try {
      const response = await fetch(`${API_BASE}/api/site/playlist-ambiente`, {
        method: "POST",
        headers: apiHeaders(),
        body: JSON.stringify({ links: split.youtube }),
      });
      if (response.ok) {
        const data = await response.json();
        remoteYoutubeLinks = cleanYoutubeLinks(data.links || split.youtube);
        savedYoutube = true;
      }
    } catch (error) {
      savedYoutube = false;
    }

    try {
      const response = await fetch(`${API_BASE}/api/uploads/musicas/links`, {
        method: "POST",
        headers: apiHeaders(),
        body: JSON.stringify({ links: split.audio }),
      });
      if (response.ok) {
        const data = await response.json();
        remoteAudioLinks = cleanAudioLinks(data.links || split.audio);
        savedAudio = true;
      }
    } catch (error) {
      savedAudio = false;
    }

    const mode = savedYoutube || savedAudio ? "api" : "local";
    const next = mode === "api" ? [...(remoteYoutubeLinks || []), ...(remoteAudioLinks || [])] : clean;
    writeLocalLinks(next);
    return { links: next, youtube: split.youtube.length, audio: split.audio.length, mode };
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

      .ambient-playlist-admin-status,
      .ambient-player-status {
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
      <p>Cadastre links do YouTube ou links diretos de áudio, um por linha. Links diretos terminados em MP3, WAV, OGG, WEBM ou M4A podem tocar no player do site.</p>
      <textarea data-ambient-playlist-input placeholder="https://www.youtube.com/watch?v=...\nhttps://site.com/musica.mp3">${links.join("\n")}</textarea>
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
      status.textContent = result.mode === "api"
        ? `${result.links.length} link(s) salvo(s): ${result.youtube} YouTube e ${result.audio} áudio direto.`
        : `${result.links.length} link(s) salvo(s) neste navegador. API indisponível.`;
      await renderPublicPlaylist(true);
      updateAudioSource(true);
    });
    panel.querySelector("[data-ambient-playlist-clear]")?.addEventListener("click", async () => {
      status.textContent = "Limpando links...";
      const result = await saveLinks([]);
      input.value = "";
      status.textContent = result.mode === "api" ? "Links limpos na API." : "Links limpos neste navegador. API indisponível.";
      await renderPublicPlaylist(true);
      updateAudioSource(true);
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

  function firstYoutubeUrl() {
    return (remoteYoutubeLinks || splitLinks(readLocalLinks()).youtube)[0] || "";
  }

  function audioCandidates() {
    const uploaded = (remoteTracks || []).map((track) => absoluteApiUrl(track.url)).filter(Boolean);
    const direct = remoteAudioLinks || splitLinks(readLocalLinks()).audio;
    return [...uploaded, ...direct].filter(Boolean);
  }

  function setPlayerStatus(text) {
    const status = document.querySelector("[data-ambient-player-status]");
    if (status) status.textContent = text;
  }

  function updateAudioSource(force = false) {
    const panel = document.querySelector("[data-ambient-playlist-public]");
    if (!panel) return null;
    let audio = panel.querySelector("[data-ambient-audio-player]");
    const source = audioCandidates()[0] || "";
    if (!source) return null;

    if (!audio) {
      audio = document.createElement("audio");
      audio.className = "ambient-audio-player";
      audio.controls = true;
      audio.loop = true;
      audio.preload = "auto";
      audio.dataset.ambientAudioPlayer = "true";
      panel.appendChild(audio);
    }

    if (force || audio.src !== source) {
      audio.pause();
      audio.src = source;
      audio.load();
      setPlayerStatus("Player atualizado com a música ambiente.");
    }
    currentAudio = audio;
    return audio;
  }

  async function refreshAudioData() {
    remoteLoaded = false;
    tracksLoaded = false;
    await fetchRemoteLinks();
    await fetchTracks();
  }

  async function playPreferredAudio() {
    const panel = document.querySelector("[data-ambient-playlist-public]");
    if (!panel) return;
    const audio = updateAudioSource(true);
    if (!audio) {
      setPlayerStatus("Nenhum áudio direto disponível. Use o botão do YouTube, se houver.");
      return;
    }

    try {
      audio.volume = 0.22;
      await audio.play();
      setPlayerStatus("Música ambiente tocando no player do site.");
    } catch (error) {
      setPlayerStatus("Clique no player para iniciar a música neste navegador.");
    }
  }

  async function renderPublicPlaylist(force = false) {
    if (force) document.querySelectorAll("[data-ambient-playlist-public]").forEach((item) => item.remove());
    if (document.querySelector("[data-ambient-playlist-public]")) return;

    if (!remoteLoaded) await fetchRemoteLinks();
    if (!tracksLoaded) await fetchTracks();
    const youtubeUrl = firstYoutubeUrl();
    const hasAudio = audioCandidates().length > 0;
    if (!youtubeUrl && !hasAudio) return;

    const card = document.querySelector("[data-ambient-card]");
    if (!card) return;

    const panel = document.createElement("div");
    panel.className = "ambient-playlist-public";
    panel.dataset.ambientPlaylistPublic = "true";
    panel.innerHTML = `
      <strong>Playlist especial da loja</strong>
      <span>Ao ativar o ambiente, o site tenta tocar automaticamente a música cadastrada no player. Links do YouTube ficam como opção externa.</span>
      <div class="ambient-playlist-public-actions">
        ${youtubeUrl ? `<a class="btn btn-secondary" href="${youtubeUrl}" target="_blank" rel="noopener" data-ambient-playlist-open>Abrir playlist no YouTube</a>` : ""}
        ${hasAudio ? `<button class="btn btn-secondary" type="button" data-ambient-player-play>Tocar no site</button>` : ""}
        <span class="ambient-player-status" data-ambient-player-status>${hasAudio ? "Player pronto para tocar após ativação." : "Sem áudio direto cadastrado."}</span>
      </div>
    `;
    card.appendChild(panel);
    updateAudioSource(true);
    panel.querySelector("[data-ambient-player-play]")?.addEventListener("click", playPreferredAudio);
  }

  function hookAmbientButton() {
    const button = document.querySelector("[data-ambient-toggle]");
    if (!button || button.dataset.playlistHook === "true") return;
    button.dataset.playlistHook = "true";
    button.addEventListener("click", () => {
      setTimeout(async () => {
        await refreshAudioData();
        await renderPublicPlaylist(true);
        const isOn = button.getAttribute("aria-pressed") === "true";
        if (isOn) await playPreferredAudio();
        else if (currentAudio) {
          currentAudio.pause();
          setPlayerStatus("Música ambiente pausada.");
        }
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
    play: playPreferredAudio,
    apply,
  };
})();
