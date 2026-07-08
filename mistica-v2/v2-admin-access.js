(() => {
  const ADMIN_HASH = '#adminbruxo';
  const ADMIN_USER = 'bruxo';
  const ADMIN_PASS = 'mistica2026';

  const ready = (fn) => document.readyState === 'loading' ? document.addEventListener('DOMContentLoaded', fn) : fn();

  ready(() => {
    const adminSection = document.getElementById('admin');
    const loginPanel = document.getElementById('adminLoginPanel');
    const adminContent = document.getElementById('adminContent');
    const loginForm = document.getElementById('adminLoginForm');
    const passwordInput = document.getElementById('adminPassword');
    const loginStatus = document.getElementById('adminLoginStatus');

    if (!adminSection || !loginPanel || !adminContent || !loginForm || !passwordInput) return;

    const showStatus = (message, ok = false) => {
      if (!loginStatus) return;
      loginStatus.hidden = false;
      loginStatus.textContent = message;
      loginStatus.className = ok ? 'warning-box' : 'warning-box warning-danger';
    };

    const ensureUserField = () => {
      if (document.getElementById('adminUser')) return document.getElementById('adminUser');
      const label = document.createElement('label');
      label.textContent = 'Login';
      const input = document.createElement('input');
      input.id = 'adminUser';
      input.name = 'adminUser';
      input.type = 'text';
      input.autocomplete = 'username';
      input.placeholder = 'bruxo';
      input.required = true;
      label.appendChild(input);
      loginForm.insertBefore(label, passwordInput.parentElement || passwordInput);
      return input;
    };

    const prepareLoginLabels = () => {
      if (!passwordInput.closest('label')) {
        const label = document.createElement('label');
        label.textContent = 'Senha';
        passwordInput.parentNode.insertBefore(label, passwordInput);
        label.appendChild(passwordInput);
      }
      passwordInput.placeholder = 'Digite a senha';
      passwordInput.autocomplete = 'current-password';
      ensureUserField();
    };

    const showAdminLogin = () => {
      adminSection.hidden = false;
      loginPanel.hidden = false;
      adminContent.hidden = true;
      prepareLoginLabels();
      setTimeout(() => adminSection.scrollIntoView({ behavior: 'smooth', block: 'start' }), 80);
    };

    const unlockAdmin = () => {
      adminSection.hidden = false;
      loginPanel.hidden = true;
      adminContent.hidden = false;
      localStorage.setItem('misticaAdminUnlocked', '1');
      showStatus('Admin liberado.', true);
    };

    const syncRoute = () => {
      if (window.location.hash === ADMIN_HASH) {
        if (localStorage.getItem('misticaAdminUnlocked') === '1') unlockAdmin();
        else showAdminLogin();
      } else if (window.location.hash === '#admin') {
        window.location.hash = ADMIN_HASH;
      }
    };

    loginForm.addEventListener('submit', (event) => {
      if (window.location.hash !== ADMIN_HASH) return;
      event.preventDefault();
      event.stopImmediatePropagation();
      const userInput = document.getElementById('adminUser');
      const user = (userInput?.value || '').trim().toLowerCase();
      const pass = passwordInput.value.trim();
      if (user === ADMIN_USER && pass === ADMIN_PASS) {
        unlockAdmin();
        return;
      }
      showStatus('Login ou senha incorretos. Use o acesso administrativo correto.');
    }, true);

    window.addEventListener('hashchange', syncRoute);
    syncRoute();
  });
})();
