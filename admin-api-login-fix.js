(() => {
  const cfg = window.misticaSiteConfig || {};
  const API_BASE = String(cfg.apiBaseUrl || "https://misticapresentes-api.onrender.com").replace(/\/$/, "");

  function form() { return document.getElementById("adminLoginForm"); }
  function statusBox() { return document.getElementById("adminLoginStatus"); }
  function adminPanel() { return document.getElementById("adminLoginPanel"); }
  function adminContent() { return document.getElementById("adminContent"); }
  function passwordInput() { return document.getElementById("adminPassword"); }

  function loadScriptOnce(id, src) {
    if (document.getElementById(id)) return;
    const script = document.createElement("script");
    script.id = id;
    script.defer = true;
    script.src = src;
    document.head.appendChild(script);
  }

  function loadMusicAdminAfterLogin() {
    setTimeout(() => {
      loadScriptOnce("adminAmbientMusicScript", "admin-ambient-music.js?v=20260707-google-drive");
      loadScriptOnce("ambientPlayerUnifyScript", "ambient-player-unify.js?v=20260707-google-drive");
      loadScriptOnce("ambientSinglePlayerGuardScript", "ambient-single-player-guard.js?v=20260707-google-drive");
    }, 1000);
  }

  function showStatus(message, ok = false) {
    const box = statusBox();
    if (!box) return;
    box.hidden = false;
    box.textContent = message;
    box.classList.toggle("success", Boolean(ok));
  }

  function normalizeLoginField() {
    const f = form();
    if (!f) return null;
    const pass = passwordInput();
    let login = document.getElementById("adminUser") || document.getElementById("adminLogin") || f.querySelector('input[name="login"]');
    if (!login) {
      login = document.createElement("input");
      login.id = "adminUser";
      login.name = "login";
      login.type = "text";
      login.required = true;
      login.autocomplete = "username";
      login.value = "admin";
      const label = document.createElement("label");
      label.textContent = "Usuário";
      label.appendChild(login);
      if (pass?.closest("label")) f.insertBefore(label, pass.closest("label"));
      else f.prepend(label);
    }
    login.value = "admin";
    login.placeholder = "admin";
    login.autocomplete = "username";
    Array.from(f.querySelectorAll("label")).forEach(label => {
      if (label.contains(login)) label.childNodes[0].textContent = "Usuário";
      if (pass && label.contains(pass)) label.childNodes[0].textContent = "Senha administrativa";
    });
    if (pass) pass.autocomplete = "current-password";
    return login;
  }

  async function loginApi(login, senha) {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 15000);
    try {
      const response = await fetch(`${API_BASE}/api/auth/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json", "Accept": "application/json" },
        body: JSON.stringify({ login, senha }),
        signal: controller.signal,
      });
      const text = await response.text();
      let body = {};
      try { body = text ? JSON.parse(text) : {}; } catch {}
      if (!response.ok) throw new Error(body.detail || `Erro ${response.status}`);
      return body;
    } catch (error) {
      if (error && error.name === "AbortError") throw new Error("API demorou mais de 15 segundos. Aguarde o Render responder e tente novamente.");
      throw error;
    } finally {
      clearTimeout(timer);
    }
  }

  function liberarAdmin(data) {
    try { sessionStorage.setItem("misticaAdminApiUser", JSON.stringify(data)); } catch {}
    const painel = adminPanel();
    const content = adminContent();
    if (painel) painel.hidden = true;
    if (content) content.hidden = false;
    showStatus("Login administrativo autorizado pela API.", true);
    try { if (typeof renderAll === "function") renderAll(); } catch {}
    try { if (typeof renderAdminDashboard === "function") renderAdminDashboard(); } catch {}
    loadMusicAdminAfterLogin();
  }

  async function submitAdminLogin(event) {
    if (event) {
      event.preventDefault();
      event.stopPropagation();
      event.stopImmediatePropagation();
    }
    const loginField = normalizeLoginField();
    const pass = passwordInput();
    const login = String(loginField?.value || "admin").trim().toLowerCase();
    const senha = String(pass?.value || "");
    if (!login || !senha) return showStatus("Informe usuário e senha.");
    showStatus("Validando login pela API...");
    try {
      const data = await loginApi(login, senha);
      liberarAdmin(data);
    } catch (error) {
      showStatus(`Falha no login da API: ${String(error.message || error)}`);
    }
  }

  function install() {
    const f = form();
    if (!f) return;
    normalizeLoginField();
    window.unlockAdmin = () => { submitAdminLogin(); };
    f.onsubmit = submitAdminLogin;
    if (f.dataset.apiLoginFix !== "4") {
      f.dataset.apiLoginFix = "4";
      f.addEventListener("submit", submitAdminLogin, true);
      const button = f.querySelector('button[type="submit"], button');
      if (button) button.addEventListener("click", event => submitAdminLogin(event), true);
    }
  }

  const saved = (() => { try { return JSON.parse(sessionStorage.getItem("misticaAdminApiUser") || "null"); } catch { return null; } })();
  if (saved?.status === "ok") window.addEventListener("load", () => liberarAdmin(saved));
  window.addEventListener("DOMContentLoaded", install);
  window.addEventListener("load", () => { install(); setTimeout(install, 300); setTimeout(install, 1200); });
})();
