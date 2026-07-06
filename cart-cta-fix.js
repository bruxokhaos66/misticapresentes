(() => {
  const styleId = "misticaCartCtaStyle";
  const noteId = "cartPremiumCtaNote";

  function installStyle() {
    if (document.getElementById(styleId)) return;

    const style = document.createElement("style");
    style.id = styleId;
    style.textContent = `
      #checkout .form-panel:first-child {
        position: relative;
        overflow: hidden;
        border-color: rgba(240,197,106,.34) !important;
        box-shadow: 0 28px 82px rgba(0,0,0,.24), 0 0 0 1px rgba(240,197,106,.10) inset !important;
      }

      #checkout .form-panel:first-child::before {
        content: "";
        position: absolute;
        inset: 0;
        pointer-events: none;
        background:
          radial-gradient(circle at 16% 0, rgba(240,197,106,.15), transparent 34%),
          linear-gradient(135deg, rgba(255,248,230,.06), transparent 44%);
      }

      #checkout .form-panel:first-child > * {
        position: relative;
        z-index: 1;
      }

      .cart-premium-cta-note {
        display: grid;
        gap: 7px;
        margin: 12px 0 16px;
        border: 1px solid rgba(184,201,119,.24);
        border-radius: 22px;
        padding: 13px 14px;
        background: rgba(184,201,119,.075);
        color: #efe7d1;
        font-weight: 720;
      }

      .cart-premium-cta-note strong {
        color: #f0c56a;
        font-family: Cinzel, Georgia, serif;
        letter-spacing: .04em;
      }

      .cart-premium-cta-note span {
        color: #d8cbb6;
        font-size: .93rem;
        line-height: 1.45;
      }

      #checkout .cart-list {
        min-height: 74px;
      }

      #checkout .total-box {
        border: 1px solid rgba(240,197,106,.36) !important;
        border-radius: 24px !important;
        padding: 16px !important;
        background:
          radial-gradient(circle at 92% 20%, rgba(240,197,106,.18), transparent 32%),
          rgba(240,197,106,.08) !important;
      }

      #checkout .total-box span {
        color: #e8d8b4;
        font-weight: 900;
        letter-spacing: .10em;
        text-transform: uppercase;
      }

      #checkout .total-box strong {
        color: #fff3c4;
        text-shadow: 0 0 20px rgba(240,197,106,.20);
      }

      #checkout .checkout-actions {
        display: grid !important;
        grid-template-columns: 1fr 1fr;
        gap: 10px;
      }

      #checkout [data-generate-pix] {
        grid-column: 1 / -1;
        min-height: 54px;
        border: 1px solid rgba(240,197,106,.55) !important;
        background:
          linear-gradient(135deg, #f0c56a, #d8a846 62%, #fff0b2) !important;
        color: #171007 !important;
        box-shadow: 0 20px 54px rgba(240,197,106,.18) !important;
        font-size: 1rem;
        letter-spacing: .04em;
      }

      #checkout [data-send-sale-whatsapp] {
        border-color: rgba(184,201,119,.45) !important;
        color: #dfeab2 !important;
        background: rgba(184,201,119,.08) !important;
      }

      #checkout [data-clear-cart] {
        opacity: .82;
      }

      .cart-has-items #checkout [data-send-sale-whatsapp]::after {
        content: " ✓";
      }

      .cart-has-items #checkout [data-generate-pix]::after {
        content: " agora";
      }

      @media (max-width: 620px) {
        #checkout .checkout-actions {
          grid-template-columns: 1fr;
        }

        #checkout [data-generate-pix] {
          grid-column: auto;
        }
      }
    `;

    document.head.appendChild(style);
  }

  function cartHasItems() {
    const cart = document.getElementById("cartList");
    const total = document.getElementById("cartTotal")?.textContent || "";
    const emptyByTotal = /0,00|R\$\s*0/i.test(total);
    return Boolean(cart && cart.textContent.trim() && !emptyByTotal);
  }

  function mountNote() {
    const panel = document.querySelector("#checkout .form-panel:first-child");
    const cart = document.getElementById("cartList");
    if (!panel || !cart) return;

    let note = document.getElementById(noteId);
    if (!note) {
      note = document.createElement("div");
      note.id = noteId;
      note.className = "cart-premium-cta-note";
      cart.insertAdjacentElement("beforebegin", note);
    }

    if (cartHasItems()) {
      document.body.classList.add("cart-has-items");
      note.innerHTML = `
        <strong>Pedido quase pronto</strong>
        <span>Revise os itens, gere o Pix e envie o pedido pelo WhatsApp para a loja confirmar disponibilidade e retirada.</span>
      `;
    } else {
      document.body.classList.remove("cart-has-items");
      note.innerHTML = `
        <strong>Monte seu pedido</strong>
        <span>Adicione produtos ao carrinho para gerar Pix e enviar o pedido completo pelo WhatsApp.</span>
      `;
    }
  }

  function installObservers() {
    const cart = document.getElementById("cartList");
    const total = document.getElementById("cartTotal");

    if (cart && cart.dataset.cartCtaObserver !== "true") {
      cart.dataset.cartCtaObserver = "true";
      new MutationObserver(() => requestAnimationFrame(mountNote)).observe(cart, { childList: true, subtree: true, characterData: true });
    }

    if (total && total.dataset.cartCtaObserver !== "true") {
      total.dataset.cartCtaObserver = "true";
      new MutationObserver(() => requestAnimationFrame(mountNote)).observe(total, { childList: true, subtree: true, characterData: true });
    }
  }

  function apply() {
    installStyle();
    mountNote();
    installObservers();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", apply, { once: true });
  } else {
    apply();
  }

  window.addEventListener("load", () => {
    apply();
    setTimeout(apply, 700);
  });

  window.misticaCartCta = { apply: mountNote };
})();
