(() => {
  const ADMIN_HASH = '#adminbruxo';
  const LEGACY_HASH = '#admin';
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
      input.placeholder = 'bruxo';
      input.required = true;
      label.appendChild(input);
      loginForm.insertBefore(label, loginForm.firstElementChild || passwordInput);
      return input;
    };

    const prepareOldStylePanel = () => {
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
      ensureUserField();
      passwordInput.placeholder = 'Digite a senha';
      passwordInput.autocomplete = 'current-password';
      if (!loginPanel.querySelector('[data-admin-title]')) {
        const title = document.createElement('div');
        title.setAttribute('data-admin-title', 'true');
        title.innerHTML = '<p class="eyebrow">Administração</p><h2>Painel interno da Mística</h2><p class="privacy-note">Área interna para produtos, vendas, estoque, fornecedores, backup e música do site.</p>';
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
      localStorage.setItem('misticaAdminUnlocked', '1');
      showStatus('Admin liberado.', true);
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
        if (localStorage.getItem('misticaAdminUnlocked') === '1') unlockAdmin();
        else prepareOldStylePanel();
      } else {
        closeAdminUnlessRoute();
      }
    };

    loginForm.addEventListener('submit', (event) => {
      if (window.location.hash !== ADMIN_HASH) return;
      event.preventDefault();
      event.stopPropagation();
      event.stopImmediatePropagation();
      const user = (document.getElementById('adminUser')?.value || '').trim().toLowerCase();
      const pass = passwordInput.value.trim();
      if (user === ADMIN_USER && pass === ADMIN_PASS) return unlockAdmin();
      showStatus('Login ou senha incorretos. Use o acesso administrativo correto.');
    }, true);

    window.addEventListener('hashchange', syncRoute);
    syncRoute();
  });
})();
