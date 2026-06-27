# -*- coding: utf-8 -*-
"""
Stage 3.5 (optional) - in-browser dynamic preview of EVERY scene before rendering.

Generates output/preview.html: a responsive grid where each scene_NN.html is
embedded in a down-scaled iframe and animates itself on a loop (the scene runtime
self-drives when opened with ?dur=SECONDS - see templates/scene_base.html). Each
cell sits on a still grabbed from the real 4K background, so what you see is what
you will render - just looping and without audio.

Why this exists: the expensive step is the multi-minute NVENC render. This lets
you catch a mis-placed element / overflow / bad cue in 5 seconds in a browser
first. Open output/preview.html (double-click) - no server needed; every iframe
drives its own timeline, so file:// cross-origin rules never get in the way.

Public entry:  build(names=None) -> output/preview.html
"""

import os
import sys
import json
import glob
import subprocess

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config

PREVIEW_HTML = os.path.join(config.DIR_OUTPUT, "preview.html")
PREVIEW_BG = os.path.join(config.DIR_OUTPUT, "_preview_bg.jpg")


def _ensure_bg():
    """One still from the looping background, so cells look like the final frame."""
    if os.path.exists(PREVIEW_BG):
        return
    if not os.path.exists(config.BG_VIDEO):
        return
    subprocess.run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
                    "-i", config.BG_VIDEO, "-frames:v", "1", PREVIEW_BG], check=True)


def _fmt(t):
    m, s = divmod(int(round(t)), 60)
    return f"{m:02d}:{s:02d}"


def build(names=None, out=PREVIEW_HTML):
    config.ensure_dirs()
    _ensure_bg()
    with open(config.DURATIONS_JSON, "r", encoding="utf-8") as f:
        durs = json.load(f)
    scenes = sorted(glob.glob(os.path.join(config.DIR_SCENE, "scene_*.html")))
    if not scenes:
        print("[preview] no scenes built yet"); return None
    n = min(len(scenes), len(durs))
    total = sum(durs[:n])
    has_bg = os.path.exists(PREVIEW_BG)

    cards, acc = [], 0.0
    for i in range(n):
        rel = os.path.relpath(scenes[i], config.DIR_OUTPUT).replace("\\", "/")
        d = durs[i]
        nm = names[i] if names and i < len(names) else f"scene_{i+1:02d}"
        cards.append(f"""
      <figure class="card">
        <div class="frame"><iframe loading="lazy" src="../scene_html/{os.path.basename(scenes[i])}?dur={d:.3f}"></iframe></div>
        <figcaption><b>#{i+1:02d} · {nm}</b><span>起 {_fmt(acc)} · 时长 {d:.1f}s</span></figcaption>
      </figure>""")
        acc += d
    cards_html = "".join(cards)

    bg_css = (f"background:#10231a url('{os.path.basename(PREVIEW_BG)}') center/cover no-repeat;"
              if has_bg else "background:#eef5f0;")

    html = f"""<!DOCTYPE html><html lang="zh-CN"><head><meta charset="UTF-8">
<title>预览 · {len(scenes)} 场景 · {_fmt(total)}</title>
<style>
  :root{{--w:600px;}}
  *{{box-sizing:border-box;}}
  body{{margin:0;background:#0c1512;color:#dff0e7;
       font-family:'Microsoft YaHei','PingFang SC',-apple-system,sans-serif;}}
  header{{position:sticky;top:0;z-index:5;backdrop-filter:blur(8px);
    background:rgba(12,21,18,0.86);padding:18px 28px;border-bottom:1px solid #1f3a2c;}}
  header h1{{margin:0;font-size:22px;color:#fff;}}
  header p{{margin:6px 0 10px;font-size:14px;color:#8fbfa6;}}
  header label{{font-size:14px;color:#bfe3d0;margin-right:14px;}}
  .grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(var(--w),1fr));
    gap:26px;padding:26px;}}
  .card{{margin:0;background:#0f1c17;border:1px solid #1f3a2c;border-radius:12px;
    overflow:hidden;box-shadow:0 6px 22px rgba(0,0,0,.35);}}
  .frame{{position:relative;width:100%;aspect-ratio:16/9;{bg_css}}}
  /* 3840x2160 scene scaled to the card width via a CSS var the JS keeps in sync */
  .frame iframe{{position:absolute;top:0;left:0;width:3840px;height:2160px;border:0;
    background:transparent;transform-origin:top left;transform:scale(calc(var(--cw,600)/3840));}}
  figcaption{{display:flex;justify-content:space-between;align-items:baseline;
    gap:10px;padding:10px 14px;font-size:14px;}}
  figcaption b{{color:#eafff4;font-weight:700;}}
  figcaption span{{color:#7fae97;font-size:12.5px;white-space:nowrap;}}
</style></head><body>
<header>
  <h1>游戏王MD氪金指南 · 全场景动态预览</h1>
  <p>{len(scenes)} 个场景 · 全片 {_fmt(total)} · 每格循环播放（无声、无转场），仅供渲染前自检布局/动画/音画cue。</p>
  <label>缩放 <input id="z" type="range" min="360" max="900" value="600"></label>
  <label><input id="play" type="checkbox" checked> 播放</label>
</header>
<div class="grid" id="grid">{cards_html}</div>
<script>
  // keep each iframe's scale matched to its actual rendered width
  const frames = [...document.querySelectorAll('.frame')];
  function sync(){{ frames.forEach(f=>f.style.setProperty('--cw', f.clientWidth)); }}
  new ResizeObserver(sync).observe(document.body); sync();
  // zoom = grid column min-width
  const z = document.getElementById('z');
  z.oninput = () => {{ document.documentElement.style.setProperty('--w', z.value+'px'); requestAnimationFrame(sync); }};
  // pause/play: toggling an iframe's src is the simplest cross-browser stop
  const play = document.getElementById('play');
  const srcs = frames.map(f=>f.querySelector('iframe').src);
  play.onchange = () => frames.forEach((f,i)=>{{ const fr=f.querySelector('iframe');
    fr.src = play.checked ? srcs[i] : 'about:blank'; }});
</script>
</body></html>"""

    with open(out, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"[preview] {len(scenes)} scenes -> {out}  (open it in a browser)")
    return out


if __name__ == "__main__":
    build()
