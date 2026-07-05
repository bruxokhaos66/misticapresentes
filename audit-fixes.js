(() => {
  const officialWhatsapp = "554999172137";
  const buildOfficialUrl = message => `https://wa.me/${officialWhatsapp}?text=${encodeURIComponent(message)}`;

  try {
    window.buildWhatsappUrl = buildOfficialUrl;
    if (typeof buildWhatsappUrl !== "undefined") buildWhatsappUrl = buildOfficialUrl;
  } catch {}

  const updateLinks = () => {
    document.querySelectorAll("[data-whatsapp-link], .floating-whatsapp").forEach(link => {
      link.href = buildOfficialUrl("Olá, vim pelo site da Mística Presentes e gostaria de atendimento.");
      link.target = "_blank";
      link.rel = "noopener";
    });
  };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", updateLinks, { once: true });
  } else {
    updateLinks();
  }
})();
