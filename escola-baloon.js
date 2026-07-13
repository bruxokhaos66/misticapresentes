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

    const particulas = montarParticulas();

    const brasa = document.createElement("div");
    brasa.className = "escola-baloon-edge";
    brasa.setAttribute("aria-hidden", "true");

    const emblema = document.createElement("div");
    emblema.className = "escola-baloon-emblem";
    emblema.setAttribute("aria-hidden", "true");
    const chama = document.createElement("span");
    chama.className = "escola-baloon-flame";
    emblema.appendChild(chama);

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
    cta.textContent = "Ver cursos";

    corpo.appendChild(eyebrow);
    corpo.appendChild(titulo);
    corpo.appendChild(texto);
    corpo.appendChild(cta);

    baloon.appendChild(brasa);
    baloon.appendChild(particulas);
    baloon.appendChild(fechar);
    baloon.appendChild(emblema);
    baloon.appendChild(corpo);

    return baloon;
  }

  function montarParticulas() {
    const container = document.createElement("div");
    container.className = "escola-baloon-particles";
    container.setAttribute("aria-hidden", "true");

    for (let i = 0; i < 9; i += 1) {
      const spark = document.createElement("span");
      spark.className = "escola-baloon-spark";
      const esquerda = 10 + Math.random() * 80;
      const deriva = (Math.random() - 0.5) * 30;
      const duracao = 1.6 + Math.random() * 1.4;
      const atraso = Math.random() * 2.5;
      spark.style.left = `${esquerda}%`;
      spark.style.setProperty("--drift", `${deriva}px`);
      spark.style.animationDuration = `${duracao}s`;
      spark.style.animationDelay = `${atraso}s`;
      container.appendChild(spark);
    }

    for (let i = 0; i < 5; i += 1) {
      const cinza = document.createElement("span");
      cinza.className = "escola-baloon-ash";
      const esquerda = 15 + Math.random() * 70;
      const deriva = (Math.random() - 0.5) * 24;
      const tamanho = 3 + Math.random() * 4;
      const duracao = 2.6 + Math.random() * 1.8;
      const atraso = Math.random() * 3;
      cinza.style.left = `${esquerda}%`;
      cinza.style.width = `${tamanho}px`;
      cinza.style.height = `${tamanho}px`;
      cinza.style.setProperty("--drift", `${deriva}px`);
      cinza.style.animationDuration = `${duracao}s`;
      cinza.style.animationDelay = `${atraso}s`;
      container.appendChild(cinza);
    }

    return container;
  }

  function reposicionar(baloon) {
    const consentBanner = document.getElementById("consentBanner");
    const espacoExtra = consentBanner ? consentBanner.offsetHeight + 12 : 0;
    baloon.style.bottom = `${96 + espacoExtra}px`;
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
