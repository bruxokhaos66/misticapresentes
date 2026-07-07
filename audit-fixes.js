(() => {
  if (window.__MISTICA_AUDIT_FIXES_LOADED__) return;
  window.__MISTICA_AUDIT_FIXES_LOADED__ = true;

  const officialWhatsapp = "554999172137";
  const buildOfficialUrl = message => `https://wa.me/${officialWhatsapp}?text=${encodeURIComponent(message)}`;

  const css = `
    .skip-link{position:absolute!important;left:16px!important;top:12px!important;z-index:9999!important;transform:translateY(-160%)!important;padding:12px 16px!important;border-radius:999px!important;background:#f0c56a!important;color:#08070d!important;font-weight:900!important;text-decoration:none!important;box-shadow:0 12px 32px rgba(0,0,0,.32)!important;}
    .skip-link:focus{transform:translateY(0)!important;}
    a:focus-visible,button:focus-visible,input:focus-visible,textarea:focus-visible,select:focus-visible{outline:3px solid #f0c56a!important;outline-offset:4px!important;box-shadow:0 0 0 6px rgba(240,197,106,.18)!important;}
    .brand-logo-modern{display:block!important;width:58px!important;height:58px!important;object-fit:contain!important;border-radius:999px!important;filter:drop-shadow(0 12px 26px rgba(240,197,106,.18))!important;}
    .footer-mark .brand-logo-modern{width:48px!important;height:48px!important;}
    @media(max-width:560px){.brand-logo-modern{width:46px!important;height:46px!important;}}
    @media(prefers-reduced-motion:reduce){*,*::before,*::after{animation-duration:.01ms!important;animation-iteration-count:1!important;scroll-behavior:auto!important;transition-duration:.01ms!important;}}
  `;

  try {
    window.buildWhatsappUrl = buildOfficialUrl;
    if (typeof buildWhatsappUrl !== "undefined") buildWhatsappUrl = buildOfficialUrl;
  } catch {}

  function ensureSkipLink() {
    if (document.querySelector(".skip-link")) return;
    const main = document.querySelector("main");
    if (main && !main.id) main.id = "conteudo";
    const skip = document.createElement("a");
    skip.className = "skip-link";
    skip.href = main ? `#${main.id}` : "#inicio";
    skip.textContent = "Pular para o conteúdo";
    document.body.prepend(skip);
  }

  function improveImages(root) {
    root.querySelectorAll("img").forEach(img => {
      if (!img.hasAttribute("loading")) img.loading = img.closest(".hero-section") ? "eager" : "lazy";
      if (!img.hasAttribute("decoding")) img.decoding = "async";
      if (!img.alt && !img.getAttribute("aria-hidden")) img.alt = "Imagem da Mística Presentes";
    });
  }

  function improveButtons() {
    const menuButton = document.querySelector("[data-menu-toggle]");
    const navLinks = document.querySelector("[data-nav-links]");
    if (menuButton && navLinks && !menuButton.dataset.auditReady) {
      menuButton.dataset.auditReady = "true";
      if (!navLinks.id) navLinks.id = "menu-principal";
      menuButton.setAttribute("aria-controls", navLinks.id);
      menuButton.setAttribute("aria-expanded", String(navLinks.classList.contains("is-open") || navLinks.classList.contains("open")));
      menuButton.addEventListener("click", () => {
        setTimeout(() => menuButton.setAttribute("aria-expanded", String(navLinks.classList.contains("is-open") || navLinks.classList.contains("open"))), 0);
      });
    }

    document.querySelectorAll("button:not([aria-label])").forEach(button => {
      const text = button.textContent.trim();
      if (text) button.setAttribute("aria-label", text);
    });
  }

  function improveLiveRegions() {
    ["cartTotal", "pixStatus", "publishWarning", "adminLoginStatus", "backupStatus"].forEach(id => {
      const el = document.getElementById(id);
      if (!el) return;
      el.setAttribute("aria-live", "polite");
      el.setAttribute("role", "status");
    });
  }

  function improveLinks() {
    document.querySelectorAll("[data-whatsapp-link], .floating-whatsapp").forEach(link => {
      link.href = buildOfficialUrl("Olá, vim pelo site da Mística Presentes e gostaria de atendimento.");
      link.target = "_blank";
      link.rel = "noopener";
      if (!link.getAttribute("aria-label")) link.setAttribute("aria-label", "Chamar a Mística Presentes no WhatsApp");
    });

    document.querySelectorAll('a[target="_blank"]').forEach(link => {
      const rel = new Set((link.rel || "").split(/\s+/).filter(Boolean));
      rel.add("noopener");
      link.rel = Array.from(rel).join(" ");
    });
  }

  function applyVisualFixes() {
    let style = document.getElementById("mistica-final-audit-fixes");
    if (!style) {
      style = document.createElement("style");
      style.id = "mistica-final-audit-fixes";
      document.head.appendChild(style);
    }
    style.textContent = css;
    ensureSkipLink();
    improveLinks();
    improveButtons();
    improveLiveRegions();
    improveImages(document);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", applyVisualFixes, { once: true });
  } else {
    applyVisualFixes();
  }
})();
