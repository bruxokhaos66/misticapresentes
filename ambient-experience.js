(() => {
  const STORAGE_KEY = "misticaAmbientEnabled";
  const VOLUME_KEY = "misticaAmbientVolume";
  const DEFAULT_VOLUME = 0.18;

  let audioContext = null;
  let masterGain = null;
  let oscillators = [];
  let noiseSource = null;
  let noiseGain = null;
  let isPlaying = false;

  function injectStyles() {
    if (document.getElementById("misticaAmbientStyles")) return;
    const style = document.createElement("style");
    style.id = "misticaAmbientStyles";
    style.textContent = `
      .ambient-card {
        position: relative;
        z-index: 4;
        margin-top: 18px;
        border: 1px solid rgba(240,197,106,.28);
        border-radius: 26px;
        padding: clamp(16px, 2.4vw, 22px);
        background:
          radial-gradient(circle at 12% 10%, rgba(240,197,106,.16), transparent 34%),
          linear-gradient(145deg, rgba(255,248,230,.075), rgba(83,107,55,.11));
        box-shadow: 0 22px 68px rgba(0,0,0,.24);
      }

      .ambient-card strong {
        display: block;
        color: #fff6dc;
        font-family: Cinzel, Georgia, serif;
        font-size: clamp(1.05rem, 1.8vw, 1.35rem);
        letter-spacing: .03em;
      }

      .ambient-card p {
        margin: 8px 0 14px;
        color: #efe1c5;
        font-size: clamp(.98rem, 1.15vw, 1.08rem);
        line-height: 1.55;
      }

      .ambient-controls {
        display: flex;
        flex-wrap: wrap;
        align-items: center;
        gap: 12px;
      }

      .ambient-toggle[aria-pressed="true"] {
        border-color: rgba(184,201,119,.52);
        color: #10150e;
        background: linear-gradient(135deg, #dfeab2, #b8c977 62%, #fff6cc);
      }

      .ambient-volume {
        min-width: min(220px, 100%);
        accent-color: #f0c56a;
      }

      .ambient-status {
        color: #b8c977;
        font-size: .86rem;
        font-weight: 800;
      }

      .hero-copy h1 {
        max-width: 820px;
        font-size: clamp(2.25rem, 4.25vw, 4.55rem);
      }

      .hero-text,
      .section-title p,
      .category-grid p,
      .confidence-grid span,
      .product-card p,
      .privacy-note,
      .contact-card p {
        font-size: clamp(.98rem, 1.04vw, 1.08rem);
      }

      .hero-visual {
        align-self: stretch;
      }

      .mystic-logo-card.hero-card-isis-publicitaria {
        width: min(96%, 450px);
        min-height: clamp(540px, 58vw, 650px);
        justify-content: end;
      }

      .hero-isis-publicitaria {
        width: min(106%, 470px) !important;
        max-height: 575px !important;
        margin-bottom: -2px !important;
      }

      .isis-layout {
        align-items: center;
      }

      .isis-panel-image:has(.isis-human-img) {
        min-height: clamp(560px, 58vw, 680px);
        padding: 18px 18px 16px;
      }

      .isis-human-img,
      .isis-human-produtos {
        width: min(104%, 540px) !important;
        max-height: 650px !important;
      }

      .isis-chat-panel h2 {
        font-size: clamp(2rem, 3vw, 3.1rem);
      }

      .isis-chat-panel .privacy-note {
        color: #efe1c5;
        font-weight: 600;
      }

      @media (max-width: 980px) {
        .mystic-logo-card.hero-card-isis-publicitaria {
          width: min(100%, 420px);
          min-height: 520px;
        }

        .hero-isis-publicitaria {
          max-height: 455px !important;
        }
      }

      @media (max-width: 680px) {
        .ambient-card {
          text-align: left;
        }

        .ambient-controls .btn,
        .ambient-volume {
          width: 100%;
        }

        .mystic-logo-card.hero-card-isis-publicitaria {
          min-height: 500px !important;
        }

        .isis-panel-image:has(.isis-human-img) {
          min-height: 500px !important;
        }

        .isis-human-img,
        .isis-human-produtos {
          max-height: 485px !important;
        }
      }
    `;
    document.head.appendChild(style);
  }

  function createNoiseBuffer(context) {
    const length = Math.max(1, Math.floor(context.sampleRate * 2));
    const buffer = context.createBuffer(1, length, context.sampleRate);
    const output = buffer.getChannelData(0);
    for (let i = 0; i < length; i += 1) {
      output[i] = (Math.random() * 2 - 1) * 0.18;
    }
    return buffer;
  }

  function buildAmbientSound() {
    if (audioContext) return;
    const AudioContextClass = window.AudioContext || window.webkitAudioContext;
    if (!AudioContextClass) throw new Error("Áudio não suportado neste navegador.");

    audioContext = new AudioContextClass();
    masterGain = audioContext.createGain();
    masterGain.gain.value = 0;
    masterGain.connect(audioContext.destination);

    const frequencies = [110, 164.81, 220];
    oscillators = frequencies.map((frequency, index) => {
      const oscillator = audioContext.createOscillator();
      const gain = audioContext.createGain();
      oscillator.type = index === 1 ? "triangle" : "sine";
      oscillator.frequency.value = frequency;
      gain.gain.value = index === 0 ? 0.12 : 0.055;
      oscillator.connect(gain).connect(masterGain);
      oscillator.start();
      return { oscillator, gain };
    });

    const filter = audioContext.createBiquadFilter();
    filter.type = "lowpass";
    filter.frequency.value = 650;
    filter.Q.value = 0.8;

    noiseGain = audioContext.createGain();
    noiseGain.gain.value = 0.025;
    noiseSource = audioContext.createBufferSource();
    noiseSource.buffer = createNoiseBuffer(audioContext);
    noiseSource.loop = true;
    noiseSource.connect(filter).connect(noiseGain).connect(masterGain);
    noiseSource.start();
  }

  function selectedVolume() {
    const saved = Number(localStorage.getItem(VOLUME_KEY));
    if (Number.isFinite(saved) && saved >= 0 && saved <= 1) return saved;
    return DEFAULT_VOLUME;
  }

  function setVolume(value) {
    const nextVolume = Math.min(0.42, Math.max(0, Number(value) || 0));
    localStorage.setItem(VOLUME_KEY, String(nextVolume));
    if (masterGain && audioContext) {
      masterGain.gain.cancelScheduledValues(audioContext.currentTime);
      masterGain.gain.setTargetAtTime(isPlaying ? nextVolume : 0, audioContext.currentTime, 0.08);
    }
    return nextVolume;
  }

  async function startAmbient() {
    buildAmbientSound();
    if (audioContext.state === "suspended") await audioContext.resume();
    isPlaying = true;
    localStorage.setItem(STORAGE_KEY, "true");
    setVolume(selectedVolume());
  }

  function stopAmbient() {
    isPlaying = false;
    localStorage.setItem(STORAGE_KEY, "false");
    if (masterGain && audioContext) {
      masterGain.gain.cancelScheduledValues(audioContext.currentTime);
      masterGain.gain.setTargetAtTime(0, audioContext.currentTime, 0.08);
    }
  }

  function updateUi(card) {
    const button = card.querySelector("[data-ambient-toggle]");
    const status = card.querySelector("[data-ambient-status]");
    if (button) {
      button.setAttribute("aria-pressed", String(isPlaying));
      button.textContent = isPlaying ? "Desligar música ambiente" : "Ativar ambiente xamânico";
    }
    if (status) status.textContent = isPlaying ? "Música ambiente ligada em volume suave." : "Toque somente após o cliente ativar.";
  }

  function createAmbientCard() {
    const heroCopy = document.querySelector(".hero-copy");
    if (!heroCopy || document.querySelector("[data-ambient-card]")) return;

    const card = document.createElement("div");
    card.className = "ambient-card";
    card.dataset.ambientCard = "true";
    card.innerHTML = `
      <strong>🌿 Experiência sonora xamânica</strong>
      <p>Para uma navegação mais imersiva, o cliente pode ativar uma trilha ambiente suave. Ela não toca sozinha: respeita as regras dos navegadores e a escolha do visitante.</p>
      <div class="ambient-controls">
        <button class="btn ambient-toggle" type="button" data-ambient-toggle aria-pressed="false">Ativar ambiente xamânico</button>
        <input class="ambient-volume" type="range" min="0" max="0.42" step="0.01" value="${selectedVolume()}" aria-label="Volume da música ambiente" data-ambient-volume>
        <span class="ambient-status" data-ambient-status>Toque somente após o cliente ativar.</span>
      </div>
    `;

    const trustRow = heroCopy.querySelector(".trust-row");
    if (trustRow) {
      heroCopy.insertBefore(card, trustRow);
    } else {
      heroCopy.appendChild(card);
    }

    const button = card.querySelector("[data-ambient-toggle]");
    const volume = card.querySelector("[data-ambient-volume]");

    button.addEventListener("click", async () => {
      try {
        if (isPlaying) stopAmbient();
        else await startAmbient();
      } catch (error) {
        const status = card.querySelector("[data-ambient-status]");
        if (status) status.textContent = "Não foi possível iniciar o áudio neste navegador.";
      }
      updateUi(card);
    });

    volume.addEventListener("input", () => {
      setVolume(volume.value);
      updateUi(card);
    });

    updateUi(card);
  }

  function init() {
    injectStyles();
    createAmbientCard();
    if (localStorage.getItem(STORAGE_KEY) === "true") {
      const resumeOnInteraction = async () => {
        try {
          await startAmbient();
          const card = document.querySelector("[data-ambient-card]");
          if (card) updateUi(card);
        } finally {
          document.removeEventListener("pointerdown", resumeOnInteraction);
          document.removeEventListener("keydown", resumeOnInteraction);
        }
      };
      document.addEventListener("pointerdown", resumeOnInteraction, { once: true });
      document.addEventListener("keydown", resumeOnInteraction, { once: true });
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }

  window.misticaAmbientExperience = {
    start: startAmbient,
    stop: stopAmbient,
    isPlaying: () => isPlaying,
    setVolume
  };
})();
