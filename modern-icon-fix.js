(() => {
  const VERSION = "20260706-modern-icon-hardfix";
  const ICON = `assets/logo-mistica-modern.svg?v=${VERSION}`;

  function applyModernIcon() {
    document.querySelectorAll('link[rel~="icon"]').forEach(link => link.remove());
    const favicon = document.createElement("link");
    favicon.rel = "icon";
    favicon.type = "image/svg+xml";
    favicon.href = ICON;
    document.head.appendChild(favicon);

    document.querySelectorAll(".brand-mark, .footer-mark").forEach(mark => {
      const img = mark.querySelector("img");
      if (img && img.src.includes("logo-mistica-modern.svg")) return;
      mark.classList.remove("asset-failed");
      mark.innerHTML = `<img class="brand-logo-img brand-logo-modern" src="${ICON}" alt="Logo Mística Presentes" width="64" height="64" loading="eager" decoding="async">`;
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", applyModernIcon, { once: true });
  } else {
    applyModernIcon();
  }

  window.addEventListener("load", () => {
    applyModernIcon();
    setTimeout(applyModernIcon, 400);
    setTimeout(applyModernIcon, 1500);
  });
})();
