(() => {
  if (window.__MISTICA_SITE_FINAL_POLISH_LOADED__) return;
  window.__MISTICA_SITE_FINAL_POLISH_LOADED__ = true;

  function setText(selector, value) {
    const el = document.querySelector(selector);
    if (el) el.textContent = value;
  }

  function setTrustText(item, title, desc) {
    if (!item) return;
    let strong = item.querySelector('strong');
    if (!strong) {
      strong = document.createElement('strong');
      item.prepend(strong);
    }
    strong.textContent = title;
    Array.from(item.childNodes).forEach(node => {
      if (node !== strong) node.remove();
    });
    item.append(document.createTextNode(' ' + desc));
  }

  function cleanHero() {
    const hero = document.querySelector('#inicio.hero-section');
    if (!hero) return;
    hero.classList.add('legacy-premium-hero');
    setText('#inicio .hero-copy .eyebrow', 'Mística Presentes • atendimento espiritual e comercial em Pinhalzinho-SC');
    setText('#inicio .hero-copy h1', 'Presentes místicos fáceis de escolher, comprar e enviar pelo WhatsApp');
    setText('#inicio .hero-text', 'Cristais, incensos, velas, aromas, banhos e kits especiais organizados para o cliente entender rápido, escolher com segurança e finalizar o pedido em poucos cliques.');
    document.querySelectorAll('#inicio .hero-actions [data-scroll-categorias]').forEach(button => button.remove());
    const trust = document.querySelectorAll('#inicio .trust-row span');
    if (trust.length >= 3) {
      setTrustText(trust[0], 'Compra rápida', 'escolha, coloque no carrinho e envie pelo WhatsApp.');
      setTrustText(trust[1], 'Pix facilitado', 'gere QR Code e copie a chave direto no pedido.');
      setTrustText(trust[2], 'Atendimento local', 'loja em Pinhalzinho-SC com retirada combinada.');
    }
  }

  function cleanProducts() {
    setText('#produtos .section-title .eyebrow', 'Catálogo');
    setText('#produtos .section-title h2', 'Escolha produtos por intenção, presente e energia');
    setText('#produtos .section-title p:not(.eyebrow)', 'Use a busca e os filtros para encontrar rápido incensos, cristais, velas, aromas, banhos e presentes com significado.');
  }

  function cleanCheckout() {
    setText('#checkout .form-panel:first-child .eyebrow', 'Carrinho');
    setText('#checkout .form-panel:first-child h2', 'Carrinho claro para finalizar o pedido');
    setText('#checkout .pix-panel .eyebrow', 'Pagamento');
    setText('#checkout .pix-panel h2', 'Pix com QR Code');
  }

  function cleanIsis() {
    const section = document.querySelector('#isis');
    if (!section) return;
    const panel = section.querySelector('.isis-panel-image');
    if (panel) {
      panel.querySelectorAll('.isis-symbol').forEach(symbol => {
        symbol.setAttribute('aria-hidden', 'true');
        symbol.hidden = true;
        symbol.style.setProperty('display', 'none', 'important');
        symbol.style.setProperty('visibility', 'hidden', 'important');
        symbol.style.setProperty('opacity', '0', 'important');
      });
      let caption = panel.querySelector('p');
      if (!caption) {
        caption = document.createElement('p');
        panel.appendChild(caption);
      }
      caption.textContent = 'A Isis guia o cliente por produtos, intenções, presentes e sugestões rápidas para facilitar a compra.';
      panel.dataset.finalPolish = 'true';
    }
    setText('#isis .isis-chat-panel .eyebrow', 'Isis a Bruxinha');
    setText('#isis .isis-chat-panel h2', 'Atendimento místico, comercial e inteligente');
    setText('#isis .isis-chat-panel .privacy-note', 'Peça sugestões de produtos, kits para presente, itens por intenção ou apoio para encontrar o que combina com cada momento.');
  }

  function apply() {
    document.body.classList.add('mistica-final-polish');
    cleanHero();
    cleanProducts();
    cleanCheckout();
    cleanIsis();
  }

  function schedule() {
    apply();
    window.setTimeout(apply, 120);
    window.setTimeout(apply, 500);
    window.setTimeout(apply, 1200);
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', schedule, { once: true });
  else schedule();
})();
