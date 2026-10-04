/* Optional live player. A work only needs window.webfilm, never this file. */
(() => {
  'use strict';
  const work = window.webfilm;
  if (!work || typeof work.render !== 'function') throw new Error('Missing webfilm.render(t)');
  const capture = window.__WEBFILM_CAPTURE__ === true;
  let audioContext = null;
  let start = 0;
  let position = 0;
  let running = true;
  let rendering = false;
  const draw = async (time) => {
    position = Math.min(work.duration, Math.max(0, time));
    await work.render(position);
  };
  window.addEventListener('resize', () => draw(position));
  draw(0);
  if (capture) return;
  start = performance.now();

  const controls = document.createElement('div');
  controls.dataset.webfilmPlayer = '';
  controls.style.cssText = 'position:fixed;right:22px;bottom:20px;z-index:999;display:flex;gap:8px;align-items:center;font:13px system-ui;color:#294c3e';
  const button = (label) => {
    const node = document.createElement('button');
    node.textContent = label;
    node.style.cssText = 'border:1px solid #78938366;border-radius:30px;background:#fffcf3e8;color:#294c3e;padding:10px 15px;cursor:pointer;font:inherit;box-shadow:0 2px 12px #203b2510';
    controls.append(node);
    return node;
  };
  const restart = button('重新开始');
  let music;
  if (typeof work.audio === 'function') music = button('开启音乐');
  const clock = document.createElement('span');
  clock.style.cssText = 'padding:0 8px;background:#fffcf3dc;border-radius:20px;font-variant-numeric:tabular-nums';
  controls.append(clock);
  document.body.append(controls);

  async function reset(withMusic) {
    if (audioContext) { await audioContext.close(); audioContext = null; }
    position = 0;
    if (withMusic) {
      const Audio = window.AudioContext || window.webkitAudioContext;
      audioContext = new Audio({sampleRate: 48000});
      await audioContext.resume();
      await work.audio(audioContext);
      if (music) music.textContent = '音乐已开启';
    }
    start = performance.now();
    running = true;
    await draw(0);
  }
  restart.addEventListener('click', () => reset(audioContext !== null));
  if (music) music.addEventListener('click', () => reset(true));
  async function frame(now) {
    if (!rendering && running) {
      rendering = true;
      try {
        await draw((now - start) / 1000);
        clock.textContent = `${position.toFixed(1)} / ${work.duration.toFixed(1)} 秒`;
        if (position >= work.duration) running = false;
      } catch (error) {
        running = false;
        clock.textContent = '播放失败';
        console.error(error);
      } finally { rendering = false; }
    }
    requestAnimationFrame(frame);
  }
  requestAnimationFrame(frame);
})();
