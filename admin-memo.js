(() => {
  const KEY = "misticaAdminMemo";

  function todayKey() {
    return new Date().toISOString().slice(0, 10);
  }

  function loadMemo() {
    const raw = localStorage.getItem(KEY);
    try {
      const parsed = JSON.parse(raw || "{}");
      return parsed.date === todayKey() ? parsed.text || "" : "";
    } catch {
      return "";
    }
  }

  function saveMemo() {
    const textarea = document.getElementById("adminMemoText");
    if (!textarea) return;
    localStorage.setItem(KEY, JSON.stringify({ date: todayKey(), text: textarea.value }));
    alert("Anotacao salva.");
  }

  function clearMemo() {
    if (!confirm("Limpar anotacoes de hoje?")) return;
    localStorage.setItem(KEY, JSON.stringify({ date: todayKey(), text: "" }));
    const textarea = document.getElementById("adminMemoText");
    if (textarea) textarea.value = "";
  }

  async function copyMemo() {
    const text = document.getElementById("adminMemoText")?.value || "";
    if (!text.trim()) return alert("Nao ha anotacao para copiar.");
    try {
      await navigator.clipboard.writeText(text);
      alert("Anotacao copiada.");
    } catch {
      prompt("Copie a anotacao:", text);
    }
  }

  function mountMemo() {
    const admin = document.getElementById("adminContent");
    if (!admin || document.getElementById("adminMemoPanel")) return;
    const panel = document.createElement("section");
    panel.id = "adminMemoPanel";
    panel.className = "form-panel admin-report-panel";
    panel.innerHTML = `
      <p class="eyebrow">Anotacoes</p>
      <h2>Anotacoes rapidas do dia</h2>
      <p class="privacy-note">Use para pendencias, lembretes, encomendas e observacoes internas.</p>
      <textarea id="adminMemoText" rows="6" placeholder="Ex.: separar pedido da cliente, confirmar fornecedor, conferir reposicao..."></textarea>
      <div class="report-export-actions">
        <button class="btn btn-ghost" type="button" onclick="misticaAdminMemo.save()">Salvar</button>
        <button class="btn btn-ghost" type="button" onclick="misticaAdminMemo.copy()">Copiar</button>
        <button class="btn btn-ghost" type="button" onclick="misticaAdminMemo.clear()">Limpar</button>
      </div>
    `;
    const tasks = document.getElementById("dailyTasksPanel");
    if (tasks?.nextSibling) admin.insertBefore(panel, tasks.nextSibling);
    else admin.appendChild(panel);
    document.getElementById("adminMemoText").value = loadMemo();
  }

  window.misticaAdminMemo = {
    save: saveMemo,
    clear: clearMemo,
    copy: copyMemo,
  };

  window.addEventListener("load", mountMemo);
})();
