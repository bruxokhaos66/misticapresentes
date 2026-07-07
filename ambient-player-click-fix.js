(() => {
  if (window.__MISTICA_AMBIENT_CLICK_FIX_LOADED__) return;
  window.__MISTICA_AMBIENT_CLICK_FIX_LOADED__ = true;

  function openOrClose(button) {
    window.setTimeout(() => {
      const active = button.getAttribute("aria-pressed") === "true" || button.textContent.includes("Desligar");
      if (active && window.misticaAmbientPlayerFix?.play) {
        window.misticaAmbientPlayerFix.play(true);
      }
      if (!active && window.misticaAmbientPlayerFix?.pause) {
        window.misticaAmbientPlayerFix.pause();
      }
      if (!active) {
        document.querySelectorAll("[data-unified-player-panel]").forEach(panel => { panel.dataset.open = "false"; });
        document.querySelectorAll("audio").forEach(audio => { try { audio.pause(); } catch {} });
      }
    }, 80);
  }

  document.addEventListener("click", event => {
    const button = event.target?.closest?.("[data-ambient-toggle]");
    if (!button) return;
    openOrClose(button);
  }, true);
})();
