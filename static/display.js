/* global MessagePack */
(() => {
  'use strict';
  const audio = document.querySelector('#audio');
  const cover = document.querySelector('#cover');
  const title = document.querySelector('#title');
  const status = document.querySelector('#status');
  const connection = document.querySelector('#connection');
  const previous = document.querySelector('#previous');
  const current = document.querySelector('#current');
  const next = document.querySelector('#next');
  let cues = [];
  let audioUrl;
  let coverUrl;
  let started = false;
  let frame;
  let socket;
  let reconnect;
  let leaving = false;

  function parseSrt(text) {
    const timestamp = value => {
      const parts = value.replace(',', '.').split(':').map(Number);
      return parts[0] * 3600 + parts[1] * 60 + parts[2];
    };
    const result = [];
    for (const block of text.replace(/^\uFEFF/, '').replace(/\r\n?/g, '\n').trim().split(/\n\s*\n/)) {
      const lines = block.split('\n');
      const timing = /^\s*(\d{2,}:\d{2}:\d{2}[,.]\d{3})\s*-->\s*(\d{2,}:\d{2}:\d{2}[,.]\d{3})\s*$/.exec(lines[1] || '');
      if (!timing) throw new Error('The backend sent invalid SRT lyrics.');
      const start = timestamp(timing[1]);
      const end = timestamp(timing[2]);
      if (end <= start || lines.length < 3) throw new Error('The backend sent invalid lyric timings.');
      result.push({ start, end, text: lines.slice(2).join('\n') });
    }
    return result.sort((a, b) => a.start - b.start);
  }

  function setText(element, value) {
    if (element.textContent !== value) element.textContent = value;
  }

  function renderLyrics() {
    if (!cues.length) return;
    const time = audio.currentTime;
    // Upper bound also handles seeking backwards and gaps between lines.
    let low = 0;
    let high = cues.length;
    while (low < high) {
      const middle = (low + high) >>> 1;
      if (cues[middle].start <= time) low = middle + 1;
      else high = middle;
    }
    const index = low - 1;
    const active = index >= 0 && time < cues[index].end;
    setText(previous, cues[active ? index - 1 : index]?.text || '');
    setText(current, active ? cues[index].text : (low < cues.length ? '♪' : ''));
    setText(next, cues[low]?.text || '');
  }

  function tick() {
    renderLyrics();
    if (!audio.paused && !audio.ended) frame = requestAnimationFrame(tick);
  }

  function resetSong() {
    audio.pause();
    audio.removeAttribute('src');
    audio.load();
    if (audioUrl) URL.revokeObjectURL(audioUrl);
    if (coverUrl) URL.revokeObjectURL(coverUrl);
    audioUrl = coverUrl = undefined;
    cover.removeAttribute('src');
    cover.hidden = true;
    cues = [];
    started = false;
    previous.textContent = next.textContent = '';
    current.textContent = 'Getting your song ready…';
  }

  async function startWhenReady() {
    if (!audioUrl || !cues.length || started) return;
    started = true;
    renderLyrics();
    status.textContent = 'Ready to sing.';
    try {
      await audio.play();
    } catch (error) {
      status.textContent = error.name === 'NotAllowedError'
        ? 'Song ready — press Play to enable audio.'
        : 'Audio could not start. Use Play to try again.';
    }
  }

  function receive(event) {
    try {
      const message = MessagePack.decode(new Uint8Array(event.data));
      switch (message.type) {
        case 'processing_notification':
          resetSong();
          title.textContent = 'Preparing your next song';
          status.textContent = 'The backend is separating audio and aligning lyrics…';
          break;
        case 'wavefile':
          // A new audio file also starts a fresh song if a notification was missed.
          if (audioUrl) resetSong();
          if (!(message.payload instanceof Uint8Array)) throw new Error('Invalid audio payload.');
          audioUrl = URL.createObjectURL(new Blob([message.payload], { type: 'audio/wav' }));
          audio.src = audioUrl;
          title.textContent = message.filename || 'Untitled song';
          status.textContent = 'Audio received. Waiting for lyrics…';
          void startWhenReady();
          break;
        case 'srtfile':
          if (!(message.payload instanceof Uint8Array)) throw new Error('Invalid lyrics payload.');
          cues = parseSrt(new TextDecoder('utf-8', { fatal: true }).decode(message.payload));
          status.textContent = audioUrl ? 'Lyrics received.' : 'Lyrics received. Waiting for audio…';
          void startWhenReady();
          break;
        case 'pngfile':
          if (!(message.payload instanceof Uint8Array)) throw new Error('Invalid cover payload.');
          if (coverUrl) URL.revokeObjectURL(coverUrl);
          coverUrl = URL.createObjectURL(new Blob([message.payload], { type: 'image/png' }));
          cover.src = coverUrl;
          cover.hidden = false;
          break;
        case 'youtube_video':
          resetSong();
          title.textContent = 'YouTube video selected';
          current.textContent = 'Video playback is not available here';
          status.textContent = 'The backend sends no video URL. Choose a generated song for audio and lyrics.';
          break;
      }
    } catch (error) {
      status.textContent = `Could not load backend media: ${error.message}`;
    }
  }

  function connect() {
    connection.dataset.state = 'connecting';
    connection.textContent = 'Connecting to backend…';
    const url = new URL('/webSockets', window.location.href);
    url.protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
    socket = new WebSocket(url);
    socket.binaryType = 'arraybuffer';
    socket.addEventListener('open', () => {
      connection.dataset.state = 'connected';
      connection.textContent = 'Connected to backend';
    });
    socket.addEventListener('message', receive);
    socket.addEventListener('close', () => {
      connection.dataset.state = 'disconnected';
      connection.textContent = 'Disconnected — reconnecting…';
      if (!leaving) reconnect = setTimeout(connect, 3000);
    });
    socket.addEventListener('error', () => {
      connection.textContent = 'Backend connection unavailable';
    });
  }

  audio.addEventListener('play', () => {
    status.textContent = 'Playing';
    cancelAnimationFrame(frame);
    tick();
  });
  audio.addEventListener('pause', () => {
    cancelAnimationFrame(frame);
    if (audioUrl && !audio.ended) status.textContent = 'Paused';
  });
  audio.addEventListener('ended', () => {
    cancelAnimationFrame(frame);
    renderLyrics();
    status.textContent = 'Song finished. Choose another song to keep singing.';
  });
  audio.addEventListener('timeupdate', renderLyrics);
  audio.addEventListener('seeked', renderLyrics);
  audio.addEventListener('error', () => {
    if (audioUrl) status.textContent = 'This audio could not be decoded. Request another song.';
  });
  cover.addEventListener('error', () => { cover.hidden = true; });
  document.querySelector('#fullscreen').addEventListener('click', async () => {
    try {
      if (document.fullscreenElement) await document.exitFullscreen();
      else await document.documentElement.requestFullscreen();
    } catch {
      status.textContent = 'Fullscreen is not available in this browser.';
    }
  });
  document.addEventListener('fullscreenchange', () => {
    document.querySelector('#fullscreen').textContent = document.fullscreenElement ? 'Exit fullscreen' : 'Fullscreen';
  });
  window.addEventListener('pagehide', () => {
    leaving = true;
    clearTimeout(reconnect);
    socket.close();
    cancelAnimationFrame(frame);
  });
  window.addEventListener('pageshow', event => {
    if (event.persisted) { leaving = false; connect(); }
  });
  connect();
})();
