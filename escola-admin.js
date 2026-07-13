(() => {
  "use strict";
  // Console administrativo da Escola Mística. Reutiliza a sessão administrativa
  // do painel (cookie mistica_painel_sessao, via /api/auth/login) — não cria
  // autenticação nova. Toda a validação de fato acontece no backend
  // (/api/admin/escola/*, protegido por sessão de administrador).
  const API = String((window.misticaSiteConfig || {}).apiBaseUrl || "https://api.misticaesotericos.com.br").replace(/\/$/, "");
  const root = document.querySelector("[data-admin-root]");
  const esc = v => String(v ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  let slugAtual = "";

  async function api(path, options = {}) {
    const res = await fetch(`${API}${path}`, {
      credentials: "include",
      headers: { "Content-Type": "application/json", ...(options.headers || {}) },
      ...options,
    });
    const body = await res.json().catch(() => ({}));
    return { ok: res.ok, status: res.status, body };
  }

  function toast(msg, erro) {
    const el = document.querySelector("[data-toast]");
    if (!el) return;
    el.textContent = msg;
    el.className = `escola-admin-toast ${erro ? "is-erro" : "is-ok"}`;
    el.hidden = false;
    clearTimeout(toast._t);
    toast._t = setTimeout(() => { el.hidden = true; }, 4000);
  }

  // ---- Login ------------------------------------------------------------
  async function estaLogado() {
    const r = await api("/api/auth/me");
    return r.ok && (r.body.perfil === "adm" || (r.body.usuario && r.body.usuario.perfil === "adm") || r.body.autenticado);
  }

  function renderLogin(msg) {
    root.innerHTML = `
      <div class="escola-admin-login">
        <h1>Gestão de Cursos</h1>
        <p>Entre com seu usuário administrador do painel.</p>
        <form data-login>
          <input placeholder="Usuário" data-login-user autocomplete="username" required>
          <input type="password" placeholder="Senha" data-login-pass autocomplete="current-password" required>
          <button class="btn" type="submit">Entrar</button>
        </form>
        <p class="escola-admin-status">${msg ? esc(msg) : ""}</p>
      </div>`;
    root.querySelector("[data-login]").addEventListener("submit", async e => {
      e.preventDefault();
      const r = await api("/api/auth/login", {
        method: "POST",
        body: JSON.stringify({ login: root.querySelector("[data-login-user]").value.trim(), senha: root.querySelector("[data-login-pass]").value }),
      });
      if (!r.ok) return renderLogin(r.body.detail || "Login ou senha inválidos.");
      boot();
    });
  }

  // ---- Layout principal -------------------------------------------------
  function renderShell() {
    root.innerHTML = `
      <div class="escola-admin-toast" data-toast hidden></div>
      <div class="escola-admin-header">
        <h1>Gestão de Cursos</h1>
        <button class="btn btn-ghost btn-small" type="button" data-logout>Sair</button>
      </div>
      <div class="escola-admin-picker">
        <label>Slug do curso (o mesmo do produto/venda, ex.: <code>rape-uso-tradicao</code>)
          <input data-slug value="${esc(slugAtual)}" placeholder="ex.: rape-uso-tradicao">
        </label>
        <button class="btn" type="button" data-carregar>Carregar curso</button>
      </div>
      <div data-curso></div>
      <div class="escola-admin-alunos-wrap" data-alunos></div>`;
    root.querySelector("[data-logout]").addEventListener("click", async () => { await api("/api/auth/logout", { method: "POST" }); renderLogin("Sessão encerrada."); });
    root.querySelector("[data-carregar]").addEventListener("click", () => {
      slugAtual = root.querySelector("[data-slug]").value.trim();
      if (slugAtual) { carregarCurso(); carregarAlunos(); }
    });
  }

  // ---- Curso + árvore ---------------------------------------------------
  async function carregarCurso() {
    const box = root.querySelector("[data-curso]");
    box.innerHTML = "<p>Carregando curso…</p>";
    const r = await api(`/api/admin/escola/cursos/${encodeURIComponent(slugAtual)}`);
    if (!r.ok) { box.innerHTML = `<p class="escola-admin-status">${esc(r.body.detail || "Não foi possível carregar.")}</p>`; return; }
    const cfg = r.body.config || { nota_minima: 70, certificado: true, publicado: true };
    box.innerHTML = `
      <section class="escola-admin-card">
        <h2>Configuração do curso</h2>
        <form data-cfg class="escola-admin-form">
          <label>Título<input data-cfg-titulo value="${esc(cfg.titulo || "")}"></label>
          <label>Descrição<textarea data-cfg-desc>${esc(cfg.descricao || "")}</textarea></label>
          <label>Imagem (URL)<input data-cfg-img value="${esc(cfg.imagem || "")}"></label>
          <div class="escola-admin-row">
            <label>Nota mínima (%)<input type="number" min="0" max="100" data-cfg-nota value="${cfg.nota_minima ?? 70}"></label>
            <label class="escola-admin-check"><input type="checkbox" data-cfg-cert ${cfg.certificado ? "checked" : ""}> Emite certificado</label>
            <label class="escola-admin-check"><input type="checkbox" data-cfg-pub ${cfg.publicado ? "checked" : ""}> Publicado</label>
          </div>
          <button class="btn" type="submit">Salvar configuração</button>
        </form>
      </section>
      <section class="escola-admin-card">
        <div class="escola-admin-card-head"><h2>Módulos</h2><button class="btn btn-small" type="button" data-novo-modulo>+ Novo módulo</button></div>
        <div data-modulos>${renderModulos(r.body.modulos)}</div>
      </section>`;
    bindCfg(cfg);
    bindModulos();
  }

  function bindCfg() {
    root.querySelector("[data-cfg]").addEventListener("submit", async e => {
      e.preventDefault();
      const b = root.querySelector("[data-curso]");
      const payload = {
        titulo: b.querySelector("[data-cfg-titulo]").value.trim() || null,
        descricao: b.querySelector("[data-cfg-desc]").value.trim() || null,
        imagem: b.querySelector("[data-cfg-img]").value.trim() || null,
        nota_minima: Number(b.querySelector("[data-cfg-nota]").value) || 70,
        certificado: b.querySelector("[data-cfg-cert]").checked,
        publicado: b.querySelector("[data-cfg-pub]").checked,
      };
      const r = await api(`/api/admin/escola/cursos/${encodeURIComponent(slugAtual)}`, { method: "PUT", body: JSON.stringify(payload) });
      toast(r.ok ? "Configuração salva." : (r.body.detail || "Erro ao salvar."), !r.ok);
    });
  }

  function renderModulos(modulos) {
    if (!modulos.length) return `<p class="escola-admin-empty">Nenhum módulo ainda. Crie o primeiro.</p>`;
    return modulos.map((m, i) => `
      <details class="escola-admin-modulo">
        <summary><span class="escola-admin-badge">${i + 1}</span> ${esc(m.titulo)} ${m.publicado ? "" : "<em>(rascunho)</em>"} <span class="escola-admin-count">${m.aulas.length} aula(s)${m.quiz ? " • avaliação" : ""}</span></summary>
        <div class="escola-admin-modulo-body">
          <form data-modulo-form="${m.id}" class="escola-admin-form">
            <label>Título<input data-f="titulo" value="${esc(m.titulo)}"></label>
            <label>Descrição<textarea data-f="descricao">${esc(m.descricao || "")}</textarea></label>
            <div class="escola-admin-row">
              <label>Ordem<input type="number" data-f="ordem" value="${m.ordem}"></label>
              <label>Nota mínima<input type="number" min="0" max="100" data-f="nota_minima" value="${m.nota_minima ?? ""}" placeholder="curso"></label>
              <label class="escola-admin-check"><input type="checkbox" data-f="publicado" ${m.publicado ? "checked" : ""}> Publicado</label>
            </div>
            <div class="escola-admin-actions">
              <button class="btn btn-small" type="submit">Salvar módulo</button>
              <button class="btn btn-small btn-ghost" type="button" data-dup="${m.id}">Duplicar</button>
              <button class="btn btn-small btn-ghost" type="button" data-del-mod="${m.id}">Excluir</button>
            </div>
          </form>

          <div class="escola-admin-aulas">
            <div class="escola-admin-card-head"><h3>Aulas</h3><button class="btn btn-small" type="button" data-nova-aula="${m.id}">+ Nova aula</button></div>
            ${m.aulas.map(a => renderAulaForm(a)).join("") || `<p class="escola-admin-empty">Sem aulas.</p>`}
          </div>

          <div class="escola-admin-quiz">
            <h3>Avaliação do módulo</h3>
            ${renderQuizForm(m)}
          </div>
        </div>
      </details>`).join("");
  }

  function renderAulaForm(a) {
    const tipos = ["texto", "video", "imagem", "material", "misto"];
    return `<form data-aula-form="${a.id}" class="escola-admin-subform">
      <div class="escola-admin-row">
        <label class="grow">Título<input data-f="titulo" value="${esc(a.titulo)}"></label>
        <label>Tipo<select data-f="tipo">${tipos.map(t => `<option value="${t}" ${a.tipo === t ? "selected" : ""}>${t}</option>`).join("")}</select></label>
        <label>Ordem<input type="number" data-f="ordem" value="${a.ordem}"></label>
      </div>
      <label>Descrição<input data-f="descricao" value="${esc(a.descricao || "")}"></label>
      <label>Conteúdo (texto/HTML)<textarea data-f="conteudo">${esc(a.conteudo || "")}</textarea></label>
      <div class="escola-admin-row">
        <label class="grow">Vídeo (URL)<input data-f="video_url" value="${esc(a.video_url || "")}"></label>
        <label class="grow">Material (URL)<input data-f="material_url" value="${esc(a.material_url || "")}"></label>
      </div>
      <div class="escola-admin-row">
        <label>Duração (min)<input type="number" data-f="duracao_min" value="${a.duracao_min ?? ""}"></label>
        <label>% mín. vídeo<input type="number" min="0" max="100" data-f="percentual_minimo" value="${a.percentual_minimo ?? ""}" placeholder="80"></label>
        <label class="escola-admin-check"><input type="checkbox" data-f="obrigatoria" ${a.obrigatoria ? "checked" : ""}> Obrigatória</label>
        <label class="escola-admin-check"><input type="checkbox" data-f="publicado" ${a.publicado ? "checked" : ""}> Publicada</label>
      </div>
      <div class="escola-admin-actions">
        <button class="btn btn-small" type="submit">Salvar aula</button>
        <button class="btn btn-small btn-ghost" type="button" data-del-aula="${a.id}">Excluir</button>
      </div>
    </form>`;
  }

  function renderQuizForm(m) {
    const q = m.quiz;
    return `<form data-quiz-form="${m.id}" class="escola-admin-subform">
      <div class="escola-admin-row">
        <label class="grow">Título<input data-f="titulo" value="${esc((q && q.titulo) || "Avaliação do módulo")}"></label>
        <label>Nota mín.<input type="number" min="0" max="100" data-f="nota_minima" value="${(q && q.nota_minima) ?? ""}" placeholder="curso"></label>
        <label>Nº perguntas<input type="number" min="1" data-f="num_perguntas" value="${(q && q.num_perguntas) ?? ""}" placeholder="todas"></label>
      </div>
      <div class="escola-admin-row">
        <label>Máx. tentativas<input type="number" min="1" data-f="max_tentativas" value="${(q && q.max_tentativas) ?? ""}" placeholder="∞"></label>
        <label>Intervalo (min)<input type="number" min="0" data-f="intervalo_min" value="${(q && q.intervalo_min) ?? 0}"></label>
        <label class="escola-admin-check"><input type="checkbox" data-f="embaralhar_perguntas" ${!q || q.embaralhar_perguntas ? "checked" : ""}> Embaralhar perguntas</label>
        <label class="escola-admin-check"><input type="checkbox" data-f="embaralhar_opcoes" ${!q || q.embaralhar_opcoes ? "checked" : ""}> Embaralhar opções</label>
      </div>
      <button class="btn btn-small" type="submit">${q ? "Salvar avaliação" : "Criar avaliação"}</button>
      ${q ? renderPerguntas(q) : `<p class="escola-admin-empty">Crie a avaliação para adicionar perguntas.</p>`}
    </form>`;
  }

  function renderPerguntas(q) {
    return `<div class="escola-admin-perguntas">
      <div class="escola-admin-card-head"><h4>Banco de perguntas</h4><button class="btn btn-small" type="button" data-nova-pergunta="${q.id}">+ Pergunta</button></div>
      ${(q.perguntas || []).map(p => `
        <div class="escola-admin-pergunta">
          <strong>${esc(p.enunciado)}</strong>
          <ul>${p.opcoes.map(o => `<li class="${o.correta ? "correta" : ""}">${o.correta ? "✓ " : ""}${esc(o.texto)}</li>`).join("")}</ul>
          ${p.explicacao ? `<em>${esc(p.explicacao)}</em>` : ""}
          <button class="btn btn-small btn-ghost" type="button" data-del-perg="${p.id}">Excluir pergunta</button>
        </div>`).join("") || `<p class="escola-admin-empty">Sem perguntas.</p>`}
    </div>`;
  }

  // ---- Bindings da árvore ----------------------------------------------
  function bindModulos() {
    const box = root.querySelector("[data-curso]");
    box.querySelector("[data-novo-modulo]")?.addEventListener("click", async () => {
      const titulo = prompt("Título do novo módulo:");
      if (!titulo) return;
      const r = await api("/api/admin/escola/modulos", { method: "POST", body: JSON.stringify({ slug: slugAtual, titulo, ordem: 99, publicado: false }) });
      toast(r.ok ? "Módulo criado." : (r.body.detail || "Erro."), !r.ok);
      if (r.ok) carregarCurso();
    });

    box.querySelectorAll("[data-modulo-form]").forEach(form => {
      form.addEventListener("submit", async e => {
        e.preventDefault();
        const id = form.dataset.moduloForm;
        const payload = {
          slug: slugAtual,
          titulo: form.querySelector('[data-f="titulo"]').value.trim(),
          descricao: form.querySelector('[data-f="descricao"]').value.trim() || null,
          ordem: Number(form.querySelector('[data-f="ordem"]').value) || 0,
          nota_minima: form.querySelector('[data-f="nota_minima"]').value ? Number(form.querySelector('[data-f="nota_minima"]').value) : null,
          publicado: form.querySelector('[data-f="publicado"]').checked,
        };
        const r = await api(`/api/admin/escola/modulos/${id}`, { method: "PUT", body: JSON.stringify(payload) });
        toast(r.ok ? "Módulo salvo." : (r.body.detail || "Erro."), !r.ok);
        if (r.ok) carregarCurso();
      });
    });
    box.querySelectorAll("[data-dup]").forEach(b => b.addEventListener("click", async () => {
      const r = await api(`/api/admin/escola/modulos/${b.dataset.dup}/duplicar`, { method: "POST" });
      toast(r.ok ? "Módulo duplicado." : "Erro.", !r.ok); if (r.ok) carregarCurso();
    }));
    box.querySelectorAll("[data-del-mod]").forEach(b => b.addEventListener("click", async () => {
      if (!confirm("Excluir este módulo? (bloqueado se houver progresso de aluno)")) return;
      const r = await api(`/api/admin/escola/modulos/${b.dataset.delMod}`, { method: "DELETE" });
      toast(r.ok ? "Módulo excluído." : (r.body.detail || "Não foi possível excluir."), !r.ok); if (r.ok) carregarCurso();
    }));

    box.querySelectorAll("[data-nova-aula]").forEach(b => b.addEventListener("click", async () => {
      const titulo = prompt("Título da nova aula:");
      if (!titulo) return;
      const r = await api("/api/admin/escola/aulas", { method: "POST", body: JSON.stringify({ modulo_id: Number(b.dataset.novaAula), titulo, ordem: 99, tipo: "texto", publicado: true, obrigatoria: true }) });
      toast(r.ok ? "Aula criada." : "Erro.", !r.ok); if (r.ok) carregarCurso();
    }));
    box.querySelectorAll("[data-aula-form]").forEach(form => {
      form.addEventListener("submit", async e => {
        e.preventDefault();
        const id = form.dataset.aulaForm;
        const num = sel => { const v = form.querySelector(sel).value; return v === "" ? null : Number(v); };
        const payload = {
          modulo_id: 0, // ignorado no update (mantém o vínculo); backend exige campo, então enviamos o real:
          titulo: form.querySelector('[data-f="titulo"]').value.trim(),
          descricao: form.querySelector('[data-f="descricao"]').value.trim() || null,
          tipo: form.querySelector('[data-f="tipo"]').value,
          conteudo: form.querySelector('[data-f="conteudo"]').value || null,
          video_url: form.querySelector('[data-f="video_url"]').value.trim() || null,
          material_url: form.querySelector('[data-f="material_url"]').value.trim() || null,
          ordem: Number(form.querySelector('[data-f="ordem"]').value) || 0,
          duracao_min: num('[data-f="duracao_min"]'),
          percentual_minimo: num('[data-f="percentual_minimo"]'),
          obrigatoria: form.querySelector('[data-f="obrigatoria"]').checked,
          publicado: form.querySelector('[data-f="publicado"]').checked,
        };
        const r = await api(`/api/admin/escola/aulas/${id}`, { method: "PUT", body: JSON.stringify(payload) });
        toast(r.ok ? "Aula salva." : (r.body.detail || "Erro."), !r.ok); if (r.ok) carregarCurso();
      });
    });
    box.querySelectorAll("[data-del-aula]").forEach(b => b.addEventListener("click", async () => {
      if (!confirm("Excluir esta aula?")) return;
      const r = await api(`/api/admin/escola/aulas/${b.dataset.delAula}`, { method: "DELETE" });
      toast(r.ok ? "Aula excluída." : "Erro.", !r.ok); if (r.ok) carregarCurso();
    }));

    box.querySelectorAll("[data-quiz-form]").forEach(form => {
      form.addEventListener("submit", async e => {
        e.preventDefault();
        const moduloId = Number(form.dataset.quizForm);
        const num = sel => { const v = form.querySelector(sel).value; return v === "" ? null : Number(v); };
        const payload = {
          modulo_id: moduloId,
          titulo: form.querySelector('[data-f="titulo"]').value.trim() || null,
          nota_minima: num('[data-f="nota_minima"]'),
          num_perguntas: num('[data-f="num_perguntas"]'),
          max_tentativas: num('[data-f="max_tentativas"]'),
          intervalo_min: Number(form.querySelector('[data-f="intervalo_min"]').value) || 0,
          embaralhar_perguntas: form.querySelector('[data-f="embaralhar_perguntas"]').checked,
          embaralhar_opcoes: form.querySelector('[data-f="embaralhar_opcoes"]').checked,
          publicado: true,
        };
        const r = await api("/api/admin/escola/quizzes", { method: "PUT", body: JSON.stringify(payload) });
        toast(r.ok ? "Avaliação salva." : (r.body.detail || "Erro."), !r.ok); if (r.ok) carregarCurso();
      });
    });
    box.querySelectorAll("[data-nova-pergunta]").forEach(b => b.addEventListener("click", () => novaPergunta(Number(b.dataset.novaPergunta))));
    box.querySelectorAll("[data-del-perg]").forEach(b => b.addEventListener("click", async () => {
      if (!confirm("Excluir esta pergunta?")) return;
      const r = await api(`/api/admin/escola/perguntas/${b.dataset.delPerg}`, { method: "DELETE" });
      toast(r.ok ? "Pergunta excluída." : "Erro.", !r.ok); if (r.ok) carregarCurso();
    }));
  }

  async function novaPergunta(quizId) {
    const enunciado = prompt("Enunciado da pergunta:");
    if (!enunciado) return;
    const opcoes = [];
    for (let i = 1; i <= 4; i++) {
      const t = prompt(`Alternativa ${i} (deixe vazio para parar):`);
      if (!t) break;
      opcoes.push({ texto: t, correta: false });
    }
    if (opcoes.length < 2) { alert("Cadastre ao menos 2 alternativas."); return; }
    const corretaNum = Number(prompt(`Qual alternativa é a correta? (1 a ${opcoes.length})`));
    if (!(corretaNum >= 1 && corretaNum <= opcoes.length)) { alert("Alternativa correta inválida."); return; }
    opcoes[corretaNum - 1].correta = true;
    const explicacao = prompt("Explicação (opcional):") || null;
    const r = await api("/api/admin/escola/perguntas", { method: "POST", body: JSON.stringify({ quiz_id: quizId, enunciado, tipo: "unica", explicacao, opcoes }) });
    toast(r.ok ? "Pergunta criada." : (r.body.detail || "Erro."), !r.ok); if (r.ok) carregarCurso();
  }

  // ---- Alunos -----------------------------------------------------------
  async function carregarAlunos() {
    const box = root.querySelector("[data-alunos]");
    box.innerHTML = "<p>Carregando alunos…</p>";
    const r = await api(`/api/admin/escola/alunos?slug=${encodeURIComponent(slugAtual)}`);
    if (!r.ok) { box.innerHTML = ""; return; }
    const alunos = r.body;
    box.innerHTML = `<section class="escola-admin-card">
      <h2>Alunos matriculados (${alunos.length})</h2>
      ${alunos.length ? `<table class="escola-admin-tabela"><thead><tr><th>Nome</th><th>E-mail</th><th>Progresso</th><th>Status</th><th>Ações</th></tr></thead>
        <tbody>${alunos.map(a => `<tr>
          <td>${esc(a.nome)}</td><td>${esc(a.email)}</td><td>${a.aulas_concluidas} aula(s)</td>
          <td>${a.suspenso ? "Suspenso" : "Ativo"}</td>
          <td class="escola-admin-aluno-acoes">
            ${a.suspenso ? `<button class="btn btn-small" data-reativar="${a.aluno_id}">Reativar</button>` : `<button class="btn btn-small btn-ghost" data-suspender="${a.aluno_id}">Suspender</button>`}
            <button class="btn btn-small btn-ghost" data-reset="${a.aluno_id}">Resetar progresso</button>
          </td></tr>`).join("")}</tbody></table>` : `<p class="escola-admin-empty">Nenhum aluno neste curso ainda.</p>`}
    </section>`;
    box.querySelectorAll("[data-suspender]").forEach(b => b.addEventListener("click", async () => {
      const r = await api("/api/admin/escola/alunos/suspender", { method: "POST", body: JSON.stringify({ aluno_id: Number(b.dataset.suspender), slug: slugAtual }) });
      toast(r.ok ? "Acesso suspenso." : "Erro.", !r.ok); if (r.ok) carregarAlunos();
    }));
    box.querySelectorAll("[data-reativar]").forEach(b => b.addEventListener("click", async () => {
      const r = await api("/api/admin/escola/alunos/liberar-curso", { method: "POST", body: JSON.stringify({ aluno_id: Number(b.dataset.reativar), slug: slugAtual }) });
      toast(r.ok ? "Acesso reativado." : "Erro.", !r.ok); if (r.ok) carregarAlunos();
    }));
    box.querySelectorAll("[data-reset]").forEach(b => b.addEventListener("click", async () => {
      if (!confirm("Resetar TODO o progresso deste aluno neste curso? Esta ação não pode ser desfeita.")) return;
      const r = await api("/api/admin/escola/alunos/resetar-progresso", { method: "POST", body: JSON.stringify({ aluno_id: Number(b.dataset.reset), slug: slugAtual, confirmar: true }) });
      toast(r.ok ? "Progresso resetado." : "Erro.", !r.ok); if (r.ok) carregarAlunos();
    }));
  }

  // ---- Boot -------------------------------------------------------------
  async function boot() {
    if (!(await estaLogado())) return renderLogin();
    renderShell();
    if (slugAtual) { carregarCurso(); carregarAlunos(); }
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", boot, { once: true });
  else boot();
})();
