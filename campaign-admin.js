(() => {
  const cfg = window.misticaSiteConfig || {};
  const API_BASE = String(cfg.apiBaseUrl || "https://api.misticaesotericos.com.br").replace(/\/$/, "");

  const ready = (fn) => (document.readyState === "loading" ? document.addEventListener("DOMContentLoaded", fn) : fn());
  const money = new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" });
  const esc = (value) => String(value ?? "").replace(/[&<>"']/g, (ch) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[ch]));

  const TIPOS = {
    banner: "Banner (só divulgação)",
    desconto_percentual: "Desconto percentual",
    desconto_fixo: "Desconto em reais",
    frete_gratis: "Frete grátis",
  };

  ready(() => {
    const adminContent = document.getElementById("adminContent");
    if (!adminContent) return;

    let editingId = null;
    let campanhas = [];

    const panel = document.createElement("section");
    panel.className = "form-panel campaign-admin-panel";
    panel.innerHTML = `
      <p class="eyebrow">Marketing</p>
      <h2>Campanhas promocionais</h2>
      <p class="privacy-note">Crie banners e descontos com período de vigência. Só campanhas ativas e dentro do período aparecem no site.</p>
      <div class="warning-box" data-campaign-admin-status>Carregando campanhas...</div>
      <form id="campaignAdminForm" class="admin-product-form">
        <input type="hidden" id="campaignId">
        <div class="admin-product-grid">
          <label>Título
            <input id="campaignTitulo" type="text" placeholder="Ex.: Black Friday Mística" required>
          </label>
          <label>Tipo
            <select id="campaignTipo">
              ${Object.entries(TIPOS).map(([valor, rotulo]) => `<option value="${valor}">${rotulo}</option>`).join("")}
            </select>
          </label>
          <label>Valor (% ou R$, conforme o tipo)
            <input id="campaignValor" type="number" min="0" step="0.01" value="0">
          </label>
          <label>Código do cupom (opcional)
            <input id="campaignCupom" type="text" placeholder="Ex.: BF20">
          </label>
          <label>Início da vigência
            <input id="campaignInicio" type="datetime-local">
          </label>
          <label>Fim da vigência
            <input id="campaignFim" type="datetime-local">
          </label>
        </div>
        <label>Descrição / texto do banner
          <textarea id="campaignDescricao" rows="3" placeholder="Texto exibido no banner do site."></textarea>
        </label>
        <label>Link opcional (produto, categoria, WhatsApp...)
          <input id="campaignLink" type="url" placeholder="https://...">
        </label>
        <label class="campaign-active-toggle"><input id="campaignAtivo" type="checkbox" checked> Campanha ativa</label>
        <div class="checkout-actions">
          <button class="btn" type="submit">Salvar campanha</button>
          <button class="btn btn-ghost" type="button" data-new-campaign>Nova campanha</button>
        </div>
      </form>
      <div class="admin-product-list" data-campaign-admin-list></div>
    `;

    const audioPanel = adminContent.querySelector(".audio-admin-panel");
    adminContent.insertBefore(panel, audioPanel || adminContent.firstChild);

    const status = panel.querySelector("[data-campaign-admin-status]");
    const list = panel.querySelector("[data-campaign-admin-list]");
    const form = panel.querySelector("#campaignAdminForm");

    const setStatus = (message, ok = false) => {
      status.textContent = message;
      status.className = ok ? "warning-box" : "warning-box warning-danger";
    };

    const clearForm = () => {
      editingId = null;
      form.reset();
      panel.querySelector("#campaignId").value = "";
      panel.querySelector("#campaignAtivo").checked = true;
    };

    const toDatetimeLocal = (isoValue) => {
      if (!isoValue) return "";
      return String(isoValue).slice(0, 16);
    };

    const readFormPayload = () => ({
      titulo: panel.querySelector("#campaignTitulo").value.trim(),
      descricao: panel.querySelector("#campaignDescricao").value.trim(),
      tipo: panel.querySelector("#campaignTipo").value,
      valor: Number(panel.querySelector("#campaignValor").value) || 0,
      codigo_cupom: panel.querySelector("#campaignCupom").value.trim() || null,
      link: panel.querySelector("#campaignLink").value.trim() || null,
      ativo: panel.querySelector("#campaignAtivo").checked,
      data_inicio: panel.querySelector("#campaignInicio").value || null,
      data_fim: panel.querySelector("#campaignFim").value || null,
    });

    const renderList = () => {
      if (!campanhas.length) {
        list.innerHTML = '<div class="history-item"><span>Nenhuma campanha cadastrada ainda.</span></div>';
        return;
      }
      list.innerHTML = campanhas.map((campanha) => `
        <article class="admin-product-item">
          <div class="admin-product-thumb">${campanha.ativo ? "📣" : "⏸️"}</div>
          <div>
            <strong>${esc(campanha.titulo)}</strong>
            <span>${esc(TIPOS[campanha.tipo] || campanha.tipo)}${campanha.valor ? ` • ${campanha.tipo === "desconto_fixo" ? money.format(campanha.valor) : `${campanha.valor}%`}` : ""}</span>
            <span>${campanha.ativo ? "Ativa" : "Inativa"}${campanha.codigo_cupom ? ` • Cupom: ${esc(campanha.codigo_cupom)}` : ""}</span>
            <small>${esc(campanha.descricao || "Sem descrição.")}</small>
          </div>
          <div class="admin-product-actions">
            <button class="btn btn-ghost" type="button" data-edit-campaign="${campanha.id}">Editar</button>
            <button class="btn btn-ghost" type="button" data-delete-campaign="${campanha.id}">Excluir</button>
          </div>
        </article>
      `).join("");
    };

    const loadCampanhas = async () => {
      try {
        const response = await fetch(`${API_BASE}/api/campanhas`, { credentials: "include" });
        if (!response.ok) throw new Error("Não foi possível carregar as campanhas.");
        campanhas = await response.json();
        renderList();
        setStatus(`Campanhas atualizadas: ${campanhas.length} cadastrada(s).`, true);
      } catch (error) {
        setStatus(error.message || "Falha ao carregar campanhas.");
      }
    };

    const editCampaign = (id) => {
      const campanha = campanhas.find((item) => String(item.id) === String(id));
      if (!campanha) return;
      editingId = campanha.id;
      panel.querySelector("#campaignId").value = campanha.id;
      panel.querySelector("#campaignTitulo").value = campanha.titulo || "";
      panel.querySelector("#campaignTipo").value = campanha.tipo || "banner";
      panel.querySelector("#campaignValor").value = campanha.valor || 0;
      panel.querySelector("#campaignCupom").value = campanha.codigo_cupom || "";
      panel.querySelector("#campaignLink").value = campanha.link || "";
      panel.querySelector("#campaignDescricao").value = campanha.descricao || "";
      panel.querySelector("#campaignAtivo").checked = Boolean(campanha.ativo);
      panel.querySelector("#campaignInicio").value = toDatetimeLocal(campanha.data_inicio);
      panel.querySelector("#campaignFim").value = toDatetimeLocal(campanha.data_fim);
      window.scrollTo({ top: panel.offsetTop - 20, behavior: "smooth" });
    };

    const deleteCampaign = async (id) => {
      if (!window.confirm("Excluir esta campanha?")) return;
      try {
        const response = await fetch(`${API_BASE}/api/campanhas/${encodeURIComponent(id)}`, { method: "DELETE", credentials: "include" });
        if (!response.ok) throw new Error("Não foi possível excluir a campanha.");
        setStatus("Campanha excluída.", true);
        await loadCampanhas();
      } catch (error) {
        setStatus(error.message || "Falha ao excluir campanha.");
      }
    };

    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      const payload = readFormPayload();
      if (!payload.titulo) return setStatus("Informe o título da campanha.");
      try {
        const url = editingId ? `${API_BASE}/api/campanhas/${editingId}` : `${API_BASE}/api/campanhas`;
        const response = await fetch(url, {
          method: editingId ? "PUT" : "POST",
          credentials: "include",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });
        const data = await response.json().catch(() => ({}));
        if (!response.ok || !data.ok) throw new Error(data.detail || "Falha ao salvar campanha.");
        setStatus(editingId ? "Campanha atualizada." : "Campanha criada.", true);
        clearForm();
        await loadCampanhas();
      } catch (error) {
        setStatus(error.message || "Falha ao salvar campanha.");
      }
    });

    panel.querySelector("[data-new-campaign]").addEventListener("click", clearForm);
    list.addEventListener("click", (event) => {
      const editBtn = event.target.closest("[data-edit-campaign]");
      if (editBtn) return editCampaign(editBtn.dataset.editCampaign);
      const delBtn = event.target.closest("[data-delete-campaign]");
      if (delBtn) return deleteCampaign(delBtn.dataset.deleteCampaign);
    });

    loadCampanhas();
  });
})();
