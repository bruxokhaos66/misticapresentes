(() => {
  const STORAGE_KEY = "misticaAmbientEnabled";
  let userClicked = false;

  function loadPremiumCss() {
    if (document.getElementById("homePremiumFinishCss")) return;
    const link = document.createElement("link");
    link.id = "homePremiumFinishCss";
    link.rel = "stylesheet";
    link.href = "home-premium-finish.css?v=20260707-premium-css";
    document.head.appendChild(link);
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

  loadPremiumCss();
  forceOff();
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", () => { loadPremiumCss(); forceOff(); }, { once: true });
  window.addEventListener("load", () => {
    loadPremiumCss();
    forceOff();
    setTimeout(forceOff, 250);
    setTimeout(forceOff, 900);
    setTimeout(forceOff, 1800);
  });
})();