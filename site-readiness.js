(() => {
  const cfg = window.misticaSiteConfig || {};
  const API_BASE = (cfg.apiBaseUrl || "https://api.misticaesotericos.com.br").replace(/\/$/, "");
  const OFFICIAL_WHATSAPP = "554999172137";
  let whatsappObserverInstalled = false;

  function make(tag, className, html) {
    const el = document.createElement(tag);
    if (className) el.className = className;
    if (html !== undefined) el.innerHTML = html;
    return el;
  }

  function fixWhatsapp() {
    try {
      if (window.storeConfig) window.storeConfig.whatsappNumber = OFFICIAL_WHATSAPP;
    } catch {}

    document.querySelectorAll("[data-whatsapp-link], .floating-whatsapp").forEach(link => {
      const msg = "Olá, vim pelo site da Mística Presentes e gostaria de atendimento.";
      link.href = `https://wa.me/${OFFICIAL_WHATSAPP}?text=${encodeURIComponent(msg)}`;
      link.target = "_blank";
      link.rel = "noopener";
    });
  }

  function installWhatsappObserver() {
    if (whatsappObserverInstalled || !document.body) return;
    whatsappObserverInstalled = true;

    const observer = new MutationObserver(mutations => {
      if (mutations.some(mutation => mutation.addedNodes.length > 0)) {
        requestAnimationFrame(fixWhatsapp);
      }
    });

    observer.observe(document.body, { childList: true, subtree: true });
    window.misticaWhatsappObserver = observer;
  }

  function mountHowToBuy() {
    if (document.getElementById("como-comprar")) return;
    const productsSection = document.getElementById("produtos");
    if (!productsSection) return;

    const section = make("section", "section how-to-buy-section", `
      <div class="container section-title centered">
        <p class="eyebrow">Como comprar</p>
        <h2>Pedido simples, rápido e seguro</h2>
        <p>Escolha seus produtos, envie o pedido pelo WhatsApp e combine pagamento, retirada ou entrega com a loja.</p>
      </div>
      <div class="container how-to-buy-grid">
        <article><span>1</span><strong>Escolha os produtos</strong><p>Navegue pelo catálogo, filtre por categoria e adicione ao carrinho.</p></article>
        <article><span>2</span><strong>Envie pelo WhatsApp</strong><p>O site monta a mensagem com itens, quantidade e total automaticamente.</p></article>
        <article><span>3</span><strong>Confirme o Pix</strong><p>Confira valor e recebedor antes de pagar. Envie o comprovante para agilizar.</p></article>
        <article><span>4</span><strong>Retire ou combine entrega</strong><p>A loja confirma disponibilidade, separa o pedido e orienta a retirada.</p></article>
      </div>
    `);
    section.id = "como-comprar";
    productsSection.parentNode.insertBefore(section, productsSection);
  }

  function mountApiHealthPanel() {
    const admin = document.getElementById("adminContent");
    if (!admin || document.getElementById("apiHealthPanel")) return;

    const panel = make("section", "form-panel api-health-panel", `
      <p class="eyebrow">API</p>
      <h2>Saúde da integração</h2>
      <p class="privacy-note">Verifica se o backend responde antes de depender de pedidos, estoque e login remoto.</p>
      <div id="apiHealthContent" class="history-list"><div class="history-item"><span>Aguardando teste...</span></div></div>
      <button class="btn btn-ghost btn-full" type="button" data-test-api-health>Testar API agora</button>
    `);
    admin.insertBefore(panel, admin.firstChild);
    testApiHealth();
  }

  async function testEndpoint(path) {
    const started = performance.now();
    const response = await fetch(`${API_BASE}${path}`, { cache: "no-store" });
    const ms = Math.round(performance.now() - started);
    return { path, ok: response.ok, status: response.status, ms };
  }

  async function testApiHealth() {
    const root = document.getElementById("apiHealthContent");
    if (!root) return;
    root.innerHTML = `<div class="history-item"><span>Testando API...</span></div>`;
    const checks = ["/api/status", "/api/produtos?limite=1", "/api/vendas?limite=1", "/api/clientes?limite=1"];
    const results = [];
    for (const path of checks) {
      try {
        results.push(await testEndpoint(path));
      } catch (error) {
        results.push({ path, ok: false, status: "offline", ms: 0, error: error.message });
      }
    }
    root.innerHTML = results.map(item => `
      <div class="history-item">
        <strong>${item.ok ? "Online" : "Falha"} • ${item.path}</strong>
        <span>Status: ${item.status}${item.ms ? ` • ${item.ms}ms` : ""}</span>
        ${item.error ? `<span>${item.error}</span>` : ""}
      </div>
    `).join("");
  }

  function disableDuplicateIsisLocalLayer() {
    const form = document.getElementById("isisForm");
    if (!form) return;
    form.dataset.localIsisDisabled = "true";
  }

  document.addEventListener("click", event => {
    if (event.target?.dataset?.testApiHealth !== undefined) testApiHealth();
  });

  window.addEventListener("load", () => {
    fixWhatsapp();
    installWhatsappObserver();
    mountHowToBuy();
    mountApiHealthPanel();
    disableDuplicateIsisLocalLayer();
  });

  window.misticaSiteReadiness = { fixWhatsapp, testApiHealth, mountHowToBuy, installWhatsappObserver };
})();
