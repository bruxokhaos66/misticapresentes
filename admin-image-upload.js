(() => {
  const cfg = window.misticaSiteConfig || {};
  const API_BASE = (cfg.apiBaseUrl || "https://api.misticaesotericos.com.br").replace(/\/$/, "");
  const SITE_API_KEY = String(cfg.siteApiKey || "").trim();

  function make(tag, cls, text) {
    const el = document.createElement(tag);
    if (cls) el.className = cls;
    if (text !== undefined) el.textContent = text;
    return el;
  }

  function headers() {
    return SITE_API_KEY ? { "X-Mistica-Api-Key": SITE_API_KEY } : {};
  }

  function fullUrl(path) {
    if (!path) return "";
    if (path.startsWith("http://") || path.startsWith("https://")) return path;
    return `${API_BASE}${path.startsWith("/") ? "" : "/"}${path}`;
  }

  function status(text, ok = true) {
    const el = document.getElementById("imageUploadStatus");
    if (!el) return;
    el.textContent = text;
    el.className = ok ? "saved-box" : "warning-box warning-danger";
    el.hidden = false;
  }

  async function uploadImage(file, produtoId) {
    const form = new FormData();
    form.append("arquivo", file);
    const response = await fetch(`${API_BASE}/api/uploads/produtos?produto_id=${encodeURIComponent(produtoId || "produto")}`, {
      method: "POST",
      headers: headers(),
      body: form,
    });
    if (!response.ok) {
      let detail = `Erro ${response.status}`;
      try {
        const body = await response.json();
        detail = body.detail || detail;
      } catch {}
      throw new Error(detail);
    }
    return response.json();
  }

  function inserirUrlNoCampo(url) {
    const field = document.getElementById("productImages");
    if (!field) return false;
    const atual = field.value.trim();
    field.value = atual ? `${atual}\n${url}` : url;
    field.dispatchEvent(new Event("input", { bubbles: true }));
    return true;
  }

  function mountImageUploader() {
    if (document.getElementById("imageUploadPanel")) return;
    const form = document.getElementById("productAdminForm");
    if (!form) return;

    const panel = make("div", "image-upload-panel");
    panel.id = "imageUploadPanel";
    panel.innerHTML = `
      <p class="eyebrow">Imagem do produto</p>
      <h3>Enviar foto para a API</h3>
      <p class="privacy-note">Escolha uma imagem JPG, PNG ou WEBP de até 4 MB. A URL gerada será adicionada ao campo de imagens.</p>
      <label class="image-upload-drop">
        <span>Selecionar imagem do produto</span>
        <input id="productImageFile" type="file" accept="image/png,image/jpeg,image/webp" />
      </label>
      <div id="imagePreviewBox" class="image-preview-box" hidden></div>
      <div class="image-upload-actions">
        <button class="btn" type="button" id="sendProductImage">Enviar imagem</button>
        <button class="btn btn-ghost" type="button" id="copyUploadedImage" hidden>Copiar URL</button>
      </div>
      <div id="imageUploadStatus" hidden></div>
    `;
    form.appendChild(panel);

    const input = document.getElementById("productImageFile");
    const preview = document.getElementById("imagePreviewBox");
    const send = document.getElementById("sendProductImage");
    const copy = document.getElementById("copyUploadedImage");
    let uploadedUrl = "";

    input.addEventListener("change", () => {
      const file = input.files?.[0];
      uploadedUrl = "";
      copy.hidden = true;
      if (!file) {
        preview.hidden = true;
        preview.innerHTML = "";
        return;
      }
      if (file.size > 4 * 1024 * 1024) {
        status("Imagem muito grande. Use até 4 MB.", false);
        input.value = "";
        return;
      }
      const url = URL.createObjectURL(file);
      preview.hidden = false;
      preview.innerHTML = `<img src="${url}" alt="Prévia da imagem"><span>${file.name}</span>`;
    });

    send.addEventListener("click", async () => {
      const file = input.files?.[0];
      if (!file) return status("Selecione uma imagem antes de enviar.", false);
      const productName = document.getElementById("productName")?.value || "produto";
      send.disabled = true;
      status("Enviando imagem...", true);
      try {
        const result = await uploadImage(file, productName);
        uploadedUrl = fullUrl(result.url);
        inserirUrlNoCampo(uploadedUrl);
        copy.hidden = false;
        status("Imagem enviada e URL adicionada ao campo de imagens.", true);
      } catch (error) {
        status(`Falha ao enviar imagem: ${error.message}`, false);
      } finally {
        send.disabled = false;
      }
    });

    copy.addEventListener("click", async () => {
      if (!uploadedUrl) return;
      try {
        await navigator.clipboard.writeText(uploadedUrl);
        status("URL da imagem copiada.", true);
      } catch {
        window.prompt("Copie a URL da imagem:", uploadedUrl);
      }
    });
  }

  window.addEventListener("load", () => {
    mountImageUploader();
    setInterval(mountImageUploader, 1500);
  });
})();
