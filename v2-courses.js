const courseMaterialTypes = {
  pdf: { label: "PDF", icon: "📄" },
  ppt: { label: "Apresentação", icon: "📊" },
  video: { label: "Vídeo", icon: "🎬" }
};

const seedCourseMaterials = [
  { id: "seed-cristais-guia", titulo: "Guia de Cristais e Energias", categoria: "Produtos", tipo: "pdf", descricao: "Material completo sobre significado, uso e indicação dos principais cristais da loja.", url: "" },
  { id: "seed-apresentacao-institucional", titulo: "Apresentação Institucional Mística Presentes", categoria: "Institucional", tipo: "ppt", descricao: "Slides para novos vendedores conhecerem a história, valores e catálogo da loja.", url: "" },
  { id: "seed-video-atendimento", titulo: "Como apresentar os produtos ao cliente", categoria: "Vendas", tipo: "video", descricao: "Aula em vídeo com técnicas de atendimento místico, comercial e humano.", url: "" }
];

(() => {
  // Fonte única da URL da API: site-config.js (window.misticaSiteConfig).
  const COURSE_API_BASE = String(
    (window.misticaSiteConfig || {}).apiBaseUrl || "https://api.misticaesotericos.com.br"
  ).replace(/\/$/, "");
  const COURSE_CACHE_KEY = "misticaCourseMaterialsCache";

  let courseMaterials = [];
  let activeCourseFilter = "todos";

  const normalizeUrl = url => {
    const value = String(url || "").trim();
    if (!value) return "";
    if (value.startsWith("http")) return value;
    if (value.startsWith("/")) return `${COURSE_API_BASE}${value}`;
    return value;
  };

  function allCourseMaterials() {
    return seedCourseMaterials.concat(courseMaterials);
  }

  function renderCourseGrid() {
    const grid = document.querySelector("[data-course-grid]");
    if (!grid) return;
    const materials = allCourseMaterials().filter(item => activeCourseFilter === "todos" || item.tipo === activeCourseFilter);
    if (!materials.length) {
      grid.innerHTML = `<div class="course-empty">Nenhum material nesta categoria ainda. Use o painel administrativo para adicionar PDFs, apresentações e vídeos.</div>`;
      return;
    }
    grid.innerHTML = materials.map(item => {
      const typeInfo = courseMaterialTypes[item.tipo] || courseMaterialTypes.pdf;
      const url = normalizeUrl(item.url);
      const action = url
        ? `<a class="btn btn-ghost btn-full" href="${url}" target="_blank" rel="noopener">Abrir material</a>`
        : `<button class="btn btn-ghost btn-full" type="button" disabled>Link em breve</button>`;
      return `<article class="course-card"><span class="course-card-type">${typeInfo.label}</span><div class="course-card-icon" aria-hidden="true">${typeInfo.icon}</div><span class="course-card-tag">${item.categoria}</span><h3>${item.titulo}</h3><p>${item.descricao || ""}</p>${action}</article>`;
    }).join("");
  }

  function renderCourseAdminList() {
    const list = document.querySelector("[data-course-admin-list]");
    if (!list) return;
    if (!courseMaterials.length) {
      list.innerHTML = `<div class="history-item"><span>Nenhum material cadastrado pela API ainda.</span></div>`;
      return;
    }
    list.innerHTML = courseMaterials.map(item => {
      const typeInfo = courseMaterialTypes[item.tipo] || courseMaterialTypes.pdf;
      return `<div class="course-admin-item"><div class="course-card-icon" aria-hidden="true">${typeInfo.icon}</div><div><strong>${item.titulo}</strong><span>${item.categoria} • ${typeInfo.label}</span></div><button class="btn btn-ghost course-admin-remove" type="button" data-remove-course="${item.id}">Remover</button></div>`;
    }).join("");
  }

  function setCourseAdminStatus(message) {
    const status = document.getElementById("courseAdminStatus");
    if (status) { status.hidden = false; status.textContent = message; }
  }

  async function loadCourseMaterials() {
    try {
      const response = await fetch(`${COURSE_API_BASE}/api/cursos`);
      if (!response.ok) throw new Error("Falha ao carregar materiais.");
      courseMaterials = await response.json();
      localStorage.setItem(COURSE_CACHE_KEY, JSON.stringify(courseMaterials));
    } catch {
      try { courseMaterials = JSON.parse(localStorage.getItem(COURSE_CACHE_KEY) || "[]"); } catch { courseMaterials = []; }
    }
    renderCourseGrid();
    renderCourseAdminList();
  }

  async function uploadCourseFile(file, titulo) {
    const fd = new FormData();
    fd.append("arquivo", file);
    const response = await fetch(`${COURSE_API_BASE}/api/uploads/cursos?titulo=${encodeURIComponent(titulo)}`, {
      method: "POST",
      credentials: "include",
      body: fd
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok || !data.ok) throw new Error(data.detail || "Falha no upload do arquivo.");
    return data.url;
  }

  async function handleCourseAdminSubmit(event) {
    event.preventDefault();
    const titulo = document.getElementById("courseTitle")?.value.trim();
    const categoria = document.getElementById("courseCategory")?.value.trim();
    const tipo = document.getElementById("courseType")?.value;
    const url = document.getElementById("courseUrl")?.value.trim();
    const descricao = document.getElementById("courseDescription")?.value.trim();
    const file = document.getElementById("courseFile")?.files?.[0];

    if (!titulo || !categoria) return setCourseAdminStatus("Preencha título e categoria do material.");
    if (!url && !file) return setCourseAdminStatus("Envie um arquivo ou informe um link para o material.");

    setCourseAdminStatus("Salvando material...");
    try {
      let finalUrl = url;
      if (file) finalUrl = await uploadCourseFile(file, titulo);
      const response = await fetch(`${COURSE_API_BASE}/api/cursos`, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ titulo, categoria, tipo, descricao, url: finalUrl })
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok || !data.ok) throw new Error(data.detail || "Falha ao salvar material.");
      await loadCourseMaterials();
      event.target.reset();
      setCourseAdminStatus(`Material "${titulo}" adicionado ao curso.`);
    } catch (error) {
      setCourseAdminStatus(error.message || "Erro ao salvar material.");
    }
  }

  async function handleRemoveCourseMaterial(id) {
    try {
      const response = await fetch(`${COURSE_API_BASE}/api/cursos/${id}`, { method: "DELETE", credentials: "include" });
      const data = await response.json().catch(() => ({}));
      if (!response.ok || !data.ok) throw new Error(data.detail || "Falha ao remover material.");
      await loadCourseMaterials();
      setCourseAdminStatus("Material removido.");
    } catch (error) {
      setCourseAdminStatus(error.message || "Erro ao remover material.");
    }
  }

  document.querySelectorAll("[data-course-filter]").forEach(button => {
    button.addEventListener("click", () => {
      activeCourseFilter = button.dataset.courseFilter;
      document.querySelectorAll("[data-course-filter]").forEach(btn => btn.classList.toggle("is-active", btn === button));
      renderCourseGrid();
    });
  });

  document.getElementById("courseAdminForm")?.addEventListener("submit", handleCourseAdminSubmit);
  document.querySelector("[data-course-admin-list]")?.addEventListener("click", event => {
    const button = event.target.closest("[data-remove-course]");
    if (button) handleRemoveCourseMaterial(button.dataset.removeCourse);
  });

  function setCourseOrdersStatus(message) {
    const status = document.getElementById("courseOrdersStatus");
    if (status) { status.hidden = false; status.textContent = message; }
  }

  function courseOrderItemHtml(pedido) {
    const pago = pedido.status === "Pago";
    const acao = pago
      ? `<span class="course-card-tag">Pago — acesso liberado</span>`
      : `<button class="btn btn-ghost course-admin-remove" type="button" data-confirm-course-order="${pedido.id}">Confirmar pagamento</button>`;
    return `<div class="course-admin-item"><div><strong>${pedido.titulo}</strong><span>${pedido.nome || "(sem nome)"} • ${pedido.email || "(sem e-mail)"} • ${pedido.status}</span></div>${acao}</div>`;
  }

  async function loadCourseOrders() {
    const list = document.querySelector("[data-course-orders-list]");
    if (!list) return;
    try {
      const response = await fetch(`${COURSE_API_BASE}/api/checkout/cursos`, { credentials: "include" });
      const data = await response.json().catch(() => []);
      if (!response.ok) throw new Error(data.detail || "Falha ao carregar pedidos de cursos.");
      list.innerHTML = data.length
        ? data.map(courseOrderItemHtml).join("")
        : `<div class="history-item"><span>Nenhum pedido de curso ainda.</span></div>`;
    } catch (error) {
      setCourseOrdersStatus(error.message || "Erro ao carregar pedidos de cursos.");
    }
  }

  async function confirmarPedidoCurso(id) {
    try {
      const response = await fetch(`${COURSE_API_BASE}/api/checkout/cursos/${id}/confirmar`, {
        method: "POST",
        credentials: "include",
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok || !data.ok) throw new Error(data.detail || "Falha ao confirmar pagamento.");
      setCourseOrdersStatus(
        data.link_acesso
          ? `Pagamento confirmado. Envie este link pelo WhatsApp para o aluno criar a senha: ${data.link_acesso}`
          : "Pagamento confirmado. O aluno já tem senha e pode entrar normalmente com o e-mail cadastrado."
      );
      await loadCourseOrders();
    } catch (error) {
      setCourseOrdersStatus(error.message || "Erro ao confirmar pagamento.");
    }
  }

  document.querySelector("[data-course-orders-refresh]")?.addEventListener("click", loadCourseOrders);
  document.querySelector("[data-course-orders-list]")?.addEventListener("click", event => {
    const button = event.target.closest("[data-confirm-course-order]");
    if (button) confirmarPedidoCurso(button.dataset.confirmCourseOrder);
  });

  loadCourseMaterials();
  loadCourseOrders();
})();
