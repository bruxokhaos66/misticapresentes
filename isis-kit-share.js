(() => {
  const cfg = window.misticaSiteConfig || {};
  const WHATSAPP = cfg.whatsappNumber || "554999172137";

  function money(value) {
    try { return currency.format(Number(value || 0)); } catch { return `R$ ${Number(value || 0).toFixed(2)}`; }
  }

  function montarTextoKit(kit) {
    const itens = kit.items.map(row => `• ${row.slot.label}: ${row.product.name} - ${money(row.product.price)}`).join("\n");
    return `Olá, vim pelo site da Mística Presentes.\n\nTenho interesse neste kit sugerido pela Isis:\n\n${kit.title}\n${itens}\n\nTotal sugerido: ${money(kit.total)}\n\nPode confirmar disponibilidade para mim?`;
  }

  function abrirWhatsApp(texto) {
    window.open(`https://wa.me/${WHATSAPP}?text=${encodeURIComponent(texto)}`, "_blank", "noopener");
  }

  function enviarKit(kitKey) {
    const lista = window.__isisLastProducts || window.products || [];
    const kit = window.misticaIsisCommerce?.buildKit?.(lista, kitKey);
    if (!kit) return alert("Não consegui montar este kit agora.");
    abrirWhatsApp(montarTextoKit(kit));
  }

  function instalarBotoes() {
    document.querySelectorAll("[data-isis-add-kit]").forEach(btn => {
      if (btn.dataset.shareReady === "1") return;
      btn.dataset.shareReady = "1";
      const kitKey = btn.dataset.isisAddKit;
      const share = document.createElement("button");
      share.className = "btn btn-ghost";
      share.type = "button";
      share.textContent = "Enviar kit no WhatsApp";
      share.dataset.isisShareKit = kitKey;
      btn.insertAdjacentElement("afterend", share);
    });
  }

  document.addEventListener("click", event => {
    const kitKey = event.target?.dataset?.isisShareKit;
    if (kitKey) enviarKit(kitKey);
  });

  window.addEventListener("load", () => {
    instalarBotoes();
    setInterval(instalarBotoes, 1200);
  });
})();
