(() => {
  const officialWhatsapp = "554999172137";
  const buildOfficialUrl = message => `https://wa.me/${officialWhatsapp}?text=${encodeURIComponent(message)}`;

  try {
    window.buildWhatsappUrl = buildOfficialUrl;
    if (typeof buildWhatsappUrl !== "undefined") buildWhatsappUrl = buildOfficialUrl;
  } catch {}

  const css = `
    .highlight-strip{
      display:flex!important;
      align-items:center!important;
      justify-content:center!important;
      flex-wrap:wrap!important;
      gap:12px!important;
      min-height:auto!important;
      padding:16px!important;
      border:1px solid rgba(240,197,106,.22)!important;
      border-radius:22px!important;
      background:linear-gradient(135deg,rgba(8,8,13,.96),rgba(35,16,53,.50),rgba(49,67,38,.36))!important;
      background-image:linear-gradient(135deg,rgba(8,8,13,.96),rgba(35,16,53,.50),rgba(49,67,38,.36))!important;
      box-shadow:0 24px 70px rgba(0,0,0,.24)!important;
      overflow:hidden!important;
    }
    .highlight-strip span{
      display:inline-flex!important;
      align-items:center!important;
      justify-content:center!important;
      min-width:140px!important;
      padding:12px 18px!important;
      border-radius:999px!important;
      border:1px solid rgba(240,197,106,.28)!important;
      background:rgba(255,255,255,.08)!important;
      color:#fff6dc!important;
      font-weight:900!important;
      white-space:nowrap!important;
      backdrop-filter:blur(10px)!important;
    }
    .products-section .section-title h2{
      font-size:clamp(2.1rem,4.2vw,4.8rem)!important;
      line-height:1.06!important;
      max-width:980px!important;
      margin-left:auto!important;
      margin-right:auto!important;
      text-align:center!important;
    }
    .products-section .section-title p{
      max-width:760px!important;
      margin-left:auto!important;
      margin-right:auto!important;
      text-align:center!important;
    }
    .hero-card-isis{
      position:relative!important;
      min-height:560px!important;
      border-radius:34px!important;
      overflow:hidden!important;
      background:radial-gradient(circle at 50% 34%,rgba(240,197,106,.20),transparent 34%),linear-gradient(145deg,rgba(12,9,18,.84),rgba(20,31,15,.34))!important;
    }
    .hero-card-isis::before{
      background:radial-gradient(circle at 50% 34%,rgba(240,197,106,.18),transparent 28%),radial-gradient(circle at 60% 70%,rgba(126,63,242,.14),transparent 34%)!important;
    }
    .hero-card-isis .isis-hero-fallback{
      position:absolute!important;
      inset:28px!important;
      z-index:20!important;
      display:grid!important;
      place-items:center!important;
      text-align:center!important;
      border:1px solid rgba(240,197,106,.24)!important;
      border-radius:28px!important;
      background:radial-gradient(circle at center,rgba(240,197,106,.20),transparent 42%),linear-gradient(180deg,rgba(7,6,11,.10),rgba(7,6,11,.72))!important;
      pointer-events:none!important;
    }
    .hero-card-isis .isis-hero-fallback strong{
      font-family:Cinzel,serif!important;
      font-size:clamp(3.4rem,6vw,6.4rem)!important;
      color:#f0c56a!important;
      text-shadow:0 0 32px rgba(240,197,106,.26)!important;
    }
    .hero-card-isis .isis-hero-fallback span{
      display:block!important;
      margin-top:10px!important;
      color:#eadfcf!important;
      letter-spacing:.14em!important;
      text-transform:uppercase!important;
      font-weight:800!important;
    }
    .hero-card-isis .floating-card{z-index:25!important;}
    @media(max-width:560px){
      .highlight-strip{justify-content:flex-start!important;}
      .highlight-strip span{width:100%!important;min-width:auto!important;}
    }
  `;

  const applyVisualFixes = () => {
    let style = document.getElementById("mistica-final-audit-fixes");
    if (!style) {
      style = document.createElement("style");
      style.id = "mistica-final-audit-fixes";
      document.head.appendChild(style);
    }
    style.textContent = css;

    document.querySelectorAll("[data-whatsapp-link], .floating-whatsapp").forEach(link => {
      link.href = buildOfficialUrl("Olá, vim pelo site da Mística Presentes e gostaria de atendimento.");
      link.target = "_blank";
      link.rel = "noopener";
    });

    document.querySelectorAll(".hero-card-isis").forEach(card => {
      if (!card.querySelector(".isis-hero-fallback")) {
        const fallback = document.createElement("div");
        fallback.className = "isis-hero-fallback";
        fallback.setAttribute("aria-hidden", "true");
        fallback.innerHTML = "<div><strong>Isis</strong><span>Sua guia espiritual</span></div>";
        card.prepend(fallback);
      }
    });
  };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", applyVisualFixes, { once: true });
  } else {
    applyVisualFixes();
  }
})();
