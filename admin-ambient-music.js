(() => {
  const config = window.misticaSiteConfig || {};
  const API_BASE = String(config.apiBaseUrl || "https://api.misticaesotericos.com.br").replace(/\/$/, "");
  const styleId = "adminAmbientMusicStyle";

  function isAdminView() {
    return window.location.search.includes("admin=mistica") || window.location.hash.includes("admin-mistica") || document.body?.classList.contains("admin-mode") || document.querySelector("#adminContent:not([hidden])");
  }

  function apiHeaders() {
    const headers = {};
    if (config.siteApiKey) headers["X-Mistica-Api-Key"] = config.siteApiKey;
    return headers;
  }

  function installStyle() {
    if (document.getElementById(styleId)) return;
    const style = document.createElement("style");
    style.id = styleId;
    style.textContent = `
      .admin-ambient-music {
        margin: 22px auto;
        border: 1px solid rgba(240,197,106,.24);
        border-radius: 24px;
        padding: clamp(16px, 2.4vw, 24px);
        background: linear-gradient(145deg, rgba(255,248,230,.07), rgba(83,107,55,.08));
        box-shadow: 0 18px 54px rgba(0,0,0,.18);
      }

      .admin-ambient-music h3 {
        margin: 0 0 8px;
        color: #fff6dc;
        font-family: Cinzel, Georgia, serif;
        letter-spacing: .05em;
      }

      .admin-ambient-music p,
      .admin-ambient-music small {
        color: #e7dac1;
        line-height: 1.45;
      }

      .admin-ambient-music input[type="file"] {
        width: 100%;
        margin-top: 10px;
        border: 1px solid rgba(240,197,106,.28);
        border-radius: 16px;
        padding: 12px;
        color: #fff6dc;
        background: rgba(0,0,0,.24);
      }

      .admin-ambient-actions {
        display: flex;
        flex-wrap: wrap;
        gap: 10px;
        align-items: center;
        margin-top: 12px;
      }

      .admin-ambient-status {
        color: #b8c977;
        font-weight: 800;
        font-size: .9rem;
      }

      .admin-ambient-list {
        display: grid;
        gap: 8px;
        margin-top: 12px;
        color: #d9ccb5;
        font-size: .9rem;
      }
    `;
    document.head.appendChild(style);
  }

  function findAdminTarget() {
    return document.querySelector("#adminContent") || document.querySelector(".admin-content") || document.querySelector("#admin") || document.querySelector("main") || document.body;
  }

  async function listTracks(panel) {
    const list = panel.querySelector("[data-admin-ambient-list]");
    const status = panel.querySelector("[data-admin-ambient-status]");
    if (status) status.textContent = "Verificando músicas na API...";

    try {
      const response = await fetch(`${API_BASE}/api/uploads/musicas`, { cache: "no-store" });
      if (!response.ok) throw new Error(`API respondeu ${response.status}`);
      const data = await response.json();
      const musicas = Array.isArray(data.musicas) ? data.musicas : [];
      if (status) status.textContent = `${musicas.length} música(s) encontrada(s) na API.`;
      if (list) {
        list.innerHTML = musicas.length
          ? musicas.slice(0, 12).map((item) => `<span>🎵 ${item.filename || "música"} • ${Math.round((item.size_bytes || 0) / 1024)} KB</span>`).join("")
          : "<span>Nenhuma música encontrada. Envie novamente após o deploy da correção.</span>";
      }
      return musicas;
    } catch (error) {
      if (status) status.textContent = "Não consegui consultar a API de músicas.";
      if (list) list.innerHTML = `<span>Erro: ${error.message || "API indisponível"}</span>`;
      return [];
    }
  }

  async function uploadTrack(panel) {
    const input = panel.querySelector("[data-admin-ambient-file]");
    const status = panel.querySelector("[data-admin-ambient-status]");
    const file = input?.files?.[0];

    if (!file) {
      if (status) status.textContent = "Selecione uma música antes de enviar.";
      return;
    }

    const form = new FormData();
    form.append("arquivo", file);
    form.append("nome_base", file.name.replace(/\.[^.]+$/, "") || "ambiente-xamanico");

    try {
      if (status) status.textContent = "Enviando música para a API...";
      const response = await fetch(`${API_BASE}/api/uploads/musicas`, {
        method: "POST",
        headers: apiHeaders(),
        body: form,
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(data.detail || `API respondeu ${response.status}`);
      if (status) status.textContent = `Música enviada: ${data.filename || file.name}`;
      input.value = "";
      await listTracks(panel);
    } catch (error) {
      if (status) status.textContent = `Falha ao enviar: ${error.message || "erro desconhecido"}`;
    }
  }

  function renderPanel() {
    if (!isAdminView()) return;
    if (document.querySelector("[data-admin-ambient-music]")) return;

    const target = findAdminTarget();
    if (!target) return;

    const panel = document.createElement("section");
    panel.className = "admin-ambient-music";
    panel.dataset.adminAmbientMusic = "true";
    panel.innerHTML = `
      <h3>Músicas do ambiente xamânico</h3>
      <p>Envie músicas próprias, autorizadas ou livres para uso comercial. Elas serão usadas no player do site quando o cliente ativar o ambiente xamânico.</p>
      <input type="file" accept="audio/mpeg,audio/mp3,audio/wav,audio/ogg,audio/webm" data-admin-ambient-file>
      <div class="admin-ambient-actions">
        <button class="btn" type="button" data-admin-ambient-upload>Enviar música</button>
        <button class="btn btn-secondary" type="button" data-admin-ambient-refresh>Atualizar lista</button>
        <span class="admin-ambient-status" data-admin-ambient-status>Pronto para enviar.</span>
      </div>
      <small>Formatos aceitos: MP3, WAV, OGG e WEBM. Limite atual: 18 MB por arquivo.</small>
      <div class="admin-ambient-list" data-admin-ambient-list></div>
    `;

    target.appendChild(panel);
    panel.querySelector("[data-admin-ambient-upload]")?.addEventListener("click", () => uploadTrack(panel));
    panel.querySelector("[data-admin-ambient-refresh]")?.addEventListener("click", () => listTracks(panel));
    listTracks(panel);
  }

  function apply() {
    installStyle();
    renderPanel();
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", apply, { once: true });
  else apply();

  window.addEventListener("load", () => {
    apply();
    setTimeout(apply, 600);
    setTimeout(apply, 1800);
  });

  document.addEventListener("click", () => setTimeout(apply, 250));
})();
