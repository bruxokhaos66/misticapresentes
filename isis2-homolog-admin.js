// Painel administrativo "Isis — Homologação".
//
// Injeta um painel dentro de #adminContent (mesmo padrão de
// campaign-admin.js), visível só para quem já está autenticado como
// admin no painel (garantirCampoUsuario/restaurarSessao em
// site-config.js já garantem isso antes deste script rodar). Todas as
// chamadas usam credentials:"include" (cookie HttpOnly de sessão) --
// nunca query string, hash, localStorage nem sessionStorage. O servidor
// (backend/isis2_homolog.py) é a única fonte de verdade: qualquer falha
// de rede deixa o painel mostrando "DESATIVADA" (mesmo fail-safe da
// homologação em si).
(() => {
  const cfg = window.misticaSiteConfig || {};
  const API_BASE = String(cfg.apiBaseUrl || "https://api.misticaesotericos.com.br").replace(/\/$/, "");

  const ready = (fn) => (document.readyState === "loading" ? document.addEventListener("DOMContentLoaded", fn) : fn());
  const esc = (value) => String(value ?? "").replace(/[&<>"']/g, (ch) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[ch]));

  ready(() => {
    const adminContent = document.getElementById("adminContent");
    if (!adminContent || document.getElementById("isis2HomologAdminPanel")) return;

    const panel = document.createElement("section");
    panel.id = "isis2HomologAdminPanel";
    panel.className = "form-panel isis2-homolog-admin-panel";
    panel.innerHTML = `
      <p class="eyebrow">Isis 2.0</p>
      <h2>Isis — Homologação</h2>
      <p class="privacy-note">
        Liga a Isis 2.0 completa (comercial + Especialista da Mística Escola + Refinamento) só para
        administradores autenticados e para os alunos autorizados abaixo -- nunca para o público geral.
        Detalhes técnicos: <code>isis2/README.md</code>.
      </p>
      <div class="warning-box" data-isis2-homolog-estado>Consultando estado...</div>
      <div class="checkout-actions">
        <button class="btn" type="button" data-isis2-homolog-ativar>Ativar homologação</button>
        <button class="btn btn-ghost" type="button" data-isis2-homolog-desativar>Desativar homologação</button>
      </div>
      <p class="privacy-note">
        Qualquer administrador autenticado já pode testar automaticamente, mesmo sem estar na lista de
        alunos abaixo -- basta o interruptor acima estar ativo.
      </p>
      <p class="privacy-note">
        <strong>Como validar no site:</strong> abra o site normalmente (mesmo domínio de produção), logado
        como admin ou como um aluno autorizado. Se estiver tudo certo, aparece um selo discreto
        "Isis em homologação" no canto inferior esquerdo da tela e o assistente muda para a versão nova.
        Sem o selo, o site está exatamente como qualquer visitante comum vê.
      </p>

      <h3>Alunos autorizados</h3>
      <label>Buscar aluno por nome ou e-mail (só para localizar a conta -- a autorização usa sempre o ID interno)
        <input type="search" data-isis2-homolog-busca placeholder="Digite ao menos 2 letras..." autocomplete="off">
      </label>
      <div class="admin-product-list" data-isis2-homolog-busca-resultado></div>

      <div class="warning-box" data-isis2-homolog-testers-status hidden></div>
      <div class="admin-product-list" data-isis2-homolog-testers-list></div>
      <div class="checkout-actions">
        <button class="btn btn-ghost" type="button" data-isis2-homolog-revogar-todos>Revogar todos os testadores</button>
      </div>
    `;

    const audioPanel = adminContent.querySelector(".audio-admin-panel");
    adminContent.insertBefore(panel, audioPanel || adminContent.firstChild);

    const estadoBox = panel.querySelector("[data-isis2-homolog-estado]");
    const buscaInput = panel.querySelector("[data-isis2-homolog-busca]");
    const buscaResultado = panel.querySelector("[data-isis2-homolog-busca-resultado]");
    const testersStatus = panel.querySelector("[data-isis2-homolog-testers-status]");
    const testersList = panel.querySelector("[data-isis2-homolog-testers-list]");
    const btnAtivar = panel.querySelector("[data-isis2-homolog-ativar]");
    const btnDesativar = panel.querySelector("[data-isis2-homolog-desativar]");
    const btnRevogarTodos = panel.querySelector("[data-isis2-homolog-revogar-todos]");

    const setTestersStatus = (message, ok = false) => {
      testersStatus.hidden = !message;
      testersStatus.textContent = message || "";
      testersStatus.className = ok ? "warning-box" : "warning-box warning-danger";
    };

    const renderEstado = (ativo) => {
      estadoBox.className = ativo ? "warning-box" : "warning-box warning-danger";
      estadoBox.textContent = ativo
        ? "Estado: ATIVA -- administradores e alunos autorizados já veem a Isis 2.0 completa."
        : "Estado: DESATIVADA -- ninguém vê a Isis 2.0 além do que já está em produção.";
    };

    const carregarEstado = async () => {
      try {
        const response = await fetch(`${API_BASE}/api/isis2/homolog/estado`, { credentials: "include", cache: "no-store" });
        if (!response.ok) throw new Error();
        const dados = await response.json();
        renderEstado(dados.ativo === true);
      } catch {
        // Fail-safe: qualquer falha de rede/permissão mostra "desativada",
        // nunca "ativada" por omissão.
        renderEstado(false);
      }
    };

    const renderTesters = (testadores) => {
      if (!testadores.length) {
        testersList.innerHTML = '<div class="history-item"><span>Nenhum aluno autorizado no momento.</span></div>';
        return;
      }
      testersList.innerHTML = testadores.map((testador) => `
        <article class="admin-product-item">
          <div class="admin-product-thumb">🧪</div>
          <div>
            <strong>${esc(testador.nome)}</strong>
            <span>${esc(testador.email)}</span>
            <small>ID interno ${esc(testador.aluno_id)} • autorizado em ${esc(testador.adicionado_em)}</small>
          </div>
          <div class="admin-product-actions">
            <button class="btn btn-ghost" type="button" data-isis2-homolog-remover="${esc(testador.aluno_id)}">Remover</button>
          </div>
        </article>
      `).join("");
    };

    const carregarTesters = async () => {
      try {
        const response = await fetch(`${API_BASE}/api/isis2/homolog-testers`, { credentials: "include", cache: "no-store" });
        if (!response.ok) throw new Error("Não foi possível carregar a lista de alunos autorizados.");
        const testadores = await response.json();
        renderTesters(testadores);
      } catch (error) {
        setTestersStatus(error.message || "Falha ao carregar alunos autorizados.");
      }
    };

    btnAtivar.addEventListener("click", async () => {
      try {
        const response = await fetch(`${API_BASE}/api/isis2/homolog/ativar`, { method: "POST", credentials: "include" });
        if (!response.ok) throw new Error("Não foi possível ativar a homologação.");
        await carregarEstado();
      } catch (error) {
        setTestersStatus(error.message || "Falha ao ativar a homologação.");
      }
    });

    btnDesativar.addEventListener("click", async () => {
      try {
        const response = await fetch(`${API_BASE}/api/isis2/homolog/desativar`, { method: "POST", credentials: "include" });
        if (!response.ok) throw new Error("Não foi possível desativar a homologação.");
        await carregarEstado();
      } catch (error) {
        setTestersStatus(error.message || "Falha ao desativar a homologação.");
      }
    });

    btnRevogarTodos.addEventListener("click", async () => {
      if (!window.confirm("Revogar TODOS os testadores autorizados? Essa ação não pode ser desfeita -- será preciso autorizar de novo um por um.")) return;
      try {
        const response = await fetch(`${API_BASE}/api/isis2/homolog-testers/revogar-todos`, { method: "POST", credentials: "include" });
        if (!response.ok) throw new Error("Não foi possível revogar os testadores.");
        setTestersStatus("Todos os testadores foram revogados.", true);
        await carregarTesters();
      } catch (error) {
        setTestersStatus(error.message || "Falha ao revogar testadores.");
      }
    });

    testersList.addEventListener("click", async (event) => {
      const botao = event.target.closest("[data-isis2-homolog-remover]");
      if (!botao) return;
      const alunoId = botao.dataset.isis2HomologRemover;
      if (!window.confirm("Remover este aluno da lista de autorizados?")) return;
      try {
        const response = await fetch(`${API_BASE}/api/isis2/homolog-testers/${encodeURIComponent(alunoId)}`, {
          method: "DELETE",
          credentials: "include",
        });
        if (!response.ok) throw new Error("Não foi possível remover este aluno.");
        setTestersStatus("Aluno removido da homologação.", true);
        await carregarTesters();
      } catch (error) {
        setTestersStatus(error.message || "Falha ao remover aluno.");
      }
    });

    const renderBusca = (resultados) => {
      if (!resultados.length) {
        buscaResultado.innerHTML = "";
        return;
      }
      buscaResultado.innerHTML = resultados.map((aluno) => `
        <article class="admin-product-item">
          <div class="admin-product-thumb">🔎</div>
          <div>
            <strong>${esc(aluno.nome)}</strong>
            <span>${esc(aluno.email)}</span>
            <small>ID interno ${esc(aluno.aluno_id)}</small>
          </div>
          <div class="admin-product-actions">
            <button class="btn" type="button" data-isis2-homolog-adicionar="${esc(aluno.aluno_id)}">Autorizar</button>
          </div>
        </article>
      `).join("");
    };

    let buscaEmAndamento = null;
    buscaInput.addEventListener("input", () => {
      const termo = buscaInput.value.trim();
      if (buscaEmAndamento) clearTimeout(buscaEmAndamento);
      if (termo.length < 2) {
        buscaResultado.innerHTML = "";
        return;
      }
      buscaEmAndamento = setTimeout(async () => {
        try {
          const response = await fetch(`${API_BASE}/api/isis2/homolog/buscar-alunos?q=${encodeURIComponent(termo)}`, {
            credentials: "include",
            cache: "no-store",
          });
          if (!response.ok) throw new Error();
          const resultados = await response.json();
          renderBusca(resultados);
        } catch {
          buscaResultado.innerHTML = '<div class="history-item"><span>Falha ao buscar alunos.</span></div>';
        }
      }, 300);
    });

    buscaResultado.addEventListener("click", async (event) => {
      const botao = event.target.closest("[data-isis2-homolog-adicionar]");
      if (!botao) return;
      const alunoId = botao.dataset.isis2HomologAdicionar;
      try {
        const response = await fetch(`${API_BASE}/api/isis2/homolog-testers/${encodeURIComponent(alunoId)}`, {
          method: "POST",
          credentials: "include",
        });
        if (!response.ok) throw new Error("Não foi possível autorizar este aluno.");
        setTestersStatus("Aluno autorizado para a homologação.", true);
        buscaInput.value = "";
        buscaResultado.innerHTML = "";
        await carregarTesters();
      } catch (error) {
        setTestersStatus(error.message || "Falha ao autorizar aluno.");
      }
    });

    carregarEstado();
    carregarTesters();
  });
})();
