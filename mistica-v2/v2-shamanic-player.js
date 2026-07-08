(() => {
  const tracks = [
    {
      title: 'Ambiente xamânico da loja',
      src: 'assets/audio/xamanico-ambiente.mp3',
      note: 'Adicione o arquivo em mistica-v2/assets/audio/xamanico-ambiente.mp3 para ativar a trilha principal.'
    },
    {
      title: 'Tambor e floresta',
      src: 'assets/audio/tambor-floresta.mp3',
      note: 'Faixa opcional: coloque o arquivo em mistica-v2/assets/audio/tambor-floresta.mp3.'
    },
    {
      title: 'Cristais e incensos',
      src: 'assets/audio/cristais-incensos.mp3',
      note: 'Faixa opcional: coloque o arquivo em mistica-v2/assets/audio/cristais-incensos.mp3.'
    }
  ];

  const ready = (fn) => {
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', fn);
    else fn();
  };

  ready(() => {
    const root = document.querySelector('[data-shamanic-player]');
    if (!root) return;

    const audio = new Audio();
    audio.preload = 'none';
    audio.loop = true;
    audio.volume = 0.35;

    let currentIndex = 0;
    let audioUnlocked = false;

    const title = root.querySelector('[data-player-title]');
    const status = root.querySelector('[data-player-status]');
    const playButton = root.querySelector('[data-player-play]');
    const stopButton = root.querySelector('[data-player-stop]');
    const volume = root.querySelector('[data-player-volume]');
    const orb = root.querySelector('[data-player-orb]');
    const list = root.querySelector('[data-player-list]');

    const setStatus = (message) => {
      if (status) status.textContent = message;
    };

    const setActiveTrack = (index) => {
      currentIndex = index;
      const track = tracks[currentIndex];
      audio.src = track.src;
      audio.load();
      if (title) title.textContent = track.title;
      setStatus(track.note || 'Trilha pronta. Clique em tocar para iniciar.');
      if (list) {
        list.querySelectorAll('[data-track-index]').forEach((button) => {
          button.classList.toggle('is-active', Number(button.dataset.trackIndex) === currentIndex);
        });
      }
    };

    const setPlayingUi = (isPlaying) => {
      if (playButton) playButton.textContent = isPlaying ? 'Pausar ambiente' : 'Tocar ambiente';
      if (orb) orb.classList.toggle('is-playing', isPlaying);
    };

    if (volume) {
      volume.value = String(Math.round(audio.volume * 100));
      volume.addEventListener('input', () => {
        audio.volume = Math.max(0, Math.min(1, Number(volume.value) / 100));
      });
    }

    if (list) {
      list.innerHTML = tracks.map((track, index) => `<button class="track-button" type="button" data-track-index="${index}">${track.title}</button>`).join('');
      list.addEventListener('click', async (event) => {
        const button = event.target.closest('[data-track-index]');
        if (!button) return;
        const nextIndex = Number(button.dataset.trackIndex);
        const wasPlaying = !audio.paused;
        setActiveTrack(nextIndex);
        if (wasPlaying) {
          try {
            await audio.play();
            setPlayingUi(true);
            setStatus('Ambiente tocando.');
          } catch (error) {
            setPlayingUi(false);
            setStatus('Arquivo de áudio não encontrado ou bloqueado pelo navegador. Adicione a faixa na pasta assets/audio.');
          }
        }
      });
    }

    if (playButton) {
      playButton.addEventListener('click', async () => {
        audioUnlocked = true;
        if (!audio.src) setActiveTrack(currentIndex);
        if (!audio.paused) {
          audio.pause();
          setPlayingUi(false);
          setStatus('Ambiente pausado.');
          return;
        }
        try {
          await audio.play();
          setPlayingUi(true);
          setStatus('Ambiente tocando.');
        } catch (error) {
          setPlayingUi(false);
          setStatus('Não foi possível tocar agora. Confirme se o arquivo existe em mistica-v2/assets/audio.');
        }
      });
    }

    if (stopButton) {
      stopButton.addEventListener('click', () => {
        audio.pause();
        audio.currentTime = 0;
        setPlayingUi(false);
        setStatus(audioUnlocked ? 'Ambiente parado.' : 'Ambiente pronto. Clique em tocar para iniciar.');
      });
    }

    audio.addEventListener('error', () => {
      setPlayingUi(false);
      setStatus('Arquivo de áudio não encontrado. Coloque a faixa em mistica-v2/assets/audio ou ajuste o caminho no player.');
    });

    audio.addEventListener('ended', () => setPlayingUi(false));

    setActiveTrack(0);
  });
})();
