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

  // Mapeia um status HTTP de falha para uma mensagem segura ao usuário, sem
  // vazar detalhes internos (stack trace, corpo bruto da resposta etc.).
  const mensagemErroHttp = (status, mensagemPadrao) => {
    if (status === 401) return "Sessão expirada. Faça login novamente.";
    if (status === 403) return "Você não tem permissão para realizar esta ação.";
    if (status === 404) return "Campanha não encontrada. Ela pode já ter sido removida.";
    return mensagemPadrao;
  };

  // Erros de fetch() que nunca chegam a uma resposta HTTP (rede fora do ar,
  // CORS bloqueado, DNS etc.) chegam aqui como TypeError, sem `status`.
  const mensagemErroRede = (error, mensagemPadrao) => {
    if (error instanceof TypeError) return "Não foi possível conectar à API. Verifique sua conexão.";
    return (error && error.message) || mensagemPadrao;
  };

  // Classifica o status visível da campanha combinando o campo `ativo` com
  // as datas de vigência e o horário atual. Isso é só apresentação no
  // painel administrativo -- não influencia em nada a regra usada pela rota
  // pública /api/campanhas/ativas (essa continua só no backend).
  const classificarStatus = (campanha, agora) => {
    const inicio = campanha.data_inicio ? new Date(campanha.data_inicio) : null;
    const fim = campanha.data_fim ? new Date(campanha.data_fim) : null;
    if (!campanha.ativo) {
      return campanha.data_fim ? { rotulo: "Encerrada", icone: "🔚" } : { rotulo: "Inativa", icone: "⏸️" };
    }
    if (inicio && !Number.isNaN(inicio.getTime()) && inicio > agora) return { rotulo: "Agendada", icone: "🕒" };
    if (fim && !Number.isNaN(fim.getTime()) && fim < agora) return { rotulo: "Expirada", icone: "⌛" };
    return { rotulo: "Ativa", icone: "📣" };
  };

  ready(() => {
    const adminContent = document.getElementById("adminContent");
    if (!adminContent) return;

    let editingId = null;
    let campanhas = [];
    let carregando = false;
    const idsEmProcessamento = new Set();

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
      const agora = new Date();
      list.innerHTML = campanhas.map((campanha) => {
        const situacao = classificarStatus(campanha, agora);
        const emProcessamento = idsEmProcessamento.has(String(campanha.id));
        return `
        <article class="admin-product-item">
          <div class="admin-product-thumb">${situacao.icone}</div>
          <div>
            <strong>${esc(campanha.titulo)}</strong>
            <span>${esc(TIPOS[campanha.tipo] || campanha.tipo)}${campanha.valor ? ` • ${campanha.tipo === "desconto_fixo" ? money.format(campanha.valor) : `${campanha.valor}%`}` : ""}</span>
            <span>${esc(situacao.rotulo)}${campanha.codigo_cupom ? ` • Cupom: ${esc(campanha.codigo_cupom)}` : ""}</span>
            <small>${esc(campanha.descricao || "Sem descrição.")}</small>
          </div>
          <div class="admin-product-actions">
            <button class="btn btn-ghost" type="button" data-edit-campaign="${campanha.id}">Editar</button>
            ${campanha.ativo ? `<button class="btn btn-ghost" type="button" data-end-campaign="${campanha.id}" ${emProcessamento ? "disabled" : ""}>Encerrar campanha</button>` : ""}
            <button class="btn btn-ghost" type="button" data-delete-campaign="${campanha.id}" ${emProcessamento ? "disabled" : ""}>Excluir</button>
          </div>
        </article>
      `;
      }).join("");
    };

    const loadCampanhas = async () => {
      // Evita corridas: se já existe uma busca em andamento (ex.: o carregamento
      // inicial e o evento de desbloqueio disparam quase juntos), a segunda
      // chamada não dispara outra requisição -- só a primeira em voo importa,
      // pois ambas buscam exatamente a mesma lista.
      if (carregando) return;
      carregando = true;
      try {
        const response = await fetch(`${API_BASE}/api/campanhas`, { credentials: "include" });
        if (!response.ok) throw new Error(mensagemErroHttp(response.status, "Não foi possível carregar as campanhas."));
        campanhas = await response.json();
        renderList();
        setStatus(`Campanhas atualizadas: ${campanhas.length} cadastrada(s).`, true);
      } catch (error) {
        setStatus(mensagemErroRede(error, "Não foi possível carregar as campanhas."));
      } finally {
        carregando = false;
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
      const chave = String(id);
      if (idsEmProcessamento.has(chave)) return;
      idsEmProcessamento.add(chave);
      renderList();
      try {
        const response = await fetch(`${API_BASE}/api/campanhas/${encodeURIComponent(id)}`, { method: "DELETE", credentials: "include" });
        if (!response.ok) throw new Error(mensagemErroHttp(response.status, "Não foi possível excluir a campanha."));
        setStatus("Campanha excluída.", true);
        await loadCampanhas();
      } catch (error) {
        setStatus(mensagemErroRede(error, "Não foi possível excluir a campanha."));
      } finally {
        idsEmProcessamento.delete(chave);
        renderList();
      }
    };

    const endCampaign = async (id) => {
      if (!window.confirm("Tem certeza de que deseja encerrar esta campanha? Ela deixará de aparecer no site imediatamente.")) return;
      const chave = String(id);
      if (idsEmProcessamento.has(chave)) return;
      idsEmProcessamento.add(chave);
      renderList();
      try {
        const response = await fetch(`${API_BASE}/api/campanhas/${encodeURIComponent(id)}/encerrar`, {
          method: "POST",
          credentials: "include",
        });
        if (!response.ok) throw new Error(mensagemErroHttp(response.status, "Não foi possível encerrar a campanha."));
        setStatus("Campanha encerrada.", true);
        await loadCampanhas();
      } catch (error) {
        setStatus(mensagemErroRede(error, "Não foi possível encerrar a campanha."));
      } finally {
        idsEmProcessamento.delete(chave);
        renderList();
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
        if (!response.ok || !data.ok) throw new Error(mensagemErroHttp(response.status, data.detail || "Falha ao salvar campanha."));
        setStatus(editingId ? "Campanha atualizada." : "Campanha criada.", true);
        clearForm();
        await loadCampanhas();
      } catch (error) {
        setStatus(mensagemErroRede(error, "Falha ao salvar campanha."));
      }
    });

    panel.querySelector("[data-new-campaign]").addEventListener("click", clearForm);
    list.addEventListener("click", (event) => {
      const editBtn = event.target.closest("[data-edit-campaign]");
      if (editBtn) return editCampaign(editBtn.dataset.editCampaign);
      const endBtn = event.target.closest("[data-end-campaign]");
      if (endBtn) return endCampaign(endBtn.dataset.endCampaign);
      const delBtn = event.target.closest("[data-delete-campaign]");
      if (delBtn) return deleteCampaign(delBtn.dataset.deleteCampaign);
    });

    // Carga inicial: cobre o caso de a página já abrir com uma sessão válida
    // (cookie de sessão persistido de um login anterior).
    loadCampanhas();

    // Esse painel pode ser injetado (carregarPainelAdmin, em site-config.js)
    // antes de a sessão existir -- a primeira loadCampanhas() acima roda sem
    // cookie e recebe 401. site-config.js dispara "mistica:admin-unlocked"
    // assim que o painel é autorizado e liberado (login novo ou sessão
    // restaurada), então escutamos aqui para tentar de novo sem exigir F5.
    // O guard em window evita empilhar um novo listener por instância caso
    // este script seja injetado mais de uma vez na mesma página.
    if (!window.__misticaCampaignAdminUnlockListenerInstalled) {
      window.__misticaCampaignAdminUnlockListenerInstalled = true;
      window.addEventListener("mistica:admin-unlocked", () => loadCampanhas());
    }
  });
})();
