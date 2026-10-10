/* Controls a work iframe using the sound clock and absolute render(t). */
(() => {
  'use strict';
  const config = window.webfilmPreviewConfig;
  const frame = document.getElementById('work');
  const playButton = document.getElementById('play'), restart = document.getElementById('restart');
  const slider = document.getElementById('seek'), clock = document.getElementById('clock');
  const status = document.getElementById('status'), stage = document.getElementById('stage');
  let work, context, buffer, source, ready = false, running = false, loading = false;
  let position = 0, epoch = 0, drawings = Promise.resolve(), drawVersion = 0;
  const clamp = t => Math.max(0, Math.min(config.duration, Number(t) || 0));
  const current = () => running ? clamp(context.currentTime - epoch) : position;
  function stopSource() {
    if (source) { source.stop(); source.disconnect(); source = null; }
  }
  function fail(error) {
    running = false;
    stopSource();
    status.textContent = '预览失败：' + (error.message || error);
    playButton.disabled = restart.disabled = slider.disabled = true;
    console.error(error);
  }
  function fit() {
    frame.style.transform = `scale(${stage.clientWidth / config.width})`;
  }
  function draw(t) {
    const version = ++drawVersion;
    drawings = drawings.then(async () => {
      if (version !== drawVersion) return;
      frame.contentWindow.__WEBFILM_TIME__ = t;
      await work.render(t);
      for (const animation of frame.contentDocument.getAnimations()) {
        animation.pause(); animation.currentTime = t * 1000;
      }
      slider.value = String(t);
      clock.textContent = `${t.toFixed(1)} / ${config.duration.toFixed(1)} 秒`;
    });
    return drawings;
  }
  function begin() {
    stopSource();
    const start = context.currentTime;
    epoch = start - position;
    if (buffer) {
      source = context.createBufferSource();
      source.buffer = buffer; source.connect(context.destination);
      source.start(start, position);
    }
    running = true;
    playButton.textContent = '暂停';
  }
  async function play() {
    if (!ready || running) return;
    if (!context) context = new AudioContext({sampleRate: 48000});
    await context.resume();
    if (position >= config.duration) position = 0;
    begin();
    await draw(position);
  }
  function pause() {
    position = current(); running = false; stopSource();
    playButton.textContent = '播放';
    return draw(position);
  }
  function seek(t) {
    position = clamp(t);
    if (running && position < config.duration) begin();
    else if (position >= config.duration) {
      running = false; stopSource(); playButton.textContent = '播放';
    }
    return draw(position);
  }
  async function tick() {
    try {
      if (running) {
        position = current();
        await draw(position);
        if (position >= config.duration) await pause();
      }
    } catch (error) { fail(error); }
    requestAnimationFrame(tick);
  }
  const loadWork = async () => {
    if (loading || frame.contentWindow.location.href === 'about:blank') return; loading = true;
    try {
      fit();
      work = frame.contentWindow.webfilm;
      if (!work || typeof work.render !== 'function' || work.duration !== config.duration)
        throw new Error('作品缺少 render(t)，或时长与 work.json 不一致');
      if (work.ready) await work.ready;
      await frame.contentDocument.fonts.ready;
      await Promise.all([...frame.contentDocument.images].map(image => image.decode()));
      if (config.audio === 'generated' || config.narration_url) {
        status.textContent = '正在准备声音…';
        const offline = new OfflineAudioContext(2, Math.round(config.duration * 48000), 48000);
        if (config.audio === 'generated') {
          if (typeof work.audio !== 'function') throw new Error('有声作品缺少 audio(ctx)');
          await work.audio(offline);
        }
        if (config.narration_url) {
          const response = await fetch(config.narration_url);
          if (!response.ok) throw new Error('无法读取指定配音文件');
          const voice = offline.createBufferSource();
          voice.buffer = await offline.decodeAudioData(await response.arrayBuffer());
          voice.connect(offline.destination); voice.start(0);
        }
        buffer = await offline.startRendering();
      }
      await draw(0);
      ready = true;
      playButton.disabled = restart.disabled = slider.disabled = false;
      status.textContent = buffer ? '声音已准备，点击播放' : '无声作品已准备，点击播放';
    } catch (error) { fail(error); }
  };
  frame.addEventListener('load', loadWork);
  if (frame.contentDocument?.readyState === 'complete') loadWork();
  playButton.addEventListener('click', () => (running ? pause() : play()).catch(fail));
  restart.addEventListener('click', async () => {
    try { await pause(); await seek(0); await play(); } catch (error) { fail(error); }
  });
  slider.addEventListener('input', () => seek(slider.value).catch(fail));
  document.getElementById('reload').addEventListener('click', () => location.reload());
  window.addEventListener('resize', fit);
  window.addEventListener('pagehide', () => { stopSource(); if (context) context.close(); });
  window.webfilmPreview = {play, pause, seek, get position() { return current(); }, get playing() { return running; }};
  requestAnimationFrame(tick);
})();
