(() => {
  const DB_NAME = 'misticaAudioStore';
  const DB_VERSION = 1;
  const STORE_NAME = 'tracks';
  const UPLOADED_KEY = 'uploaded-main';
  const PUBLIC_AUDIO_PATH = 'mistica-v2/assets/audio/xamanico-ambiente.mp3';
  const VOLUME_KEY = 'misticaShamanicPlayerVolume';
  const ACTIVE_TITLE = 'Ambiente Xamânico ativado';
  const FALLBACK_TRACK = {
    title: ACTIVE_TITLE,
    src: 'assets/audio/xamanico-ambiente.mp3',
    note: 'Arquivo de áudio não encontrado. Use upload no Admin ou coloque a faixa em mistica-v2/assets/audio.'
  };

  const ready = (fn) => document.readyState === 'loading' ? document.addEventListener('DOMContentLoaded', fn) : fn();
  const formatBytes = (bytes) => {
    if (!Number.isFinite(bytes) || bytes <= 0) return '0 KB';
    const units = ['bytes', 'KB', 'MB', 'GB'];
    const index = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), units.length - 1);
    return `${(bytes / Math.pow(1024, index)).toFixed(index ? 1 : 0)} ${units[index]}`;
  };
  const clampVolume = (value) => Math.max(0, Math.min(1, Number(value) || 0));
  const savedVolume = () => {
    const stored = Number(localStorage.getItem(VOLUME_KEY));
    return Number.isFinite(stored) && stored >= 0 && stored <= 1 ? stored : 0.35;
  };

  function openDb() {
    return new Promise((resolve, reject) => {
      if (!('indexedDB' in window)) return reject(new Error('IndexedDB indisponível'));
      const request = indexedDB.open(DB_NAME, DB_VERSION);
      request.onupgradeneeded = () => {
        const db = request.result;
        if (!db.objectStoreNames.contains(STORE_NAME)) db.createObjectStore(STORE_NAME, { keyPath: 'id' });
      };
      request.onsuccess = () => resolve(request.result);
      request.onerror = () => reject(request.error);
    });
  }

  async function readUploadedTrack() {
    const db = await openDb();
    return new Promise((resolve, reject) => {
      const tx = db.transaction(STORE_NAME, 'readonly');
      const request = tx.objectStore(STORE_NAME).get(UPLOADED_KEY);
      request.onsuccess = () => resolve(request.result || null);
      request.onerror = () => reject(request.error);
      tx.oncomplete = () => db.close();
    });
  }

  function readAudioFile(file, onProgress) {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onprogress = (event) => {
        if (!event.lengthComputable) return onProgress?.(12, 'Lendo arquivo de áudio...');
        const percent = Math.min(80, Math.round((event.loaded / event.total) * 80));
        onProgress?.(percent, `Lendo arquivo: ${percent}%`);
      };
      reader.onload = () => resolve(reader.result);
      reader.onerror = () => reject(reader.error || new Error('Falha ao ler arquivo.'));
      reader.readAsArrayBuffer(file);
    });
  }

  async function saveUploadedTrack(file, onProgress) {
    if (!file || !file.type.startsWith('audio/')) throw new Error('Envie um arquivo de áudio válido.');
    onProgress?.(5, `Preparando ${file.name} (${formatBytes(file.size)})...`);
    const buffer = await readAudioFile(file, onProgress);
    onProgress?.(85, 'Salvando música localmente no navegador...');
    const db = await openDb();
    const payload = {
      id: UPLOADED_KEY,
      name: file.name,
      type: file.type || 'audio/mpeg',
      size: file.size,
      updatedAt: new Date().toISOString(),
      blob: new Blob([buffer], { type: file.type || 'audio/mpeg' })
    };
    return new Promise((resolve, reject) => {
      const tx = db.transaction(STORE_NAME, 'readwrite');
      tx.objectStore(STORE_NAME).put(payload);
      tx.oncomplete = () => { db.close(); onProgress?.(100, 'Upload local concluído: 100%'); resolve(payload); };
      tx.onerror = () => { db.close(); reject(tx.error); };
    });
  }

  async function deleteUploadedTrack() {
    const db = await openDb();
    return new Promise((resolve, reject) => {
      const tx = db.transaction(STORE_NAME, 'readwrite');
      tx.objectStore(STORE_NAME).delete(UPLOADED_KEY);
      tx.oncomplete = () => { db.close(); resolve(); };
      tx.onerror = () => { db.close(); reject(tx.error); };
    });
  }

  ready(async () => {
    const root = document.querySelector('[data-shamanic-player]');
    if (!root) return;

    const audio = new Audio();
    audio.preload = 'metadata';
    audio.loop = true;
    audio.volume = savedVolume();
    audio.playsInline = true;

    let uploadedUrl = '';
    let activeTrack = { ...FALLBACK_TRACK };
    let audioUnlocked = false;
    let userRequestedPlay = false;

    const title = root.querySelector('[data-player-title]');
    const status = root.querySelector('[data-player-status]');
    const playButton = root.querySelector('[data-player-play]');
    const stopButton = root.querySelector('[data-player-stop]');
    const volume = root.querySelector('[data-player-volume]');
    const orb = root.querySelector('[data-player-orb]');
    const list = root.querySelector('[data-player-list]');
    const adminFile = document.querySelector('[data-admin-audio-file]');
    const adminSave = document.querySelector('[data-admin-audio-save]');
    const adminRemove = document.querySelector('[data-admin-audio-remove]');
    const adminStatus = document.querySelector('[data-admin-audio-status]');
    const adminProgress = document.querySelector('[data-admin-audio-progress]');
    const adminPercent = document.querySelector('[data-admin-audio-percent]');
    const adminPath = document.querySelector('[data-admin-audio-path]');

    const loadingBox = document.createElement('div');
    loadingBox.className = 'player-loading';
    loadingBox.hidden = true;
    loadingBox.innerHTML = '<div class="player-loading-row"><span data-player-loading-label>Preparando áudio...</span><strong data-player-loading-percent>0%</strong></div><progress max="100" value="0" data-player-loading-progress>0%</progress>';
    root.querySelector('.player-panel')?.insertBefore(loadingBox, volume?.closest('.volume-row') || null);

    const loadingLabel = loadingBox.querySelector('[data-player-loading-label]');
    const loadingPercent = loadingBox.querySelector('[data-player-loading-percent]');
    const loadingProgress = loadingBox.querySelector('[data-player-loading-progress]');

    const setStatus = (message) => { if (status) status.textContent = message; };
    const setAdminStatus = (message) => { if (adminStatus) adminStatus.textContent = message; };
    const setUploadProgress = (percent, message) => {
      const value = Math.max(0, Math.min(100, Number(percent) || 0));
      if (adminProgress) adminProgress.value = value;
      if (adminPercent) adminPercent.textContent = `${Math.round(value)}%`;
      if (message) setAdminStatus(message);
    };
    const setLoading = (percent, message, visible = true) => {
      const value = Math.max(0, Math.min(100, Number(percent) || 0));
      loadingBox.hidden = !visible;
      if (loadingProgress) loadingProgress.value = value;
      if (loadingPercent) loadingPercent.textContent = `${Math.round(value)}%`;
      if (loadingLabel && message) loadingLabel.textContent = message;
    };

    if (adminPath) adminPath.textContent = PUBLIC_AUDIO_PATH;
    if (list) list.replaceChildren();

    const revokeUploadedUrl = () => {
      if (uploadedUrl) URL.revokeObjectURL(uploadedUrl);
      uploadedUrl = '';
    };

    const applyTrack = (track) => {
      activeTrack = track;
      audio.src = activeTrack.src;
      audio.load();
      if (title) title.textContent = ACTIVE_TITLE;
      setStatus('Ambiente pronto. Toque em tocar para iniciar.');
      setLoading(0, 'Preparando áudio...', false);
      if (list) list.replaceChildren();
    };

    const loadTrack = async () => {
      revokeUploadedUrl();
      try {
        const uploaded = await readUploadedTrack();
        if (uploaded?.blob) {
          uploadedUrl = URL.createObjectURL(uploaded.blob);
          applyTrack({ title: ACTIVE_TITLE, src: uploadedUrl });
          setAdminStatus(`Música local ativa: ${uploaded.name} (${formatBytes(uploaded.size)}).`);
          setUploadProgress(100);
          return;
        }
        setAdminStatus(`Nenhuma música local enviada. Para todos os visitantes, envie o MP3 como ${PUBLIC_AUDIO_PATH}.`);
        setUploadProgress(0);
      } catch {
        setAdminStatus('Não foi possível acessar o armazenamento local de música neste navegador.');
      }
      applyTrack({ ...FALLBACK_TRACK });
    };

    const setPlayingUi = (isPlaying) => {
      if (playButton) playButton.textContent = isPlaying ? 'Pausar ambiente' : 'Tocar ambiente';
      if (orb) orb.classList.toggle('is-playing', isPlaying);
    };

    if (volume) {
      volume.value = String(Math.round(audio.volume * 100));
      volume.addEventListener('input', () => {
        audio.volume = clampVolume(Number(volume.value) / 100);
        localStorage.setItem(VOLUME_KEY, String(audio.volume));
      });
    }

    if (adminFile) {
      adminFile.addEventListener('change', () => {
        const file = adminFile.files?.[0];
        if (!file) return setUploadProgress(0, 'Nenhum arquivo selecionado.');
        setUploadProgress(0, `Arquivo selecionado: ${file.name} (${formatBytes(file.size)}). Clique em salvar para enviar.`);
      });
    }

    if (playButton) {
      playButton.addEventListener('click', async () => {
        audioUnlocked = true;
        userRequestedPlay = true;
        if (!audio.src) applyTrack(activeTrack);
        if (!audio.paused) {
          audio.pause();
          userRequestedPlay = false;
          setPlayingUi(false);
          setLoading(0, 'Áudio pausado.', false);
          setStatus('Ambiente pausado.');
          return;
        }
        playButton.disabled = true;
        audio.preload = 'auto';
        setLoading(4, 'Carregando ambiente...', true);
        setStatus('Carregando ambiente xamânico...');
        try {
          await audio.play();
          setPlayingUi(true);
          setLoading(100, 'Áudio pronto.', false);
          setStatus('Ambiente Xamânico ativado.');
        } catch (error) {
          userRequestedPlay = false;
          setPlayingUi(false);
          setLoading(0, 'Não foi possível iniciar.', false);
          if (error?.name === 'NotAllowedError') {
            setStatus('O navegador bloqueou o áudio. Toque novamente em “Tocar ambiente”.');
          } else if (!navigator.onLine) {
            setStatus('Sem conexão para carregar a música. Verifique a internet e tente novamente.');
          } else {
            setStatus('Não foi possível carregar a música. Atualize a página e tente novamente.');
          }
        } finally {
          playButton.disabled = false;
        }
      });
    }

    if (stopButton) {
      stopButton.addEventListener('click', () => {
        userRequestedPlay = false;
        audio.pause();
        audio.currentTime = 0;
        setPlayingUi(false);
        setLoading(0, 'Ambiente parado.', false);
        setStatus(audioUnlocked ? 'Ambiente parado.' : 'Ambiente pronto. Toque em tocar para iniciar.');
      });
    }

    if (adminSave) {
      adminSave.addEventListener('click', async () => {
        const file = adminFile?.files?.[0];
        if (!file) return setUploadProgress(0, 'Selecione um arquivo de música primeiro.');
        adminSave.disabled = true;
        setUploadProgress(0, 'Iniciando upload local...');
        try {
          await saveUploadedTrack(file, setUploadProgress);
          await loadTrack();
          setUploadProgress(100, `Música enviada e salva localmente: ${file.name}.`);
        } catch (error) {
          setUploadProgress(0, `Erro ao salvar música: ${error.message || 'verifique o arquivo.'}`);
        } finally {
          adminSave.disabled = false;
        }
      });
    }

    if (adminRemove) {
      adminRemove.addEventListener('click', async () => {
        try {
          await deleteUploadedTrack();
          await loadTrack();
          setUploadProgress(0, 'Música local removida. O player voltou para a pasta assets/audio.');
        } catch {
          setAdminStatus('Não foi possível remover a música local.');
        }
      });
    }

    audio.addEventListener('loadstart', () => {
      if (userRequestedPlay) setLoading(5, 'Iniciando carregamento...', true);
    });
    audio.addEventListener('progress', () => {
      if (!userRequestedPlay || !audio.duration || !audio.buffered.length) return;
      const end = audio.buffered.end(audio.buffered.length - 1);
      const percent = Math.min(99, Math.round((end / audio.duration) * 100));
      setLoading(percent, `Carregando ambiente... ${percent}%`, true);
    });
    audio.addEventListener('waiting', () => {
      if (userRequestedPlay) {
        setLoading(Number(loadingProgress?.value || 12), 'Conexão lenta. Carregando mais áudio...', true);
        setStatus('Aguarde um instante: carregando a trilha.');
      }
    });
    audio.addEventListener('canplay', () => {
      if (userRequestedPlay) setLoading(100, 'Áudio pronto.', false);
    });
    audio.addEventListener('playing', () => {
      setPlayingUi(true);
      setLoading(100, 'Áudio pronto.', false);
      setStatus('Ambiente Xamânico ativado.');
    });
    audio.addEventListener('pause', () => {
      if (!audio.ended) setPlayingUi(false);
    });
    audio.addEventListener('error', () => {
      userRequestedPlay = false;
      setPlayingUi(false);
      setLoading(0, 'Falha no carregamento.', false);
      setStatus('Áudio indisponível no momento. Atualize a página e tente novamente.');
    });
    audio.addEventListener('ended', () => setPlayingUi(false));

    await loadTrack();
    window.addEventListener('beforeunload', revokeUploadedUrl);
  });
})();
