(() => {
  function carregarPainelAuth() {
    if (document.getElementById("painelAuthScript")) return;
    const script = document.createElement("script");
    script.id = "painelAuthScript";
    script.src = "painel-auth.js?v=20260710-admin-api-final";
    script.defer = true;
    document.head.appendChild(script);
  }

  function limparFormularioLegado() {
    const form = document.getElementById("adminLoginForm");
    if (!form) return;

    // app.js antigo instala um listener local que sempre exibe
    // "Admin local bloqueado". Clonar o formulário remove apenas listeners
    // JavaScript antigos, preservando campos, estilos e atributos HTML.
    const clone = form.cloneNode(true);
    clone.dataset.apiLoginClean = "true";
    form.replaceWith(clone);
  }

  function iniciar() {
    limparFormularioLegado();
    carregarPainelAuth();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", iniciar, { once: true });
  } else {
    iniciar();
  }
})();
