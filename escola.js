(() => {
  const COURSE_API_BASE = "https://misticapresentes-api.onrender.com";

  const storeConfig = {
    whatsappNumber: (window.misticaSiteConfig && window.misticaSiteConfig.whatsappNumber) || "554999172137"
  };

  const cursos = [
    {
      slug: "xamanismo-introducao",
      titulo: "Xamanismo: Introdução",
      icone: "🌿",
      tipo: "gratuito",
      preco: 0,
      tags: ["Xamanismo", "Iniciante"],
      resumo: "Fundamentos do xamanismo: história, práticas, símbolos e como essa sabedoria ancestral se conecta com o dia a dia."
    },
    {
      slug: "rape-uso-tradicao",
      titulo: "Rapé: Uso e Tradição",
      icone: "🍃",
      tipo: "pago",
      preco: 97,
      tags: ["Rapé", "Ritual"],
      resumo: "A origem indígena do rapé, seus usos tradicionais, cuidados, contraindicações e como recebê-lo com respeito."
    },
    {
      slug: "ayahuasca-fundamentos",
      titulo: "Ayahuasca: Fundamentos",
      icone: "🌀",
      tipo: "pago",
      preco: 127,
      tags: ["Ayahuasca", "Ritual"],
      resumo: "História, preparo tradicional, contexto ritualístico e cuidados essenciais para compreender a ayahuasca."
    },
    {
      slug: "origem-universo-dias-atuais",
      titulo: "Origem do Universo até os Dias Atuais",
      icone: "✨",
      tipo: "pago",
      preco: 147,
      tags: ["Cosmologia", "História"],
      resumo: "Uma jornada pela origem do universo, a formação da vida e da consciência humana até os dias atuais."
    }
  ];

  const currency = new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" });
  let materiaisCache = null;

  function buildWhatsappUrl(message) {
    return `https://wa.me/${storeConfig.whatsappNumber}?text=${encodeURIComponent(message)}`;
  }

  function text(value) { return String(value ?? ""); }

  async function criarPedidoCurso(slug) {
    // O Pix (chave, nome, cidade e pre\u00e7o) \u00e9 gerado s\u00f3 no servidor a partir do
    // cat\u00e1logo autoritativo de cursos pagos (ver backend/course_routes.py);
    // o navegador nunca monta o payload sozinho.
    const response = await fetch(`${COURSE_API_BASE}/api/checkout/cursos`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ slug }),
    });
    const body = await response.json().catch(() => ({}));
    if (!response.ok || !body.pix_copia_cola) {
      throw new Error(body.detail || body.message || "N\u00e3o foi poss\u00edvel gerar o Pix para este curso agora.");
    }
    return body;
  }

  async function fetchMateriais() {
    if (materiaisCache) return materiaisCache;
    try {
      const response = await fetch(`${COURSE_API_BASE}/api/cursos`);
      if (!response.ok) throw new Error("Falha ao carregar materiais.");
      materiaisCache = await response.json();
    } catch {
      materiaisCache = [];
    }
    return materiaisCache;
  }

  function normalizeUrl(url) {
    const value = text(url).trim();
    if (!value) return "";
    if (value.startsWith("http")) return value;
    if (value.startsWith("/")) return `${COURSE_API_BASE}${value}`;
    return value;
  }

  async function renderMateriais(curso, container) {
    const materiais = (await fetchMateriais()).filter(item => item.categoria === curso.slug);
    if (!materiais.length) {
      container.innerHTML = `<div class="escola-materials-empty">Conteúdo em preparação. Assim que as aulas forem publicadas elas aparecem aqui automaticamente.</div>`;
      return;
    }
    container.innerHTML = materiais.map(item => {
      const url = normalizeUrl(item.url);
      return url
        ? `<a class="escola-material-item" href="${url}" target="_blank" rel="noopener">📘 ${item.titulo}</a>`
        : `<div class="escola-material-item">📘 ${item.titulo}</div>`;
    }).join("");
  }

  function purchasePanelHtml(curso) {
    return `
      <div class="escola-purchase" data-purchase-panel hidden>
        <div class="warning-box"><strong>Antes de pagar:</strong> confira no banco se o valor e o recebedor estão corretos.</div>
        <div class="escola-qr-wrap">
          <canvas width="180" height="180" data-purchase-qr aria-label="QR Code Pix do curso"></canvas>
          <div>
            <p><strong>Valor:</strong> ${currency.format(curso.preco)}</p>
            <p class="escola-purchase-status" data-purchase-status>Gere o Pix para liberar o acesso ao curso.</p>
          </div>
        </div>
        <textarea readonly data-purchase-payload placeholder="Pix copia e cola aparecerá aqui"></textarea>
        <div class="escola-card-actions">
          <button class="btn" type="button" data-purchase-generate>Gerar Pix de ${currency.format(curso.preco)}</button>
          <button class="btn btn-ghost" type="button" data-purchase-copy>Copiar Pix copia e cola</button>
          <button class="btn btn-ghost" type="button" data-purchase-whatsapp>Enviar comprovante pelo WhatsApp</button>
        </div>
        <p class="escola-purchase-status">Após a confirmação do pagamento, nossa equipe libera o acesso completo ao curso pelo WhatsApp.</p>
      </div>`;
  }

  function cardHtml(curso) {
    const badge = curso.tipo === "gratuito" ? `<span class="escola-badge gratuito">Grátis</span>` : `<span class="escola-badge pago">Pago</span>`;
    const price = curso.tipo === "gratuito"
      ? `<div class="escola-card-price"><strong>Grátis</strong><small>acesso imediato</small></div>`
      : `<div class="escola-card-price"><strong>${currency.format(curso.preco)}</strong><small>acesso após confirmação do Pix</small></div>`;
    const primaryAction = curso.tipo === "gratuito"
      ? `<button class="btn btn-full" type="button" data-action="ver">Acessar curso grátis</button>`
      : `<button class="btn btn-full" type="button" data-action="comprar">Comprar acesso</button>`;
    return `
      <article class="escola-card" data-course-card="${curso.slug}">
        ${badge}
        <div class="escola-card-icon" aria-hidden="true">${curso.icone}</div>
        <div class="escola-card-tags">${curso.tags.map(tag => `<span>${tag}</span>`).join("")}</div>
        <h3>${curso.titulo}</h3>
        <p>${curso.resumo}</p>
        ${price}
        <div class="escola-card-actions">
          ${primaryAction}
          <button class="btn btn-ghost escola-card-toggle" type="button" data-action="toggle">Ver conteúdo do curso</button>
        </div>
        <div class="escola-detail" data-detail hidden>
          <div class="escola-materials" data-materials></div>
          ${curso.tipo === "pago" ? purchasePanelHtml(curso) : ""}
        </div>
      </article>`;
  }

  function setupCard(article, curso) {
    const detail = article.querySelector("[data-detail]");
    const materialsBox = article.querySelector("[data-materials]");
    let materiaisLoaded = false;

    async function openDetail() {
      detail.hidden = false;
      if (!materiaisLoaded) {
        materiaisLoaded = true;
        await renderMateriais(curso, materialsBox);
      }
    }

    article.querySelector('[data-action="toggle"]')?.addEventListener("click", () => {
      detail.hidden = !detail.hidden;
      if (!detail.hidden) openDetail();
    });

    article.querySelector('[data-action="ver"]')?.addEventListener("click", () => {
      detail.hidden = false;
      openDetail();
      article.scrollIntoView({ behavior: "smooth", block: "start" });
    });

    const buyButton = article.querySelector('[data-action="comprar"]');
    const purchasePanel = article.querySelector("[data-purchase-panel]");
    if (buyButton && purchasePanel) {
      buyButton.addEventListener("click", () => {
        detail.hidden = false;
        openDetail();
        purchasePanel.hidden = false;
        article.scrollIntoView({ behavior: "smooth", block: "start" });
      });

      const qrCanvas = purchasePanel.querySelector("[data-purchase-qr]");
      const payloadBox = purchasePanel.querySelector("[data-purchase-payload]");
      const statusBox = purchasePanel.querySelector("[data-purchase-status]");

      purchasePanel.querySelector("[data-purchase-generate]")?.addEventListener("click", async () => {
        payloadBox.value = "";
        statusBox.textContent = "Gerando Pix com o servidor...";
        let pedido;
        try {
          pedido = await criarPedidoCurso(curso.slug);
        } catch (error) {
          statusBox.textContent = error.message || "Não foi possível gerar o Pix agora. Tente novamente ou fale pelo WhatsApp.";
          return;
        }
        payloadBox.value = pedido.pix_copia_cola;
        try {
          if (!window.QRCode) throw new Error("Biblioteca de QR Code não carregou.");
          await window.QRCode.toCanvas(qrCanvas, pedido.pix_copia_cola, { width: 180, margin: 2, errorCorrectionLevel: "M" });
          statusBox.textContent = `QR Code gerado para ${currency.format(curso.preco)}. Pague e envie o comprovante pelo WhatsApp para liberarmos o acesso.`;
        } catch {
          statusBox.textContent = "Pix copia e cola gerado. Não foi possível desenhar o QR Code agora.";
        }
      });

      purchasePanel.querySelector("[data-purchase-copy]")?.addEventListener("click", async () => {
        if (!payloadBox.value) { statusBox.textContent = "Gere o Pix antes de copiar."; return; }
        try {
          await navigator.clipboard.writeText(payloadBox.value);
          statusBox.textContent = "Pix copia e cola copiado.";
        } catch {
          payloadBox.select();
          document.execCommand("copy");
          statusBox.textContent = "Pix copia e cola selecionado para copiar.";
        }
      });

      purchasePanel.querySelector("[data-purchase-whatsapp]")?.addEventListener("click", () => {
        const message = `Olá! Fiz o Pix de ${currency.format(curso.preco)} para o curso "${curso.titulo}" da Escola Mística e gostaria de receber o acesso.`;
        window.open(buildWhatsappUrl(message), "_blank", "noopener");
      });
    }
  }

  function renderCatalog() {
    const grid = document.querySelector("[data-escola-grid]");
    if (!grid) return;
    grid.innerHTML = cursos.map(cardHtml).join("");
    grid.querySelectorAll("[data-course-card]").forEach(article => {
      const curso = cursos.find(item => item.slug === article.dataset.courseCard);
      if (curso) setupCard(article, curso);
    });
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", renderCatalog, { once: true });
  else renderCatalog();
})();
