(() => {
  const STORAGE_KEY = "misticaAmbientPlaylistLinks";
  const styleId = "misticaAmbientPlaylistStyle";
  const config = window.misticaSiteConfig || {};
  const API_BASE = String(config.apiBaseUrl || "https://api.misticaesotericos.com.br").replace(/\/$/, "");

  let remoteLinks = null;
  let remoteLoaded = false;

  function isAdminView() {
    return window.location.search.includes("admin=mistica") || window.location.hash.includes("admin-mistica") || document.body?.classList.contains("admin-mode");
  }

  function apiHeaders() {
    const headers = { "Content-Type": "application/json" };
    if (config.siteApiKey) headers["X-Mistica-Api-Key"] = config.siteApiKey;
    return headers;
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

      .ambient-playlist-admin textarea {
        width: 100%;
        min-height: 120px;
        border: 1px solid rgba(240,197,106,.28);
        border-radius: 16px;
        padding: 12px;
        color: #fff6dc;
        background: rgba(0,0,0,.24);
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

      .ambient-playlist-public a {
        text-decoration: none;
      }
    `;
    document.head.appendChild(style);
  }

  async function renderAdminPanel() {
    if (!isAdminView() || document.querySelector("[data-ambient-playlist-admin]")) return;
    const target = document.querySelector("#adminPanel") || document.querySelector(".admin-panel") || document.querySelector("main") || document.body;
    if (!target) return;

    const links = remoteLoaded ? readLinks() : await fetchRemoteLinks();
    const panel = document.createElement("section");
    panel.className = "ambient-playlist-admin";
    panel.dataset.ambientPlaylistAdmin = "true";
    panel.innerHTML = `
      <h3>Playlist do ambiente xamânico</h3>
      <p>Cadastre links do YouTube, um por linha. Quando a API estiver ativa, a playlist passa a valer para todos os clientes.</p>
      <textarea data-ambient-playlist-input placeholder="https://www.youtube.com/watch?v=...">${links.join("\n")}</textarea>
      <div class="ambient-playlist-admin-actions">
        <button class="btn" type="button" data-ambient-playlist-save>Salvar playlist</button>
        <button class="btn btn-secondary" type="button" data-ambient-playlist-clear>Limpar</button>
        <span class="ambient-playlist-admin-status" data-ambient-playlist-status>${links.length} link(s) carregado(s).</span>
      </div>
    `;

    target.appendChild(panel);

    const input = panel.querySelector("[data-ambient-playlist-input]");
    const status = panel.querySelector("[data-ambient-playlist-status]");
    panel.querySelector("[data-ambient-playlist-save]")?.addEventListener("click", async () => {
      status.textContent = "Salvando playlist...";
      const result = await saveLinks(String(input.value || "").split(/\n+/));
      input.value = result.links.join("\n");
      status.textContent = result.mode === "api" ? `${result.links.length} link(s) salvo(s) na API.` : `${result.links.length} link(s) salvo(s) neste navegador. API indisponível.`;
      renderPublicPlaylist(true);
    });
    panel.querySelector("[data-ambient-playlist-clear]")?.addEventListener("click", async () => {
      status.textContent = "Limpando playlist...";
      const result = await saveLinks([]);
      input.value = "";
      status.textContent = result.mode === "api" ? "Playlist limpa na API." : "Playlist limpa neste navegador. API indisponível.";
      renderPublicPlaylist(true);
    });
  }

  function firstPlaylistUrl() {
    return readLinks()[0] || "";
  }

  async function renderPublicPlaylist(force = false) {
    if (force) document.querySelectorAll("[data-ambient-playlist-public]").forEach((item) => item.remove());
    if (document.querySelector("[data-ambient-playlist-public]")) return;

    if (!remoteLoaded) await fetchRemoteLinks();
    const url = firstPlaylistUrl();
    if (!url) return;

    const card = document.querySelector("[data-ambient-card]");
    if (!card) return;

    const panel = document.createElement("div");
    panel.className = "ambient-playlist-public";
    panel.dataset.ambientPlaylistPublic = "true";
    panel.innerHTML = `
      <strong>Playlist especial da loja</strong>
      <span>Ao ativar o ambiente, o cliente também pode abrir uma playlist suave escolhida pela Mística Presentes.</span>
      <div class="ambient-playlist-public-actions">
        <a class="btn btn-secondary" href="${url}" target="_blank" rel="noopener" data-ambient-playlist-open>Abrir playlist no YouTube</a>
      </div>
    `;
    card.appendChild(panel);
  }

  function hookAmbientButton() {
    const button = document.querySelector("[data-ambient-toggle]");
    if (!button || button.dataset.playlistHook === "true") return;
    button.dataset.playlistHook = "true";
    button.addEventListener("click", () => {
      setTimeout(() => renderPublicPlaylist(), 120);
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
    apply,
  };
})();
