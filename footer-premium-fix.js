(() => {
  if (window.__MISTICA_FOOTER_PREMIUM_FIX_LOADED__) return;
  window.__MISTICA_FOOTER_PREMIUM_FIX_LOADED__ = true;

  function loadScriptOnce(id, src) {
    if (document.getElementById(id)) return;
    const script = document.createElement("script");
    script.id = id;
    script.defer = true;
    script.src = src;
    document.head.appendChild(script);
  }

  function init() {
    if (!document.getElementById("mistica-footer-premium-style")) {
      const style = document.createElement("style");
      style.id = "mistica-footer-premium-style";
      style.textContent = `
        .contact-section { position: relative; overflow: hidden; border-top: 1px solid rgba(240,197,106,.18); border-bottom: 1px solid rgba(240,197,106,.16); background: radial-gradient(circle at 12% 18%, rgba(240,197,106,.14), transparent 30rem), radial-gradient(circle at 84% 78%, rgba(184,201,119,.12), transparent 28rem), linear-gradient(180deg, rgba(8,7,13,.94), rgba(3,3,5,.98)); }
        .contact-section .split { align-items: stretch; gap: clamp(18px, 3vw, 34px); }
        .contact-section .split > div:first-child, .contact-section .contact-card { border: 1px solid rgba(240,197,106,.24); border-radius: clamp(24px, 3vw, 36px); padding: clamp(24px, 4vw, 42px); background: radial-gradient(circle at 18% 12%, rgba(240,197,106,.14), transparent 34%), linear-gradient(145deg, rgba(255,248,230,.075), rgba(83,107,55,.075)), rgba(3,3,5,.32); box-shadow: 0 24px 80px rgba(0,0,0,.30); backdrop-filter: blur(10px); }
        .contact-section .contact-card { display: grid; gap: 14px; }
        .contact-section .contact-card p { margin: 0; padding: 12px 14px; border: 1px solid rgba(240,197,106,.16); border-radius: 18px; background: rgba(255,248,230,.045); color: #e5d8bf; font-weight: 750; }
        .footer { position: relative; overflow: hidden; padding: 28px 0 92px; border-top: 1px solid rgba(240,197,106,.20); background: radial-gradient(circle at 50% 0, rgba(240,197,106,.10), transparent 30rem), linear-gradient(180deg, rgba(8,7,13,.92), rgba(3,3,5,.98)); box-shadow: inset 0 1px 0 rgba(255,248,230,.06); }
        .footer::after { content: "☾"; position: absolute; right: clamp(18px, 6vw, 92px); bottom: -34px; color: rgba(240,197,106,.07); font-family: Cinzel, Georgia, serif; font-size: clamp(8rem, 18vw, 18rem); line-height: 1; pointer-events: none; }
        .footer-grid { position: relative; z-index: 1; display: block; }
        .footer-grid > div:first-child { width: min(1180px, 100%); border: 1px solid rgba(240,197,106,.22); border-radius: 999px; padding: 14px 18px; display: flex; flex-wrap: wrap; gap: 10px 16px; align-items: center; justify-content: space-between; background: rgba(255,248,230,.045); box-shadow: 0 18px 60px rgba(0,0,0,.20); backdrop-filter: blur(10px); }
      `;
      document.head.appendChild(style);
    }
    const contact = document.querySelector("#contato");
    if (contact) contact.dataset.singleContact = "true";
    const footer = document.querySelector(".footer");
    if (footer) footer.dataset.singleStoreFooter = "true";
    loadScriptOnce("commercialBadgesFixScript", "commercial-badges-fix.js?v=20260707-safe-badges");
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init, { once: true });
  else init();
})();
