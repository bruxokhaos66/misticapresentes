(() => {
  const TEMPLATES = [
    ["Atendimento inicial", "Ola! Seja bem-vindo(a) a Mistica Presentes. Como podemos te ajudar hoje?"],
    ["Pedido recebido", "Ola! Recebemos seu pedido na Mistica Presentes. Vamos conferir os itens e ja te retornamos com a confirmacao."],
    ["Aguardando pagamento", "Ola! Seu pedido esta reservado e aguardando confirmacao do pagamento."],
    ["Pagamento confirmado", "Pagamento confirmado! Gratidao pela preferencia. Vamos separar seu pedido com carinho."],
    ["Pronto para retirada", "Ola! Seu pedido da Mistica Presentes esta pronto para retirada. Gratidao pela preferencia."],
    ["Pos-venda", "Ola! Passando para agradecer sua compra na Mistica Presentes. Esperamos que seus produtos levem boas energias para o seu dia."],
    ["Recontato", "Ola! Passando para saber se voce precisa de incensos, velas, cristais, presentes ou algum produto especial da Mistica Presentes."]
  ];

  async function copyTemplate(index) {
    const text = TEMPLATES[index]?.[1] || "";
    try {
      await navigator.clipboard.writeText(text);
      alert("Mensagem copiada.");
    } catch {
      prompt("Copie a mensagem:", text);
    }
  }

  function whatsappNumber() {
    const siteNumber = window.misticaSiteConfig?.whatsappNumber;
    const configNumber = typeof storeConfig !== "undefined" ? storeConfig.whatsappNumber : "";
    return String(siteNumber || configNumber || "554999172137").replace(/\D/g, "");
  }

  function sendTemplate(index) {
    const text = TEMPLATES[index]?.[1] || "";
    if (!text) return;
    window.open(`https://wa.me/${whatsappNumber()}?text=${encodeURIComponent(text)}`, "_blank", "noopener");
  }

  function renderTemplates() {
    const content = document.getElementById("messageTemplatesContent");
    if (!content) return;
    content.innerHTML = TEMPLATES.map((template, index) => `
      <div class="history-item">
        <strong>${template[0]}</strong>
        <span>${template[1]}</span>
        <div class="pedido-actions">
          <button class="btn btn-ghost" type="button" onclick="misticaMessageTemplates.copy(${index})">Copiar</button>
          <button class="btn btn-ghost" type="button" onclick="misticaMessageTemplates.whatsapp(${index})">WhatsApp</button>
        </div>
      </div>
    `).join("");
  }

  function mountTemplates() {
    const admin = document.getElementById("adminContent");
    if (!admin || document.getElementById("messageTemplatesPanel")) return;
    const panel = document.createElement("section");
    panel.id = "messageTemplatesPanel";
    panel.className = "form-panel admin-report-panel";
    panel.innerHTML = `
      <p class="eyebrow">Atendimento</p>
      <h2>Modelos de mensagens rapidas</h2>
      <p class="privacy-note">Mensagens prontas para copiar ou abrir no WhatsApp da loja.</p>
      <div id="messageTemplatesContent" class="history-list"></div>
    `;
    const followup = document.getElementById("customerFollowupPanel");
    if (followup?.nextSibling) admin.insertBefore(panel, followup.nextSibling);
    else admin.appendChild(panel);
    renderTemplates();
  }

  window.misticaMessageTemplates = {
    templates: TEMPLATES,
    render: renderTemplates,
    copy: copyTemplate,
    whatsapp: sendTemplate,
  };

  window.addEventListener("load", mountTemplates);
})();
