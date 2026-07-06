(() => {
  const version = "20260706-isis-final-separado";
  const finalPath = "assistente-isis-produtos-final.webp";
  const sources = [
    `assets/${finalPath}?v=${version}`,
    `./assets/${finalPath}?v=${version}`,
    `/assets/${finalPath}?v=${version}`
  ];

  function renderAssistantIsis() {
    const panel = document.querySelector(".isis-panel-image");
    if (!panel) return;

    const current = panel.querySelector("img");
    if (current && current.src.includes(finalPath)) {
      panel.classList.remove("asset-failed");
      return;
    }

    let attempt = 0;
    const render = src => {
      panel.classList.remove("asset-failed");
      panel.innerHTML = `<img class="isis-human-img isis-human-produtos" src="${src}" alt="Isis da Mística Presentes apresentando produtos" width="720" height="900" loading="eager" decoding="async"><p>Isis, presença misteriosa e xamânica para guiar escolhas, produtos e atendimento da loja.</p>`;
      const img = panel.querySelector("img");
      img.onerror = () => {
        attempt += 1;
        if (sources[attempt]) render(sources[attempt]);
      };
    };

    render(sources[0]);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", renderAssistantIsis, { once: true });
  } else {
    renderAssistantIsis();
  }

  window.addEventListener("load", () => {
    renderAssistantIsis();
    setTimeout(renderAssistantIsis, 600);
    setTimeout(renderAssistantIsis, 1600);
    setTimeout(renderAssistantIsis, 3600);
  });
})();
