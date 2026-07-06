(() => {
  const config = window.misticaSiteConfig || {};
  const API_BASE = String(config.apiBaseUrl || "https://api.misticaesotericos.com.br").replace(/\/$/, "");
  const styleId = "adminAmbientMusicStyle";
  const MAX_AUDIO_BYTES = 30 * 1024 * 1024;

  function isAdminView() {
    return window.location.search.includes("admin=mistica") || window.location.hash.includes("admin-mistica") || document.body?.classList.contains("admin-mode") || document.querySelector("#adminContent:not([hidden])");
  }

  function apiHeaders() {
    const headers = {};
    if (config.siteApiKey) headers["X-Mistica-Api-Key"] = config.siteApiKey;
    return headers;
  }

  function formatBytes(bytes) {
    const value = Number(bytes) || 0;
    if (value >= 1024 * 1024) return `${(value / 1024 / 1024).toFixed(1)} MB`;
    if (value >= 1024) return `${Math.round(value / 1024)} KB`;
    return `${value} B`;
  }

  function fetchWithTimeout(url, options = {}, timeoutMs = 12000) {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), timeoutMs);
    return fetch(url, { ...options, signal: controller.signal }).finally(() => clearTimeout(timer));
  }

  function installStyle() {
    if (document.getElementById(styleId)) return;
    const style = document.createElement("style");
    style.id = styleId;
    style.textContent = `
      .admin-ambient-music { margin: 22px auto; border: 1px solid rgba(240,197,106,.24); border-radius: 24px; padding: clamp(16px, 2.4vw, 24px); background: linear-gradient(145deg, rgba(255,248,230,.07), rgba(83,107,55,.08)); box-shadow: 0 18px 54px rgba(0,0,0,.18); }
      .admin-ambient-music h3 { margin: 0 0 8px; color: #fff6dc; font-family: Cinzel, Georgia, serif; letter-spacing: .05em; }
      .admin-ambient-music p, .admin-ambient-music small { color: #e7dac1; line-height: 1.45; }
      .admin-ambient-music input[type="file"] { width: 100%; margin-top: 10px; border: 1px solid rgba(240,197,106,.28); border-radius: 16px; padding: 12px; color: #fff6dc; background: rgba(0,0,0,.24); }
      .admin-ambient-actions { display: flex; flex-wrap: wrap; gap: 10px; align-items: center; margin-top: 12px; }
      .admin-ambient-status { color: #b8c977; font-weight: 800; font-size: .9rem; }
      .admin-ambient-list { display: grid; gap: 8px; margin-top: 12px; color: #d9ccb5; font-size: .9rem; }
      .admin-ambient-progress-wrap { width: min(460px, 100%); height: 10px; border: 1px solid rgba(240,197,106,.28); border-radius: 999px; overflow: hidden; background: rgba(0,0,0,.22); }
      .admin-ambient-progress-bar { width: 0%; height: 100%; background: linear-gradient(135deg, #f7d77f, #b8c977); transition: width .18s ease; }
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
      const response = await fetchWithTimeout(`${API_BASE}/api/uploads/musicas?t=${Date.now()}`, { cache: "no-store" }, 12000);
      if (!response.ok) throw new Error(`API respondeu ${response.status}`);
      const data = await response.json();
      const musicas = Array.isArray(data.musicas) ? data.musicas : [];
      if (status) status.textContent = `${musicas.length} música(s) encontrada(s) na API.`;
      if (list) {
        list.innerHTML = musicas.length
          ? musicas.slice(0, 12).map((item) => `<span>🎵 ${item.filename || "música"} • ${formatBytes(item.size_bytes || 0)}</span>`).join("")
          : "<span>Nenhuma música encontrada. Envie uma música e aguarde a confirmação.</span>";
      }
      return musicas;
    } catch (error) {
      const msg = error.name === "AbortError" ? "A API demorou para responder. Tente enviar a música mesmo assim ou recarregue o ADM." : (error.message || "API indisponível");
      if (status) status.textContent = msg;
      if (list) list.innerHTML = `<span>${msg}</span>`;
      return [];
    }
  }

  function uploadWithProgress(url, form, headers, onProgress) {
    return new Promise((resolve, reject) => {
      const xhr = new XMLHttpRequest();
      xhr.open("POST", url, true);
      xhr.timeout = 90000;
      Object.entries(headers || {}).forEach(([key, value]) => xhr.setRequestHeader(key, value));
      xhr.upload.onprogress = (event) => {
        if (event.lengthComputable && onProgress) onProgress(Math.round((event.loaded / event.total) * 100));
      };
      xhr.onload = () => {
        let data = {};
        try { data = JSON.parse(xhr.responseText || "{}"); } catch (error) { data = {}; }
        if (xhr.status >= 200 && xhr.status < 300) resolve(data);
        else reject(new Error(data.detail || `API respondeu ${xhr.status}`));
      };
      xhr.onerror = () => reject(new Error("Falha de conexão com a API."));
      xhr.ontimeout = () => reject(new Error("O envio demorou demais. Tente um MP3 menor ou confira a conexão."));
      xhr.send(form);
    });
  }

  async function uploadTrack(panel) {
    const input = panel.querySelector("[data-admin-ambient-file]");
    const status = panel.querySelector("[data-admin-ambient-status]");
    const button = panel.querySelector("[data-admin-ambient-upload]");
    const progress = panel.querySelector("[data-admin-ambient-progress]");
    const file = input?.files?.[0];

    if (!file) {
      if (status) status.textContent = "Selecione uma música antes de enviar.";
      return;
    }

    if (file.size > MAX_AUDIO_BYTES) {
      if (status) status.textContent = `Arquivo muito grande: ${formatBytes(file.size)}. Limite: 30 MB.`;
      return;
    }

    const form = new FormData();
    form.append("arquivo", file);
    form.append("nome_base", file.name.replace(/\.[^.]+$/, "") || "ambiente-xamanico");

    try {
      if (button) button.disabled = true;
      if (progress) progress.style.width = "0%";
      if (status) status.textContent = `Enviando ${file.name} (${formatBytes(file.size)})...`;
      const data = await uploadWithProgress(`${API_BASE}/api/uploads/musicas`, form, apiHeaders(), (percent) => {
        if (progress) progress.style.width = `${percent}%`;
        if (status) status.textContent = `Enviando ${file.name}: ${percent}%`;
      });
      if (status) status.textContent = `Música enviada: ${data.filename || file.name}`;
      if (progress) progress.style.width = "100%";
      input.value = "";
      setTimeout(() => listTracks(panel), 900);
    } catch (error) {
      if (status) status.textContent = `Falha ao enviar: ${error.message || "erro desconhecido"}`;
    } finally {
      if (button) button.disabled = false;
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
      <input type="file" accept="audio/mpeg,audio/mp3,audio/wav,audio/ogg,audio/webm,audio/mp4,audio/x-m4a" data-admin-ambient-file>
      <div class="admin-ambient-actions">
        <button class="btn" type="button" data-admin-ambient-upload>Enviar música</button>
        <button class="btn btn-secondary" type="button" data-admin-ambient-refresh>Atualizar lista</button>
        <span class="admin-ambient-status" data-admin-ambient-status>Pronto para enviar.</span>
      </div>
      <div class="admin-ambient-progress-wrap"><div class="admin-ambient-progress-bar" data-admin-ambient-progress></div></div>
      <small>Formatos aceitos: MP3, WAV, OGG, WEBM e M4A. Limite atual: 30 MB por arquivo.</small>
      <div class="admin-ambient-list" data-admin-ambient-list></div>
    `;

    target.appendChild(panel);
    panel.querySelector("[data-admin-ambient-upload]")?.addEventListener("click", () => uploadTrack(panel));
    panel.querySelector("[data-admin-ambient-refresh]")?.addEventListener("click", () => listTracks(panel));
    setTimeout(() => listTracks(panel), 200);
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
