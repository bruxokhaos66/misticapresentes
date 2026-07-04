(() => {
  const KEY = "misticaDailyTasks";
  const TASKS = [
    "Conferir limpeza e organizacao da loja",
    "Conferir produtos em destaque",
    "Conferir estoque baixo",
    "Conferir pedidos pendentes",
    "Conferir mensagens do WhatsApp",
    "Fechar vendas do dia",
    "Baixar backup JSON"
  ];

  function todayKey() {
    return new Date().toISOString().slice(0, 10);
  }

  function state() {
    const raw = localStorage.getItem(KEY);
    try {
      const parsed = JSON.parse(raw || "{}");
      return parsed.date === todayKey() ? parsed.done || {} : {};
    } catch {
      return {};
    }
  }

  function save(done) {
    localStorage.setItem(KEY, JSON.stringify({ date: todayKey(), done }));
  }

  function toggleTask(index) {
    const done = state();
    done[index] = !done[index];
    save(done);
    renderTasks();
  }

  function resetTasks() {
    if (!confirm("Limpar as tarefas marcadas de hoje?")) return;
    save({});
    renderTasks();
  }

  function renderTasks() {
    const content = document.getElementById("dailyTasksContent");
    if (!content) return;
    const done = state();
    const totalDone = TASKS.filter((_, index) => done[index]).length;
    content.innerHTML = `
      <div class="privacy-note">${totalDone}/${TASKS.length} tarefa(s) concluida(s) hoje.</div>
      ${TASKS.map((task, index) => `
        <label class="history-item" style="cursor:pointer">
          <span><input type="checkbox" ${done[index] ? "checked" : ""} onchange="misticaDailyTasks.toggle(${index})"> ${task}</span>
        </label>
      `).join("")}
    `;
  }

  function mountTasks() {
    const admin = document.getElementById("adminContent");
    if (!admin || document.getElementById("dailyTasksPanel")) return;
    const panel = document.createElement("section");
    panel.id = "dailyTasksPanel";
    panel.className = "form-panel admin-report-panel";
    panel.innerHTML = `
      <p class="eyebrow">Rotina</p>
      <h2>Tarefas diarias da loja</h2>
      <p class="privacy-note">Checklist simples de abertura, operacao e fechamento.</p>
      <div class="report-export-actions">
        <button class="btn btn-ghost" type="button" onclick="misticaDailyTasks.render()">Atualizar</button>
        <button class="btn btn-ghost" type="button" onclick="misticaDailyTasks.reset()">Limpar hoje</button>
      </div>
      <div id="dailyTasksContent" class="history-list"></div>
    `;
    const templates = document.getElementById("messageTemplatesPanel");
    if (templates?.nextSibling) admin.insertBefore(panel, templates.nextSibling);
    else admin.appendChild(panel);
    renderTasks();
  }

  window.misticaDailyTasks = {
    render: renderTasks,
    toggle: toggleTask,
    reset: resetTasks,
  };

  window.addEventListener("load", mountTasks);
})();
