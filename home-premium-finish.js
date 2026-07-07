(() => {
  if (window.__MISTICA_HOME_PREMIUM_FINISH_LOADED__) return;
  window.__MISTICA_HOME_PREMIUM_FINISH_LOADED__ = true;

  if (document.getElementById("mistica-home-premium-finish-style")) return;
  const style = document.createElement("style");
  style.id = "mistica-home-premium-finish-style";
  style.textContent = `
    .hero-section {
      position: relative;
      overflow: hidden;
      background:
        radial-gradient(circle at 18% 18%, rgba(240,197,106,.16), transparent 28rem),
        radial-gradient(circle at 84% 20%, rgba(184,201,119,.12), transparent 26rem),
        radial-gradient(circle at 50% 100%, rgba(98,57,138,.12), transparent 34rem),
        linear-gradient(180deg, rgba(8,7,13,.96), rgba(3,3,5,.98));
    }
    .hero-section::before {
      content: "";
      position: absolute;
      inset: 0;
      pointer-events: none;
      background-image:
        radial-gradient(circle at 20% 30%, rgba(240,197,106,.20) 0 1px, transparent 2px),
        radial-gradient(circle at 70% 18%, rgba(184,201,119,.22) 0 1px, transparent 2px),
        radial-gradient(circle at 82% 62%, rgba(240,197,106,.16) 0 1px, transparent 2px);
      background-size: 190px 190px, 230px 230px, 270px 270px;
      opacity: .48;
    }
    .hero-grid, .section .container, .footer .container { position: relative; z-index: 1; }
    .hero-copy h1 {
      letter-spacing: -.035em;
      text-shadow: 0 18px 55px rgba(0,0,0,.38);
    }
    .hero-text { color: #efe1c5; font-weight: 600; }
    .mystic-logo-card,
    .category-grid article,
    .confidence-grid article,
    .product-card,
    .form-panel,
    .contact-card {
      backdrop-filter: blur(10px);
      box-shadow: 0 24px 78px rgba(0,0,0,.24);
    }
    .category-grid article,
    .confidence-grid article {
      transition: transform .22s ease, border-color .22s ease, box-shadow .22s ease;
    }
    .category-grid article:hover,
    .confidence-grid article:hover {
      transform: translateY(-3px);
      border-color: rgba(240,197,106,.34);
      box-shadow: 0 28px 86px rgba(240,197,106,.10), 0 24px 74px rgba(0,0,0,.30);
    }
    .product-card {
      transition: transform .22s ease, border-color .22s ease, box-shadow .22s ease;
    }
    .product-card:hover {
      transform: translateY(-4px);
      border-color: rgba(240,197,106,.38);
      box-shadow: 0 30px 92px rgba(240,197,106,.10), 0 26px 80px rgba(0,0,0,.34);
    }
    .btn {
      box-shadow: 0 18px 44px rgba(240,197,106,.13);
    }
    .btn:hover {
      transform: translateY(-1px);
    }
    .top-ribbon {
      background: linear-gradient(90deg, rgba(8,7,13,.98), rgba(39,31,20,.94), rgba(8,7,13,.98));
      border-bottom: 1px solid rgba(240,197,106,.18);
    }
    .site-header {
      border-bottom: 1px solid rgba(240,197,106,.14);
      backdrop-filter: blur(14px);
    }
    @media (prefers-reduced-motion: reduce) {
      .category-grid article,
      .confidence-grid article,
      .product-card,
      .btn { transition: none !important; }
      .category-grid article:hover,
      .confidence-grid article:hover,
      .product-card:hover,
      .btn:hover { transform: none !important; }
    }
  `;
  document.head.appendChild(style);
})();
