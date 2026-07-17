(() => {
  "use strict";
  // Console administrativo do Estúdio de Conteúdo da Isis (Isis 2.0 — Fase 3).
  // Reutiliza a sessão administrativa do painel (cookie mistica_painel_sessao),
  // igual a escola-admin.js — nenhuma autenticação nova é criada aqui. Toda
  // validação de fato (feature flag, permissão, transições de status)
  // acontece no backend (/api/admin/isis-conteudo/*).

  const escapeHtml = value => String(value ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

  const STATUS_LABELS = {
    rascunho: "Rascunho",
    aprovado: "Aprovado",
    rejeitado: "Rejeitado",
    publicado: "Publicado",
  };

  const TIPO_LABELS = {
    bom_dia: "Bom dia",
    produto_do_dia: "Produto do dia",
  };

  function statusLabel(status) {
    return STATUS_LABELS[status] || escapeHtml(status || "");
  }

  function tipoLabel(tipo) {
    return TIPO_LABELS[tipo] || escapeHtml(tipo || "");
  }

  // Normaliza o texto de hashtags digitado por um administrador: remove
  // marcação HTML (defesa extra além do backend) e colapsa espaços.
  function sanitizeHashtagsInput(value) {
    return String(value ?? "").replace(/<[^>]*>/g, "").replace(/\s+/g, " ").trim();
  }

  function formatDataReferencia(data) {
    if (!data || !/^\d{4}-\d{2}-\d{2}$/.test(data)) return escapeHtml(data || "");
    const [ano, mes, dia] = data.split("-");
    return `${dia}/${mes}/${ano}`;
  }

  function podeEditar(draft) {
    return draft && draft.status === "rascunho";
  }

  function podeAprovar(draft) {
    return draft && draft.status === "rascunho";
  }

  function podeRejeitar(draft) {
    return draft && (draft.status === "rascunho" || draft.status === "aprovado");
  }

  function podePublicarManual(draft) {
    return draft && draft.status === "aprovado";
  }

  const IsisConteudoAdmin = {
    escapeHtml,
    statusLabel,
    tipoLabel,
    sanitizeHashtagsInput,
    formatDataReferencia,
    podeEditar,
    podeAprovar,
    podeRejeitar,
    podePublicarManual,
  };

  if (typeof window !== "undefined") {
    window.IsisConteudoAdmin = Object.assign(window.IsisConteudoAdmin || {}, IsisConteudoAdmin);
  }
  if (typeof module !== "undefined" && module.exports) {
    module.exports = IsisConteudoAdmin;
  }

  // ---- App (só roda em navegador; document.querySelector inexistente em Node) ----
  if (typeof document === "undefined" || !document.querySelector) return;

  const API = String((window.misticaSiteConfig || {}).apiBaseUrl || "https://api.misticaesotericos.com.br").replace(/\/$/, "");
  const root = document.querySelector("[data-admin-root]");
  if (!root) return;

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

  async function estaLogado() {
    const r = await api("/api/auth/me");
    return r.ok && (r.body.perfil === "adm" || (r.body.usuario && r.body.usuario.perfil === "adm") || r.body.autenticado);
  }

  function renderLogin(msg) {
    root.innerHTML = `
      <div class="escola-admin-login">
        <h1>Conteúdos da Isis</h1>
        <p>Entre com seu usuário administrador do painel.</p>
        <form data-login>
          <input placeholder="Usuário" data-login-user autocomplete="username" required>
          <input type="password" placeholder="Senha" data-login-pass autocomplete="current-password" required>
          <button class="btn" type="submit">Entrar</button>
        </form>
        <p class="escola-admin-status">${msg ? escapeHtml(msg) : ""}</p>
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

  function renderDesativado() {
    root.innerHTML = `
      <div class="escola-admin-card">
        <h2>Conteúdos da Isis</h2>
        <p class="escola-admin-status">O Estúdio de Conteúdo está desativado (MISTICA_ISIS_CONTENT_STUDIO_ENABLED=false). Nenhum rascunho é exibido ou gerado enquanto a flag estiver desligada.</p>
      </div>`;
  }

  function renderShell(flags) {
    root.innerHTML = `
      <div class="escola-admin-toast" data-toast hidden></div>
      <div class="escola-admin-header">
        <h1>Conteúdos da Isis</h1>
        <button class="btn btn-ghost btn-small" type="button" data-logout>Sair</button>
      </div>
      <div class="escola-admin-card">
        <p class="escola-admin-status">
          Geração automática: <strong>${flags.auto_generation_enabled ? "ligada" : "desligada"}</strong> ·
          Geração de imagem: <strong>${flags.image_generation_enabled ? "ligada" : "desligada"}</strong> ·
          Publicação automática: <strong>desligada (não implementada nesta fase)</strong>
        </p>
        <div class="escola-admin-row">
          <label class="grow">Data
            <input type="date" data-filtro-data>
          </label>
          <label class="grow">Status
            <select data-filtro-status>
              <option value="">Todos</option>
              <option value="rascunho">Rascunho</option>
              <option value="aprovado">Aprovado</option>
              <option value="rejeitado">Rejeitado</option>
              <option value="publicado">Publicado</option>
            </select>
          </label>
          <button class="btn" type="button" data-carregar>Filtrar</button>
          <button class="btn btn-ghost" type="button" data-gerar-hoje>Gerar rascunhos de hoje</button>
        </div>
      </div>
      <div data-lista></div>`;
    root.querySelector("[data-logout]").addEventListener("click", async () => { await api("/api/auth/logout", { method: "POST" }); renderLogin("Sessão encerrada."); });
    root.querySelector("[data-carregar]").addEventListener("click", carregarLista);
    root.querySelector("[data-gerar-hoje]").addEventListener("click", gerarHoje);
  }

  function draftCardHtml(draft) {
    const assets = (draft.assets || []).map(asset => `
      <div class="isis-conteudo-asset">
        <span>${escapeHtml(asset.variante)} (${asset.largura || "?"}×${asset.altura || "?"})</span>
        <a class="btn btn-ghost btn-small" href="${escapeHtml(asset.arquivo)}" target="_blank" rel="noopener">Baixar imagem</a>
      </div>`).join("") || `<p class="escola-admin-empty">Sem imagem gerada (geração de imagem desligada ou ainda não executada).</p>`;

    return `
      <div class="escola-admin-card" data-draft-card="${draft.id}">
        <div class="escola-admin-card-head">
          <h2>${tipoLabel(draft.tipo)} — ${formatDataReferencia(draft.data_referencia)}</h2>
          <span class="isis-conteudo-status isis-conteudo-status-${escapeHtml(draft.status)}">${statusLabel(draft.status)}</span>
        </div>
        ${draft.produto_nome ? `<p><strong>Produto:</strong> ${escapeHtml(draft.produto_nome)} (${escapeHtml(draft.produto_codigo || "")})</p>` : ""}
        ${draft.justificativa ? `<p class="escola-admin-status"><strong>Justificativa:</strong> ${escapeHtml(draft.justificativa)}</p>` : ""}
        <label>Legenda
          <textarea data-campo="legenda" ${podeEditar(draft) ? "" : "disabled"}>${escapeHtml(draft.legenda || "")}</textarea>
        </label>
        <label>Hashtags
          <input data-campo="hashtags" value="${escapeHtml(draft.hashtags || "")}" ${podeEditar(draft) ? "" : "disabled"}>
        </label>
        <label>Texto alternativo
          <input data-campo="texto_alternativo" value="${escapeHtml(draft.texto_alternativo || "")}" ${podeEditar(draft) ? "" : "disabled"}>
        </label>
        <p class="escola-admin-status"><strong>Prompt visual:</strong> ${escapeHtml(draft.prompt_visual || "")}</p>
        <div class="isis-conteudo-assets">${assets}</div>
        <div class="escola-admin-actions">
          ${podeEditar(draft) ? `<button class="btn btn-ghost btn-small" type="button" data-acao="salvar">Salvar edição</button>` : ""}
          ${podeEditar(draft) ? `<button class="btn btn-ghost btn-small" type="button" data-acao="regenerar-texto">Regenerar texto</button>` : ""}
          ${podeEditar(draft) ? `<button class="btn btn-ghost btn-small" type="button" data-acao="regenerar-imagem">Regenerar imagem</button>` : ""}
          <button class="btn btn-ghost btn-small" type="button" data-acao="copiar-legenda">Copiar legenda</button>
          ${podeAprovar(draft) ? `<button class="btn btn-small" type="button" data-acao="aprovar">Aprovar</button>` : ""}
          ${podeRejeitar(draft) ? `<button class="btn btn-ghost btn-small" type="button" data-acao="rejeitar">Rejeitar</button>` : ""}
          ${podePublicarManual(draft) ? `<button class="btn btn-small" type="button" data-acao="publicar-manual">Marcar como publicado manualmente</button>` : ""}
        </div>
      </div>`;
  }

  function ligarAcoesDoCard(container, draft) {
    const card = container.querySelector(`[data-draft-card="${draft.id}"]`);
    if (!card) return;
    card.querySelectorAll("[data-acao]").forEach(botao => {
      botao.addEventListener("click", () => executarAcao(draft.id, botao.dataset.acao, card));
    });
  }

  async function executarAcao(draftId, acao, card) {
    if (acao === "salvar") {
      const payload = {
        legenda: card.querySelector('[data-campo="legenda"]').value,
        hashtags: sanitizeHashtagsInput(card.querySelector('[data-campo="hashtags"]').value),
        texto_alternativo: card.querySelector('[data-campo="texto_alternativo"]').value,
      };
      const r = await api(`/api/admin/isis-conteudo/drafts/${draftId}`, { method: "PUT", body: JSON.stringify(payload) });
      return r.ok ? (toast("Rascunho atualizado."), carregarLista()) : toast(r.body.detail || "Falha ao salvar.", true);
    }
    if (acao === "regenerar-texto") {
      const r = await api(`/api/admin/isis-conteudo/drafts/${draftId}/regenerar-texto`, { method: "POST" });
      return r.ok ? (toast("Texto regenerado."), carregarLista()) : toast(r.body.detail || "Falha ao regenerar texto.", true);
    }
    if (acao === "regenerar-imagem") {
      const r = await api(`/api/admin/isis-conteudo/drafts/${draftId}/regenerar-imagem`, { method: "POST" });
      return r.ok ? (toast("Imagem regenerada."), carregarLista()) : toast(r.body.detail || "Falha ao regenerar imagem.", true);
    }
    if (acao === "copiar-legenda") {
      const texto = card.querySelector('[data-campo="legenda"]').value;
      try { await navigator.clipboard.writeText(texto); toast("Legenda copiada."); } catch { toast("Não foi possível copiar.", true); }
      return;
    }
    if (acao === "aprovar") {
      const r = await api(`/api/admin/isis-conteudo/drafts/${draftId}/aprovar`, { method: "POST" });
      return r.ok ? (toast("Aprovado."), carregarLista()) : toast(r.body.detail || "Falha ao aprovar.", true);
    }
    if (acao === "rejeitar") {
      const motivo = window.prompt("Motivo da rejeição:");
      if (!motivo) return;
      const r = await api(`/api/admin/isis-conteudo/drafts/${draftId}/rejeitar`, { method: "POST", body: JSON.stringify({ motivo }) });
      return r.ok ? (toast("Rejeitado."), carregarLista()) : toast(r.body.detail || "Falha ao rejeitar.", true);
    }
    if (acao === "publicar-manual") {
      const r = await api(`/api/admin/isis-conteudo/drafts/${draftId}/publicar-manual`, { method: "POST" });
      return r.ok ? (toast("Marcado como publicado."), carregarLista()) : toast(r.body.detail || "Falha ao marcar publicado.", true);
    }
  }

  async function carregarLista() {
    const lista = root.querySelector("[data-lista]");
    if (!lista) return;
    lista.innerHTML = "<p>Carregando rascunhos…</p>";
    const dataFiltro = root.querySelector("[data-filtro-data]").value;
    const statusFiltro = root.querySelector("[data-filtro-status]").value;
    const params = new URLSearchParams();
    if (dataFiltro) params.set("data_referencia", dataFiltro);
    if (statusFiltro) params.set("status", statusFiltro);
    const r = await api(`/api/admin/isis-conteudo/drafts?${params.toString()}`);
    if (!r.ok) { lista.innerHTML = `<p class="escola-admin-status">${escapeHtml(r.body.detail || "Não foi possível carregar.")}</p>`; return; }
    const drafts = r.body.drafts || [];
    if (!drafts.length) { lista.innerHTML = `<p class="escola-admin-empty">Nenhum rascunho encontrado.</p>`; return; }
    lista.innerHTML = drafts.map(draftCardHtml).join("");
    drafts.forEach(draft => ligarAcoesDoCard(lista, draft));
  }

  async function gerarHoje() {
    const r = await api("/api/admin/isis-conteudo/gerar-diario", { method: "POST", body: JSON.stringify({}) });
    if (!r.ok) return toast(r.body.detail || "Falha ao gerar rascunhos.", true);
    toast(r.body.reaproveitado ? "Rascunhos de hoje já existiam." : "Rascunhos de hoje gerados.");
    carregarLista();
  }

  async function boot() {
    if (!(await estaLogado())) return renderLogin();
    const r = await api("/api/admin/isis-conteudo/status");
    if (!r.ok) return renderLogin(r.body.detail || "Sessão inválida.");
    if (!r.body.content_studio_enabled) return renderDesativado();
    renderShell(r.body);
    carregarLista();
  }

  boot();
})();
