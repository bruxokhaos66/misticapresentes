(() => {
  const STORAGE_KEY = "misticaAmbientEnabled";
  let userClicked = false;

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

  forceOff();
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", forceOff, { once: true });
  window.addEventListener("load", () => {
    forceOff();
    setTimeout(forceOff, 250);
    setTimeout(forceOff, 900);
    setTimeout(forceOff, 1800);
  });
})();
