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

  // Estado do aluno logado (nulo enquanto não carregado ou deslogado).
  let alunoAtual = null;
  let alunoCarregado = false;

  function buildWhatsappUrl(message) {
    return `https://wa.me/${storeConfig.whatsappNumber}?text=${encodeURIComponent(message)}`;
  }

  function text(value) { return String(value ?? ""); }

  async function apiJson(path, options = {}) {
    const response = await fetch(`${COURSE_API_BASE}${path}`, {
      credentials: "include",
      headers: { "Content-Type": "application/json", ...(options.headers || {}) },
      ...options,
    });
    const body = await response.json().catch(() => ({}));
    return { ok: response.ok, status: response.status, body };
  }

  async function criarPedidoCurso(slug, cadastro) {
    // O Pix (chave, nome, cidade e preço) é gerado só no servidor a partir do
    // catálogo autoritativo de cursos pagos (ver backend/course_routes.py);
    // o navegador nunca monta o payload sozinho. O cadastro (nome/e-mail/senha)
    // cria a conta do aluno, que ganha acesso ao curso quando o pagamento for
    // confirmado.
    const { ok, body } = await apiJson("/api/checkout/cursos", {
      method: "POST",
      body: JSON.stringify({ slug, ...cadastro }),
    });
    if (!ok || !body.pix_copia_cola) {
      throw new Error(body.detail || body.message || "Não foi possível gerar o Pix para este curso agora.");
    }
    return body;
  }

  async function carregarAlunoAtual() {
    if (alunoCarregado) return alunoAtual;
    alunoCarregado = true;
    const { ok, body } = await apiJson("/api/alunos/me");
    alunoAtual = ok ? body : null;
    return alunoAtual;
  }

  async function loginAluno(email, senha) {
    const { ok, body } = await apiJson("/api/alunos/login", {
      method: "POST",
      body: JSON.stringify({ email, senha }),
    });
    if (!ok) throw new Error(body.detail || "E-mail ou senha inválidos.");
    alunoAtual = { nome: body.nome, email: body.email, cursos: [] };
    alunoCarregado = false;
    await carregarAlunoAtual();
    return alunoAtual;
  }

  async function logoutAluno() {
    await apiJson("/api/alunos/logout", { method: "POST" });
    alunoAtual = null;
    alunoCarregado = true;
  }

  function normalizeUrl(url) {
    const value = text(url).trim();
    if (!value) return "";
    if (value.startsWith("http")) return value;
    if (value.startsWith("/")) return `${COURSE_API_BASE}${value}`;
    return value;
  }

  function materiaisHtml(materiais) {
    if (!materiais.length) {
      return `<div class="escola-materials-empty">Conteúdo em preparação. Assim que as aulas forem publicadas elas aparecem aqui automaticamente.</div>`;
    }
    return materiais.map(item => {
      const url = normalizeUrl(item.url);
      return url
        ? `<a class="escola-material-item" href="${url}" target="_blank" rel="noopener">📘 ${item.titulo}</a>`
        : `<div class="escola-material-item">📘 ${item.titulo}</div>`;
    }).join("");
  }

  function loginFormHtml(curso) {
    return `
      <div class="escola-login-box" data-login-box>
        <p><strong>Já comprou este curso?</strong> Entre com o e-mail e a senha cadastrados na compra para acessar os módulos, vídeos e artigos.</p>
        <form class="escola-login-form" data-login-form>
          <input type="email" placeholder="Seu e-mail" data-login-email required autocomplete="email">
          <input type="password" placeholder="Sua senha" data-login-senha required autocomplete="current-password">
          <button class="btn" type="submit">Entrar</button>
        </form>
        <p class="escola-login-status" data-login-status hidden></p>
      </div>`;
  }

  async function renderMateriaisArea(curso, container) {
    if (curso.tipo === "gratuito") {
      const { ok, body } = await apiJson(`/api/cursos/${encodeURIComponent(curso.slug)}/conteudo`);
      container.innerHTML = ok ? materiaisHtml(body) : `<div class="escola-materials-empty">Não foi possível carregar o conteúdo agora. Tente novamente em instantes.</div>`;
      return;
    }

    const aluno = await carregarAlunoAtual();
    if (aluno && aluno.cursos && aluno.cursos.includes(curso.slug)) {
      const { ok, body } = await apiJson(`/api/cursos/${encodeURIComponent(curso.slug)}/conteudo`);
      container.innerHTML = ok ? materiaisHtml(body) : `<div class="escola-materials-empty">Não foi possível carregar o conteúdo agora. Tente novamente em instantes.</div>`;
      return;
    }

    if (aluno) {
      container.innerHTML = `<div class="escola-materials-empty">Seu pagamento ainda está em análise. Assim que confirmarmos, o conteúdo aparece aqui automaticamente. Se já pagou, fale com a gente pelo WhatsApp.</div>`;
      return;
    }

    container.innerHTML = loginFormHtml(curso);
    setupLoginForm(container, curso, container.closest("[data-detail]"));
  }

  function setupLoginForm(container, curso, detail) {
    const form = container.querySelector("[data-login-form]");
    const status = container.querySelector("[data-login-status]");
    form?.addEventListener("submit", async event => {
      event.preventDefault();
      const email = form.querySelector("[data-login-email]").value.trim();
      const senha = form.querySelector("[data-login-senha]").value;
      status.hidden = false;
      status.textContent = "Entrando...";
      try {
        await loginAluno(email, senha);
        status.textContent = "Login realizado! Carregando conteúdo...";
        await renderMateriaisArea(curso, container);
        atualizarBarraConta();
      } catch (error) {
        status.textContent = error.message || "Não foi possível entrar. Confira e-mail e senha.";
      }
    });
  }

  function purchasePanelHtml(curso) {
    return `
      <div class="escola-purchase" data-purchase-panel hidden>
        <div class="warning-box"><strong>Antes de pagar:</strong> confira no banco se o valor e o recebedor estão corretos.</div>
        <form class="escola-cadastro-form" data-purchase-cadastro>
          <p class="escola-cadastro-eyebrow">Cadastro de acesso ao curso</p>
          <input type="text" placeholder="Seu nome completo" data-cadastro-nome required autocomplete="name">
          <input type="email" placeholder="Seu e-mail (será seu login)" data-cadastro-email required autocomplete="email">
          <input type="password" placeholder="Crie uma senha (mín. 8 caracteres)" data-cadastro-senha required minlength="8" autocomplete="new-password">
        </form>
        <div class="escola-qr-wrap">
          <canvas width="180" height="180" data-purchase-qr aria-label="QR Code Pix do curso"></canvas>
          <div>
            <p><strong>Valor:</strong> ${currency.format(curso.preco)}</p>
            <p class="escola-purchase-status" data-purchase-status>Preencha seus dados e gere o Pix para liberar o acesso ao curso.</p>
          </div>
        </div>
        <textarea readonly data-purchase-payload placeholder="Pix copia e cola aparecerá aqui"></textarea>
        <div class="escola-card-actions">
          <button class="btn" type="button" data-purchase-generate>Gerar Pix de ${currency.format(curso.preco)}</button>
          <button class="btn btn-ghost" type="button" data-purchase-copy>Copiar Pix copia e cola</button>
          <button class="btn btn-ghost" type="button" data-purchase-whatsapp>Enviar comprovante pelo WhatsApp</button>
        </div>
        <p class="escola-purchase-status">Após a confirmação do pagamento, seu login e senha cadastrados acima liberam automaticamente o acesso completo ao curso nesta página.</p>
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
        await renderMateriaisArea(curso, materialsBox);
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
      const cadastroForm = purchasePanel.querySelector("[data-purchase-cadastro]");

      purchasePanel.querySelector("[data-purchase-generate]")?.addEventListener("click", async () => {
        const nome = cadastroForm.querySelector("[data-cadastro-nome]").value.trim();
        const email = cadastroForm.querySelector("[data-cadastro-email]").value.trim();
        const senha = cadastroForm.querySelector("[data-cadastro-senha]").value;
        if (!cadastroForm.reportValidity()) return;

        payloadBox.value = "";
        statusBox.textContent = "Gerando Pix com o servidor...";
        let pedido;
        try {
          pedido = await criarPedidoCurso(curso.slug, { nome, email, senha });
        } catch (error) {
          statusBox.textContent = error.message || "Não foi possível gerar o Pix agora. Tente novamente ou fale pelo WhatsApp.";
          return;
        }
        payloadBox.value = pedido.pix_copia_cola;
        try {
          if (!window.QRCode) throw new Error("Biblioteca de QR Code não carregou.");
          await window.QRCode.toCanvas(qrCanvas, pedido.pix_copia_cola, { width: 180, margin: 2, errorCorrectionLevel: "M" });
          statusBox.textContent = `QR Code gerado para ${currency.format(curso.preco)}. Pague e envie o comprovante pelo WhatsApp para liberarmos o acesso. Depois, use o e-mail e a senha cadastrados para entrar.`;
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

  function accountBarHtml() {
    return `<div class="escola-account" data-escola-account></div>`;
  }

  async function atualizarBarraConta() {
    const box = document.querySelector("[data-escola-account]");
    if (!box) return;
    const aluno = await carregarAlunoAtual();
    box.innerHTML = aluno
      ? `<span>Olá, ${aluno.nome}</span><button class="btn btn-ghost btn-small" type="button" data-escola-logout>Sair</button>`
      : `<span>Já comprou algum curso? Faça login abrindo o curso e informando seu e-mail e senha.</span>`;
    box.querySelector("[data-escola-logout]")?.addEventListener("click", async () => {
      await logoutAluno();
      await atualizarBarraConta();
    });
  }

  function renderCatalog() {
    const grid = document.querySelector("[data-escola-grid]");
    if (!grid) return;
    grid.insertAdjacentHTML("beforebegin", accountBarHtml());
    grid.innerHTML = cursos.map(cardHtml).join("");
    grid.querySelectorAll("[data-course-card]").forEach(article => {
      const curso = cursos.find(item => item.slug === article.dataset.courseCard);
      if (curso) setupCard(article, curso);
    });
    atualizarBarraConta();
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", renderCatalog, { once: true });
  else renderCatalog();
})();
