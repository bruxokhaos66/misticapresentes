(() => {
  const STORAGE_KEY = "misticaEscolaBaloonFechadoEm";
  const COOLDOWN_MS = 1000 * 60 * 60 * 12;
  const SHOW_DELAY_MS = 6000;

  function fechadoRecentemente() {
    try {
      const valor = window.localStorage.getItem(STORAGE_KEY);
      if (!valor) return false;
      return Date.now() - Number(valor) < COOLDOWN_MS;
    } catch {
      return false;
    }
  }

  function registrarFechamento() {
    try {
      window.localStorage.setItem(STORAGE_KEY, String(Date.now()));
    } catch {
      // Sem localStorage disponível, o balão pode reaparecer na próxima visita.
    }
  }

  function montarBaloon() {
    const baloon = document.createElement("div");
    baloon.className = "escola-baloon";
    baloon.setAttribute("role", "complementary");
    baloon.setAttribute("aria-label", "Convite para a Escola Mística");

    const fechar = document.createElement("button");
    fechar.type = "button";
    fechar.className = "escola-baloon-close";
    fechar.setAttribute("aria-label", "Fechar aviso da Escola Mística");
    fechar.textContent = "✕";
    fechar.addEventListener("click", () => {
      baloon.classList.remove("is-visible");
      registrarFechamento();
      setTimeout(() => baloon.remove(), 500);
    });

    const emblema = document.createElement("div");
    emblema.className = "escola-baloon-emblem";
    emblema.setAttribute("aria-hidden", "true");
    emblema.textContent = "☾";

    const corpo = document.createElement("div");
    corpo.className = "escola-baloon-body";

    const eyebrow = document.createElement("p");
    eyebrow.className = "escola-baloon-eyebrow";
    eyebrow.textContent = "Escola Mística";

    const titulo = document.createElement("p");
    titulo.className = "escola-baloon-title";
    titulo.textContent = "Curioso sobre xamanismo?";

    const texto = document.createElement("p");
    texto.className = "escola-baloon-text";
    texto.textContent = "Conheça nossos cursos sobre xamanismo, rapé, ayahuasca e as medicinas da floresta.";

    const cta = document.createElement("a");
    cta.className = "escola-baloon-cta";
    cta.href = "/escola.html";
    cta.textContent = "🍃 Ver cursos";

    corpo.appendChild(eyebrow);
    corpo.appendChild(titulo);
    corpo.appendChild(texto);
    corpo.appendChild(cta);

    baloon.appendChild(fechar);
    baloon.appendChild(emblema);
    baloon.appendChild(corpo);

    return baloon;
  }

  function reposicionar(baloon) {
    const consentBanner = document.getElementById("consentBanner");
    const espacoExtra = consentBanner ? consentBanner.offsetHeight + 12 : 0;
    baloon.style.bottom = `${18 + espacoExtra}px`;
  }

  function iniciar() {
    if (fechadoRecentemente()) return;
    if (document.querySelector(".escola-baloon")) return;

    const baloon = montarBaloon();
    document.body.appendChild(baloon);
    reposicionar(baloon);

    const observer = new MutationObserver(() => reposicionar(baloon));
    observer.observe(document.body, { childList: true });
    window.addEventListener("resize", () => reposicionar(baloon));

    requestAnimationFrame(() => {
      setTimeout(() => baloon.classList.add("is-visible"), SHOW_DELAY_MS);
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", iniciar);
  } else {
    iniciar();
  }
})();
