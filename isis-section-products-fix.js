(() => {
  const version = "20260706-isis-png-final";
  const finalPath = "isis-humana-xamanica-03-produtos.png";
  const finalSrc = `assets/${finalPath}?v=${version}`;

  function ensureStyle() {
    if (document.getElementById("isis-section-products-lock-style")) return;
    const style = document.createElement("style");
    style.id = "isis-section-products-lock-style";
    style.textContent = `
      .isis-panel-image img:not([src*="${finalPath}"]) {
        opacity: 0 !important;
        visibility: hidden !important;
      }
      .isis-panel-image .isis-human-produtos {
        opacity: 1 !important;
        visibility: visible !important;
      }
    `;
    document.head.appendChild(style);
  }

  function lockAssistantIsis() {
    ensureStyle();
    const panel = document.querySelector(".isis-panel-image");
    if (!panel) return;

    panel.classList.remove("asset-failed");

    let img = panel.querySelector("img.isis-human-produtos") || panel.querySelector("img");
    if (!img) {
      img = document.createElement("img");
      panel.prepend(img);
    }

    img.className = "isis-human-img isis-human-produtos";
    img.alt = "Isis da Mística Presentes apresentando produtos";
    img.width = 720;
    img.height = 900;
    img.loading = "eager";
    img.decoding = "async";

    if (!img.getAttribute("src") || !img.src.includes(finalPath)) {
      img.src = finalSrc;
    }

    let text = panel.querySelector("p");
    if (!text) {
      text = document.createElement("p");
      panel.appendChild(text);
    }
    text.textContent = "Isis, presença misteriosa e xamânica para guiar escolhas, produtos e atendimento da loja.";
  }

  function startLock() {
    lockAssistantIsis();

    const panel = document.querySelector(".isis-panel-image");
    if (!panel || panel.dataset.isisProductsLocked === "true") return;
    panel.dataset.isisProductsLocked = "true";

    const observer = new MutationObserver(() => {
      const current = panel.querySelector("img");
      if (!current || !current.src.includes(finalPath)) {
        requestAnimationFrame(lockAssistantIsis);
      }
    });

    observer.observe(panel, {
      childList: true,
      subtree: true,
      attributes: true,
      attributeFilter: ["src", "class"]
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", startLock, { once: true });
  } else {
    startLock();
  }

  window.addEventListener("load", () => {
    startLock();
    setTimeout(startLock, 250);
    setTimeout(startLock, 900);
    setTimeout(startLock, 2000);
  });
})();
