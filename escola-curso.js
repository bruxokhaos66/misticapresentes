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

  // ---- Login ------------------------------------------------------------
  // Só é chamado quando o visitante interage com algo protegido (conteúdo
  // pago, progresso, avaliação ou certificado) — nunca para as partes
  // públicas do curso. Preserva o destino: o slug segue na URL e, ao voltar
  // ou logar, o mesmo curso é recarregado.
  function renderLogin(mensagem, permitirVoltar) {
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

  async function carregarCursoPublico() {
    const r = await api(`/api/escola/publico/cursos/${encodeURIComponent(slug)}`);
    if (!r.ok) {
      shell.innerHTML = `<div class="plataforma-vazio"><h1>Curso não disponível</h1><p>${esc(r.body.detail || "Este curso não tem conteúdo público no momento.")}</p><a class="btn" href="escola.html">Voltar ao catálogo</a></div>`;
      return;
    }
    modoAnonimo = true;
    const progressoLocal = lerProgressoAnonimo();
    curso = {
      ...r.body,
      certificado: false,
      progresso: { total_aulas: 0, aulas_concluidas: 0, percentual: 0, concluido: false },
      modulos: r.body.modulos.map(m => ({
        ...m,
        liberado: !m.bloqueado,
        concluido: false,
        quiz: null,
        aulas: (m.aulas || []).map(a => ({ ...a, status: progressoLocal[a.id] === "concluida" ? "concluida" : "nao_iniciada", percentual: 0 })),
      })),
    };
    if (!curso.modulos.length) { shell.innerHTML = `<div class="plataforma-vazio"><h1>${esc(curso.titulo)}</h1><p>Conteúdo em preparação. Volte em breve.</p></div>`; return; }
    if (!aulaAtiva) selecionarPrimeiraPendente();
    renderPlayer();
  }

  function statusIcon(status) {
    return status === "concluida" ? "✓" : status === "em_andamento" ? "◔" : "○";
  }

  function renderSidebar() {
    return `<aside class="plataforma-sidebar" data-sidebar>
      <div class="plataforma-sidebar-head">
        <strong>${esc(curso.titulo)}</strong>
        <div class="plataforma-progress"><span style="width:${curso.progresso.percentual}%"></span></div>
        <small>${curso.progresso.aulas_concluidas}/${curso.progresso.total_aulas} aulas • ${curso.progresso.percentual}%</small>
      </div>
      <nav class="plataforma-modulos">
        ${curso.modulos.map((m, i) => {
          const bloqueadoPago = modoAnonimo && m.bloqueado;
          const cls = m.concluido ? "is-done" : m.liberado ? "is-open" : "is-locked";
          const badge = m.concluido ? "Concluído" : bloqueadoPago ? "🔒 Conteúdo pago" : !m.liberado ? "🔒 Bloqueado" : "Em andamento";
          const bloqueio = bloqueadoPago
            ? `<p class="plataforma-modulo-bloqueado">Continue sua jornada assinando o plano completo.</p>
               <button type="button" class="btn btn-small" data-login-cta>Entrar / assinar para continuar</button>`
            : `<p class="plataforma-modulo-bloqueado">Conclua o módulo anterior para liberar.</p>`;
          const capa = m.imagem ? `<div class="plataforma-modulo-capa" style="background-image:url('${esc(normalizeUrl(m.imagem))}')" aria-hidden="true"></div>` : "";
          return `<div class="plataforma-modulo ${cls}">
            ${capa}
            <div class="plataforma-modulo-head"><span class="plataforma-modulo-num">${i + 1}</span><div><strong>${esc(m.titulo)}</strong><small>${badge}</small></div></div>
            ${m.liberado ? `<ul class="plataforma-aulas">
              ${m.aulas.map(a => `<li>
                <button type="button" class="plataforma-aula-link ${aulaAtiva && aulaAtiva.aulaId === a.id ? "is-active" : ""} ${a.status === "concluida" ? "is-done" : ""}" data-aula="${a.id}" data-modulo="${m.id}">
                  <span class="plataforma-aula-status">${statusIcon(a.status)}</span>
                  <span class="plataforma-aula-titulo">${esc(a.titulo)}${a.obrigatoria ? "" : " <em>(opcional)</em>"}</span>
                </button></li>`).join("")}
              ${m.quiz ? `<li><button type="button" class="plataforma-quiz-link ${m.quiz.disponivel ? "" : "is-locked"} ${m.quiz.aprovado ? "is-done" : ""}" data-quiz="${m.quiz.id}" ${m.quiz.disponivel ? "" : "disabled"}>
                <span class="plataforma-aula-status">${m.quiz.aprovado ? "✓" : "★"}</span>
                <span class="plataforma-aula-titulo">${esc(m.quiz.titulo)}${m.quiz.maior_nota != null ? ` — melhor nota ${m.quiz.maior_nota}%` : ""}</span></button></li>` : ""}
            </ul>` : bloqueio}
          </div>`;
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
    const texto = aula.conteudo ? `<div class="plataforma-texto">${sanitizeHtml(aula.conteudo)}</div>` : "";

    const flat = todasAulas().filter(a => a.moduloLiberado);
    const idx = flat.findIndex(a => a.id === aula.id);
    const prev = idx > 0 ? flat[idx - 1] : null;
    const next = idx >= 0 && idx < flat.length - 1 ? flat[idx + 1] : null;
    const feito = aula.status === "concluida";

    return `<div class="plataforma-conteudo-head">
        <p class="plataforma-conteudo-modulo">${esc(modulo.titulo)}</p>
        <h1>${esc(aula.titulo)}</h1>
        ${aula.descricao ? `<p class="plataforma-conteudo-desc">${esc(aula.descricao)}</p>` : ""}
      </div>
      ${midia}
      ${texto}
      <div class="plataforma-conteudo-material">${material}</div>
      <div class="plataforma-conteudo-actions">
        <button class="btn btn-ghost" type="button" data-prev ${prev ? "" : "disabled"}>← Anterior</button>
        <button class="btn ${feito ? "btn-ghost" : ""}" type="button" data-concluir data-aula="${aula.id}" data-tipo="${aula.tipo}" data-min="${aula.percentual_minimo || 80}">${feito ? "✓ Concluída" : "Marcar como concluída"}</button>
        <button class="btn btn-ghost" type="button" data-next ${next ? "" : "disabled"}>Próxima →</button>
      </div>`;
  }

  function renderPlayer() {
    shell.innerHTML = `
      <div class="plataforma-topbar">
        <button class="btn btn-ghost btn-small plataforma-drawer-toggle" type="button" data-drawer-toggle aria-label="Abrir módulos">☰ Módulos</button>
        <span class="plataforma-topbar-titulo">${esc(curso.titulo)}</span>
      </div>
      <div class="plataforma-layout" data-layout>
        ${renderSidebar()}
        <section class="plataforma-conteudo" data-conteudo>${renderConteudoAula()}</section>
      </div>`;
    bindPlayer();
  }

  function refreshConteudo() {
    const box = shell.querySelector("[data-conteudo]");
    if (box) { box.innerHTML = renderConteudoAula(); bindConteudo(); }
    const side = shell.querySelector("[data-sidebar]");
    if (side) side.outerHTML = renderSidebar();
    bindSidebar();
  }

  // Único ponto em que o visitante anônimo é levado ao login: ele clicou em
  // algo protegido (módulo pago, progresso, certificado) — nunca acontece só
  // por navegar pelas partes públicas.
  function pedirLoginParaRecursoProtegido() {
    renderLogin("Entre para continuar: essa parte do curso é exclusiva de quem tem plano ativo.", true);
  }

  function bindSidebar() {
    shell.querySelectorAll("[data-aula]").forEach(btn => {
      if (btn.classList.contains("plataforma-quiz-link")) return;
      btn.addEventListener("click", () => {
        aulaAtiva = { moduloId: Number(btn.dataset.modulo), aulaId: Number(btn.dataset.aula) };
        shell.querySelector("[data-layout]")?.classList.remove("drawer-open");
        refreshConteudo();
      });
    });
    shell.querySelectorAll("[data-quiz]").forEach(btn => {
      btn.addEventListener("click", () => { if (!btn.disabled) abrirQuiz(Number(btn.dataset.quiz)); });
    });
    shell.querySelectorAll("[data-login-cta]").forEach(btn => {
      btn.addEventListener("click", pedirLoginParaRecursoProtegido);
    });
  }

  function bindConteudo() {
    const box = shell.querySelector("[data-conteudo]");
    if (!box) return;
    box.querySelector("[data-prev]")?.addEventListener("click", () => navegar(-1));
    box.querySelector("[data-next]")?.addEventListener("click", () => navegar(1));
    box.querySelector("[data-login-cta]")?.addEventListener("click", pedirLoginParaRecursoProtegido);
    box.querySelector("[data-concluir]")?.addEventListener("click", async e => {
      const btn = e.currentTarget;
      const aulaId = Number(btn.dataset.aula);
      const tipo = btn.dataset.tipo;
      // Para vídeo, enviamos 100% ao marcar manualmente (o aluno declara que assistiu).
      const percentual = tipo === "video" ? 100 : 100;
      btn.disabled = true;
      if (modoAnonimo) {
        // Visitante sem sessão: marcação é só visual (sessionStorage), nunca
        // grava progresso no servidor nem exige conta.
        marcarProgressoAnonimo(aulaId);
        const found = aulaPorId(aulaId);
        if (found) found.aula.status = "concluida";
        refreshConteudo();
        return;
      }
      const r = await api(`/api/escola/aulas/${aulaId}/progresso`, { method: "POST", body: JSON.stringify({ status: "concluida", percentual }) });
      if (r.ok) await carregarCurso(); else btn.disabled = false;
    });
  }

  function navegar(dir) {
    const flat = todasAulas().filter(a => a.moduloLiberado);
    const idx = flat.findIndex(a => a.id === aulaAtiva.aulaId);
    const alvo = flat[idx + dir];
    if (alvo) { aulaAtiva = { moduloId: alvo.moduloId, aulaId: alvo.id }; refreshConteudo(); }
  }

  function bindPlayer() {
    bindSidebar();
    bindConteudo();
    shell.querySelector("[data-drawer-toggle]")?.addEventListener("click", () => {
      shell.querySelector("[data-layout]")?.classList.toggle("drawer-open");
    });
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
    if (slug) { aulaAtiva = null; curso = null; await carregarCurso(); }
    else await renderLista();
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", boot, { once: true });
  else boot();
})();
