(() => {
  // Fonte única da URL da API: site-config.js (window.misticaSiteConfig).
  // Evita hosts divergentes espalhados pelos scripts (antes esta página
  // apontava direto para o host do provedor de hospedagem).
  const COURSE_API_BASE = String(
    (window.misticaSiteConfig || {}).apiBaseUrl || "https://api.misticaesotericos.com.br"
  ).replace(/\/$/, "");

  const storeConfig = {
    whatsappNumber: (window.misticaSiteConfig && window.misticaSiteConfig.whatsappNumber) || "554999172137"
  };

  // Fallback de imagem via atributo data- em vez de onerror= inline (exigido
  // pela CSP do site, script-src sem 'unsafe-inline'). Cobre também
  // escola-incensos-catalog.js e escola-medicinas-floresta-catalog.js,
  // carregados nesta mesma página. "error" em <img> não borbulha: precisa
  // capture:true para um listener único no document capturar.
  document.addEventListener("error", event => {
    const img = event.target;
    if (!(img instanceof HTMLImageElement) || img.dataset.fallbackRemove === undefined) return;
    img.remove();
  }, true);

  const cursos = [
    {
      slug: "xamanismo-introducao",
      titulo: "Xamanismo: Introdução",
      icone: "🌿",
      tipo: "gratuito",
      preco: 0,
      tags: ["Xamanismo", "Iniciante"],
      resumo: "Fundamentos do xamanismo: história, práticas, símbolos e como essa sabedoria ancestral se conecta com o dia a dia.",
      capa: "assets/escola/xamanismo/xamanismo-introducao.webp",
      // Este curso usa a plataforma de estudo (LMS) em escola-curso.html: as
      // partes introdutórias abrem direto, sem login/cadastro/matrícula.
      lms: true
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

  // Exposição somente-leitura do catálogo real para a Isis 2.0 — Escola
  // (isis2/school-knowledge.js, Fase 2). Congelamento profundo (array,
  // cada curso, e cada array/objeto aninhado como "tags") para que nenhum
  // script consumidor possa alterar o catálogo em memória, nem por essa
  // via nem escrevendo num campo aninhado; a única fonte que grava aqui
  // continua sendo este arquivo. Sem isso, o School Knowledge teria que
  // reimplementar/duplicar esta lista (proibido pela auditoria: "nunca
  // criar dados fictícios em produção").
  function deepFreeze(value) {
    if (value === null || typeof value !== "object" || Object.isFrozen(value)) return value;
    Object.values(value).forEach(deepFreeze);
    return Object.freeze(value);
  }
  window.MISTICA_ESCOLA_CURSOS = deepFreeze(cursos.map(curso => ({ ...curso })));

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
    // o navegador nunca monta o payload sozinho. O cadastro (nome/e-mail)
    // identifica o comprador; a senha só é criada depois, pelo link enviado
    // quando o pagamento é confirmado.
    const { ok, body } = await apiJson("/api/checkout/cursos", {
      method: "POST",
      body: JSON.stringify({ slug, ...cadastro }),
    });
    if (!ok || !body.pix_copia_cola) {
      throw new Error(body.detail || body.message || "Não foi possível gerar o Pix para este curso agora.");
    }
    return body;
  }

  async function definirSenhaAluno(token, senha) {
    const { ok, body } = await apiJson("/api/alunos/definir-senha", {
      method: "POST",
      body: JSON.stringify({ token, senha }),
    });
    if (!ok) throw new Error(body.detail || "Não foi possível criar sua senha. O link pode ter expirado.");
    alunoAtual = { nome: body.nome, email: body.email, cursos: [] };
    alunoCarregado = false;
    resetIsis2SchoolIdentity();
    await carregarAlunoAtual();
    return alunoAtual;
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
    resetIsis2SchoolIdentity();
    await carregarAlunoAtual();
    return alunoAtual;
  }

  async function logoutAluno() {
    await apiJson("/api/alunos/logout", { method: "POST" });
    alunoAtual = null;
    alunoCarregado = true;
    resetIsis2SchoolIdentity();
  }

  // Login/logout troca a sessão do navegador (cookie), mas a Isis 2.0 —
  // Escola (isis2/student-context.js) guarda em memória, por página, se o
  // aluno está autenticado (StudentContext.me()) e sinais de conversa
  // (ContextMemory school) — sem isso, trocar de conta na mesma aba sem
  // recarregar a página deixaria esse cache local desatualizado. Todo
  // dado real (cursos, progresso) continua sempre vindo fresco da API a
  // cada consulta, então isso nunca foi uma falha de autorização — mas
  // limpa mesmo assim, por clareza e para não misturar contexto de
  // conversa entre contas diferentes na mesma aba.
  function resetIsis2SchoolIdentity() {
    try {
      window.Isis2?.StudentContext?.resetCache?.();
      window.Isis2?.ContextMemory?.resetSchool?.();
    } catch {
      /* Isis 2.0 pode não estar carregada (flag desligada) — nunca quebra login/logout */
    }
  }

  function normalizeUrl(url) {
    const value = text(url).trim();
    if (!value) return "";
    if (value.startsWith("http")) return value;
    if (value.startsWith("/")) return `${COURSE_API_BASE}${value}`;
    return value;
  }

  function escapeHtml(value) {
    return String(value ?? "").replace(/[&<>"']/g, ch => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[ch]));
  }

  function materiaisHtml(materiais) {
    if (!materiais.length) {
      return `<div class="escola-materials-empty">Conteúdo em preparação. Assim que as aulas forem publicadas elas aparecem aqui automaticamente.</div>`;
    }
    return materiais.map(item => {
      const url = normalizeUrl(item.url);
      return url
        ? `<a class="escola-material-item" href="${url}" target="_blank" rel="noopener">📘 ${escapeHtml(item.titulo)}</a>`
        : `<div class="escola-material-item">📘 ${escapeHtml(item.titulo)}</div>`;
    }).join("");
  }

  async function fetchProgresso(slug) {
    const { ok, body } = await apiJson(`/api/cursos/${encodeURIComponent(slug)}/progresso`);
    return ok ? body : null;
  }

  async function toggleMaterial(slug, materialId, concluido) {
    const { ok, body } = await apiJson(`/api/cursos/${encodeURIComponent(slug)}/progresso`, {
      method: "POST",
      body: JSON.stringify({ material_id: materialId, concluido }),
    });
    return ok ? body : null;
  }

  // Renderiza o conteúdo do curso com barra de progresso, marcação de aula
  // concluída, "continuar estudando" e certificado (retenção do aluno).
  function renderCursoComProgresso(curso, container, materiais, progresso) {
    const concluidos = new Set((progresso && progresso.materiais_concluidos) || []);
    const total = materiais.length;
    const feitos = materiais.filter(m => concluidos.has(m.id)).length;
    const pct = total ? Math.round((feitos / total) * 100) : 0;
    const completo = total > 0 && feitos >= total;

    const listaHtml = total
      ? materiais.map(item => {
          const url = normalizeUrl(item.url);
          const feito = concluidos.has(item.id);
          const link = url
            ? `<a class="escola-material-link" href="${url}" target="_blank" rel="noopener">📘 ${escapeHtml(item.titulo)}</a>`
            : `<span class="escola-material-link">📘 ${escapeHtml(item.titulo)}</span>`;
          return `<li class="escola-material-row${feito ? " is-done" : ""}">
            <label class="escola-material-check"><input type="checkbox" data-material-id="${item.id}" ${feito ? "checked" : ""}><span>Concluí</span></label>
            ${link}
          </li>`;
        }).join("")
      : `<li class="escola-materials-empty">Conteúdo em preparação. Assim que as aulas forem publicadas elas aparecem aqui.</li>`;

    container.innerHTML = `
      <div class="escola-progress" data-progress-box>
        <div class="escola-progress-head">
          <strong data-progress-label>${feitos}/${total} aulas concluídas</strong>
          <span data-progress-pct>${pct}%</span>
        </div>
        <div class="escola-progress-bar"><span data-progress-fill style="width:${pct}%"></span></div>
        <div class="escola-progress-actions">
          <button class="btn btn-ghost" type="button" data-continuar ${completo || !total ? "disabled" : ""}>Continuar estudando</button>
          <button class="btn" type="button" data-certificado ${completo ? "" : "disabled"}>${completo ? "Emitir certificado 🎓" : "Certificado ao concluir"}</button>
        </div>
      </div>
      <ul class="escola-material-list">${listaHtml}</ul>
    `;

    const fill = container.querySelector("[data-progress-fill]");
    const label = container.querySelector("[data-progress-label]");
    const pctEl = container.querySelector("[data-progress-pct]");
    const btnContinuar = container.querySelector("[data-continuar]");
    const btnCert = container.querySelector("[data-certificado]");

    function atualizar(resumo) {
      if (!resumo) return;
      const p = resumo.percentual ?? 0;
      if (fill) fill.style.width = `${p}%`;
      if (pctEl) pctEl.textContent = `${p}%`;
      if (label) label.textContent = `${resumo.concluidos}/${resumo.total} aulas concluídas`;
      if (btnCert) { btnCert.disabled = !resumo.completo; btnCert.textContent = resumo.completo ? "Emitir certificado 🎓" : "Certificado ao concluir"; }
      if (btnContinuar) btnContinuar.disabled = resumo.completo || !resumo.total;
    }

    container.querySelectorAll("[data-material-id]").forEach(chk => {
      chk.addEventListener("change", async () => {
        chk.disabled = true;
        const resumo = await toggleMaterial(curso.slug, Number(chk.dataset.materialId), chk.checked);
        chk.disabled = false;
        chk.closest(".escola-material-row")?.classList.toggle("is-done", chk.checked);
        if (resumo) atualizar(resumo);
      });
    });

    btnContinuar?.addEventListener("click", () => {
      const proximo = materiais.find(m => !concluidos.has(m.id) && normalizeUrl(m.url));
      if (proximo) window.open(normalizeUrl(proximo.url), "_blank", "noopener");
    });

    btnCert?.addEventListener("click", () => {
      window.open(`${COURSE_API_BASE}/api/cursos/${encodeURIComponent(curso.slug)}/certificado`, "_blank", "noopener");
    });
  }

  function loginFormHtml(curso) {
    return `
      <div class="escola-login-box" data-login-box>
        <p><strong>Já comprou este curso?</strong> Entre com o e-mail e a senha que você criou no link de acesso enviado pelo WhatsApp após a confirmação do pagamento.</p>
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
      if (!ok) { container.innerHTML = `<div class="escola-materials-empty">Não foi possível carregar o conteúdo agora. Tente novamente em instantes.</div>`; return; }
      // Aluno logado num curso gratuito também ganha progresso/certificado.
      const aluno = await carregarAlunoAtual();
      if (aluno) {
        const progresso = await fetchProgresso(curso.slug);
        renderCursoComProgresso(curso, container, body, progresso);
      } else {
        container.innerHTML = materiaisHtml(body);
      }
      return;
    }

    const aluno = await carregarAlunoAtual();
    if (aluno && aluno.cursos && aluno.cursos.includes(curso.slug)) {
      const { ok, body } = await apiJson(`/api/cursos/${encodeURIComponent(curso.slug)}/conteudo`);
      if (!ok) { container.innerHTML = `<div class="escola-materials-empty">Não foi possível carregar o conteúdo agora. Tente novamente em instantes.</div>`; return; }
      const progresso = await fetchProgresso(curso.slug);
      renderCursoComProgresso(curso, container, body, progresso);
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
          <p class="escola-cadastro-eyebrow">Identificação da compra</p>
          <input type="text" placeholder="Seu nome completo" data-cadastro-nome required autocomplete="name">
          <input type="email" placeholder="Seu e-mail (será seu login)" data-cadastro-email required autocomplete="email">
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
        <p class="escola-purchase-status">Após a confirmação do pagamento, você recebe pelo WhatsApp um link para criar sua senha e acessar o curso nesta página.</p>
      </div>`;
  }

  function coverHtml(curso) {
    if (!curso.capa) return "";
    const alt = `Capa do curso ${escapeHtml(curso.titulo)}`;
    return `<img class="escola-card-cover" src="${escapeHtml(curso.capa)}" alt="${alt}" width="1200" height="630" loading="lazy" data-fallback-remove>`;
  }

  function cardHtml(curso) {
    const badge = curso.tipo === "gratuito" ? `<span class="escola-badge gratuito">Gratuito</span>` : `<span class="escola-badge pago">Pago</span>`;
    const price = curso.tipo === "gratuito"
      ? `<div class="escola-card-price"><strong>Grátis</strong><small>acesso imediato</small></div>`
      : `<div class="escola-card-price"><strong>${currency.format(curso.preco)}</strong><small>acesso após confirmação do Pix</small></div>`;
    if (curso.lms) {
      // Curso com plataforma de estudo própria (LMS): o botão leva direto para
      // escola-curso.html, sem exigir login para as partes introdutórias.
      return `
        <article class="escola-card" data-course-card="${curso.slug}">
          ${coverHtml(curso)}
          ${badge}
          <div class="escola-card-icon" aria-hidden="true">${curso.icone}</div>
          <div class="escola-card-tags">${curso.tags.map(tag => `<span>${tag}</span>`).join("")}</div>
          <h3>${curso.titulo}</h3>
          <p>${curso.resumo}</p>
          ${price}
          <div class="escola-card-actions">
            <a class="btn btn-full" href="escola-curso.html?curso=${encodeURIComponent(curso.slug)}">Começar agora</a>
          </div>
          <p class="escola-card-note" aria-hidden="true">&nbsp;</p>
        </article>`;
    }
    // O rodapé abaixo do botão fica reservado, mas vazio, em todos os
    // cards, para que os botões fiquem na mesma posição vertical.
    const primaryAction = curso.tipo === "gratuito"
      ? `<button class="btn btn-full" type="button" data-action="ver">Acessar curso grátis</button>`
      : `<button class="btn btn-full" type="button" data-action="comprar">Comprar acesso</button>`;
    return `
      <article class="escola-card" data-course-card="${curso.slug}">
        ${coverHtml(curso)}
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
        <p class="escola-card-note" aria-hidden="true">&nbsp;</p>
        <div class="escola-detail" data-detail hidden>
          <div class="escola-materials" data-materials></div>
          ${curso.tipo === "pago" ? purchasePanelHtml(curso) : ""}
        </div>
      </article>`;
  }

  function setupCard(article, curso) {
    if (curso.lms) return; // botão já é um link direto; nada para vincular aqui.
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
        if (!cadastroForm.reportValidity()) return;

        payloadBox.value = "";
        statusBox.textContent = "Gerando Pix com o servidor...";
        let pedido;
        try {
          pedido = await criarPedidoCurso(curso.slug, { nome, email });
        } catch (error) {
          statusBox.textContent = error.message || "Não foi possível gerar o Pix agora. Tente novamente ou fale pelo WhatsApp.";
          return;
        }
        payloadBox.value = pedido.pix_copia_cola;
        try {
          if (!window.QRCode) throw new Error("Biblioteca de QR Code não carregou.");
          await window.QRCode.toCanvas(qrCanvas, pedido.pix_copia_cola, { width: 180, margin: 2, errorCorrectionLevel: "M" });
          statusBox.textContent = `QR Code gerado para ${currency.format(curso.preco)}. Pague e envie o comprovante pelo WhatsApp: assim que confirmarmos, você recebe o link para criar sua senha.`;
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

  function criarSenhaBoxHtml() {
    return `
      <div class="escola-login-box" data-criar-senha-box>
        <p><strong>Pagamento confirmado!</strong> Crie sua senha de acesso para entrar na Escola Mística.</p>
        <form class="escola-login-form" data-criar-senha-form>
          <input type="password" placeholder="Crie uma senha (mín. 8 caracteres)" data-criar-senha-valor required minlength="8" autocomplete="new-password">
          <button class="btn" type="submit">Criar senha e entrar</button>
        </form>
        <p class="escola-login-status" data-criar-senha-status hidden></p>
      </div>`;
  }

  function setupCriarSenhaBox(token) {
    const grid = document.querySelector("[data-escola-grid]");
    if (!grid) return;
    grid.insertAdjacentHTML("beforebegin", criarSenhaBoxHtml());
    const box = document.querySelector("[data-criar-senha-box]");
    const form = box.querySelector("[data-criar-senha-form]");
    const status = box.querySelector("[data-criar-senha-status]");
    form.addEventListener("submit", async event => {
      event.preventDefault();
      const senha = form.querySelector("[data-criar-senha-valor]").value;
      status.hidden = false;
      status.textContent = "Criando sua senha...";
      try {
        await definirSenhaAluno(token, senha);
        status.textContent = "Senha criada! Você já está logado.";
        const url = new URL(window.location.href);
        url.searchParams.delete("acesso");
        window.history.replaceState({}, "", url);
        box.remove();
        await atualizarBarraConta();
      } catch (error) {
        status.textContent = error.message || "Não foi possível criar sua senha agora.";
      }
    });
  }

  async function atualizarBarraConta() {
    const box = document.querySelector("[data-escola-account]");
    if (!box) return;
    const aluno = await carregarAlunoAtual();
    box.innerHTML = aluno
      ? `<span>Olá, ${escapeHtml(aluno.nome)}</span><a class="btn btn-small" href="escola-curso.html">Ir para meus cursos</a><button class="btn btn-ghost btn-small" type="button" data-escola-logout>Sair</button>`
      : `<span>Já comprou algum curso? <a href="escola-curso.html">Entre em “Meus cursos”</a> ou abra o curso abaixo para acessar.</span>`;
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

    const tokenAcesso = new URL(window.location.href).searchParams.get("acesso");
    if (tokenAcesso) setupCriarSenhaBox(tokenAcesso);
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", renderCatalog, { once: true });
  else renderCatalog();
})();

// Menu mobile do cabeçalho (mesmo comportamento usado em app.js nas demais
// páginas): abre/fecha, sincroniza aria-expanded, fecha com Escape, clique
// fora ou ao escolher um link, e bloqueia o scroll de fundo enquanto aberto.
(() => {
  const toggleBtn = document.querySelector("[data-menu-toggle]");
  const navLinks = document.querySelector("[data-nav-links]");
  const header = document.querySelector(".site-header");
  if (!toggleBtn || !navLinks) return;
  const setMenuOpen = open => {
    navLinks.classList.toggle("open", open);
    header?.classList.toggle("menu-open", open);
    toggleBtn.setAttribute("aria-expanded", String(open));
    toggleBtn.setAttribute("aria-label", open ? "Fechar menu" : "Abrir menu");
    document.body.style.overflow = open ? "hidden" : "";
  };
  toggleBtn.addEventListener("click", () => setMenuOpen(!navLinks.classList.contains("open")));
  document.addEventListener("keydown", event => {
    if (event.key === "Escape" && navLinks.classList.contains("open")) setMenuOpen(false);
  });
  document.addEventListener("click", event => {
    if (!navLinks.classList.contains("open")) return;
    if (navLinks.contains(event.target) || toggleBtn.contains(event.target)) return;
    setMenuOpen(false);
  });
  navLinks.addEventListener("click", event => {
    if (event.target.closest("a")) setMenuOpen(false);
  });
})();
