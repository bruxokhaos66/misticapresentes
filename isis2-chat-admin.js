// Painel administrativo "Isis — Chat Inteligente".
//
// Injeta um painel dentro de #adminContent (mesmo padrão de
// isis2-homolog-admin.js), visível só para quem já está autenticado como
// admin no painel. Todas as chamadas usam credentials:"include". Este
// painel é SOMENTE LEITURA para as flags (elas só mudam por variável de
// ambiente do servidor -- nunca por aqui, nunca editando o .env) e só
// permite uma ação segura: limpar sessões expiradas.
(() => {
  const cfg = window.misticaSiteConfig || {};
  const API_BASE = String(cfg.apiBaseUrl || "https://api.misticaesotericos.com.br").replace(/\/$/, "");

  const ready = (fn) => (document.readyState === "loading" ? document.addEventListener("DOMContentLoaded", fn) : fn());
  const esc = (value) => String(value ?? "").replace(/[&<>"']/g, (ch) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[ch]));

  ready(() => {
    const adminContent = document.getElementById("adminContent");
    if (!adminContent || document.getElementById("isisChatAdminPanel")) return;

    const panel = document.createElement("section");
    panel.id = "isisChatAdminPanel";
    panel.className = "form-panel isis-chat-admin-panel";
    panel.innerHTML = `
      <p class="eyebrow">Isis 2.0</p>
      <h2>Isis — Chat Inteligente</h2>
      <p class="privacy-note">
        Chat de recomendação de produtos e apoio comercial, em homologação controlada. Não ativa o
        Estúdio Inteligente de Conteúdo (Fase 3) -- as flags dos dois módulos são independentes.
        Flags reais só mudam por variável de ambiente do servidor (nunca por este painel).
      </p>
      <div class="warning-box" data-isis-chat-status>Consultando estado...</div>

      <h3>Métricas de hoje</h3>
      <div class="admin-product-list" data-isis-chat-metricas>Carregando métricas...</div>

      <h3>Sessões recentes</h3>
      <div class="checkout-actions">
        <button class="btn btn-ghost" type="button" data-isis-chat-limpar-expiradas>Limpar sessões expiradas</button>
      </div>
      <div class="warning-box" data-isis-chat-limpeza-status hidden></div>
      <div class="admin-product-list" data-isis-chat-sessoes>Carregando sessões...</div>
    `;

    const audioPanel = adminContent.querySelector(".audio-admin-panel");
    adminContent.insertBefore(panel, audioPanel || adminContent.firstChild);

    const statusBox = panel.querySelector("[data-isis-chat-status]");
    const metricasBox = panel.querySelector("[data-isis-chat-metricas]");
    const sessoesBox = panel.querySelector("[data-isis-chat-sessoes]");
    const limpezaStatus = panel.querySelector("[data-isis-chat-limpeza-status]");
    const btnLimpar = panel.querySelector("[data-isis-chat-limpar-expiradas]");

    const renderStatus = (config) => {
      const chat = (config && config.chat) || {};
      const estudio = (config && config.content_studio_fase3) || {};
      statusBox.className = chat.chat_enabled ? "warning-box" : "warning-box warning-danger";
      statusBox.innerHTML = `
        Chat: <strong>${chat.chat_enabled ? "LIGADO" : "DESLIGADO"}</strong> ·
        Homologação: <strong>${chat.chat_homolog_enabled ? "LIGADA" : "DESLIGADA"}</strong> ·
        IA: <strong>${chat.chat_ai_enabled ? "LIGADA (sem provedor configurado)" : "DESLIGADA (modo determinístico)"}</strong> ·
        Recomendações: <strong>${chat.chat_product_recommendations_enabled ? "LIGADAS" : "DESLIGADAS"}</strong><br>
        Limites: ${esc(chat.limits?.max_messages_per_session)} msgs/sessão ·
        ${esc(chat.limits?.max_sessions_per_hour)} sessões/hora ·
        TTL ${esc(chat.limits?.session_ttl_minutes)} min ·
        custo diário máx. ${esc(chat.limits?.daily_cost_limit_cents)} centavos<br>
        <small>Estúdio de Conteúdo (Fase 3): ${estudio.content_studio_enabled ? "ATIVO" : "desativado"} (independente deste chat).</small>
      `;
    };

    const carregarConfig = async () => {
      try {
        const response = await fetch(`${API_BASE}/api/admin/isis2/chat/config`, { credentials: "include", cache: "no-store" });
        if (!response.ok) throw new Error();
        renderStatus(await response.json());
      } catch {
        statusBox.className = "warning-box warning-danger";
        statusBox.textContent = "Não foi possível consultar o estado do chat agora.";
      }
    };

    const renderMetricas = (m) => {
      metricasBox.innerHTML = `
        <article class="admin-product-item">
          <div class="admin-product-thumb">💬</div>
          <div>
            <strong>${esc(m.sessoes_iniciadas_hoje)} sessões iniciadas hoje</strong>
            <span>${esc(m.sessoes_ativas_agora)} ativas agora · ${esc(m.sessoes_expiradas_total)} expiradas (total)</span>
            <small>${esc(m.mensagens_recebidas_hoje)} mensagens · ${esc(m.recomendacoes_exibidas_hoje)} recomendações · ${esc(m.kits_sugeridos_hoje)} kits · ${esc(m.fallback_sem_resultado_hoje)} sem resultado · ${esc(m.prompt_injection_bloqueado_hoje)} tentativas de prompt injection bloqueadas</small>
            <small>Chamadas de IA hoje: ${esc(m.chamadas_ia_hoje)} · Custo estimado: R$ ${(Number(m.custo_estimado_centavos_hoje || 0) / 100).toFixed(2)}</small>
          </div>
        </article>
      `;
    };

    const carregarMetricas = async () => {
      try {
        const response = await fetch(`${API_BASE}/api/admin/isis2/chat/metricas`, { credentials: "include", cache: "no-store" });
        if (!response.ok) throw new Error();
        renderMetricas(await response.json());
      } catch {
        metricasBox.innerHTML = '<div class="history-item"><span>Falha ao carregar métricas.</span></div>';
      }
    };

    const renderSessoes = (sessoes) => {
      if (!sessoes.length) {
        sessoesBox.innerHTML = '<div class="history-item"><span>Nenhuma sessão registrada ainda.</span></div>';
        return;
      }
      sessoesBox.innerHTML = sessoes.slice(0, 20).map((s) => `
        <article class="admin-product-item">
          <div class="admin-product-thumb">🗂️</div>
          <div>
            <strong>${esc(s.user_type)} · ${esc(s.status)}</strong>
            <span>Intenção atual: ${esc(s.intent_atual || "-")}</span>
            <small>${esc(s.contador_mensagens)} mensagens · criada em ${esc(s.criado_em)} · último acesso ${esc(s.ultimo_acesso)}</small>
          </div>
        </article>
      `).join("");
    };

    const carregarSessoes = async () => {
      try {
        const response = await fetch(`${API_BASE}/api/admin/isis2/chat/sessoes`, { credentials: "include", cache: "no-store" });
        if (!response.ok) throw new Error();
        const dados = await response.json();
        renderSessoes(dados.sessoes || []);
      } catch {
        sessoesBox.innerHTML = '<div class="history-item"><span>Falha ao carregar sessões.</span></div>';
      }
    };

    btnLimpar.addEventListener("click", async () => {
      try {
        const response = await fetch(`${API_BASE}/api/admin/isis2/chat/sessoes/limpar-expiradas`, {
          method: "POST",
          credentials: "include",
        });
        if (!response.ok) throw new Error("Não foi possível limpar as sessões expiradas.");
        const dados = await response.json();
        limpezaStatus.hidden = false;
        limpezaStatus.className = "warning-box";
        limpezaStatus.textContent = `${dados.removidas} sessão(ões) expirada(s) removida(s).`;
        await carregarSessoes();
      } catch (error) {
        limpezaStatus.hidden = false;
        limpezaStatus.className = "warning-box warning-danger";
        limpezaStatus.textContent = error.message || "Falha ao limpar sessões.";
      }
    });

    carregarConfig();
    carregarMetricas();
    carregarSessoes();
  });
})();
