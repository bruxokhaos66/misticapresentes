(() => {
  "use strict";
  // Plataforma de estudo da Escola Mística (cursos progressivos).
  // Reutiliza a sessão de aluno e a API já existentes; toda regra de bloqueio,
  // progressão e nota é decidida pelo backend — aqui só refletimos o estado.
  const API = String((window.misticaSiteConfig || {}).apiBaseUrl || "https://api.misticaesotericos.com.br").replace(/\/$/, "");
  const shell = document.querySelector("[data-plataforma]");
  const params = new URL(window.location.href).searchParams;
  const slug = params.get("curso");

  const esc = v => String(v ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

  // Sanitiza o HTML de conteúdo de aula (autorado no admin) antes de exibir.
  // Usa um <template> inerte (scripts não executam, imagens não carregam na
  // análise) e remove tags perigosas, handlers on* e URLs javascript:. Preserva
  // texto rico (p, strong, listas, links/imagens seguros) sem dependências.
  const TAGS_PROIBIDAS = ["SCRIPT", "IFRAME", "OBJECT", "EMBED", "STYLE", "LINK", "META", "FORM", "BASE", "SVG"];
  function sanitizeHtml(html) {
    const tpl = document.createElement("template");
    tpl.innerHTML = String(html ?? "");
    tpl.content.querySelectorAll("*").forEach(el => {
      if (TAGS_PROIBIDAS.includes(el.tagName)) { el.remove(); return; }
      [...el.attributes].forEach(attr => {
        const nome = attr.name.toLowerCase();
        const valor = attr.value.replace(/\s+/g, "").toLowerCase();
        if (nome.startsWith("on")) el.removeAttribute(attr.name);
        else if ((nome === "href" || nome === "src" || nome === "xlink:href") && (valor.startsWith("javascript:") || valor.startsWith("data:text/html"))) el.removeAttribute(attr.name);
      });
    });
    return tpl.innerHTML;
  }

  async function api(path, options = {}) {
    const res = await fetch(`${API}${path}`, {
      credentials: "include",
      headers: { "Content-Type": "application/json", ...(options.headers || {}) },
      ...options,
    });
    const body = await res.json().catch(() => ({}));
    return { ok: res.ok, status: res.status, body };
  }

  // ---- Progresso efêmero do visitante anônimo ----------------------------
  // Nunca é enviado ao backend nem persistido em localStorage: existe só em
  // sessionStorage (some ao fechar a aba) para dar feedback visual de leitura
  // sem criar matrícula, conta ou progresso permanente no servidor.
  const CHAVE_PROGRESSO_ANONIMO = "plataforma_progresso_anonimo";
  function lerProgressoAnonimo() {
    try { return JSON.parse(sessionStorage.getItem(CHAVE_PROGRESSO_ANONIMO) || "{}"); }
    catch { return {}; }
  }
  function marcarProgressoAnonimo(aulaId) {
    const mapa = lerProgressoAnonimo();
    mapa[aulaId] = "concluida";
    try { sessionStorage.setItem(CHAVE_PROGRESSO_ANONIMO, JSON.stringify(mapa)); } catch { /* sessionStorage indisponível: segue só em memória */ }
  }

  function normalizeUrl(url) {
    const v = String(url || "").trim();
    if (!v) return "";
    if (v.startsWith("http")) return v;
    if (v.startsWith("/")) return `${API}${v}`;
    return v;
  }

  // ---- Apresentação premium ----------------------------------------------
  // Tudo abaixo é somente experiência visual do aluno (hero, tempo de
  // leitura, barra de leitura, parallax): nenhuma regra de LMS, progresso ou
  // API muda aqui.
  const reduzMovimento = () => window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  // Tempo estimado de leitura: usa a duração cadastrada da aula quando
  // existe; senão estima pela contagem de palavras do texto (~180 wpm).
  function tempoLeituraMin(aula, htmlSanitizado) {
    const cadastrado = Number(aula.duracao_min);
    if (Number.isFinite(cadastrado) && cadastrado > 0) return Math.round(cadastrado);
    const tpl = document.createElement("template");
    tpl.innerHTML = String(htmlSanitizado || "");
    const palavras = (tpl.content.textContent || "").trim().split(/\s+/).filter(Boolean).length;
    return Math.max(1, Math.round(palavras / 180));
  }

  // Indicador de dificuldade (apenas visual, derivado da densidade de leitura).
  function nivelLeitura(min) {
    if (min <= 8) return { rotulo: "Leitura leve", pontos: 1 };
    if (min <= 14) return { rotulo: "Nível intermediário", pontos: 2 };
    return { rotulo: "Leitura aprofundada", pontos: 3 };
  }

  function metaAulaHtml(aula, htmlSanitizado, posicao) {
    const min = tempoLeituraMin(aula, htmlSanitizado);
    const nivel = nivelLeitura(min);
    return `<div class="aula-meta">
      ${posicao ? `<span class="aula-meta-item">${esc(posicao)}</span>` : ""}
      <span class="aula-meta-item" data-tempo-leitura>📖 ~${min} min de leitura</span>
      <span class="aula-meta-item aula-meta-nivel" data-nivel-leitura role="img" aria-label="Dificuldade: ${esc(nivel.rotulo)}">
        <span class="aula-nivel-pontos" aria-hidden="true">${[1, 2, 3].map(n => `<i class="${n <= nivel.pontos ? "is-on" : ""}"></i>`).join("")}</span>${esc(nivel.rotulo)}
      </span>
    </div>`;
  }

  // Barra de leitura fixa (sticky progress) + fundo com parallax discreto +
  // header compacto durante a leitura. Criadas uma única vez; atualizadas via
  // rAF no scroll (compositor-friendly, sem background-attachment:fixed, que
  // causava flicker no WebKit). A classe do header só é trocada quando o
  // estado realmente muda — nada de reflow a cada tick de scroll.
  let atualizarLeitura = () => {};
  let camadasPremiumProntas = false;
  let headerCompacto = false;
  function garantirCamadasPremium() {
    if (camadasPremiumProntas) return;
    camadasPremiumProntas = true;
    const readbar = document.createElement("div");
    readbar.className = "plataforma-readbar";
    readbar.setAttribute("aria-hidden", "true");
    readbar.innerHTML = "<span></span>";
    document.body.appendChild(readbar);
    // Título resumido da aula dentro do header (visível só no modo compacto).
    const nav = document.querySelector(".site-header .nav");
    if (nav && !nav.querySelector("[data-header-aula]")) {
      const resumo = document.createElement("span");
      resumo.className = "header-aula-resumo";
      resumo.setAttribute("data-header-aula", "");
      nav.insertBefore(resumo, nav.querySelector(".nav-links"));
    }
    let parallax = null;
    if (!reduzMovimento()) {
      parallax = document.createElement("div");
      parallax.className = "plataforma-parallax";
      parallax.setAttribute("aria-hidden", "true");
      document.body.prepend(parallax);
    }
    const fill = readbar.firstElementChild;
    let agendado = false;
    const medir = () => {
      agendado = false;
      // Header compacto após rolar: devolve área vertical em notebooks.
      const compacto = window.scrollY > 110 && !!shell.querySelector("[data-conteudo]");
      if (compacto !== headerCompacto) {
        headerCompacto = compacto;
        document.body.classList.toggle("is-leitura-compacta", compacto);
      }
      const box = shell.querySelector("[data-conteudo]");
      if (!box) { fill.style.transform = "scaleX(0)"; readbar.classList.remove("is-visivel"); return; }
      readbar.classList.add("is-visivel");
      const rect = box.getBoundingClientRect();
      const total = rect.height - window.innerHeight;
      const lido = total > 0 ? Math.min(1, Math.max(0, -rect.top / total)) : (rect.bottom <= window.innerHeight ? 1 : 0);
      fill.style.transform = `scaleX(${lido})`;
      if (parallax) parallax.style.transform = `translate3d(0, ${window.scrollY * -0.06}px, 0)`;
    };
    atualizarLeitura = () => { if (!agendado) { agendado = true; requestAnimationFrame(medir); } };
    window.addEventListener("scroll", atualizarLeitura, { passive: true });
    window.addEventListener("resize", atualizarLeitura, { passive: true });
    atualizarLeitura();
  }

  // document.title acompanha a aula aberta (leitores de tela e histórico do
  // navegador sabem onde o aluno está); o header compacto mostra o mesmo
  // título resumido.
  const TITULO_BASE = "Meu curso | Escola Mística";
  function atualizarTituloDocumento() {
    const found = curso && aulaAtiva ? aulaPorId(aulaAtiva.aulaId) : null;
    document.title = found ? `${found.aula.titulo} · ${curso.titulo} | Escola Mística` : (curso ? `${curso.titulo} | Escola Mística` : TITULO_BASE);
    const resumo = document.querySelector("[data-header-aula]");
    if (resumo) resumo.textContent = found ? found.aula.titulo : "";
  }

  // Move o foco para o título da aula após navegação sem reload — leitores de
  // tela anunciam a nova aula e o Tab continua do lugar certo.
  function focarConteudo() {
    const h1 = shell.querySelector(".aula-hero h1");
    if (h1) { h1.setAttribute("tabindex", "-1"); h1.focus({ preventScroll: true }); }
  }

  // Anima a barra de progresso do curso uma única vez, na primeira pintura.
  let progressoAnimado = false;
  function animarProgresso() {
    if (progressoAnimado || reduzMovimento()) { progressoAnimado = true; return; }
    progressoAnimado = true;
    shell.querySelectorAll(".plataforma-progress > span").forEach(sp => {
      const alvo = sp.style.width;
      sp.style.width = "0%";
      requestAnimationFrame(() => requestAnimationFrame(() => { sp.style.width = alvo; }));
    });
  }

  // Transição suave ao trocar de aula sem recarregar a página.
  function animarEntradaConteudo() {
    if (reduzMovimento()) return;
    const box = shell.querySelector("[data-conteudo]");
    if (!box) return;
    box.classList.remove("is-entrando");
    void box.offsetWidth; // reinicia a animação
    box.classList.add("is-entrando");
  }

  function rolarParaConteudo() {
    const box = shell.querySelector("[data-conteudo]");
    if (!box) return;
    const topo = box.getBoundingClientRect().top + window.scrollY - 76;
    window.scrollTo({ top: Math.max(0, topo), behavior: reduzMovimento() ? "auto" : "smooth" });
  }

  // ---- Login ------------------------------------------------------------
  // Só é chamado quando o visitante interage com algo protegido (conteúdo
  // pago, progresso, avaliação ou certificado) — nunca para as partes
  // públicas do curso. Preserva o destino: o slug segue na URL e, ao voltar
  // ou logar, o mesmo curso é recarregado.
  function renderLogin(mensagem, permitirVoltar) {
    document.body.classList.remove("plataforma-drawer-aberto"); // tela sem drawer: nunca deixa o scroll travado
    // Se o drawer estava aberto ao pedir login, solta o focus trap dele.
    if (drawerKeydown) { document.removeEventListener("keydown", drawerKeydown); drawerKeydown = null; drawerFocoAnterior = null; }
    shell.innerHTML = `
      <div class="plataforma-login">
        <h1>Entrar na Escola Mística</h1>
        <p>Use o e-mail e a senha que você criou no link de acesso enviado após a confirmação do pagamento.</p>
        <form data-login-form>
          <input type="email" placeholder="Seu e-mail" data-email required autocomplete="email">
          <input type="password" placeholder="Sua senha" data-senha required autocomplete="current-password">
          <button class="btn" type="submit">Entrar</button>
        </form>
        <p class="plataforma-status" data-status>${mensagem ? esc(mensagem) : ""}</p>
        ${permitirVoltar ? `<button class="btn btn-ghost" type="button" data-voltar-publico>Voltar ao conteúdo gratuito</button>` : ""}
      </div>`;
    const form = shell.querySelector("[data-login-form]");
    const status = shell.querySelector("[data-status]");
    form.addEventListener("submit", async e => {
      e.preventDefault();
      status.textContent = "Entrando…";
      const r = await api("/api/alunos/login", {
        method: "POST",
        body: JSON.stringify({ email: form.querySelector("[data-email]").value.trim(), senha: form.querySelector("[data-senha]").value }),
      });
      if (!r.ok) { status.textContent = r.body.detail || "E-mail ou senha inválidos."; return; }
      boot();
    });
    shell.querySelector("[data-voltar-publico]")?.addEventListener("click", () => carregarCursoPublico());
  }

  // ---- Lista "Meus cursos" ---------------------------------------------
  async function renderLista() {
    const r = await api("/api/escola/meus-cursos");
    if (r.status === 401) return renderLogin();
    const cursos = r.ok ? r.body : [];
    if (!cursos.length) {
      shell.innerHTML = `<div class="plataforma-vazio">
        <h1>Meus cursos</h1>
        <p>Você ainda não tem cursos com a plataforma de estudo liberada. Assim que sua matrícula for confirmada, o curso aparece aqui.</p>
        <a class="btn" href="escola.html">Ver catálogo de cursos</a></div>`;
      return;
    }
    shell.innerHTML = `<h1 class="plataforma-titulo">Meus cursos</h1>
      <div class="plataforma-grid">${cursos.map(c => `
        <article class="plataforma-curso-card">
          ${c.imagem ? `<div class="plataforma-curso-capa" style="background-image:url('${esc(normalizeUrl(c.imagem))}')"></div>` : `<div class="plataforma-curso-capa is-emblem" aria-hidden="true">☾</div>`}
          <div class="plataforma-curso-body">
            <h2>${esc(c.titulo)}</h2>
            <p>${esc(c.descricao || "")}</p>
            <div class="plataforma-progress"><span style="width:${c.percentual}%"></span></div>
            <small>${c.aulas_concluidas}/${c.total_aulas} aulas • ${c.percentual}% concluído</small>
            <a class="btn btn-full" href="escola-curso.html?curso=${encodeURIComponent(c.slug)}">${c.percentual > 0 ? "Continuar estudando" : "Começar curso"}</a>
          </div>
        </article>`).join("")}</div>`;
  }

  // ---- Player do curso --------------------------------------------------
  let curso = null;
  let aulaAtiva = null; // { moduloId, aulaId }
  // Visitante sem sessão: só as partes marcadas como públicas no backend
  // (acesso_publico) chegam com conteúdo; módulos pagos vêm só como metadados
  // bloqueados. Nenhuma matrícula, conta ou progresso é criado neste modo.
  let modoAnonimo = false;

  function todasAulas() {
    return curso.modulos.flatMap(m => m.aulas.map(a => ({ ...a, moduloId: m.id, moduloLiberado: m.liberado })));
  }

  function selecionarPrimeiraPendente() {
    for (const m of curso.modulos) {
      if (!m.liberado) continue;
      const pend = m.aulas.find(a => a.status !== "concluida") || m.aulas[0];
      if (pend) { aulaAtiva = { moduloId: m.id, aulaId: pend.id }; return; }
    }
    const m0 = curso.modulos[0];
    if (m0 && m0.aulas[0]) aulaAtiva = { moduloId: m0.id, aulaId: m0.aulas[0].id };
  }

  async function carregarCurso() {
    const r = await api(`/api/escola/cursos/${encodeURIComponent(slug)}`);
    // Sem sessão: nunca mostra tela de login para as partes públicas — cai
    // direto para a árvore anônima (só o backend decide o que é público).
    if (r.status === 401) return carregarCursoPublico();
    if (r.status === 403) { shell.innerHTML = `<div class="plataforma-vazio"><h1>Acesso não liberado</h1><p>${esc(r.body.detail || "Você ainda não tem acesso a este curso.")}</p><a class="btn" href="escola.html">Voltar ao catálogo</a></div>`; return; }
    if (!r.ok) { shell.innerHTML = `<div class="plataforma-vazio"><p>Não foi possível carregar o curso agora.</p></div>`; return; }
    modoAnonimo = false;
    curso = r.body;
    if (!curso.modulos.length) { shell.innerHTML = `<div class="plataforma-vazio"><h1>${esc(curso.titulo)}</h1><p>Conteúdo em preparação. Volte em breve.</p></div>`; return; }
    if (!aulaAtiva) selecionarPrimeiraPendente();
    renderPlayer();
  }

  // Recalcula total/concluídas/percentual a partir das aulas públicas
  // realmente presentes nos módulos liberados — nunca um valor fixo.
  function calcularProgressoPublico(modulos) {
    const aulasPublicas = modulos.filter(m => m.liberado).flatMap(m => m.aulas);
    const total_aulas = aulasPublicas.length;
    const aulas_concluidas = aulasPublicas.filter(a => a.status === "concluida").length;
    const percentual = total_aulas ? Math.round((aulas_concluidas / total_aulas) * 100) : 0;
    return { total_aulas, aulas_concluidas, percentual, concluido: total_aulas > 0 && aulas_concluidas === total_aulas };
  }

  async function carregarCursoPublico() {
    const r = await api(`/api/escola/publico/cursos/${encodeURIComponent(slug)}`);
    if (!r.ok) {
      shell.innerHTML = `<div class="plataforma-vazio"><h1>Curso não disponível</h1><p>${esc(r.body.detail || "Este curso não tem conteúdo público no momento.")}</p><a class="btn" href="escola.html">Voltar ao catálogo</a></div>`;
      return;
    }
    modoAnonimo = true;
    const progressoLocal = lerProgressoAnonimo();
    const modulos = r.body.modulos.map(m => ({
      ...m,
      liberado: !m.bloqueado,
      concluido: false,
      quiz: null,
      aulas: (m.aulas || []).map(a => ({ ...a, status: progressoLocal[a.id] === "concluida" ? "concluida" : "nao_iniciada", percentual: 0 })),
    }));
    // Contagem real das aulas públicas retornadas pela árvore anônima (nunca
    // 0/0 fixo): soma as aulas dos módulos liberados e cruza com o progresso
    // efêmero salvo em sessionStorage para saber quantas já foram concluídas.
    curso = {
      ...r.body,
      certificado: false,
      progresso: calcularProgressoPublico(modulos),
      modulos,
    };
    if (!curso.modulos.length) { shell.innerHTML = `<div class="plataforma-vazio"><h1>${esc(curso.titulo)}</h1><p>Conteúdo em preparação. Volte em breve.</p></div>`; return; }
    if (!aulaAtiva) selecionarPrimeiraPendente();
    renderPlayer();
  }

  function statusIcon(status) {
    return status === "concluida" ? "✓" : status === "em_andamento" ? "◔" : "○";
  }

  // Estado visual honesto de cada módulo. Visitante anônimo nunca vê
  // "Em andamento" genérico: os estados são "Disponível", "Você está aqui",
  // "Concluído nesta sessão" (progresso efêmero em sessionStorage) e
  // "Bloqueado". Aluno logado mantém "Concluído"/"Em andamento" reais,
  // decididos pelo backend.
  function badgeModulo(m) {
    if (modoAnonimo && m.bloqueado) return { texto: "🔒 Conteúdo pago", cls: "is-bloqueado" };
    if (!m.liberado) return { texto: "🔒 Bloqueado", cls: "is-bloqueado" };
    const aulas = m.aulas || [];
    const todasConcluidas = aulas.length > 0 && aulas.every(a => a.status === "concluida");
    if (m.concluido || todasConcluidas) return { texto: modoAnonimo ? "Concluído nesta sessão" : "Concluído", cls: "is-concluido" };
    if (aulaAtiva && aulas.some(a => a.id === aulaAtiva.aulaId)) return { texto: "Você está aqui", cls: "is-aqui" };
    if (!modoAnonimo && aulas.some(a => a.status === "concluida" || a.status === "em_andamento")) return { texto: "Em andamento", cls: "is-andamento" };
    return { texto: "Disponível", cls: "is-disponivel" };
  }

  // Só o módulo da aula ativa começa expandido; os demais ficam recolhidos e
  // podem ser abertos pelo cabeçalho (botão com aria-expanded).
  let modulosAbertos = new Set();

  function renderSidebar() {
    if (aulaAtiva && !modulosAbertos.size) modulosAbertos = new Set([aulaAtiva.moduloId]);
    return `<aside class="plataforma-sidebar" data-sidebar aria-label="Conteúdo do curso">
      <button type="button" class="plataforma-drawer-fechar" data-drawer-fechar aria-label="Fechar lista de módulos">✕</button>
      <div class="plataforma-sidebar-head">
        <strong title="${esc(curso.titulo)}">${esc(curso.titulo)}</strong>
        <div class="plataforma-progress"><span style="width:${curso.progresso.percentual}%"></span></div>
        <small>${curso.progresso.aulas_concluidas}/${curso.progresso.total_aulas} aulas • ${curso.progresso.percentual}%</small>
      </div>
      <nav class="plataforma-modulos">
        ${curso.modulos.map((m, i) => {
          const bloqueadoPago = modoAnonimo && m.bloqueado;
          const cls = m.concluido ? "is-done" : m.liberado ? "is-open" : "is-locked";
          const badge = badgeModulo(m);
          const aberto = modulosAbertos.has(m.id);
          const bloqueio = bloqueadoPago
            ? `<p class="plataforma-modulo-bloqueado">Continue sua jornada assinando o plano completo.</p>
               <button type="button" class="btn btn-small" data-login-cta>Entrar / assinar para continuar</button>`
            : `<p class="plataforma-modulo-bloqueado">Conclua o módulo anterior para liberar.</p>`;
          const capa = m.imagem && aberto ? `<div class="plataforma-modulo-capa" style="background-image:url('${esc(normalizeUrl(m.imagem))}')" aria-hidden="true"></div>` : "";
          const corpo = m.liberado ? `<ul class="plataforma-aulas">
              ${m.aulas.map(a => `<li>
                <button type="button" class="plataforma-aula-link ${aulaAtiva && aulaAtiva.aulaId === a.id ? "is-active" : ""} ${a.status === "concluida" ? "is-done" : ""}" data-aula="${a.id}" data-modulo="${m.id}" ${aulaAtiva && aulaAtiva.aulaId === a.id ? 'aria-current="true"' : ""}>
                  <span class="plataforma-aula-status" aria-hidden="true">${statusIcon(a.status)}</span>
                  <span class="plataforma-aula-titulo">${esc(a.titulo)}${a.obrigatoria ? "" : " <em>(opcional)</em>"}</span>
                  ${Number(a.duracao_min) > 0 ? `<span class="plataforma-aula-tempo">${Math.round(Number(a.duracao_min))} min</span>` : ""}
                </button></li>`).join("")}
              ${m.quiz ? `<li><button type="button" class="plataforma-quiz-link ${m.quiz.disponivel ? "" : "is-locked"} ${m.quiz.aprovado ? "is-done" : ""}" data-quiz="${m.quiz.id}" ${m.quiz.disponivel ? "" : "disabled"}>
                <span class="plataforma-aula-status" aria-hidden="true">${m.quiz.aprovado ? "✓" : "★"}</span>
                <span class="plataforma-aula-titulo">${esc(m.quiz.titulo)}${m.quiz.maior_nota != null ? ` — melhor nota ${m.quiz.maior_nota}%` : ""}</span></button></li>` : ""}
            </ul>` : bloqueio;
          return `<section class="plataforma-modulo ${cls}${aberto ? " is-aberto" : ""}">
            <button type="button" class="plataforma-modulo-head" data-toggle-modulo="${m.id}" aria-expanded="${aberto}" aria-controls="modulo-corpo-${m.id}">
              <span class="plataforma-modulo-num" aria-hidden="true">${i + 1}</span>
              <span class="plataforma-modulo-info"><strong>${esc(m.titulo)}</strong><small class="plataforma-modulo-badge ${badge.cls}">${badge.texto}</small></span>
              <span class="plataforma-modulo-seta" aria-hidden="true">▾</span>
            </button>
            <div class="plataforma-modulo-corpo" id="modulo-corpo-${m.id}" ${aberto ? "" : "hidden"}>${capa}${corpo}</div>
          </section>`;
        }).join("")}
      </nav>
      ${modoAnonimo ? `<button type="button" class="btn btn-full" data-login-cta>Entrar para salvar progresso e emitir certificado</button>` : ""}
      ${!modoAnonimo && curso.progresso.concluido && curso.certificado ? `<a class="btn btn-full" href="${API}/api/cursos/${encodeURIComponent(slug)}/certificado" target="_blank" rel="noopener">Emitir certificado 🎓</a>` : ""}
    </aside>`;
  }

  function aulaPorId(id) {
    for (const m of curso.modulos) {
      const a = m.aulas.find(x => x.id === id);
      if (a) return { aula: a, modulo: m };
    }
    return null;
  }

  function renderConteudoAula() {
    if (!aulaAtiva) return `<div class="plataforma-conteudo-vazio">Selecione uma aula ao lado para começar.</div>`;
    const found = aulaPorId(aulaAtiva.aulaId);
    if (!found) return `<div class="plataforma-conteudo-vazio">Aula não encontrada.</div>`;
    const { aula, modulo } = found;
    if (!modulo.liberado) {
      if (modoAnonimo && modulo.bloqueado) {
        return `<div class="plataforma-conteudo-vazio">
          <p>🔒 Este conteúdo faz parte do plano pago da Escola Mística.</p>
          <button type="button" class="btn" data-login-cta>Entrar / assinar para continuar</button>
        </div>`;
      }
      return `<div class="plataforma-conteudo-vazio">🔒 Este módulo ainda está bloqueado.</div>`;
    }

    let midia = "";
    if (aula.video_url) {
      const v = normalizeUrl(aula.video_url);
      const yt = v.match(/(?:youtu\.be\/|youtube\.com\/(?:watch\?v=|embed\/))([\w-]{11})/);
      midia = yt
        ? `<div class="plataforma-video"><iframe src="https://www.youtube.com/embed/${yt[1]}" title="Vídeo da aula" allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture" allowfullscreen loading="lazy"></iframe></div>`
        : `<div class="plataforma-video"><video controls preload="metadata" src="${esc(v)}"></video></div>`;
    }
    const material = aula.material_url
      ? `<a class="btn btn-ghost" href="${esc(normalizeUrl(aula.material_url))}" target="_blank" rel="noopener">📎 Material complementar</a>` : "";

    // A capa fotográfica da aula (quando abre o conteúdo) sobe para antes do
    // título: evita que o <h1> fique espremido logo acima da própria foto,
    // que já carrega o título embutido na imagem. Diagramas no meio do texto
    // (mapa/linha do tempo) não são movidos — só a capa de abertura.
    const sanitizado = aula.conteudo ? sanitizeHtml(aula.conteudo) : "";
    let capaAula = "";
    let restante = sanitizado;
    if (sanitizado) {
      const tpl = document.createElement("template");
      tpl.innerHTML = sanitizado;
      const primeiro = tpl.content.firstElementChild;
      if (primeiro && primeiro.tagName === "FIGURE" && primeiro.classList.contains("aula-imagem")
          && !primeiro.classList.contains("aula-imagem-timeline") && !primeiro.classList.contains("aula-imagem-mapa")) {
        // Esta é a capa que sobe para o topo do conteúdo: sempre a primeira
        // coisa visível da aula, nunca abaixo da dobra. O HTML de origem
        // marca a tag <img> com loading="lazy" (correto para imagens de
        // meio de texto, como mapa/linha do tempo), mas como o conteúdo é
        // injetado via innerHTML depois do fetch — nunca durante o parse
        // inicial da página — o navegador não tem como pré-carregar essa
        // imagem antecipadamente. Com "lazy" ela fica pendurada no
        // IntersectionObserver e, até resolver, mostra só o fundo quase
        // preto (#05070a) da moldura: um retângulo escuro no lugar da foto,
        // logo ao lado da barra lateral e acima do texto da aula. Como essa
        // capa é sempre a primeira coisa da tela, o carregamento deve ser
        // imediato (eager), igual a qualquer imagem acima da dobra.
        primeiro.querySelector("img")?.setAttribute("loading", "eager");
        capaAula = primeiro.outerHTML;
        primeiro.remove();
        restante = tpl.innerHTML;
      }
    }

    // Mini índice da aula + imagens internas lazy. As seções (h2/h3 do corpo)
    // ganham id e viram âncoras; imagens de meio de texto sem loading
    // explícito ficam lazy (a capa acima já foi promovida a eager).
    let indice = "";
    if (restante) {
      const tplIdx = document.createElement("template");
      tplIdx.innerHTML = restante;
      tplIdx.content.querySelectorAll("img:not([loading])").forEach(img => img.setAttribute("loading", "lazy"));
      const secoes = [];
      tplIdx.content.querySelectorAll("h2, h3").forEach(h => {
        const titulo = (h.textContent || "").trim();
        // Títulos de cards (curiosidade, ciência...) não são seções da aula.
        if (h.closest(".aula-box, .aula-glossario, .aula-revisao, aside, figure, table")) return;
        // O primeiro h2 repete o título da aula (fica visualmente oculto no
        // CSS) — não entra no índice.
        if (!titulo || titulo === String(aula.titulo).trim()) return;
        const id = `aula-secao-${secoes.length + 1}`;
        h.id = id;
        secoes.push({ id, titulo, sub: h.tagName === "H3" });
      });
      restante = tplIdx.innerHTML;
      if (secoes.length >= 2) {
        indice = `<nav class="aula-indice" aria-label="Nesta aula">
          <strong>Nesta aula</strong>
          <ol>${secoes.map(s => `<li${s.sub ? ' class="is-sub"' : ""}><a href="#${s.id}">${esc(s.titulo)}</a></li>`).join("")}</ol>
        </nav>`;
      }
    }

    // "Em poucas palavras": a descrição da aula abre o corpo do texto como
    // resumo editorial (sai do hero, onde competia com o título sobre a foto).
    const resumo = aula.descricao ? `<aside class="aula-resumo"><strong>Em poucas palavras</strong><p>${esc(aula.descricao)}</p></aside>` : "";
    const texto = restante || resumo || indice ? `<div class="plataforma-texto">${resumo}${indice}${restante}</div>` : "";

    const flat = todasAulas().filter(a => a.moduloLiberado);
    const idx = flat.findIndex(a => a.id === aula.id);
    const prev = idx > 0 ? flat[idx - 1] : null;
    const next = idx >= 0 && idx < flat.length - 1 ? flat[idx + 1] : null;
    const feito = aula.status === "concluida";

    // Hero cinematográfico: a capa fotográfica vira o pano de fundo do
    // cabeçalho da aula (título, módulo, tempo de leitura e nível por cima).
    const posicao = idx >= 0 ? `Aula ${idx + 1} de ${flat.length}` : "";
    const hero = `<header class="aula-hero${capaAula ? " has-capa" : ""}">
        ${capaAula ? `<div class="aula-hero-media">${capaAula}</div>` : ""}
        <div class="aula-hero-copy">
          <p class="plataforma-conteudo-modulo">${esc(modulo.titulo)}</p>
          <h1 tabindex="-1">${esc(aula.titulo)}</h1>
          ${metaAulaHtml(aula, restante, posicao)}
        </div>
      </header>`;

    // Prévia da próxima aula (sem botão: a ação de seguir adiante é uma só,
    // o CTA principal logo acima — nada de dois botões competindo).
    const proxima = next
      ? `<aside class="aula-next" data-next-card>
          <div class="aula-next-info">
            <span class="aula-next-kicker">A seguir na sua jornada</span>
            <strong class="aula-next-titulo">${esc(next.titulo)}</strong>
            ${next.descricao ? `<p>${esc(next.descricao)}</p>` : ""}
            ${Number(next.duracao_min) > 0 ? `<span class="aula-next-tempo">📖 ~${Math.round(Number(next.duracao_min))} min</span>` : ""}
          </div>
        </aside>`
      : `<aside class="aula-next is-fim" data-next-card>
          <span class="aula-next-kicker">Você chegou ao fim das aulas liberadas</span>
          <p>Avaliações e novos módulos aparecem na barra lateral assim que forem liberados. Bons estudos! ☾</p>
        </aside>`;

    // Uma única ação principal ao fim da aula; "Anterior" fica como ação
    // secundária discreta. O rótulo se adapta ao estado real da aula.
    const rotuloPrincipal = feito
      ? (next ? "Continuar para a próxima aula →" : "✓ Aula concluída")
      : (next ? "Marcar como concluída e continuar →" : "Marcar como concluída");
    return `${hero}
      ${midia}
      ${texto}
      <div class="plataforma-conteudo-material">${material}</div>
      <div class="plataforma-conteudo-actions">
        <button class="btn btn-ghost" type="button" data-prev ${prev ? "" : "disabled"}>← Anterior</button>
        <button class="btn plataforma-cta-principal" type="button" data-concluir-continuar data-aula="${aula.id}" data-tipo="${aula.tipo}" data-min="${aula.percentual_minimo || 80}" ${feito && !next ? "disabled" : ""}>${rotuloPrincipal}</button>
      </div>
      ${proxima}`;
  }

  function renderPlayer() {
    shell.innerHTML = `
      <div class="plataforma-topbar">
        <button class="btn btn-ghost btn-small plataforma-drawer-toggle" type="button" data-drawer-toggle aria-label="Abrir módulos">☰ Módulos</button>
        <span class="plataforma-topbar-titulo" title="${esc(curso.titulo)}">${esc(curso.titulo)}</span>
      </div>
      <div class="plataforma-layout" data-layout>
        ${renderSidebar()}
        <section class="plataforma-conteudo" data-conteudo>${renderConteudoAula()}</section>
      </div>`;
    bindPlayer();
    garantirCamadasPremium();
    animarProgresso();
    animarEntradaConteudo();
    atualizarTituloDocumento();
    atualizarLeitura();
  }

  function refreshConteudo() {
    const box = shell.querySelector("[data-conteudo]");
    if (box) { box.innerHTML = renderConteudoAula(); bindConteudo(); }
    const side = shell.querySelector("[data-sidebar]");
    if (side) side.outerHTML = renderSidebar();
    bindSidebar();
    animarEntradaConteudo();
    atualizarTituloDocumento();
    atualizarLeitura();
  }

  // Único ponto em que o visitante anônimo é levado ao login: ele clicou em
  // algo protegido (módulo pago, progresso, certificado) — nunca acontece só
  // por navegar pelas partes públicas.
  function pedirLoginParaRecursoProtegido() {
    renderLogin("Entre para continuar: essa parte do curso é exclusiva de quem tem plano ativo.", true);
  }

  // Abre/fecha o drawer de módulos travando o scroll do fundo enquanto o
  // drawer está aberto (a classe no <body> só existe com o drawer aberto).
  // Com o drawer aberto: foco preso dentro dele, Escape fecha e, ao fechar,
  // o foco volta para quem o abriu.
  let drawerKeydown = null;
  let drawerFocoAnterior = null;
  function alternarDrawer(forcar) {
    const layout = shell.querySelector("[data-layout]");
    if (!layout) return;
    const aberto = typeof forcar === "boolean" ? forcar : !layout.classList.contains("drawer-open");
    layout.classList.toggle("drawer-open", aberto);
    document.body.classList.toggle("plataforma-drawer-aberto", aberto);
    if (aberto && !drawerKeydown) {
      drawerFocoAnterior = document.activeElement;
      drawerKeydown = e => {
        if (e.key === "Escape") { e.preventDefault(); alternarDrawer(false); return; }
        if (e.key !== "Tab") return;
        const side = shell.querySelector("[data-sidebar]");
        if (!side) return;
        const focaveis = [...side.querySelectorAll("button, a[href], input, select, textarea, [tabindex]:not([tabindex='-1'])")]
          .filter(el => !el.disabled && el.offsetParent !== null);
        if (!focaveis.length) return;
        const primeiro = focaveis[0];
        const ultimo = focaveis[focaveis.length - 1];
        if (e.shiftKey && (document.activeElement === primeiro || !side.contains(document.activeElement))) { e.preventDefault(); ultimo.focus(); }
        else if (!e.shiftKey && (document.activeElement === ultimo || !side.contains(document.activeElement))) { e.preventDefault(); primeiro.focus(); }
      };
      document.addEventListener("keydown", drawerKeydown);
      shell.querySelector("[data-sidebar] [data-drawer-fechar]")?.focus();
    } else if (!aberto && drawerKeydown) {
      document.removeEventListener("keydown", drawerKeydown);
      drawerKeydown = null;
      if (drawerFocoAnterior && drawerFocoAnterior.isConnected) drawerFocoAnterior.focus();
      drawerFocoAnterior = null;
    }
  }

  // Navegação para uma aula específica sem reload: abre só o módulo dela na
  // sidebar, re-renderiza, rola até o conteúdo e move o foco para o título.
  function irParaAula(moduloId, aulaId) {
    aulaAtiva = { moduloId, aulaId };
    modulosAbertos = new Set([moduloId]);
    refreshConteudo();
    rolarParaConteudo();
    focarConteudo();
  }

  function bindSidebar() {
    shell.querySelectorAll("[data-toggle-modulo]").forEach(btn => {
      btn.addEventListener("click", () => {
        // Expande/recolhe no lugar (sem re-render): preserva foco e a posição
        // de rolagem da sidebar — navegável só com teclado.
        const id = Number(btn.dataset.toggleModulo);
        const aberto = !modulosAbertos.has(id);
        if (aberto) modulosAbertos.add(id); else modulosAbertos.delete(id);
        btn.setAttribute("aria-expanded", String(aberto));
        btn.closest(".plataforma-modulo")?.classList.toggle("is-aberto", aberto);
        const corpo = shell.querySelector(`#modulo-corpo-${id}`);
        if (corpo) corpo.hidden = !aberto;
      });
    });
    // Escopo restrito à sidebar: o CTA principal do conteúdo também carrega
    // data-aula e, sem o escopo, ganhava um segundo listener de navegação
    // (listener duplicado disparando junto com o de concluir).
    shell.querySelectorAll("[data-sidebar] [data-aula]").forEach(btn => {
      if (btn.classList.contains("plataforma-quiz-link")) return;
      btn.addEventListener("click", () => {
        alternarDrawer(false);
        irParaAula(Number(btn.dataset.modulo), Number(btn.dataset.aula));
      });
    });
    shell.querySelectorAll("[data-quiz]").forEach(btn => {
      btn.addEventListener("click", () => { if (!btn.disabled) abrirQuiz(Number(btn.dataset.quiz)); });
    });
    shell.querySelectorAll("[data-login-cta]").forEach(btn => {
      btn.addEventListener("click", pedirLoginParaRecursoProtegido);
    });
    shell.querySelector("[data-drawer-fechar]")?.addEventListener("click", () => alternarDrawer(false));
  }

  function bindConteudo() {
    const box = shell.querySelector("[data-conteudo]");
    if (!box) return;
    box.querySelector("[data-prev]")?.addEventListener("click", () => navegar(-1));
    box.querySelector("[data-login-cta]")?.addEventListener("click", pedirLoginParaRecursoProtegido);
    // Ação principal única: "Marcar como concluída e continuar". Se a aula já
    // está concluída, o mesmo botão só navega. Nenhuma regra de progresso
    // muda: o backend continua recebendo o mesmo POST de progresso de sempre.
    box.querySelector("[data-concluir-continuar]")?.addEventListener("click", async e => {
      const btn = e.currentTarget;
      const aulaId = Number(btn.dataset.aula);
      const found = aulaPorId(aulaId);
      if (found && found.aula.status === "concluida") { navegar(1); return; }
      btn.disabled = true;
      if (modoAnonimo) {
        // Visitante sem sessão: marcação é só visual (sessionStorage), nunca
        // grava progresso no servidor nem exige conta.
        marcarProgressoAnonimo(aulaId);
        if (found) found.aula.status = "concluida";
        curso.progresso = calcularProgressoPublico(curso.modulos);
        if (!navegar(1)) { refreshConteudo(); focarConteudo(); }
        return;
      }
      const r = await api(`/api/escola/aulas/${aulaId}/progresso`, { method: "POST", body: JSON.stringify({ status: "concluida", percentual: 100 }) });
      if (!r.ok) { btn.disabled = false; return; }
      // Avança para a próxima aula antes de recarregar a árvore do curso:
      // o aluno cai direto na aula seguinte, já com o progresso salvo.
      const flat = todasAulas().filter(a => a.moduloLiberado);
      const idx = flat.findIndex(a => a.id === aulaId);
      const prox = idx >= 0 ? flat[idx + 1] : null;
      if (prox) { aulaAtiva = { moduloId: prox.moduloId, aulaId: prox.id }; modulosAbertos = new Set([prox.moduloId]); }
      await carregarCurso();
      if (prox) { rolarParaConteudo(); focarConteudo(); }
    });
  }

  function navegar(dir) {
    const flat = todasAulas().filter(a => a.moduloLiberado);
    const idx = flat.findIndex(a => a.id === aulaAtiva.aulaId);
    const alvo = flat[idx + dir];
    if (!alvo) return false;
    irParaAula(alvo.moduloId, alvo.id);
    return true;
  }

  function bindPlayer() {
    bindSidebar();
    bindConteudo();
    shell.querySelector("[data-drawer-toggle]")?.addEventListener("click", () => alternarDrawer());
    // Toque no backdrop (a área escurecida fora do drawer) fecha o drawer.
    const layout = shell.querySelector("[data-layout]");
    layout?.addEventListener("click", e => {
      if (e.target === layout && layout.classList.contains("drawer-open")) alternarDrawer(false);
    });
    // O player pode ser re-renderizado com o drawer aberto: nunca deixa o
    // scroll do fundo travado sem drawer visível.
    if (!layout || !layout.classList.contains("drawer-open")) document.body.classList.remove("plataforma-drawer-aberto");
  }

  // ---- Avaliação --------------------------------------------------------
  async function abrirQuiz(quizId) {
    const r = await api(`/api/escola/quizzes/${quizId}/iniciar`);
    if (!r.ok) { alert(r.body.detail || "Não foi possível iniciar a avaliação agora."); return; }
    const q = r.body;
    const box = shell.querySelector("[data-conteudo]");
    box.innerHTML = `
      <div class="plataforma-quiz">
        <h1>${esc(q.titulo)}</h1>
        <p class="plataforma-quiz-info">Nota mínima para aprovação: <strong>${q.nota_minima}%</strong>. Responda todas as perguntas e envie.</p>
        <form data-quiz-form>
          ${q.perguntas.map((p, i) => `
            <fieldset class="plataforma-pergunta" data-pergunta="${p.id}">
              <legend>${i + 1}. ${esc(p.enunciado)}</legend>
              ${p.opcoes.map(o => `<label class="plataforma-opcao"><input type="radio" name="p${p.id}" value="${o.id}"><span>${esc(o.texto)}</span></label>`).join("")}
            </fieldset>`).join("")}
          <div class="plataforma-quiz-actions">
            <button class="btn" type="submit">Enviar avaliação</button>
            <button class="btn btn-ghost" type="button" data-cancelar>Voltar ao conteúdo</button>
          </div>
          <p class="plataforma-status" data-quiz-status></p>
        </form>
      </div>`;
    const form = box.querySelector("[data-quiz-form]");
    const status = box.querySelector("[data-quiz-status]");
    box.querySelector("[data-cancelar]").addEventListener("click", () => refreshConteudo());
    form.addEventListener("submit", async e => {
      e.preventDefault();
      const respostas = q.perguntas.map(p => {
        const sel = form.querySelector(`input[name="p${p.id}"]:checked`);
        return { pergunta_id: p.id, opcao_id: sel ? Number(sel.value) : null };
      });
      if (respostas.some(r => r.opcao_id == null)) { status.textContent = "Responda todas as perguntas antes de enviar."; return; }
      status.textContent = "Corrigindo…";
      const env = await api(`/api/escola/quizzes/${quizId}/enviar`, { method: "POST", body: JSON.stringify({ sessao_id: q.sessao_id, respostas }) });
      if (!env.ok) { status.textContent = env.body.detail || "Não foi possível enviar a avaliação."; return; }
      renderResultadoQuiz(quizId, q, env.body);
    });
  }

  function renderResultadoQuiz(quizId, q, resultado) {
    const box = shell.querySelector("[data-conteudo]");
    const aprov = resultado.aprovado;
    box.innerHTML = `
      <div class="plataforma-quiz-resultado ${aprov ? "is-aprovado" : "is-reprovado"}">
        <div class="plataforma-quiz-nota">${resultado.nota}%</div>
        <h1>${aprov ? "Aprovado! 🎉" : "Ainda não foi dessa vez"}</h1>
        <p>${resultado.acertos} de ${resultado.total} corretas. Nota mínima: ${resultado.nota_minima}%.</p>
        <p>${aprov ? "O próximo módulo foi liberado." : "Revise o conteúdo e tente novamente."}</p>
        <div class="plataforma-quiz-explicacoes">
          ${q.perguntas.map((p, i) => {
            const ex = resultado.explicacoes[p.id] || {};
            const correta = p.opcoes.find(o => o.id === ex.correta_opcao_id);
            return `<div class="plataforma-explicacao ${ex.acertou ? "ok" : "no"}">
              <strong>${i + 1}. ${esc(p.enunciado)}</strong>
              <span>Resposta correta: ${esc(correta ? correta.texto : "-")}</span>
              ${ex.explicacao ? `<em>${esc(ex.explicacao)}</em>` : ""}
            </div>`;
          }).join("")}
        </div>
        <button class="btn" type="button" data-voltar>Voltar ao curso</button>
      </div>`;
    box.querySelector("[data-voltar]").addEventListener("click", () => carregarCurso());
  }

  // ---- Boot -------------------------------------------------------------
  async function boot() {
    if (slug) { aulaAtiva = null; curso = null; modulosAbertos = new Set(); await carregarCurso(); }
    else { document.title = TITULO_BASE; await renderLista(); }
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", boot, { once: true });
  else boot();
})();
