const courseMaterialTypes = {
  pdf: { label: "PDF", icon: "📄" },
  ppt: { label: "Apresentação", icon: "📊" },
  video: { label: "Vídeo", icon: "🎬" }
};

const seedCourseMaterials = [
  { id: "curso-cristais-guia", title: "Guia de Cristais e Energias", category: "Produtos", type: "pdf", description: "Material completo sobre significado, uso e indicação dos principais cristais da loja.", url: "" },
  { id: "curso-apresentacao-institucional", title: "Apresentação Institucional Mística Presentes", category: "Institucional", type: "ppt", description: "Slides para novos vendedores conhecerem a história, valores e catálogo da loja.", url: "" },
  { id: "curso-video-atendimento", title: "Como apresentar os produtos ao cliente", category: "Vendas", type: "video", description: "Aula em vídeo com técnicas de atendimento místico, comercial e humano.", url: "" }
];

function loadCourseMaterials() {
  try {
    const stored = localStorage.getItem("misticaCourseMaterials");
    return stored ? JSON.parse(stored) : [];
  } catch {
    localStorage.removeItem("misticaCourseMaterials");
    return [];
  }
}

let courseMaterials = loadCourseMaterials();
let activeCourseFilter = "todos";

function saveCourseMaterials() {
  localStorage.setItem("misticaCourseMaterials", JSON.stringify(courseMaterials));
}

function allCourseMaterials() {
  return seedCourseMaterials.concat(courseMaterials);
}

function renderCourseGrid() {
  const grid = document.querySelector("[data-course-grid]");
  if (!grid) return;
  const materials = allCourseMaterials().filter(item => activeCourseFilter === "todos" || item.type === activeCourseFilter);
  if (!materials.length) {
    grid.innerHTML = `<div class="course-empty">Nenhum material nesta categoria ainda. Use o painel administrativo para adicionar PDFs, apresentações e vídeos.</div>`;
    return;
  }
  grid.innerHTML = materials.map(item => {
    const typeInfo = courseMaterialTypes[item.type] || courseMaterialTypes.pdf;
    const action = item.url
      ? `<a class="btn btn-ghost btn-full" href="${item.url}" target="_blank" rel="noopener">Abrir material</a>`
      : `<button class="btn btn-ghost btn-full" type="button" disabled>Link em breve</button>`;
    return `<article class="course-card"><span class="course-card-type">${typeInfo.label}</span><div class="course-card-icon" aria-hidden="true">${typeInfo.icon}</div><span class="course-card-tag">${item.category}</span><h3>${item.title}</h3><p>${item.description}</p>${action}</article>`;
  }).join("");
}

function renderCourseAdminList() {
  const list = document.querySelector("[data-course-admin-list]");
  if (!list) return;
  if (!courseMaterials.length) {
    list.innerHTML = `<div class="history-item"><span>Nenhum material cadastrado pelo painel ainda.</span></div>`;
    return;
  }
  list.innerHTML = courseMaterials.map(item => {
    const typeInfo = courseMaterialTypes[item.type] || courseMaterialTypes.pdf;
    return `<div class="course-admin-item"><div class="course-card-icon" aria-hidden="true">${typeInfo.icon}</div><div><strong>${item.title}</strong><span>${item.category} • ${typeInfo.label}</span></div><button class="btn btn-ghost course-admin-remove" type="button" onclick="removeCourseMaterial('${item.id}')">Remover</button></div>`;
  }).join("");
}

function removeCourseMaterial(id) {
  courseMaterials = courseMaterials.filter(item => item.id !== id);
  saveCourseMaterials();
  renderCourseAdminList();
  renderCourseGrid();
}

function handleCourseAdminSubmit(event) {
  event.preventDefault();
  const title = document.getElementById("courseTitle")?.value.trim();
  const category = document.getElementById("courseCategory")?.value.trim();
  const type = document.getElementById("courseType")?.value;
  const url = document.getElementById("courseUrl")?.value.trim();
  const description = document.getElementById("courseDescription")?.value.trim();
  const status = document.getElementById("courseAdminStatus");
  if (!title || !category || !url) {
    if (status) { status.hidden = false; status.textContent = "Preencha título, categoria e o link do material."; }
    return;
  }
  courseMaterials.unshift({ id: `CURSO${Date.now()}`, title, category, type, description, url });
  saveCourseMaterials();
  renderCourseAdminList();
  renderCourseGrid();
  event.target.reset();
  if (status) { status.hidden = false; status.textContent = `Material "${title}" adicionado ao curso.`; }
}

document.querySelectorAll("[data-course-filter]").forEach(button => {
  button.addEventListener("click", () => {
    activeCourseFilter = button.dataset.courseFilter;
    document.querySelectorAll("[data-course-filter]").forEach(btn => btn.classList.toggle("is-active", btn === button));
    renderCourseGrid();
  });
});

document.getElementById("courseAdminForm")?.addEventListener("submit", handleCourseAdminSubmit);

renderCourseGrid();
renderCourseAdminList();
