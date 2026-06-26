# -*- coding: utf-8 -*-
"""
Stage 6a - 4K vector cover -> output/cover.png.

Fills the opaque crystal-glass cover board with a title / subtitle / kicker and
the hero art, then takes one lossless 3840x2160 screenshot. Because the whole
page is vector + a single hi-res PNG, the edges stay razor sharp (no video
frame-grab softness).
"""

import os
import sys
import pathlib
import asyncio

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config

COVER_PNG = os.path.join(config.DIR_OUTPUT, "cover.png")
COVER_HTML = os.path.join(config.DIR_SCENE, "cover.html")


def _fill(title, subtitle, kicker, hero_path):
    with open(config.TEMPLATE_COVER, "r", encoding="utf-8") as f:
        html = f.read()
    hero_uri = pathlib.Path(os.path.abspath(hero_path)).as_uri()
    repl = {"@@TITLE@@": title, "@@SUBTITLE@@": subtitle,
            "@@KICKER@@": kicker, "@@HERO@@": hero_uri}
    for k, v in repl.items():
        html = html.replace(k, v)
    os.makedirs(os.path.dirname(COVER_HTML), exist_ok=True)
    with open(COVER_HTML, "w", encoding="utf-8") as f:
        f.write(html)
    return COVER_HTML


async def _shoot(html_path, out_png):
    from playwright.async_api import async_playwright
    uri = pathlib.Path(os.path.abspath(html_path)).as_uri()
    async with async_playwright() as p:
        try:
            browser = await p.chromium.launch(headless=True, channel="chrome")
        except Exception:
            browser = await p.chromium.launch(headless=True)
        ctx = await browser.new_context(viewport={"width": config.WIDTH, "height": config.HEIGHT},
                                        device_scale_factor=1)
        page = await ctx.new_page()
        await page.goto(uri)
        await page.screenshot(path=out_png, type="png")
        await browser.close()


def build(title, subtitle="", kicker="", hero_path=None, out_png=COVER_PNG):
    config.ensure_dirs()
    if hero_path is None:  # default: first asset
        import glob
        imgs = sorted(glob.glob(os.path.join(config.DIR_ASSETS, "*.png")))
        hero_path = imgs[0] if imgs else ""
    html = _fill(title, subtitle, kicker, hero_path)
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    asyncio.run(_shoot(html, out_png))
    print(f"[cover] -> {out_png}")
    return out_png


if __name__ == "__main__":
    build("极客配装", subtitle="RTX 5080 硬核攻略", kicker="HARDCORE GUIDE")
