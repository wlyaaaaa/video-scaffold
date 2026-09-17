# -*- coding: utf-8 -*-
"""
Stage 3.6 (optional) - static overflow linter.

Loads each built scene in Playwright, seeks to a SETTLED frame, and flags any
visible element whose rendered box leaves the canvas (HARD = almost certainly a
bug: content off-screen) or the frosted-glass safe area (soft = review; could be
an intentional full-bleed image). This automates the manual "preview & eyeball
for 越界" pass that kept catching Day1-label / caption / callout overflows.

Because the page is exactly WIDTH x HEIGHT at scale 1 and the SVG viewBox matches,
getBoundingClientRect() pixels equal SVG user units 1:1.

Public entry:  lint(scene_paths, durations, names=None) -> hard_overflow_count
"""

import os
import sys
import asyncio

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config
from pathlib import Path
from pipeline.browser_runtime import ready
from pipeline.indexed_files import indexed_files

CANVAS = (0, 0, config.WIDTH, config.HEIGHT)
# frosted-glass safe area computed from the background shader (see md-krijin notes)
GLASS = (170, 151, 3670, 2009)
HARD_TOL = 3  # px past the canvas before we call it a hard overflow
SOFT_TOL = 8  # px past the glass before we note it

_JS = """
() => {
  const out = [];
  const sel = '#stage text, #stage image, #stage rect, #stage circle, #stage ellipse,'
            + '#stage line, #stage path, #stage polyline, #stage polygon';
  for (const el of document.querySelectorAll(sel)) {
    const cs = getComputedStyle(el);
    if (parseFloat(cs.opacity) < 0.06 || cs.visibility === 'hidden') continue;
    let ancestor=el.parentElement, hidden=false;
    while(ancestor && ancestor.id!=='stage'){if(parseFloat(getComputedStyle(ancestor).opacity)<0.06){hidden=true;break;}ancestor=ancestor.parentElement;}
    if(hidden)continue;
    let r; try { r = el.getBoundingClientRect(); } catch (e) { continue; }
    if (r.width < 0.5 && r.height < 0.5) continue;
    out.push({tag: el.tagName, l: r.left, t: r.top, r: r.right, b: r.bottom,
              txt: (el.textContent || '').trim().slice(0, 18)});
  }
  return out;
}
"""


async def _run(scenes, durs, names):
    from playwright.async_api import async_playwright

    findings = []
    if len(scenes) != len(durs):
        raise ValueError("scene/duration count mismatch")
    async with async_playwright() as p:
        try:
            b = await p.chromium.launch(
                headless=True,
                channel="chrome",
                args=["--no-sandbox", "--disable-dev-shm-usage"],
            )
        except Exception:
            b = await p.chromium.launch(headless=True)
        ctx = await b.new_context(
            viewport={"width": config.WIDTH, "height": config.HEIGHT}
        )
        pg = await ctx.new_page()
        for i, html in enumerate(scenes):
            errors = []
            handler = lambda error: errors.append(str(error))
            pg.on("pageerror", handler)
            await pg.goto(Path(html).resolve().as_uri(), wait_until="load")
            await ready(pg)
            d = durs[i]
            times = await pg.evaluate("""() => [...document.querySelectorAll('[data-anim]')].flatMap(e => {
              const a=+(e.dataset.delay||0), b=+(e.dataset.dur||1);return [a,a+b/2,a+b];
            })""")
            boxes = []
            seen = set()
            for sample in sorted(
                {
                    0.0,
                    max(0.0, d - 1 / config.FPS),
                    *[
                        min(max(0.0, float(t)), max(0.0, d - 1 / config.FPS))
                        for t in times
                    ],
                }
            ):
                await pg.evaluate("t=>window.seekTime(t)", sample)
                for box in await pg.evaluate(_JS):
                    key = tuple(box.values())
                    if key not in seen:
                        seen.add(key)
                        boxes.append(box)
            pg.remove_listener("pageerror", handler)
            if errors:
                raise RuntimeError("scene JavaScript error: " + errors[0])
            nm = names[i] if names and i < len(names) else os.path.basename(html)
            for bx in boxes:
                off_canvas = (
                    bx["l"] < CANVAS[0] - HARD_TOL
                    or bx["t"] < CANVAS[1] - HARD_TOL
                    or bx["r"] > CANVAS[2] + HARD_TOL
                    or bx["b"] > CANVAS[3] + HARD_TOL
                )
                off_glass = (
                    bx["l"] < GLASS[0] - SOFT_TOL
                    or bx["t"] < GLASS[1] - SOFT_TOL
                    or bx["r"] > GLASS[2] + SOFT_TOL
                    or bx["b"] > GLASS[3] + SOFT_TOL
                )
                fully_off = (
                    bx["l"] >= CANVAS[2]
                    or bx["r"] <= CANVAS[0]
                    or bx["t"] >= CANVAS[3]
                    or bx["b"] <= CANVAS[1]
                )
                # cut-off TEXT (the recurring bug) or a fully-invisible element = HARD;
                # an image/shape bleeding off-frame is usually intentional = soft.
                hard = fully_off or (off_canvas and bx["tag"] == "text")
                if hard:
                    findings.append((nm, "HARD", bx))
                elif off_canvas or off_glass:
                    findings.append((nm, "soft", bx))
        await b.close()
    return findings


def lint(scene_paths, durations, names=None):
    """Report off-canvas (HARD) and off-glass (soft) elements.

    A browser/runtime failure raises: skipping the check must never look like a
    clean layout to the generic workflow. Returns the HARD finding count.
    """
    if not scene_paths:
        raise RuntimeError("layout lint has no scenes to inspect")
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    try:
        findings = asyncio.run(_run(scene_paths, durations, names))
    except Exception as e:
        raise RuntimeError(f"layout lint could not run: {e}") from e

    hard = [f for f in findings if f[1] == "HARD"]
    soft = [f for f in findings if f[1] == "soft"]
    if not findings:
        print(f"[lint] {len(scene_paths)} scenes clean - nothing leaves the glass.")
        return 0
    last = None
    for nm, kind, bx in sorted(findings, key=lambda f: (f[0], f[1] != "HARD")):
        if nm != last:
            print(f"[lint] {nm}:")
            last = nm
        edge = []
        if bx["l"] < GLASS[0]:
            edge.append(f"left {bx['l']:.0f}")
        if bx["t"] < GLASS[1]:
            edge.append(f"top {bx['t']:.0f}")
        if bx["r"] > GLASS[2]:
            edge.append(f"right {bx['r']:.0f}")
        if bx["b"] > GLASS[3]:
            edge.append(f"bottom {bx['b']:.0f}")
        tag = "  !! HARD" if kind == "HARD" else "   ~ soft"
        txt = f' "{bx["txt"]}"' if bx["txt"] else ""
        print(f"{tag} <{bx['tag']}>{txt}  [{', '.join(edge)}]")
    print(
        f"[lint] {len(hard)} HARD (off-canvas, fix these), {len(soft)} soft "
        f"(off-glass; full-bleed images are OK to ignore)."
    )
    return len(hard)


def _default_scene_paths():
    return list(indexed_files(os.path.join(config.DIR_SCENE, "scene_*.html")).values())


if __name__ == "__main__":
    import json

    scenes = _default_scene_paths()
    with open(config.DURATIONS_JSON, encoding="utf-8") as f:
        durs = json.load(f)
    raise SystemExit(1 if lint(scenes, durs) else 0)
