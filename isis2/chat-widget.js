// Isis Chat (homologação controlada) — widget (UI).
//
// Injetado só por isis2/chat-gate.js, depois de o servidor confirmar
// autorização (GET /api/isis2/chat/config -> {enabled:true,
// authorized:true}). Toda ação de estado (criar sessão, enviar mensagem,
// encerrar) chama o backend com `credentials: "include"` -- nunca decide
// autorização no navegador. Todo conteúdo dinâmico passa por escapeHtml()
// antes de entrar em innerHTML.
(() => {
  if (window.__MISTICA_ISIS_CHAT_WIDGET__) return;
  window.__MISTICA_ISIS_CHAT_WIDGET__ = true;

  const scriptTag = document.getElementById("misticaIsisChatWidgetScript");
  const API_BASE = String((scriptTag && scriptTag.dataset.apiBase) || window.misticaSiteConfig?.apiBaseUrl || "").replace(/\/$/, "");

  const esc = (value) => String(value ?? "").replace(/[&<>"']/g, (ch) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[ch]));

  const QUICK_REPLIES = ["Quero relaxar", "Procurar um presente", "Montar um kit", "Ver cursos", "Comparar produtos"];

  let sessionId = null;
  let remaining = null;
  let sending = false;
  let lastFocused = null;

  function ready(fn) {
    if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", fn);
    else fn();
  }

  function montarDOM() {
    if (document.getElementById("isis-chat-root")) return;
    const root = document.createElement("div");
    root.id = "isis-chat-root";
    root.innerHTML = `
      <button type="button" class="isis-chat-fab" id="isisChatOpenBtn" aria-haspopup="dialog" aria-controls="isisChatPanel" aria-label="Abrir chat com a Isis">
        <span class="isis-chat-fab-avatar" aria-hidden="true">☾</span>
        <span>Falar com a Isis</span>
      </button>
      <section class="isis-chat-panel" id="isisChatPanel" role="dialog" aria-modal="false" aria-label="Chat com a Isis" hidden>
        <header class="isis-chat-header">
          <span class="isis-chat-title">Isis</span>
          <span class="isis-chat-badge">Isis em homologação</span>
          <button type="button" class="isis-chat-close" id="isisChatCloseBtn" aria-label="Fechar chat">✕</button>
        </header>
        <p class="isis-chat-privacy">A Isis usa as informações desta conversa apenas para ajudar na recomendação de produtos e melhorar o atendimento.</p>
        <div class="isis-chat-log" id="isisChatLog" role="log" aria-live="polite"></div>
        <div class="isis-chat-quick" id="isisChatQuick"></div>
        <p class="isis-chat-error" id="isisChatError" hidden></p>
        <form class="isis-chat-form" id="isisChatForm">
          <label class="sr-only" for="isisChatInput">Mensagem para a Isis</label>
          <input class="isis-chat-input" id="isisChatInput" type="text" maxlength="1000" autocomplete="off" placeholder="Digite sua mensagem..." />
          <button type="submit" class="isis-chat-send" id="isisChatSendBtn">Enviar</button>
        </form>
      </section>
    `;
    document.body.appendChild(root);

    document.getElementById("isisChatOpenBtn").addEventListener("click", abrirPainel);
    document.getElementById("isisChatCloseBtn").addEventListener("click", fecharPainel);
    document.getElementById("isisChatForm").addEventListener("submit", aoEnviar);
    document.getElementById("isisChatPanel").addEventListener("keydown", aoTeclado);

    renderQuickReplies();
  }

  function renderQuickReplies() {
    const container = document.getElementById("isisChatQuick");
    container.innerHTML = "";
    QUICK_REPLIES.forEach((texto) => {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.textContent = texto;
      btn.addEventListener("click", () => enviarTexto(texto));
      container.appendChild(btn);
    });
  }

  function aoTeclado(evento) {
    if (evento.key === "Escape") {
      evento.stopPropagation();
      fecharPainel();
    }
  }

  async function abrirPainel() {
    const root = document.getElementById("isis-chat-root");
    const painel = document.getElementById("isisChatPanel");
    lastFocused = document.activeElement;
    root.classList.add("isis-chat-open");
    painel.hidden = false;
    if (!sessionId) await iniciarSessao();
    document.getElementById("isisChatInput").focus();
  }

  function fecharPainel() {
    const root = document.getElementById("isis-chat-root");
    const painel = document.getElementById("isisChatPanel");
    root.classList.remove("isis-chat-open");
    painel.hidden = true;
    if (lastFocused && typeof lastFocused.focus === "function") lastFocused.focus();
  }

  function mostrarErro(mensagem) {
    const el = document.getElementById("isisChatError");
    el.textContent = mensagem;
    el.hidden = !mensagem;
  }

  function adicionarMensagem(texto, autor) {
    const log = document.getElementById("isisChatLog");
    const bolha = document.createElement("div");
    bolha.className = `isis-chat-msg isis-chat-msg-${autor}`;
    bolha.textContent = texto;
    log.appendChild(bolha);
    log.scrollTop = log.scrollHeight;
    return bolha;
  }

  function renderCards(container, itens) {
    if (!itens || !itens.length) return;
    const wrap = document.createElement("div");
    wrap.className = "isis-chat-cards";
    itens.forEach((item) => {
      const card = document.createElement("div");
      card.className = "isis-chat-card";
      const imagem = item.image_url ? `<img src="${esc(item.image_url)}" alt="" loading="lazy" />` : "";
      const preco = typeof item.price === "number" ? `R$ ${item.price.toFixed(2).replace(".", ",")}` : "";
      const url = isSafeUrl(item.product_url) ? item.product_url : "#";
      card.innerHTML = `
        ${imagem}
        <div class="isis-chat-card-info">
          <div class="isis-chat-card-name">${esc(item.name)}</div>
          <div class="isis-chat-card-price">${esc(preco)}</div>
          <div class="isis-chat-card-reason">${esc(item.reason || "")}</div>
        </div>
        <a class="isis-chat-btn" href="${esc(url)}" rel="noopener">Ver produto</a>
      `;
      wrap.appendChild(card);
    });
    container.appendChild(wrap);
  }

  function isSafeUrl(url) {
    if (!url) return false;
    return /^(https?:)?\/\//.test(url) || url.startsWith("/") || url.startsWith("produto.html") || url.startsWith("escola-curso.html");
  }

  function renderKit(container, kit) {
    if (!kit) return;
    const wrap = document.createElement("div");
    wrap.className = "isis-chat-cards";
    const total = typeof kit.total_price === "number" ? kit.total_price.toFixed(2).replace(".", ",") : "0,00";
    const cabecalho = document.createElement("div");
    cabecalho.className = "isis-chat-card-reason";
    cabecalho.textContent = `Kit sugerido — total real: R$ ${total}`;
    wrap.appendChild(cabecalho);
    renderCards(wrap, (kit.items || []).map((item) => ({ ...item, name: item.name, price: item.price, product_url: item.product_url })));
    container.appendChild(wrap);
  }

  function atualizarRemaining(valor) {
    remaining = valor;
    const input = document.getElementById("isisChatInput");
    const enviar = document.getElementById("isisChatSendBtn");
    if (typeof remaining === "number" && remaining <= 0) {
      input.disabled = true;
      enviar.disabled = true;
      mostrarErro("Limite de mensagens desta conversa atingido. Feche e abra uma nova conversa.");
    }
  }

  async function iniciarSessao() {
    try {
      const resposta = await fetch(`${API_BASE}/api/isis2/chat/sessoes`, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
      });
      if (!resposta.ok) {
        mostrarErro("Não foi possível iniciar o chat agora. Tente novamente em instantes.");
        return;
      }
      const dados = await resposta.json();
      sessionId = dados.session_id;
      adicionarMensagem(dados.message, "isis");
      atualizarRemaining(dados.remaining_messages);
    } catch {
      mostrarErro("Não foi possível conectar ao chat agora. Verifique sua conexão.");
    }
  }

  async function aoEnviar(evento) {
    evento.preventDefault();
    const input = document.getElementById("isisChatInput");
    const texto = input.value.trim();
    if (!texto) return;
    input.value = "";
    await enviarTexto(texto);
  }

  async function enviarTexto(texto) {
    if (sending || !sessionId) return;
    sending = true;
    mostrarErro("");
    adicionarMensagem(texto, "user");
    const enviar = document.getElementById("isisChatSendBtn");
    enviar.disabled = true;
    try {
      const resposta = await fetch(`${API_BASE}/api/isis2/chat/sessoes/${encodeURIComponent(sessionId)}/mensagens`, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ texto }),
      });
      if (resposta.status === 429) {
        mostrarErro("Muitas mensagens em pouco tempo. Aguarde um instante antes de tentar de novo.");
        return;
      }
      if (!resposta.ok) {
        mostrarErro("Não consegui responder agora. Tente novamente em instantes.");
        return;
      }
      const dados = await resposta.json();
      const bolha = adicionarMensagem(dados.message, "isis");
      renderCards(bolha.parentElement, dados.recommendations);
      renderKit(bolha.parentElement, dados.suggested_kit);
      if (dados.complementary_items && dados.complementary_items.length) {
        const nota = document.createElement("div");
        nota.className = "isis-chat-card-reason";
        nota.textContent = "Também pode combinar com:";
        bolha.parentElement.appendChild(nota);
        renderCards(bolha.parentElement, dados.complementary_items);
      }
      atualizarRemaining(dados.remaining_messages);
    } catch {
      mostrarErro("Não consegui conectar ao chat agora. Verifique sua conexão.");
    } finally {
      sending = false;
      if (!(typeof remaining === "number" && remaining <= 0)) enviar.disabled = false;
    }
  }

  ready(montarDOM);
})();
