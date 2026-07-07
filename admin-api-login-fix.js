(() => {
  const cfg = window.misticaSiteConfig || {};
  const API_BASE = String(cfg.apiBaseUrl || "https://misticapresentes-api.onrender.com").replace(/\/$/, "");

  function findForm() {
    return document.getElementById("adminLoginForm");
  }

  function statusBox() {
    return document.getElementById("adminLoginStatus");
  }

  function adminPanel() {
    return document.getElementById("adminLoginPanel");
  }

  function adminContent() {
    return document.getElementById("adminContent");
  }

  function ensureLoginInput(form) {
    let input = document.getElementById("adminUser") || document.getElementById("adminLogin") || form.querySelector('input[name="login"]');
    if (input) return input;

    const passwordInput = document.getElementById("adminPassword");
    const label = document.createElement("label");
    label.textContent = "Usuário";
    input = document.createElement("input");
    input.id = "adminUser";
    input.name = "login";
    input.type = "text";
    input.autocomplete = "username";
    input.value = "admin";
    input.required = true;
    label.appendChild(input);

    if (passwordInput && passwordInput.closest("label")) {
      form.insertBefore(label, passwordInput.closest("label"));
    } else {
      form.prepend(label);
    }
    return input;
  }

  function showStatus(message, ok = false) {
    const box = statusBox();
    if (!box) return;
    box.hidden = false;
    box.textContent = message;
    box.classList.toggle("success", Boolean(ok));
  }

  async function loginApi(login, senha) {
    const response = await fetch(`${API_BASE}/api/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json", "Accept": "application/json" },
      body: JSON.stringify({ login, senha }),
    });
    const text = await response.text();
    let body = {};
    try { body = text ? JSON.parse(text) : {}; } catch {}
    if (!response.ok) throw new Error(body.detail || `Erro ${response.status}`);
    return body;
  }

  function liberarAdmin(data) {
    try { sessionStorage.setItem("misticaAdminApiUser", JSON.stringify(data)); } catch {}
    const loginPanel = adminPanel();
    const content = adminContent();
    if (loginPanel) loginPanel.hidden = true;
    if (content) content.hidden = false;
    showStatus("Login administrativo autorizado pela API.", true);
    try { if (typeof renderAll === "function") renderAll(); } catch {}
    try { if (typeof renderAdminDashboard === "function") renderAdminDashboard(); } catch {}
  }

  function install() {
    const form = findForm();
    if (!form || form.dataset.apiLoginFix === "1") return;
    form.dataset.apiLoginFix = "1";
    const loginInput = ensureLoginInput(form);
    const passwordInput = document.getElementById("adminPassword");
    if (passwordInput) passwordInput.autocomplete = "current-password";

    form.addEventListener("submit", async event => {
      event.preventDefault();
      event.stopImmediatePropagation();
      const login = String(loginInput.value || "admin").trim().toLowerCase();
      const senha = String((passwordInput && passwordInput.value) || "");
      if (!login || !senha) return showStatus("Informe usuário e senha.");
      showStatus("Validando login pela API...");
      try {
        const data = await loginApi(login, senha);
        liberarAdmin(data);
      } catch (error) {
        showStatus(`Falha no login da API: ${String(error.message || error)}`);
      }
    }, true);
  }

  window.addEventListener("DOMContentLoaded", install);
  window.addEventListener("load", () => {
    install();
    setTimeout(install, 300);
    setTimeout(install, 1200);
  });
})();
