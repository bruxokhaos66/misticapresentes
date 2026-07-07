(() => {
  const STORAGE_KEY = "misticaAmbientEnabled";
  let userClicked = false;

  function loadCss(id, href) {
    if (document.getElementById(id)) return;
    const link = document.createElement("link");
    link.id = id;
    link.rel = "stylesheet";
    link.href = href;
    document.head.appendChild(link);
  }

  function loadVisualCss() {
    loadCss("homePremiumFinishCss", "home-premium-finish.css?v=20260707-premium-css");
    loadCss("mobilePolishCss", "mobile-polish.css?v=20260707-mobile-polish");
    loadCss("heroLegacyPremiumCss", "hero-legacy-premium.css?v=20260707-hero-legacy");
    loadCss("ambientLegacyCompleteCss", "ambient-legacy-complete.css?v=20260707-ambient-complete");
  }

  function pauseAllAmbientAudio() {
    document.querySelectorAll("audio").forEach(audio => {
      try { audio.pause(); } catch {}
    });
  }

  function forceOff() {
    if (userClicked) return;
    try { localStorage.removeItem(STORAGE_KEY); } catch {}
    pauseAllAmbientAudio();
    document.querySelectorAll("[data-ambient-toggle]").forEach(button => {
      button.setAttribute("aria-pressed", "false");
      button.textContent = "Ativar ambiente xamânico";
    });
    document.querySelectorAll("[data-ambient-status], [data-unified-status]").forEach(status => {
      status.textContent = "Aguardando ativação.";
    });
    document.querySelectorAll("[data-unified-player-panel]").forEach(panel => {
      panel.dataset.open = "false";
    });
  }

  document.addEventListener("click", event => {
    if (event.target?.closest?.("[data-ambient-toggle], [data-unified-next], [data-unified-volume]")) {
      userClicked = true;
    }
  }, true);

  loadVisualCss();
  forceOff();
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", () => { loadVisualCss(); forceOff(); }, { once: true });
  window.addEventListener("load", () => {
    loadVisualCss();
    forceOff();
    setTimeout(forceOff, 250);
    setTimeout(forceOff, 900);
    setTimeout(forceOff, 1800);
  });
})();