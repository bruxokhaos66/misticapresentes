(() => {
  const officialWhatsapp = "554999172137";
  const buildOfficialUrl = message => `https://wa.me/${officialWhatsapp}?text=${encodeURIComponent(message)}`;
  const modernIconVersion = "20260706-modern-icon-hardfix";
  const modernIcon = `assets/logo-mistica-modern.svg?v=${modernIconVersion}`;

  try {
    window.buildWhatsappUrl = buildOfficialUrl;
    if (typeof buildWhatsappUrl !== "undefined") buildWhatsappUrl = buildOfficialUrl;
  } catch {}

  const css = `
    .skip-link{position:absolute!important;left:16px!important;top:12px!important;z-index:9999!important;transform:translateY(-160%)!important;padding:12px 16px!important;border-radius:999px!important;background:#f0c56a!important;color:#08070d!important;font-weight:900!important;text-decoration:none!important;box-shadow:0 12px 32px rgba(0,0,0,.32)!important;}
    .skip-link:focus{transform:translateY(0)!important;}
    a:focus-visible,button:focus-visible,input:focus-visible,textarea:focus-visible,select:focus-visible{outline:3px solid #f0c56a!important;outline-offset:4px!important;box-shadow:0 0 0 6px rgba(240,197,106,.18)!important;}
    .brand-logo-modern{display:block!important;width:58px!important;height:58px!important;object-fit:contain!important;border-radius:999px!important;filter:drop-shadow(0 12px 26px rgba(240,197,106,.18))!important;}
    .footer-mark .brand-logo-modern{width:48px!important;height:48px!important;}
    .highlight-strip{display:flex!important;align-items:center!important;justify-content:center!important;flex-wrap:wrap!important;gap:12px!important;min-height:auto!important;padding:16px!important;border:1px solid rgba(240,197,106,.22)!important;border-radius:22px!important;background:linear-gradient(135deg,rgba(8,8,13,.96),rgba(35,16,53,.50),rgba(49,67,38,.36))!important;box-shadow:0 24px 70px rgba(0,0,0,.24)!important;overflow:hidden!important;}
    .highlight-strip span{display:inline-flex!important;align-items:center!important;justify-content:center!important;min-width:140px!important;padding:12px 18px!important;border-radius:999px!important;border:1px solid rgba(240,197,106,.28)!important;background:rgba(255,255,255,.08)!important;color:#fff6dc!important;font-weight:900!important;white-space:nowrap!important;backdrop-filter:blur(10px)!important;}
    .products-section .section-title h2{font-size:clamp(2.1rem,4.2vw,4.8rem)!important;line-height:1.06!important;max-width:980px!important;margin-left:auto!important;margin-right:auto!important;text-align:center!important;}
    .products-section .section-title p{max-width:760px!important;margin-left:auto!important;margin-right:auto!important;text-align:center!important;}
    .isis-panel-image .isis-human-img{display:block!important;width:min(100%,430px)!important;max-height:620px!important;object-fit:contain!important;margin:0 auto 18px!important;filter:drop-shadow(0 28px 55px rgba(0,0,0,.45))!important;opacity:1!important;visibility:visible!important;}
    .hero-card-isis{position:relative!important;min-height:560px!important;border-radius:34px!important;overflow:hidden!important;background:radial-gradient(circle at 50% 34%,rgba(240,197,106,.20),transparent 34%),linear-gradient(145deg,rgba(12,9,18,.84),rgba(20,31,15,.34))!important;}
    .hero-card-isis::before{background:radial-gradient(circle at 50% 34%,rgba(240,197,106,.18),transparent 28%),radial-gradient(circle at 60% 70%,rgba(126,63,242,.14),transparent 34%)!important;}
    .hero-card-isis .isis-hero-fallback{position:absolute!important;inset:28px!important;z-index:20!important;display:grid!important;place-items:center!important;text-align:center!important;border:1px solid rgba(240,197,106,.24)!important;border-radius:28px!important;background:radial-gradient(circle at center,rgba(240,197,106,.20),transparent 42%),linear-gradient(180deg,rgba(7,6,11,.10),rgba(7,6,11,.72))!important;pointer-events:none!important;}
    .hero-card-isis .isis-hero-fallback strong{font-family:Cinzel,serif!important;font-size:clamp(3.4rem,6vw,6.4rem)!important;color:#f0c56a!important;text-shadow:0 0 32px rgba(240,197,106,.26)!important;}
    .hero-card-isis .isis-hero-fallback span{display:block!important;margin-top:10px!important;color:#eadfcf!important;letter-spacing:.14em!important;text-transform:uppercase!important;font-weight:800!important;}
    .hero-card-isis .floating-card{z-index:25!important;}
    @media(max-width:560px){.highlight-strip{justify-content:flex-start!important;}.highlight-strip span{width:100%!important;min-width:auto!important;}.isis-panel-image .isis-human-img{max-height:430px!important;}.brand-logo-modern{width:46px!important;height:46px!important;}}
    @media(prefers-reduced-motion:reduce){*,*::before,*::after{animation-duration:.01ms!important;animation-iteration-count:1!important;scroll-behavior:auto!important;transition-duration:.01ms!important;}}
  `;

  const forceModernIcon = () => {
    document.querySelectorAll('link[rel~="icon"]').forEach(link => link.remove());
    const favicon = document.createElement("link");
    favicon.rel = "icon";
    favicon.type = "image/svg+xml";
    favicon.href = modernIcon;
    document.head.appendChild(favicon);

    document.querySelectorAll(".brand-mark, .footer-mark").forEach(mark => {
      const current = mark.querySelector("img");
      if (current && current.src.includes("logo-mistica-modern.svg")) return;
      mark.classList.remove("asset-failed");
      mark.innerHTML = `<img class="brand-logo-img brand-logo-modern" src="${modernIcon}" alt="Logo Mística Presentes" width="64" height="64" loading="eager" decoding="async">`;
    });
  };

  const ensureSkipLink = () => { if (document.querySelector(".skip-link")) return; const main = document.querySelector("main"); if (main && !main.id) main.id = "conteudo"; const skip = document.createElement("a"); skip.className = "skip-link"; skip.href = main ? `#${main.id}` : "#inicio"; skip.textContent = "Pular para o conteúdo"; document.body.prepend(skip); };

  const forceIsisImage = () => {
    const panel = document.querySelector(".isis-panel-image");
    if (!panel) return;
    const version = "20260706-isis-force";
    const sources = [`assets/isis-humana-xamanica.webp?v=${version}`, `./assets/isis-humana-xamanica.webp?v=${version}`, `/assets/isis-humana-xamanica.webp?v=${version}`];
    let attempt = 0;
    const render = src => {
      panel.classList.remove("asset-failed");
      panel.innerHTML = `<img class="isis-human-img" src="${src}" alt="Isis da Mística Presentes" width="720" height="900" loading="eager" decoding="async"><p>Isis, presença misteriosa e xamânica para guiar escolhas e atendimento da loja.</p>`;
      const img = panel.querySelector("img");
      img.onerror = () => { attempt += 1; if (sources[attempt]) render(sources[attempt]); };
    };
    render(sources[0]);
  };

  const improveImages = root => { root.querySelectorAll("img").forEach(img => { if (!img.hasAttribute("loading")) img.loading = img.closest(".hero-section") ? "eager" : "lazy"; if (!img.hasAttribute("decoding")) img.decoding = "async"; if (!img.alt && !img.getAttribute("aria-hidden")) img.alt = "Imagem da Mística Presentes"; }); };
  const improveButtons = () => { const menuButton = document.querySelector("[data-menu-toggle]"); const navLinks = document.querySelector("[data-nav-links]"); if (menuButton && navLinks) { if (!navLinks.id) navLinks.id = "menu-principal"; menuButton.setAttribute("aria-controls", navLinks.id); menuButton.setAttribute("aria-expanded", String(navLinks.classList.contains("is-open") || navLinks.classList.contains("open"))); menuButton.addEventListener("click", () => { setTimeout(() => menuButton.setAttribute("aria-expanded", String(navLinks.classList.contains("is-open") || navLinks.classList.contains("open"))), 0); }); } document.querySelectorAll("button:not([aria-label])").forEach(button => { const text = button.textContent.trim(); if (text) button.setAttribute("aria-label", text); }); };
  const improveLiveRegions = () => { ["cartTotal", "pixStatus", "publishWarning", "adminLoginStatus", "backupStatus"].forEach(id => { const el = document.getElementById(id); if (!el) return; el.setAttribute("aria-live", "polite"); el.setAttribute("role", "status"); }); };
  const improveLinks = () => { document.querySelectorAll("[data-whatsapp-link], .floating-whatsapp").forEach(link => { link.href = buildOfficialUrl("Olá, vim pelo site da Mística Presentes e gostaria de atendimento."); link.target = "_blank"; link.rel = "noopener"; if (!link.getAttribute("aria-label")) link.setAttribute("aria-label", "Chamar a Mística Presentes no WhatsApp"); }); document.querySelectorAll('a[target="_blank"]').forEach(link => { const rel = new Set((link.rel || "").split(/\s+/).filter(Boolean)); rel.add("noopener"); link.rel = Array.from(rel).join(" "); }); };

  const applyVisualFixes = () => {
    let style = document.getElementById("mistica-final-audit-fixes");
    if (!style) { style = document.createElement("style"); style.id = "mistica-final-audit-fixes"; document.head.appendChild(style); }
    style.textContent = css;
    ensureSkipLink(); improveLinks(); improveButtons(); improveLiveRegions(); improveImages(document); forceModernIcon(); forceIsisImage();
    setTimeout(forceModernIcon, 100); setTimeout(forceModernIcon, 800); setTimeout(forceModernIcon, 2500);
    setTimeout(forceIsisImage, 1000); setTimeout(forceIsisImage, 3000);
    document.querySelectorAll(".hero-card-isis").forEach(card => { if (!card.querySelector(".isis-hero-fallback")) { const fallback = document.createElement("div"); fallback.className = "isis-hero-fallback"; fallback.setAttribute("aria-hidden", "true"); fallback.innerHTML = "<div><strong>Isis</strong><span>Sua guia espiritual</span></div>"; card.prepend(fallback); } });
    const observer = new MutationObserver(records => { records.forEach(record => { record.addedNodes.forEach(node => { if (node.nodeType === Node.ELEMENT_NODE) { improveImages(node); forceModernIcon(); } }); }); });
    observer.observe(document.body, { childList: true, subtree: true });
  };

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", applyVisualFixes, { once: true }); else applyVisualFixes();
})();
