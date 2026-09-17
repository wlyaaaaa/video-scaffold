"""Atomic vector cover generation with explicit optional artwork and current lineage."""

from __future__ import annotations
import asyncio
import html
import os
from pathlib import Path
import re
import tempfile
import config
from pipeline.io_utils import atomic_text, publish_bundle
from pipeline.artifact_identity import write_output_record
from pipeline.browser_runtime import ready

COVER_PNG = os.path.join(config.DIR_OUTPUT, "cover.png")
COVER_HTML = os.path.join(config.DIR_SCENE, "cover.html")


def _document(title, subtitle, kicker, hero_path):
    template = Path(config.TEMPLATE_COVER).read_text(encoding="utf-8")
    if hero_path:
        hero = Path(hero_path).resolve()
        if not hero.is_file():
            raise FileNotFoundError("cover hero image does not exist")
        hero_uri = hero.as_uri()
    else:
        hero_uri = ""
        template = re.sub(r"<image\b[^>]*(?:/>|>\s*</image>)", "", template, flags=re.I)
    values = {
        "@@TITLE@@": html.escape(str(title), quote=True),
        "@@SUBTITLE@@": html.escape(str(subtitle), quote=True),
        "@@KICKER@@": html.escape(str(kicker), quote=True),
        "@@HERO@@": html.escape(hero_uri, quote=True),
    }
    return re.sub(
        r"@@(?:TITLE|SUBTITLE|KICKER|HERO)@@",
        lambda match: values[match.group()],
        template,
    )


def _fill(title, subtitle, kicker, hero_path):
    atomic_text(COVER_HTML, _document(title, subtitle, kicker, hero_path))
    return COVER_HTML


async def _shoot(html_path, out_png):
    from playwright.async_api import async_playwright

    async with async_playwright() as playwright:
        try:
            browser = await playwright.chromium.launch(headless=True, channel="chrome")
        except Exception:
            browser = await playwright.chromium.launch(headless=True)
        try:
            page = await browser.new_page(
                viewport={"width": config.WIDTH, "height": config.HEIGHT},
                device_scale_factor=1,
            )
            await page.goto(Path(html_path).resolve().as_uri(), wait_until="load")
            await ready(page, scene=False)
            overflow = await page.evaluate(
                """() => [...document.querySelectorAll('svg text')].some(e=>{const b=e.getBoundingClientRect();return b.left<-1||b.right>innerWidth+1||b.top<-1||b.bottom>innerHeight+1;})"""
            )
            if overflow:
                raise RuntimeError("cover text leaves the canvas")
            await page.screenshot(path=out_png, type="png")
        finally:
            await browser.close()


def build(title, subtitle="", kicker="", hero_path=None, out_png=None):
    from pipeline.contracts import cover_expected

    if not str(title).strip() or str(title).strip() == "Untitled Video":
        raise ValueError("cover requires a real title")
    out_png = out_png or os.path.join(config.DIR_OUTPUT, "cover.png")
    if hero_path is None:
        images = sorted(Path(config.DIR_ASSETS).glob("*.png"))
        hero_path = str(images[0]) if images else None
    document = _document(title, subtitle, kicker, hero_path)
    expected = cover_expected(str(title).strip(), subtitle, kicker, hero_path)
    Path(out_png).parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix=".cover-", dir=Path(out_png).parent
    ) as temporary:
        source = Path(temporary) / "cover.html"
        image = Path(temporary) / "cover.png"
        record = Path(temporary) / "cover.identity.json"
        source.write_text(document, encoding="utf-8")
        asyncio.run(_shoot(str(source), str(image)))
        if expected != cover_expected(str(title).strip(), subtitle, kicker, hero_path):
            raise RuntimeError("cover inputs changed while taking screenshot")
        write_output_record(str(record), expected, str(image))
        publish_bundle([(image, out_png), (record, out_png + ".identity.json")])
    print(f"[cover] -> {out_png}")
    return out_png


if __name__ == "__main__":
    from pipeline.workflow import stage_cover
    from pipeline.io_utils import project_lock

    with project_lock(config.ROOT):
        stage_cover()
