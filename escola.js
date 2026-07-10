(() => {
  const COURSE_API_BASE = "https://misticapresentes-api.onrender.com";

  const storeConfig = {
    pixKey: "07353652969",
    merchantName: "FREDINEI JEAN BACH",
    merchantCity: "PINHALZINHO",
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

  function sanitizePixText(value, maxLength) {
    return text(value).normalize("NFD").replace(/[\u0300-\u036f]/g, "").replace(/[^a-zA-Z0-9 .@+\-_]/g, "").toUpperCase().slice(0, maxLength);
  }

  function emv(id, value) {
    const cleanValue = text(value);
    if (cleanValue.length > 99) throw new Error(`Campo Pix ${id} excedeu 99 caracteres.`);
    return `${id}${String(cleanValue.length).padStart(2, "0")}${cleanValue}`;
  }

  function crc16(payload) {
    let crc = 0xffff;
    for (let i = 0; i < payload.length; i++) {
      crc ^= payload.charCodeAt(i) << 8;
      for (let bit = 0; bit < 8; bit++) {
        crc = (crc & 0x8000) ? (crc << 1) ^ 0x1021 : crc << 1;
        crc &= 0xffff;
      }
    }
    return crc.toString(16).toUpperCase().padStart(4, "0");
  }

  function buildPixPayload({ key, name, city, amount, txid }) {
    const merchantAccount = emv("26", emv("00", "br.gov.bcb.pix") + emv("01", text(key).trim()));
    const withoutCrc = emv("00", "01") + merchantAccount + emv("52", "0000") + emv("53", "986") +
      emv("54", amount.toFixed(2)) + emv("58", "BR") +
      emv("59", sanitizePixText(name, 25) || "MISTICA PRESENTES") +
      emv("60", sanitizePixText(city, 15) || "PINHALZINHO") +
      emv("62", emv("05", sanitizePixText(txid, 25) || "ESCOLA")) + "6304";
    return withoutCrc + crc16(withoutCrc);
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
            <p><strong>Recebedor:</strong> ${storeConfig.merchantName}</p>
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
        const txid = `ESCOLA${Date.now().toString().slice(-9)}`;
        let payload = "";
        try {
          payload = buildPixPayload({ key: storeConfig.pixKey, name: storeConfig.merchantName, city: storeConfig.merchantCity, amount: curso.preco, txid });
        } catch (error) {
          statusBox.textContent = `Erro ao montar Pix: ${error.message}`;
          return;
        }
        payloadBox.value = payload;
        try {
          if (!window.QRCode) throw new Error("Biblioteca de QR Code não carregou.");
          await window.QRCode.toCanvas(qrCanvas, payload, { width: 180, margin: 2, errorCorrectionLevel: "M" });
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
