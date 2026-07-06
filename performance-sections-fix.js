(() => {
  const styleId = "misticaPerformanceSectionsStyle";

  function installStyle() {
    if (document.getElementById(styleId)) return;

    const style = document.createElement("style");
    style.id = styleId;
    style.textContent = `
      @supports (content-visibility: auto) {
        main > section.section:not(.hero-section) {
          content-visibility: auto;
          contain-intrinsic-size: 1px 720px;
        }

        main > section.products-section,
        main > section.checkout-section,
        main > section.isis-section {
          contain-intrinsic-size: 1px 940px;
        }

        main > section.admin-section,
        main > section.internal-section {
          contain-intrinsic-size: 1px 1180px;
        }
      }
    `;

    document.head.appendChild(style);
  }

  function apply() {
    installStyle();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", apply, { once: true });
  } else {
    apply();
  }

  window.misticaPerformanceSections = { apply };
})();
