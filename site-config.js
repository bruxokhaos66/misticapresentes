window.misticaSiteConfig = {
  domain: "misticaesotericos.com.br",
  publicBaseUrl: "https://misticaesotericos.com.br",
  apiBaseUrl: "https://api.misticaesotericos.com.br",
  siteApiKey: "",
  serverMode: "production",
  usePublicDomainAccess: true,
  storageMode: "api_first",
  instagram: "@misticaprodutos",
  whatsappNumber: "554999172137",
  whatsappDisplay: "(49) 99917-2137",
  headerTitle: "Mística Presentes",
  headerSubtitle: "Incensos • Cristais • Velas Ritualísticas • Aromaterapia • Banhos de Ervas • Artigos Espiritualistas",
  promoText: "Encontre tudo para espiritualidade, bem-estar e energias positivas."
};

(() => {
  const css = `
    .top-ribbon{display:none!important}
    .site-header{position:sticky!important;top:0!important;z-index:90!important;background:rgba(7,6,11,.96)!important;border-bottom:1px solid rgba(240,197,106,.24)!important}
    .nav{min-height:96px!important;align-items:center!important;gap:20px!important}
    .brand{padding-left:0!important;gap:14px!important;flex:0 1 520px!important;min-width:0!important}
    .brand:before,.footer-grid>div:first-child:before{display:none!important}
    .brand img,.footer img{content:url('assets/mistica-logo-xamanico.webp?v=20260705q')!important;opacity:1!important;visibility:visible!important;width:64px!important;height:64px!important;object-fit:cover!important;border-radius:999px!important;border:1px solid rgba(240,197,106,.42)!important;box-shadow:0 0 0 4px rgba(240,197,106,.06),0 0 28px rgba(240,197,106,.16)!important}
    .brand-copy strong{max-width:360px!important;font-size:clamp(1.45rem,2.15vw,2.12rem)!important;letter-spacing:.05em!important;white-space:nowrap!important}
    .brand-copy small{color:#b7c86e!important;letter-spacing:.18em!important}
    .nav-links{justify-content:center!important;max-width:760px!important;margin-left:auto!important;padding:10px 16px!important;border:1px solid rgba(240,197,106,.28)!important;border-radius:999px!important;background:linear-gradient(135deg,rgba(11,16,10,.92),rgba(17,13,23,.92))!important;box-shadow:0 18px 45px rgba(0,0,0,.34),inset 0 1px 0 rgba(255,255,255,.05)!important}
    .brand-hero{min-height:auto!important;padding:clamp(54px,6vw,86px) 0 54px!important;overflow:hidden!important;background:linear-gradient(90deg,rgba(7,6,11,.97),rgba(7,6,11,.84) 42%,rgba(7,6,11,.54)),radial-gradient(circle at 18% 20%,rgba(240,197,106,.14),transparent 27%),radial-gradient(circle at 82% 70%,rgba(113,138,70,.16),transparent 32%)!important}
    .brand-hero:after{content:""!important;position:absolute!important;inset:0!important;background:radial-gradient(circle at 72% 28%,rgba(240,197,106,.16),transparent 24%),radial-gradient(circle at 90% 74%,rgba(126,63,242,.16),transparent 28%)!important;opacity:.65!important;pointer-events:none!important;mix-blend-mode:normal!important;z-index:0!important}
    .brand-hero .hero-grid{position:relative!important;z-index:2!important;grid-template-columns:minmax(0,.88fr) minmax(360px,1.02fr)!important;align-items:center!important;gap:clamp(26px,4vw,58px)!important}
    .brand-hero h1{max-width:580px!important;text-transform:uppercase!important;font-size:clamp(2.1rem,3.9vw,3.75rem)!important;line-height:1.06!important;letter-spacing:.035em!important;background:linear-gradient(180deg,#fff6dc 0%,#efc168 48%,#b8ca75 100%)!important;-webkit-background-clip:text!important;background-clip:text!important;color:transparent!important}
    .hero-text{max-width:540px!important;font-size:clamp(.98rem,1.18vw,1.1rem)!important;line-height:1.62!important;color:#f1e4d1!important}
    .hero-card-isis{position:relative!important;z-index:2!important;min-height:560px!important;padding:18px!important;display:grid!important;align-content:center!important;justify-items:center!important;border:1px solid rgba(240,197,106,.24)!important;background:radial-gradient(circle at 55% 22%,rgba(240,197,106,.20),transparent 34%),linear-gradient(145deg,rgba(12,9,18,.72),rgba(20,31,15,.30))!important;box-shadow:0 24px 70px rgba(0,0,0,.38)!important;overflow:hidden!important}
    .hero-card-isis:before,.hero-card-isis:after{display:none!important}
    .hero-card-isis>img{content:url('assets/isis-humana-premium.webp?v=20260705q')!important;display:block!important;opacity:1!important;visibility:visible!important;width:100%!important;max-width:560px!important;max-height:620px!important;object-fit:contain!important;object-position:center!important;border-radius:28px!important;filter:drop-shadow(0 32px 70px rgba(0,0,0,.54))!important;z-index:2!important;position:relative!important}
    .hero-card-isis .floating-card{z-index:3!important;position:absolute!important;left:24px!important;right:24px!important;bottom:24px!important}
    @media(max-width:1180px){.brand-hero .hero-grid{grid-template-columns:1fr!important}.hero-card-isis{min-height:auto!important}.brand-copy strong{max-width:260px!important}.nav{min-height:92px!important}}
    @media(max-width:560px){.nav{min-height:76px!important}.brand img,.footer img{width:48px!important;height:48px!important}.brand-copy strong{font-size:1rem!important}.hero-copy h1{font-size:clamp(2rem,10.4vw,3.25rem)!important}.hero-card-isis>img{max-height:520px!important}.hero-card-isis .floating-card{position:static!important;margin-top:12px!important}}
  `;
  const apply = () => {
    let style = document.getElementById("isis-layout-hotfix");
    if (!style) {
      style = document.createElement("style");
      style.id = "isis-layout-hotfix";
      document.head.appendChild(style);
    }
    style.textContent = css;
  };
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", apply, { once: true });
  } else {
    apply();
  }
})();
