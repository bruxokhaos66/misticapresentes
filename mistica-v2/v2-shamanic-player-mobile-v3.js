(() => {
  const ROOT_SELECTOR = '[data-shamanic-player]';
  const AUDIO_VERSION = 'bd328f3-mobile-v3';
  const PUBLIC_AUDIO = new URL(`assets/audio/xamanico-ambiente.mp3?v=${AUDIO_VERSION}`, document.baseURI).href;
  const VOLUME_KEY = 'misticaShamanicPlayerVolume';

  const ready = (fn) => document.readyState === 'loading'
    ? document.addEventListener('DOMContentLoaded', fn, { once: true })
    : fn();

  const clamp = (value) => Math.max(0, Math.min(1, Number(value) || 0));
  const savedVolume = () => {
    const value = Number(localStorage.getItem(VOLUME_KEY));
    return Number.isFinite(value) && value >= 0 && value <= 1 ? value : 0.35;
  };

  ready(() => {
    const root = document.querySelector(ROOT_SELECTOR);
    if (!root || root.dataset.mobilePlayerV3 === 'true') return;
    root.dataset.mobilePlayerV3 = 'true';

    const panel = root.querySelector('.player-panel');
    const playButton = root.querySelector('[data-player-play]');
    const stopButton = root.querySelector('[data-player-stop]');
    const volume = root.querySelector('[data-player-volume]');
    const status = root.querySelector('[data-player-status]');
    const orb = root.querySelector('[data-player-orb]');
    if (!panel || !playButton || !stopButton) return;

    const audio = document.createElement('audio');
    audio.src = PUBLIC_AUDIO;
    audio.preload = 'metadata';
    audio.loop = true;
    audio.controls = true;
    audio.playsInline = true;
    audio.setAttribute('playsinline', '');
    audio.setAttribute('webkit-playsinline', '');
    audio.volume = savedVolume();
    audio.className = 'mobile-native-audio-fallback';
    audio.hidden = true;

    const diagnostics = document.createElement('div');
    diagnostics.className = 'player-mobile-diagnostics';
    diagnostics.hidden = true;
    diagnostics.textContent = 'Use o controle de áudio abaixo para iniciar manualmente.';

    panel.append(diagnostics, audio);

    const setStatus = (message) => {
      if (status) status.textContent = message;
    };

    const setPlaying = (playing) => {
      playButton.textContent = playing ? 'Pausar ambiente' : 'Tocar ambiente';
      orb?.classList.toggle('is-playing', playing);
    };

    const showNativeFallback = (message) => {
      diagnostics.hidden = false;
      diagnostics.textContent = message;
      audio.hidden = false;
      setStatus(message);
    };

    const errorMessage = () => {
      const code = audio.error?.code;
      if (code === 1) return 'A reprodução foi interrompida no celular.';
      if (code === 2) return 'Falha de rede ao carregar a música.';
      if (code === 3) return 'O celular não conseguiu decodificar este MP3.';
      if (code === 4) return 'Formato de áudio não suportado neste celular.';
      return 'Não foi possível iniciar a música automaticamente.';
    };

    if (volume) {
      volume.value = String(Math.round(audio.volume * 100));
      volume.addEventListener('input', () => {
        audio.volume = clamp(Number(volume.value) / 100);
        localStorage.setItem(VOLUME_KEY, String(audio.volume));
      });
    }

    playButton.addEventListener('click', async (event) => {
      event.preventDefault();
      event.stopImmediatePropagation();

      if (!audio.paused) {
        audio.pause();
        setPlaying(false);
        setStatus('Ambiente pausado.');
        return;
      }

      playButton.disabled = true;
      setStatus('Carregando ambiente xamânico...');
      try {
        audio.preload = 'auto';
        if (!audio.src.includes(AUDIO_VERSION)) {
          audio.src = PUBLIC_AUDIO;
          audio.load();
        }
        await audio.play();
        diagnostics.hidden = true;
        audio.hidden = true;
        setPlaying(true);
        setStatus('Ambiente Xamânico ativado.');
      } catch (error) {
        setPlaying(false);
        const blocked = error?.name === 'NotAllowedError';
        showNativeFallback(blocked
          ? 'O navegador bloqueou o início pelo botão. Toque no controle de áudio abaixo.'
          : `${errorMessage()} Toque no controle de áudio abaixo.`);
      } finally {
        playButton.disabled = false;
      }
    }, true);

    stopButton.addEventListener('click', (event) => {
      event.preventDefault();
      event.stopImmediatePropagation();
      audio.pause();
      try { audio.currentTime = 0; } catch {}
      setPlaying(false);
      setStatus('Ambiente parado.');
    }, true);

    audio.addEventListener('playing', () => {
      diagnostics.hidden = true;
      setPlaying(true);
      setStatus('Ambiente Xamânico ativado.');
    });

    audio.addEventListener('waiting', () => {
      setStatus('Carregando a trilha. Em conexão móvel pode levar alguns segundos.');
    });

    audio.addEventListener('canplay', () => {
      if (audio.paused) setStatus('Ambiente pronto. Toque em tocar para iniciar.');
    });

    audio.addEventListener('error', () => {
      setPlaying(false);
      showNativeFallback(`${errorMessage()} Verifique também se o arquivo abre diretamente no celular.`);
    });

    setStatus('Ambiente pronto. Toque em tocar para iniciar.');
  });
})();
