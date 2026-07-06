(() => {
  function optimizeImage(img, index) {
    if (!img || img.dataset.performanceImageOptimized === "true") return;

    img.loading = index === 0 && img.closest(".hero-section") ? "eager" : "lazy";
    img.decoding = "async";
    img.fetchPriority = index === 0 && img.closest(".hero-section") ? "high" : "low";
    img.dataset.performanceImageOptimized = "true";
  }

  function optimizeImages(root = document) {
    const images = Array.from(root.querySelectorAll ? root.querySelectorAll("img") : []);
    images.forEach(optimizeImage);
  }

  function installObserver() {
    if (!document.body || document.body.dataset.performanceImagesObserver === "true") return;
    document.body.dataset.performanceImagesObserver = "true";

    const observer = new MutationObserver(mutations => {
      let shouldOptimize = false;
      mutations.forEach(mutation => {
        mutation.addedNodes.forEach(node => {
          if (node.nodeType !== 1) return;
          if (node.matches?.("img") || node.querySelector?.("img")) shouldOptimize = true;
        });
      });
      if (shouldOptimize) requestAnimationFrame(() => optimizeImages(document));
    });

    observer.observe(document.body, { childList: true, subtree: true });
    window.misticaPerformanceImagesObserver = observer;
  }

  function apply() {
    optimizeImages(document);
    installObserver();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", apply, { once: true });
  } else {
    apply();
  }

  window.addEventListener("load", () => {
    apply();
    setTimeout(apply, 900);
  });

  window.misticaPerformanceImages = { apply: optimizeImages };
})();
