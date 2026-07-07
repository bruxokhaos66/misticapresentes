(() => {
  if (window.__MISTICA_RESTORE_VIDEO_LAYOUT_LOADED__) return;
  window.__MISTICA_RESTORE_VIDEO_LAYOUT_LOADED__ = true;

  function setText(selector, value) {
    const el = document.querySelector(selector);
    if (el) el.textContent = value;
  }

  function removeExtraHeroButton() {
    document.querySelectorAll('#inicio .hero-actions [data-scroll-categorias]').forEach(button => button.remove());
  }

  function restoreHeroFromVideo() {
    const hero = document.querySelector('#inicio.hero-section');
    if (!hero) return;
    hero.classList.add('legacy-premium-hero');
    setText('#inicio .hero-copy .eyebrow', 'Mística Presentes • atendimento espiritual e comercial em Pinhalzinho-SC');
    setText('#inicio .hero-copy h1', 'Presentes místicos fáceis de escolher, comprar e enviar pelo WhatsApp');
    setText('#inicio .hero-text', 'Cristais, incensos, velas, aromas, banhos e kits especiais organizados para o cliente entender rápido, escolher com segurança e finalizar o pedido em poucos cliques.');
    const trust = document.querySelectorAll('#inicio .trust-row span');
    if (trust.length >= 3) {
      trust[0].innerHTML = '<strong>Compra rápida</strong> escolha, coloque no carrinho e envie pelo WhatsApp.';
      trust[1].innerHTML = '<strong>Pix facilitado</strong> gere QR Code e copie a chave direto no pedido.';
      trust[2].innerHTML = '<strong>Atendimento local</strong> loja em Pinhalzinho-SC com retirada combinada.';
    }
    removeExtraHeroButton();
  }

  function restoreProductsFromVideo() {
    const section = document.querySelector('#produtos');
    if (!section) return;
    setText('#produtos .section-title .eyebrow', 'Catálogo');
    setText('#produtos .section-title h2', 'Escolha produtos por intenção, presente e energia');
    setText('#produtos .section-title p:not(.eyebrow)', 'Use a busca e os filtros para encontrar rápido incensos, cristais, velas, aromas, banhos e presentes com significado.');
  }

  function restoreCheckoutFromVideo() {
    setText('#checkout .form-panel:first-child .eyebrow', 'Carrinho');
    setText('#checkout .form-panel:first-child h2', 'Carrinho claro para finalizar o pedido');
    setText('#checkout .pix-panel h2', 'Pix com QR Code');
  }

  function cleanIsisPanel() {
    const section = document.querySelector('#isis');
    if (!section) return;
    document.body.classList.add('mistica-video-restore');

    const panel = section.querySelector('.isis-panel-image');
    if (panel) {
      panel.querySelectorAll('.isis-symbol').forEach(symbol => symbol.remove());
      let text = panel.querySelector('p');
      if (!text) {
        text = document.createElement('p');
        panel.appendChild(text);
      }
      text.textContent = 'Isis apresenta produtos xamânicos, aromas, banhos, velas e presentes com orientação clara para a escolha do cliente.';
      panel.dataset.videoRestored = 'true';
    }

    setText('#isis .isis-chat-panel .eyebrow', 'Isis a Bruxinha');
    setText('#isis .isis-chat-panel h2', 'Atendimento místico, comercial e inteligente');
    setText('#isis .isis-chat-panel .privacy-note', 'Peça sugestões de produtos, kits para presente, itens por intenção ou apoio para encontrar o que combina com cada momento.');
  }

  function apply() {
    document.body.classList.add('mistica-video-restore');
    restoreHeroFromVideo();
    restoreProductsFromVideo();
    restoreCheckoutFromVideo();
    cleanIsisPanel();
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
