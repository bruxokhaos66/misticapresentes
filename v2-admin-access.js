(() => {
  const ADMIN_HASH = '#adminbruxo';
  const LEGACY_HASH = '#admin';
  const API_BASE = 'https://misticapresentes-api.onrender.com';
  const SESSION_KEY = 'misticaAdminSession';
  const LEGACY_UNLOCK_KEY = 'misticaAdminUnlocked';

  const ready = (fn) => document.readyState === 'loading' ? document.addEventListener('DOMContentLoaded', fn) : fn();

  const safeJsonParse = (value) => {
    try { return JSON.parse(value); } catch { return null; }
  };

  const getSession = () => {
    const session = safeJsonParse(localStorage.getItem(SESSION_KEY) || 'null');
    if (!session || session.status !== 'ok') return null;
    if (!session.usuario || session.usuario.perfil !== 'adm') return null;
    return session;
  };

  const saveSession = (payload) => {
    localStorage.setItem(SESSION_KEY, JSON.stringify({
      status: 'ok',
      usuario: payload.usuario,
      permissoes: payload.permissoes,
      data_hora: payload.data_hora,
      saved_at: new Date().toISOString(),
    }));
    localStorage.removeItem(LEGACY_UNLOCK_KEY);
  };

  ready(() => {
    const adminSection = document.getElementById('admin');
    const loginPanel = document.getElementById('adminLoginPanel');
    const adminContent = document.getElementById('adminContent');
    const loginForm = document.getElementById('adminLoginForm');
    const passwordInput = document.getElementById('adminPassword');
    const loginStatus = document.getElementById('adminLoginStatus');

    if (!adminSection || !loginPanel || !adminContent || !loginForm || !passwordInput) return;

    adminSection.setAttribute('data-admin-secret', 'adminbruxo');

    const showStatus = (message, ok = false) => {
      if (!loginStatus) return;
      loginStatus.hidden = false;
      loginStatus.textContent = message;
      loginStatus.className = ok ? 'warning-box' : 'warning-box warning-danger';
    };

    const ensurePasswordLabel = () => {
      if (passwordInput.closest('label')) return;
      const label = document.createElement('label');
      label.textContent = 'Senha';
      passwordInput.parentNode.insertBefore(label, passwordInput);
      label.appendChild(passwordInput);
    };

    const ensureUserField = () => {
      let input = document.getElementById('adminUser');
      if (input) return input;
      const label = document.createElement('label');
      label.textContent = 'Login';
      input = document.createElement('input');
      input.id = 'adminUser';
      input.name = 'adminUser';
      input.type = 'text';
      input.autocomplete = 'username';
      input.placeholder = 'admin';
      input.required = true;
      label.appendChild(input);
      loginForm.insertBefore(label, loginForm.firstElementChild || passwordInput);
      return input;
    };

    const ensureLogoutButton = () => {
      if (adminContent.querySelector('[data-admin-logout]')) return;
      const button = document.createElement('button');
      button.type = 'button';
      button.className = 'btn btn-ghost';
      button.setAttribute('data-admin-logout', 'true');
      button.textContent = 'Sair do admin';
      button.addEventListener('click', () => {
        localStorage.removeItem(SESSION_KEY);
        localStorage.removeItem(LEGACY_UNLOCK_KEY);
        prepareLoginPanel();
        showStatus('Sessão encerrada com segurança.');
      });
      adminContent.insertBefore(button, adminContent.firstChild);
    };

    const prepareLoginPanel = () => {
      adminSection.classList.add('admin-section');
      adminSection.hidden = false;
      adminSection.removeAttribute('hidden');
      adminSection.style.display = 'block';
      loginPanel.hidden = false;
      loginPanel.removeAttribute('hidden');
      loginPanel.style.display = 'block';
      adminContent.hidden = true;
      adminContent.style.display = 'none';
      ensurePasswordLabel();
      const userInput = ensureUserField();
      if (!userInput.value) userInput.value = 'admin';
      passwordInput.placeholder = 'Digite a senha do Render';
      passwordInput.autocomplete = 'current-password';
      if (!loginPanel.querySelector('[data-admin-title]')) {
        const title = document.createElement('div');
        title.setAttribute('data-admin-title', 'true');
        title.innerHTML = '<p class="eyebrow">Administração segura</p><h2>Painel interno da Mística</h2><p class="privacy-note">Acesso validado pela API oficial da Mística Presentes. A senha não fica salva no site.</p>';
        loginPanel.insertBefore(title, loginForm);
      }
      setTimeout(() => adminSection.scrollIntoView({ behavior: 'smooth', block: 'start' }), 80);
    };

    const unlockAdmin = () => {
      adminSection.hidden = false;
      adminSection.removeAttribute('hidden');
      adminSection.style.display = 'block';
      loginPanel.hidden = true;
      loginPanel.style.display = 'none';
      adminContent.hidden = false;
      adminContent.removeAttribute('hidden');
      adminContent.style.display = 'block';
      ensureLogoutButton();
      showStatus('Admin liberado pela API.', true);
      setTimeout(() => adminSection.scrollIntoView({ behavior: 'smooth', block: 'start' }), 80);
    };

    const closeAdminUnlessRoute = () => {
      if (window.location.hash === ADMIN_HASH || window.location.hash === LEGACY_HASH) return;
      adminSection.hidden = true;
      adminSection.style.display = 'none';
    };

    const syncRoute = () => {
      if (window.location.hash === LEGACY_HASH) {
        window.location.hash = ADMIN_HASH;
        return;
      }
      if (window.location.hash === ADMIN_HASH) {
        if (getSession()) unlockAdmin();
        else prepareLoginPanel();
      } else {
        closeAdminUnlessRoute();
      }
    };

    const loginWithApi = async () => {
      const user = (document.getElementById('adminUser')?.value || '').trim();
      const pass = passwordInput.value.trim();
      if (!user || !pass) {
        showStatus('Informe login e senha.');
        return;
      }

      showStatus('Validando acesso na API oficial...', true);

      try {
        const response = await fetch(`${API_BASE}/api/auth/login`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ login: user, senha: pass }),
        });

        const payload = await response.json().catch(() => ({}));
        if (!response.ok || payload.status !== 'ok') {
          throw new Error(payload.detail || 'Login ou senha incorretos.');
        }
        if (payload.usuario?.perfil !== 'adm' || payload.permissoes?.admin !== true) {
          throw new Error('Este usuário não possui permissão administrativa.');
        }

        saveSession(payload);
        passwordInput.value = '';
        unlockAdmin();
      } catch (error) {
        localStorage.removeItem(SESSION_KEY);
        localStorage.removeItem(LEGACY_UNLOCK_KEY);
        showStatus(`Acesso negado: ${error.message || 'não foi possível validar na API.'}`);
      }
    };

    loginForm.addEventListener('submit', (event) => {
      if (window.location.hash !== ADMIN_HASH) return;
      event.preventDefault();
      event.stopPropagation();
      event.stopImmediatePropagation();
      loginWithApi();
    }, true);

    window.addEventListener('hashchange', syncRoute);
    syncRoute();
  });
})();